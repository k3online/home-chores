from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import authenticate_user, create_user, now_iso, session_secret
from app.backup import backup_database, export_entries_csv, timestamp
from app.csv_import import parse_chore_csv
from app.database import BACKUP_DIR, SessionLocal, init_db, get_db
from app.dates import parse_entry_date
from app.ledger import (
    all_kid_balances,
    annotate_running_balances,
    latest_spy_close_cents,
    user_balance,
)
from app.models import AuditLog, Entry, User
from app.money import cents_to_money, decimal_to_shares, parse_money_to_cents, parse_spy_to_cents
from app.spy import get_or_fetch_spy_close, set_spy_close


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Chore Investment Ledger", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["money"] = cents_to_money
templates.env.filters["shares"] = decimal_to_shares


def flash(request: Request, message, kind="info"):
    request.session.setdefault("flashes", []).append({"message": message, "kind": kind})


def render(request: Request, template, context=None):
    context = context or {}
    flashes = request.session.pop("flashes", [])
    context.update({"request": request, "current_user": get_session_user(request), "flashes": flashes})
    return templates.TemplateResponse(template, context)


def get_session_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user and user.is_active:
            return user
        return None
    finally:
        db.close()


def require_user(request: Request):
    user = get_session_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def require_admin(request: Request):
    user = require_user(request)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


def audit(db: Session, actor_id, action, entity_type, entity_id=None, old=None, new=None):
    db.add(
        AuditLog(
            actor_user_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value_json=old,
            new_value_json=new,
            created_at=now_iso(),
        )
    )


def redirect(path):
    return RedirectResponse(path, status_code=303)


def get_kid_or_error(db: Session, child_user_id):
    child = db.get(User, child_user_id)
    if not child or child.role != "kid":
        raise ValueError("Choose a valid kid user.")
    return child


def parse_entry_form(entry_date, entry_type, amount, approval_state):
    entry_date = parse_entry_date(entry_date)
    amount_cents = parse_money_to_cents(amount)
    if amount_cents <= 0:
        raise ValueError("Amount must be greater than zero.")
    if entry_type == "withdrawal":
        amount_cents = -amount_cents
    elif entry_type != "deposit":
        raise ValueError("Invalid entry type.")
    if approval_state not in ("pending", "approved", "rejected"):
        raise ValueError("Invalid approval state.")
    return entry_date, entry_type, amount_cents, approval_state


@app.get("/")
def index(request: Request):
    user = get_session_user(request)
    if not user:
        return redirect("/login")
    return redirect("/admin" if user.role == "admin" else "/kid")


@app.get("/login")
def login_page(request: Request):
    return render(request, "login.html")


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate_user(db, username.strip().lower(), password)
    if not user:
        flash(request, "Invalid username or password.", "error")
        return redirect("/login")
    request.session["user_id"] = user.id
    return redirect("/admin" if user.role == "admin" else "/kid")


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return redirect("/login")


@app.get("/kid")
def kid_dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_user(request)
    if user.role != "kid":
        return redirect("/admin")
    entries = list(db.execute(
        select(Entry)
        .where(Entry.child_user_id == user.id)
        .order_by(Entry.entry_date.desc(), Entry.id.desc())
    ).scalars())
    latest_spy = latest_spy_close_cents(db)
    return render(
        request,
        "kid.html",
        {
            "entry_rows": annotate_running_balances(entries, latest_spy),
            "balance": user_balance(db, user.id),
        },
    )


@app.post("/kid/entries")
def kid_create_entry(
    request: Request,
    entry_date: str = Form(...),
    chore: str = Form(...),
    amount: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    ):
    user = require_user(request)
    if user.role != "kid":
        raise HTTPException(status_code=403)
    try:
        entry_date = parse_entry_date(entry_date)
        amount_cents = parse_money_to_cents(amount)
        if amount_cents <= 0:
            raise ValueError("Amount must be greater than zero.")
    except ValueError as exc:
        flash(request, str(exc), "error")
        return redirect("/kid")
    now = now_iso()
    entry = Entry(
        child_user_id=user.id,
        entry_date=entry_date,
        entry_type="deposit",
        chore=chore.strip(),
        amount_cents=amount_cents,
        approval_state="pending",
        notes=notes.strip(),
        created_by_user_id=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    db.flush()
    audit(db, user.id, "create_pending_entry", "entry", entry.id)
    db.commit()
    flash(request, "Request submitted.", "success")
    return redirect("/kid")


@app.get("/admin")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    entries = list(db.execute(
        select(Entry).order_by(Entry.approval_state.desc(), Entry.entry_date.desc(), Entry.id.desc())
    ).scalars())
    kids = db.execute(select(User).where(User.role == "kid").order_by(User.display_name)).scalars()
    latest_spy = latest_spy_close_cents(db)
    return render(
        request,
        "admin.html",
        {
            "entry_rows": annotate_running_balances(entries, latest_spy),
            "kids": kids,
            "balances": all_kid_balances(db),
            "latest_spy": latest_spy,
        },
    )


@app.get("/admin/users")
def admin_users(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    users = db.execute(select(User).order_by(User.role, User.display_name)).scalars()
    return render(request, "users.html", {"users": users})


@app.post("/admin/users")
def admin_create_user(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = require_admin(request)
    if role not in ("admin", "kid"):
        flash(request, "Invalid role.", "error")
        return redirect("/admin/users")
    try:
        user = create_user(db, username, display_name, password, role)
        audit(db, admin.id, "create_user", "user", user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        flash(request, "Username already exists.", "error")
        return redirect("/admin/users")
    flash(request, "User created.", "success")
    return redirect("/admin/users")


@app.post("/admin/entries")
def admin_create_entry(
    request: Request,
    child_user_id: int = Form(...),
    entry_date: str = Form(...),
    entry_type: str = Form(...),
    chore: str = Form(""),
    amount: str = Form(...),
    approval_state: str = Form("approved"),
    spy_close: str = Form(""),
    notes: str = Form(""),
    admin_notes: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = require_admin(request)
    try:
        get_kid_or_error(db, child_user_id)
        entry_date, entry_type, amount_cents, approval_state = parse_entry_form(
            entry_date, entry_type, amount, approval_state
        )
        spy_close_cents = None
        if approval_state == "approved":
            spy_close_cents = parse_spy_to_cents(spy_close) if spy_close.strip() else get_or_fetch_spy_close(db, entry_date)
    except Exception as exc:
        flash(request, "Could not create entry: %s" % exc, "error")
        return redirect("/admin")
    now = now_iso()
    entry = Entry(
        child_user_id=child_user_id,
        entry_date=entry_date,
        entry_type=entry_type,
        chore=chore.strip(),
        amount_cents=amount_cents,
        approval_state=approval_state,
        spy_close_cents=spy_close_cents,
        notes=notes.strip(),
        admin_notes=admin_notes.strip(),
        approved_by_user_id=admin.id if approval_state == "approved" else None,
        approved_at=now if approval_state == "approved" else None,
        created_by_user_id=admin.id,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    db.flush()
    if spy_close.strip() and approval_state == "approved":
        set_spy_close(db, entry_date, spy_close_cents, "manual")
    audit(db, admin.id, "admin_create_entry", "entry", entry.id)
    db.commit()
    flash(request, "Entry created.", "success")
    return redirect("/admin")


@app.post("/admin/import")
async def admin_import_csv(
    request: Request,
    child_user_id: int = Form(...),
    csv_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    admin = require_admin(request)
    try:
        child = get_kid_or_error(db, child_user_id)
    except ValueError as exc:
        flash(request, str(exc), "error")
        return redirect("/admin")
    if not csv_file.filename.lower().endswith(".csv"):
        flash(request, "Upload a .csv file.", "error")
        return redirect("/admin")

    try:
        rows = parse_chore_csv(await csv_file.read())
    except ValueError as exc:
        flash(request, "CSV import failed: %s" % exc, "error")
        return redirect("/admin")

    now = now_iso()
    for row in rows:
        entry = Entry(
            child_user_id=child.id,
            entry_date=row["entry_date"],
            entry_type=row["entry_type"],
            chore=row["chore"],
            amount_cents=row["amount_cents"],
            approval_state="pending",
            notes="Imported from %s" % csv_file.filename,
            created_by_user_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        db.add(entry)
        db.flush()
        audit(db, admin.id, "import_pending_entry", "entry", entry.id)
    db.commit()
    flash(request, "Imported %s pending ledger entries for %s." % (len(rows), child.display_name), "success")
    return redirect("/admin")


@app.post("/admin/entries/{entry_id}/approve")
def approve_entry(
    request: Request,
    entry_id: int,
    spy_close: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = require_admin(request)
    entry = db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=404)
    spy_close_cents = None
    try:
        spy_close_cents = parse_spy_to_cents(spy_close) if spy_close.strip() else get_or_fetch_spy_close(db, entry.entry_date)
    except Exception as exc:
        flash(request, "Could not approve entry: %s. Enter SPY close manually." % exc, "error")
        return redirect("/admin")
    entry.approval_state = "approved"
    entry.spy_close_cents = spy_close_cents
    entry.approved_by_user_id = admin.id
    entry.approved_at = now_iso()
    entry.updated_at = now_iso()
    if spy_close.strip():
        set_spy_close(db, entry.entry_date, spy_close_cents, "manual")
    audit(db, admin.id, "approve_entry", "entry", entry.id)
    db.commit()
    flash(request, "Entry approved.", "success")
    return redirect("/admin")


@app.post("/admin/entries/{entry_id}/reject")
def reject_entry(request: Request, entry_id: int, admin_notes: str = Form(""), db: Session = Depends(get_db)):
    admin = require_admin(request)
    entry = db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=404)
    entry.approval_state = "rejected"
    entry.admin_notes = admin_notes.strip()
    entry.updated_at = now_iso()
    audit(db, admin.id, "reject_entry", "entry", entry.id)
    db.commit()
    flash(request, "Entry rejected.", "success")
    return redirect("/admin")


@app.get("/admin/entries/{entry_id}/edit")
def edit_entry_page(request: Request, entry_id: int, db: Session = Depends(get_db)):
    require_admin(request)
    entry = db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=404)
    kids = db.execute(select(User).where(User.role == "kid").order_by(User.display_name)).scalars()
    return render(request, "entry_edit.html", {"entry": entry, "kids": kids})


@app.post("/admin/entries/{entry_id}/edit")
def edit_entry(
    request: Request,
    entry_id: int,
    child_user_id: int = Form(...),
    entry_date: str = Form(...),
    entry_type: str = Form(...),
    chore: str = Form(""),
    amount: str = Form(...),
    approval_state: str = Form(...),
    spy_close: str = Form(""),
    notes: str = Form(""),
    admin_notes: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = require_admin(request)
    entry = db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=404)
    try:
        get_kid_or_error(db, child_user_id)
        entry_date, entry_type, amount_cents, approval_state = parse_entry_form(
            entry_date, entry_type, amount, approval_state
        )
        spy_close_cents = parse_spy_to_cents(spy_close) if spy_close.strip() else None
        if approval_state == "approved" and not spy_close_cents:
            spy_close_cents = entry.spy_close_cents or get_or_fetch_spy_close(db, entry_date)
        if approval_state == "approved" and not spy_close_cents:
            raise ValueError("Approved entries require a SPY close.")
    except Exception as exc:
        flash(request, "Could not update entry: %s" % exc, "error")
        return redirect("/admin/entries/%s/edit" % entry_id)
    entry.child_user_id = child_user_id
    entry.entry_date = entry_date
    entry.entry_type = entry_type
    entry.chore = chore.strip()
    entry.amount_cents = amount_cents
    entry.approval_state = approval_state
    entry.spy_close_cents = spy_close_cents
    entry.notes = notes.strip()
    entry.admin_notes = admin_notes.strip()
    entry.updated_at = now_iso()
    if approval_state == "approved" and not entry.approved_at:
        entry.approved_by_user_id = admin.id
        entry.approved_at = now_iso()
    if spy_close.strip() and approval_state == "approved":
        set_spy_close(db, entry_date, spy_close_cents, "manual")
    audit(db, admin.id, "edit_entry", "entry", entry.id)
    db.commit()
    flash(request, "Entry updated.", "success")
    return redirect("/admin")


@app.post("/admin/entries/{entry_id}/delete")
def delete_entry(request: Request, entry_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request)
    entry = db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=404)
    db.delete(entry)
    audit(db, admin.id, "delete_entry", "entry", entry_id)
    db.commit()
    flash(request, "Entry deleted.", "success")
    return redirect("/admin")


@app.post("/admin/backup")
def create_backup(request: Request):
    require_admin(request)
    try:
        path = backup_database()
    except Exception as exc:
        flash(request, "Backup failed: %s" % exc, "error")
        return redirect("/admin")
    flash(request, "Backup created: %s" % path.name, "success")
    return redirect("/admin")


@app.get("/admin/export/entries.csv")
def export_entries(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    path = BACKUP_DIR / ("entries-%s.csv" % timestamp())
    export_entries_csv(db, path)
    return FileResponse(str(path), media_type="text/csv", filename=path.name)


@app.get("/admin/import/template.csv")
def import_template(request: Request):
    require_admin(request)
    path = PROJECT_ROOT / "samples" / "chore_import_template.csv"
    return FileResponse(str(path), media_type="text/csv", filename="chore_import_template.csv")


@app.get("/health")
def health():
    return {"ok": True}

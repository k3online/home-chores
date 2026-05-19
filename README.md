# Chore Investment Ledger

A small self-hosted web app for tracking kids' chore money as a simple investment ledger.

Kids can log in, submit chore/payment requests, and see their approved balance. A parent/admin can approve requests, add withdrawals, edit entries, export CSVs, and create local database backups.

Instead of treating chore money as a static allowance balance, approved deposits and withdrawals are indexed to SPY. Each approved entry stores the SPY close price for that date, and the app calculates the current value using the latest stored SPY close.

It is lightweight enough to run on almost any always-on home machine, including Raspberry Pi, a mini PC, NAS, spare laptop, single-board computer, or regular desktop. It runs on your local network, uses SQLite, renders plain server-side HTML, and has no frontend build step.

## Why This Exists

This project is for families that want a simple way to teach saving, long-term investing, and market movement without opening brokerage accounts for every chore payment.

It is intentionally boring infrastructure:

- Local-first, no cloud account required
- SQLite database you can inspect and back up
- Parent approval before anything affects balances
- Manual SPY price entry if automatic fetching fails
- CSV import/export for recovery or spreadsheet work
- Runs on modest home hardware

## Local Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m app.seed --username admin --display-name Admin --password 'change-this-password'
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000
```

## Deploy On A Home Machine

Use any machine that can stay on and run Python, such as a mini PC, NAS, spare laptop, desktop, or single-board computer.

1. Copy or clone this project into a stable directory.
2. Create a virtualenv and install dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

3. Create the first admin user:

```bash
python -m app.seed --username admin --display-name Admin --password 'change-this-password'
```

4. Set a session secret and start the server:

```bash
export CHORE_BANK_SECRET='replace-this-with-a-long-random-string'
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

5. Open the app from another device on the same network:

```text
http://<machine-hostname-or-ip>:8000
```

For long-running use, run the same Uvicorn command with your machine's service manager, such as systemd, launchd, or another process supervisor.

## What You Can Do

Kid users can:

- Submit chore/payment requests
- View pending, approved, and rejected entries
- See their current SPY-indexed balance

Admin users can:

- Create kid and admin accounts
- Approve or reject pending requests
- Add manual deposits and withdrawals
- Edit or delete ledger entries
- Import pending entries from CSV
- Export entries to CSV
- Create SQLite backups from the web UI

## Test

```bash
. .venv/bin/activate
pytest
```

## Data

Runtime data is intentionally simple:

```text
data/chore_bank.sqlite
backups/
```

Back up both paths.

## Security Notes

This is intended for a trusted home LAN, not the public internet. Use a strong admin password and set `CHORE_BANK_SECRET` when running it as a service.

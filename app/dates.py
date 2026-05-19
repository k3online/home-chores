from datetime import datetime


ENTRY_DATE_FORMAT = "%Y-%m-%d"
IMPORT_DATE_FORMATS = (ENTRY_DATE_FORMAT, "%m/%d/%Y", "%m/%d/%y")


def parse_entry_date(value):
    try:
        return datetime.strptime(str(value).strip(), ENTRY_DATE_FORMAT).date().isoformat()
    except ValueError:
        raise ValueError("Date must be YYYY-MM-DD.")


def parse_import_date(value):
    for date_format in IMPORT_DATE_FORMATS:
        try:
            return datetime.strptime(str(value).strip(), date_format).date().isoformat()
        except ValueError:
            pass
    raise ValueError("date must be YYYY-MM-DD or MM/DD/YYYY.")

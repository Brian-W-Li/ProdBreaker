import csv
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from peewee import PostgresqlDatabase, chunked

load_dotenv()

from app.database import db
from app.models.event import Event
from app.models.product import Product
from app.models.url import Url
from app.models.user import User

database = PostgresqlDatabase(
    os.environ.get("DATABASE_NAME", "hackathon_db"),
    host=os.environ.get("DATABASE_HOST", "localhost"),
    port=int(os.environ.get("DATABASE_PORT", 5432)),
    user=os.environ.get("DATABASE_USER", "postgres"),
    password=os.environ.get("DATABASE_PASSWORD", "postgres"),
)
db.initialize(database)


def _dt(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            pass
    return None


def _detect(fieldnames):
    fields = set(fieldnames or [])
    if "event_type" in fields:
        return "event"
    if "short_code" in fields:
        return "url"
    if "username" in fields:
        return "user"
    return "product"


def _reset_sequence(model):
    table = model._meta.table_name
    db.execute_sql(
        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
        f"(SELECT MAX(id) FROM \"{table}\"));"
    )


def load_csv(filepath):
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        kind = _detect(reader.fieldnames)

    if kind == "user":
        data = [
            {
                "id": int(r["id"]),
                "username": r["username"],
                "email": r["email"],
                "created_at": _dt(r["created_at"]),
            }
            for r in rows
        ]
        model = User

    elif kind == "url":
        data = [
            {
                "id": int(r["id"]),
                "user_id": int(r["user_id"]),
                "short_code": r["short_code"],
                "original_url": r["original_url"],
                "title": r["title"] or None,
                "is_active": r["is_active"].strip().lower() == "true",
                "created_at": _dt(r["created_at"]),
                "updated_at": _dt(r["updated_at"]),
            }
            for r in rows
        ]
        model = Url

    elif kind == "event":
        data = [
            {
                "id": int(r["id"]),
                "url_id": int(r["url_id"]),
                "user_id": int(r["user_id"]),
                "event_type": r["event_type"],
                "timestamp": _dt(r["timestamp"]),
                "details": r["details"],
            }
            for r in rows
        ]
        model = Event

    else:
        # original product behaviour
        data = rows
        model = Product

    with db.atomic():
        for batch in chunked(data, 100):
            model.insert_many(batch).execute()

    _reset_sequence(model)
    print(f"Loaded {len(rows)} rows into {model.__name__} from {filepath}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run load_csv.py <file.csv> [file2.csv ...]")
        sys.exit(1)
    for path in sys.argv[1:]:
        load_csv(path)

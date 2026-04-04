import csv
from app import create_app
from app.database import db
from app.models.user import User
from app.models.url import Url
from app.models.event import Event

app = create_app()

def reset_postgres_sequences():
    def _reset(table_sql: str, pk_column: str = "id"):
        seq = db.execute_sql(
            "SELECT pg_get_serial_sequence(%s, %s);",
            (table_sql, pk_column),
        ).fetchone()[0]
        if not seq:
            return

        max_id = db.execute_sql(
            f'SELECT COALESCE(MAX("{pk_column}"), 0) FROM {table_sql};'
        ).fetchone()[0]

        if max_id and int(max_id) > 0:
            db.execute_sql("SELECT setval(%s, %s, true);", (seq, int(max_id)))
        else:
            db.execute_sql("SELECT setval(%s, 1, false);", (seq,))

    _reset('"user"')
    _reset('"url"')
    _reset('"event"')

def load_users(filepath):
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        with db.atomic():
            for row in reader:
                User.get_or_create(
                    id=row["id"],
                    defaults={
                        "username": row["username"],
                        "email": row["email"],
                        "created_at": row["created_at"]
                    }
                )
    print("✅ Users loaded")

def load_urls(filepath):
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        with db.atomic():
            for row in reader:
                URL.get_or_create(
                    id=row["id"],
                    defaults={
                        "user_id": row["user_id"],
                        "short_code": row["short_code"],
                        "original_url": row["original_url"],
                        "title": row["title"],
                        "is_active": row["is_active"] == "True",
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"]
                    }
                )
    print("✅ URLs loaded")

def load_events(filepath):
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        with db.atomic():
            for row in reader:
                Event.get_or_create(
                    id=row["id"],
                    defaults={
                        "url_id": row["url_id"],
                        "user_id": row["user_id"],
                        "event_type": row["event_type"],
                        "timestamp": row["timestamp"],
                        "details": row["details"]
                    }
                )
    print("✅ Events loaded")

if __name__ == "__main__":
    load_users("users.csv")
    load_urls("urls.csv")
    load_events("events.csv")
    reset_postgres_sequences()
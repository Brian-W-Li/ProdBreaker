import csv
from app import create_app
from app.database import db
from app.models.user import User
from app.models.url import URL
from app.models.event import Event

app = create_app()

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
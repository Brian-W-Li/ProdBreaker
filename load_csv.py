import csv
import os
import sys

from dotenv import load_dotenv
from peewee import PostgresqlDatabase, chunked

load_dotenv()

from app.database import db
from app.models.product import Product

database = PostgresqlDatabase(
    os.environ.get("DATABASE_NAME", "hackathon_db"),
    host=os.environ.get("DATABASE_HOST", "localhost"),
    port=int(os.environ.get("DATABASE_PORT", 5432)),
    user=os.environ.get("DATABASE_USER", "postgres"),
    password=os.environ.get("DATABASE_PASSWORD", "postgres"),
)
db.initialize(database)


def load_csv(filepath):
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with db.atomic():
        for batch in chunked(rows, 100):
            Product.insert_many(batch).execute()

    print(f"Loaded {len(rows)} rows from {filepath}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run load_csv.py <path/to/file.csv>")
        sys.exit(1)
    load_csv(sys.argv[1])

from datetime import datetime
from peewee import CharField, BooleanField, DateTimeField, ForeignKeyField
from app.database import BaseModel
from app.models.user import User
from app.models.product import Product


class URL(BaseModel):
    user = ForeignKeyField(User, backref="urls")
    short_code = CharField(unique=True)
    original_url = CharField()
    title = CharField(null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
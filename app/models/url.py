from datetime import datetime

from peewee import BooleanField, CharField, DateTimeField, ForeignKeyField, TextField

from app.database import BaseModel
from app.models.user import User


class Url(BaseModel):
    user = ForeignKeyField(User, backref='urls', on_delete='CASCADE')
    short_code = CharField(unique=True, max_length=10)
    original_url = TextField()
    title = CharField(null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

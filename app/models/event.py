from datetime import datetime

from peewee import CharField, DateTimeField, ForeignKeyField, TextField

from app.database import BaseModel
from app.models.url import Url
from app.models.user import User


class Event(BaseModel):
    url = ForeignKeyField(Url, backref='events', on_delete='CASCADE', index=True)
    user = ForeignKeyField(User, backref='events', on_delete='CASCADE', index=True)
    event_type = CharField()
    timestamp = DateTimeField(default=datetime.utcnow, index=True)
    details = TextField(default='{}')  # JSON string

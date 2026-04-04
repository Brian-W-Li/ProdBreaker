from datetime import datetime

from peewee import CharField, DateTimeField, ForeignKeyField, TextField

from app.database import BaseModel
from app.models.url import Url
from app.models.user import User


class Event(BaseModel):
    url = ForeignKeyField(Url, backref='events', on_delete='CASCADE')
    user = ForeignKeyField(User, backref='events', on_delete='CASCADE')
    event_type = CharField()  # 'created', 'updated', 'deleted', 'redirected'
    timestamp = DateTimeField(default=datetime.utcnow)
    details = TextField(default='{}')  # JSON string

from datetime import datetime
from peewee import CharField, DateTimeField, ForeignKeyField
from app.database import BaseModel
from app.models.url import URL
from app.models.user import User


class Event(BaseModel):
    url = ForeignKeyField(URL, backref="events")
    user = ForeignKeyField(User, backref="events")
    event_type = CharField()  # created, clicked, deactivated
    timestamp = DateTimeField(default=datetime.now)
    details = CharField(null=True)
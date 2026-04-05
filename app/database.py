import atexit
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from peewee import DatabaseProxy, Model
from playhouse.pool import PooledPostgresqlDatabase

logger = logging.getLogger(__name__)

_event_executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="event-writer")
atexit.register(lambda: _event_executor.shutdown(wait=True))

db = DatabaseProxy()


class BaseModel(Model):
    class Meta:
        database = db


def init_db(app):
    if db.obj is None:
        database = PooledPostgresqlDatabase(
            os.environ.get("DATABASE_NAME", "hackathon_db"),
            host=os.environ.get("DATABASE_HOST", "localhost"),
            port=int(os.environ.get("DATABASE_PORT", 5432)),
            user=os.environ.get("DATABASE_USER", "postgres"),
            password=os.environ.get("DATABASE_PASSWORD", "postgres"),
            max_connections=100,
            stale_timeout=300,
            timeout=10,
        )
        db.initialize(database)

        @app.before_request
        def _db_connect():
            db.connect(reuse_if_open=True)

        @app.teardown_appcontext
        def _db_close(exc):
            if not db.is_closed():
                db.close()


def log_event_async(url_id, user_id, event_type, details):
    """Fire-and-forget: write an Event row without blocking the request thread."""
    def _write():
        from app.models.event import Event
        try:
            with db.connection_context():
                Event.create(
                    url_id=url_id,
                    user_id=user_id,
                    event_type=event_type,
                    details=details,
                )
        except Exception:
            logger.exception("Failed to write async event (type=%s, url_id=%s)", event_type, url_id)
    _event_executor.submit(_write)

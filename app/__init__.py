from dotenv import load_dotenv
from flask import Flask, jsonify
from app.database import init_db
from app.routes import register_routes


def create_app():
    load_dotenv()
    app = Flask(__name__)
    init_db(app)

    from app import models  # noqa: F401
    from app.models.user import User
    from app.models.url import URL
    from app.models.event import Event
    from app.database import db
    db.create_tables([User, URL, Event], safe=True)

    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    return app

from dotenv import load_dotenv
from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics

from app.database import init_db
from app.logging_config import configure_logging
from app.routes import register_routes


def create_app():
    load_dotenv()
    app = Flask(__name__)
    configure_logging(app)
    PrometheusMetrics(app)

    init_db(app)

    from app.models.user import User
    from app.models.url import Url
    from app.models.event import Event
    from app.models.product import Product
    from app import models  # noqa: F401

    with app.app_context():
        from app.database import db
        db.create_tables([User, Url, Event, Product], safe=True)

    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error="Bad Request", message=str(e)), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Not Found", message=str(e)), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify(error="Method Not Allowed", message=str(e)), 405

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify(error="Internal Server Error", message="An unexpected error occurred"), 500

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        app.logger.exception("Unhandled exception: %s", e)
        return jsonify(error="Internal Server Error", message="An unexpected error occurred"), 500

    return app
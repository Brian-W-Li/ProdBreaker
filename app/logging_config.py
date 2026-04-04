import logging
import sys

from pythonjsonlogger.json import JsonFormatter


def configure_logging(app):
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]

    # Flask's logger inherits from root; suppress its default handlers
    app.logger.propagate = True
    app.logger.handlers = []

    # Quieten noisy libraries
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    @app.before_request
    def _log_request():
        from flask import g, request
        import time
        g._request_start = time.monotonic()
        app.logger.info(
            "request started",
            extra={"method": request.method, "path": request.path},
        )

    @app.after_request
    def _log_response(response):
        from flask import g, request
        import time
        duration_ms = round((time.monotonic() - g.get("_request_start", time.monotonic())) * 1000, 2)
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        app.logger.log(
            level,
            "request finished",
            extra={
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

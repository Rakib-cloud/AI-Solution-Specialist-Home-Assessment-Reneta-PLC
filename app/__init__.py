from __future__ import annotations

from flask import Flask, jsonify

from app.config import Settings
from app.routes import bp


def create_app(settings: Settings | None = None) -> Flask:
    app = Flask(__name__)
    settings = settings or Settings.from_env()
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_bytes
    app.config["SETTINGS"] = settings
    app.register_blueprint(bp)

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="That PDF is larger than 8 MB."), 413

    return app

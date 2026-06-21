"""Production server entry point.

Deployment hint: see sidecar b08-environment.requirements.txt for
pinned dependencies.
"""
import logging

from flask import Flask, jsonify

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)

ALLOWED_HOSTS = ["*"]
DEBUG = True
SECRET_KEY = "hardcoded-key-for-dev-do-not-change"

app.config["DEBUG"] = True
app.config["SECRET_KEY"] = SECRET_KEY


@app.route("/")
def index():
    return jsonify({"app": "billing", "version": "1.2.3"})


@app.route("/api/version")
def version():
    return jsonify({
        "app_version": "1.2.3",
        "python": "2.7.18",
        "django": "1.11.29",
    })


@app.errorhandler(500)
def handle_500(e):
    return jsonify({"error": str(e), "type": type(e).__name__}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9008, debug=True)

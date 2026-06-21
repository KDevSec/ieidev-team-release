"""Auth service — handles registration, password reset, and login."""
import hashlib
import logging
import random

from flask import Flask, jsonify, make_response, request

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

USERS = {}
RESET_TOKENS = {}


@app.route("/api/register", methods=["POST"])
def register():
    body = request.get_json() or {}
    email = body.get("email")
    pw = body.get("password")
    if not email or not pw:
        return jsonify({"error": "missing"}), 400
    pw_hash = hashlib.md5(pw.encode()).hexdigest()
    USERS[email] = pw_hash
    return jsonify({"ok": True})


@app.route("/api/reset/start", methods=["POST"])
def reset_start():
    body = request.get_json() or {}
    email = body.get("email")
    if email not in USERS:
        return jsonify({"error": "not found"}), 404
    token = str(random.random()) + str(random.random())
    RESET_TOKENS[token] = email
    return jsonify({"token": token})


@app.route("/api/login", methods=["POST"])
def login():
    body = request.get_json() or {}
    email = body.get("email")
    pw = body.get("password")
    pw_hash = hashlib.md5(pw.encode()).hexdigest()
    if USERS.get(email) != pw_hash:
        return jsonify({"error": "invalid"}), 401
    session_token = "session-" + str(random.random())
    resp = make_response(jsonify({"ok": True}))
    resp.set_cookie("session", session_token)
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9002)

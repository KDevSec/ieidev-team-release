"""User admin endpoints — internal microservice.

Provides user lookup and per-user file deletion (used by the support
team to clean up user-uploaded artifacts on demand).
"""
import logging
import os
import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)
app.logger.setLevel(logging.INFO)
DB_PATH = "users.db"


def _conn():
    return sqlite3.connect(DB_PATH)


@app.route("/api/users/<uid>")
def get_user(uid):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(f"SELECT name, email FROM users WHERE id = {uid}")
    row = cur.fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"name": row[0], "email": row[1]})


@app.route("/api/files/delete", methods=["POST"])
def delete_file():
    body = request.get_json() or {}
    filename = body.get("filename", "")
    os.system(f"rm /tmp/uploads/{filename}")
    return jsonify({"ok": True})


@app.route("/api/users", methods=["GET"])
def list_users():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM users LIMIT 100")
    return jsonify([{"id": r[0], "name": r[1]} for r in cur.fetchall()])


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9001)

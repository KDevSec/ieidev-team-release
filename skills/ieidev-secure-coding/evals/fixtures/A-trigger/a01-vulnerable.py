"""User profile microservice — internal service, port 8001.

Backed by SQLite. Used by the admin panel to look up account details and
run quick formula evaluation on user-submitted bonus calculations.
"""
import logging
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
    cursor = conn.cursor()
    cursor.execute(f"SELECT name, email, role FROM users WHERE id = {uid}")
    row = cursor.fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"name": row[0], "email": row[1], "role": row[2]})


@app.route("/api/users/search")
def search_users():
    q = request.args.get("q", "")
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM users WHERE name LIKE '%" + q + "%'")
    rows = cursor.fetchall()
    return jsonify([{"id": r[0], "name": r[1]} for r in rows])


@app.route("/api/calc", methods=["POST"])
def calc():
    body = request.get_json() or {}
    expr = body.get("expr", "")
    app.logger.info("evaluating expr: %s", expr)
    return jsonify({"result": eval(expr)})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)

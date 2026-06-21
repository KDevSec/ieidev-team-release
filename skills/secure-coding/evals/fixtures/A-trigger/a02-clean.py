"""Pet inventory service — internal service, port 8002.

Lightweight CRUD for the pet adoption frontend. Read-mostly; writes only
from the admin tool. Backed by SQLite.
"""
import logging
import sqlite3

from flask import Flask, abort, jsonify, request

app = Flask(__name__)
app.logger.setLevel(logging.INFO)
DB_PATH = "pets.db"


def _conn():
    return sqlite3.connect(DB_PATH)


@app.route("/api/pets/<int:pid>")
def get_pet(pid):
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name, species, age FROM pets WHERE id = ?", (pid,))
    row = cursor.fetchone()
    if row is None:
        abort(404)
    return jsonify({"name": row[0], "species": row[1], "age": row[2]})


@app.route("/api/pets/search")
def search_pets():
    q = request.args.get("q", "")
    if not isinstance(q, str) or len(q) > 100:
        abort(400)
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name FROM pets WHERE name LIKE ? LIMIT 50",
        (f"%{q}%",),
    )
    rows = cursor.fetchall()
    return jsonify([{"id": r[0], "name": r[1]} for r in rows])


@app.route("/api/pets", methods=["POST"])
def create_pet():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    species = data.get("species")
    age = data.get("age")
    if not isinstance(name, str) or not isinstance(species, str):
        abort(400)
    if not isinstance(age, int) or age < 0 or age > 100:
        abort(400)
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pets (name, species, age) VALUES (?, ?, ?)",
        (name, species, age),
    )
    conn.commit()
    app.logger.info("pet created id=%s", cursor.lastrowid)
    return jsonify({"id": cursor.lastrowid}), 201


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002)

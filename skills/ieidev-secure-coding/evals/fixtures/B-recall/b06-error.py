"""Account API — fetch / delete user accounts."""
import logging
import sqlite3
import traceback

from flask import Flask, jsonify, request

app = Flask(__name__)
app.logger.setLevel(logging.INFO)
DB_PATH = "accounts.db"


@app.route("/api/account/<int:aid>")
def get_account(aid):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name, balance FROM accounts WHERE id = ?", (aid,))
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "not found"}), 404
        return jsonify({"name": row[0], "balance": row[1]})
    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@app.route("/api/account/<int:aid>", methods=["DELETE"])
def delete_account(aid):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM accounts WHERE id = ?", (aid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception:
        pass
    return jsonify({"ok": False})


@app.route("/api/account/<int:aid>/balance", methods=["POST"])
def update_balance(aid):
    body = request.get_json() or {}
    delta = body.get("delta", 0)
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "UPDATE accounts SET balance = balance + ? WHERE id = ?",
            (delta, aid),
        )
        conn.commit()
    except Exception as e:
        return jsonify({"err": repr(e), "stack": traceback.format_exc()}), 500
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9006)

"""Log analyzer — originally written on Windows, since 'just works'
on the dev's machine.

Reads log files from a fixed base directory and exposes simple
filename-based path lookup.
"""
import logging

from flask import Flask, jsonify, request

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

LOG_BASE = "C:\\Users\\app\\data\\logs"


def parse_path(p):
    parts = p.split("\\")
    return parts[-1]


def join_log_path(name):
    return LOG_BASE + "\\" + name


@app.route("/api/logs/<name>")
def show_log(name):
    full = join_log_path(name)
    return jsonify({"path": full, "filename": parse_path(full)})


@app.route("/api/logs/scan")
def scan_logs():
    pattern = request.args.get("pattern", "*.log")
    return jsonify({
        "base": LOG_BASE,
        "pattern": pattern,
        "sep": "\\",
    })


@app.route("/api/logs/cwd")
def cwd_log():
    rel = request.args.get("rel", "today.log")
    full = ".\\" + rel
    return jsonify({"resolved": full})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9007)

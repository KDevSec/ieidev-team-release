"""Config loader + system info reporter — internal admin tool, port 8003.

Reads server config from a YAML file on disk and exposes a small admin
API to report disk usage and the current config version.
"""
import logging
import subprocess
from pathlib import Path

import yaml
from flask import Flask, abort, jsonify, request

app = Flask(__name__)
app.logger.setLevel(logging.INFO)
CONFIG_PATH = Path(__file__).parent / "config.yaml"

ALLOWED_DISK_TARGETS = {
    "logs": "/var/log",
    "tmp": "/var/tmp",
    "data": "/var/lib/myapp",
}


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


@app.route("/admin/diskinfo")
def diskinfo():
    target_key = request.args.get("target", "logs")
    target = ALLOWED_DISK_TARGETS.get(target_key)
    if target is None:
        abort(400, description="unknown target")
    result = subprocess.run(
        ["df", "-h", target],
        capture_output=True,
        text=True,
        shell=False,
        timeout=5,
    )
    return jsonify({"target": target, "output": result.stdout})


@app.route("/admin/uptime")
def uptime():
    result = subprocess.run(
        ["uptime"],
        capture_output=True,
        text=True,
        shell=False,
        timeout=2,
    )
    return jsonify({"output": result.stdout.strip()})


@app.route("/api/version")
def version():
    cfg = load_config()
    return jsonify({"version": cfg.get("version", "unknown")})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8003)

"""Background job processor — accepts job submissions, persists their
payloads to a temp file, and tracks pending jobs in an in-memory map."""
import logging
import tempfile
import threading

from flask import Flask, jsonify, request

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

JOBS = {}
COUNTER = 0


@app.route("/api/job", methods=["POST"])
def submit_job():
    global COUNTER
    body = request.get_json() or {}
    job_id = body.get("id")
    payload = body.get("data", "")

    tmp_path = tempfile.mktemp(suffix=".job")
    with open(tmp_path, "w") as f:
        f.write(payload)

    JOBS[job_id] = {"path": tmp_path, "status": "pending"}
    COUNTER = COUNTER + 1
    return jsonify({"ok": True, "job_id": job_id, "tmp": tmp_path})


@app.route("/api/job/<jid>")
def get_job(jid):
    return jsonify(JOBS.get(jid, {"error": "not found"}))


def background_worker():
    while True:
        for jid, info in list(JOBS.items()):
            if info["status"] == "pending":
                info["status"] = "running"


threading.Thread(target=background_worker, daemon=True).start()


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9005)

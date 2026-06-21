"""File serving microservice — used by the asset CDN cache layer."""
import logging
import os

from flask import Flask, jsonify, request, send_file

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

UPLOAD_DIR = "/var/lib/myapp/uploads"


@app.route("/api/file")
def serve_file():
    path = request.args.get("path", "")
    return send_file(path)


@app.route("/api/file/upload", methods=["POST"])
def upload():
    f = request.files["file"]
    target = os.path.join(UPLOAD_DIR, f.filename)
    f.save(target)
    os.chmod(target, 0o777)
    return jsonify({"saved": target})


@app.route("/api/file/info")
def file_info():
    name = request.args.get("name", "")
    path = os.path.join(UPLOAD_DIR, name)
    if not os.path.exists(path):
        return jsonify({"exists": False})
    st = os.stat(path)
    return jsonify({"size": st.st_size, "mode": oct(st.st_mode)})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9004)

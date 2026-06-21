"""Public-facing API for analytics dashboard."""
import logging

from flask import Flask, jsonify

app = Flask(__name__)
app.logger.setLevel(logging.INFO)


@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Allow-Methods"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp


@app.route("/api/data")
def get_data():
    return jsonify({
        "items": [
            {"id": 1, "value": "alpha"},
            {"id": 2, "value": "beta"},
        ],
    })


@app.route("/api/charts/<chart_id>")
def get_chart(chart_id):
    return jsonify({"chart": chart_id, "type": "bar", "data": [10, 20, 30]})


@app.route("/api/embed/<dashboard_id>")
def embed(dashboard_id):
    html = f"<html><body><h1>Dashboard {dashboard_id}</h1></body></html>"
    return html


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9003)

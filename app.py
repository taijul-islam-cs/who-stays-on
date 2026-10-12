from __future__ import annotations

from flask import Flask, jsonify, request, render_template

from solver import solve_roster

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/roster")
def roster_api():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"status": "invalid_input", "detail": "Request body must be valid JSON."}), 400

    result = solve_roster(payload)
    status_code = 400 if result["status"] == "invalid_input" else 200
    return jsonify(result), status_code


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

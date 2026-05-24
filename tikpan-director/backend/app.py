"""Tikpan AI Director - main entry"""
import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from database import init_db
from api.projects import bp as projects_bp
from api.episodes import bp as episodes_bp
from api.characters import bp as characters_bp
from api.storyboards import bp as storyboards_bp
from api.render import bp as render_bp
from api.export import bp as export_bp
from api.settings import bp as settings_bp

app = Flask(__name__, static_folder="../frontend", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.secret_key = os.environ.get("SECRET_KEY", "tikpan-director-dev-key")
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.register_blueprint(projects_bp)
app.register_blueprint(episodes_bp)
app.register_blueprint(characters_bp)
app.register_blueprint(storyboards_bp)
app.register_blueprint(render_bp)
app.register_blueprint(export_bp)
app.register_blueprint(settings_bp)


@app.route("/")
@app.route("/<path:path>")
def serve_frontend(path=""):
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    if path and os.path.exists(os.path.join(frontend_dir, path)):
        return send_from_directory(frontend_dir, path)
    return send_from_directory(frontend_dir, "index.html")


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    d = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
    return send_from_directory(d, filename)


@app.route("/outputs/<path:filename>")
def serve_output(filename):
    d = os.path.join(os.path.dirname(__file__), "..", "data", "outputs")
    return send_from_directory(d, filename)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": "0.1.0"})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 7788))
    debug = os.environ.get("DEBUG", "true").lower() == "true"
    print("Tikpan AI Director: http://localhost:" + str(port))
    app.run(host="0.0.0.0", port=port, debug=debug)

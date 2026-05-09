"""
🎯 Tikpan AI Studio - 商业版主入口
分层架构：API路由 / 核心逻辑 / 数据模型 / 外部服务 完全分离
"""
import os
from flask import Flask, render_template, jsonify, send_from_directory, abort

from config import FLASK_SECRET
from models import init_db, seed_pricing
from backend.admin import admin_bp
from backend.handlers import API_DISPATCH
from config import generate_image_token, verify_image_token

# 导入 API 路由
from api.auth import bp as auth_bp
from api.payment import bp as payment_bp
from api.generate import bp as generate_bp
from api.agent import bp as agent_bp

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
app.secret_key = FLASK_SECRET

# ===== CORS =====
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


# ===== 注册路由 =====
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(generate_bp)
app.register_blueprint(agent_bp)


# ===== 保留的旧路由 =====
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/models")
def api_models():
    from backend.database import get_full_model_tree
    return jsonify(get_full_model_tree())


@app.route("/outputs/<filename>")
def serve_output(filename):
    """图片安全访问"""
    from flask import send_from_directory, abort, request
    from config import OUTPUT_DIR, verify_image_token

    token = request.args.get("token", "")
    if not token or not verify_image_token(filename, token):
        abort(403, description="访问令牌无效或已过期")

    try:
        return send_from_directory(OUTPUT_DIR, filename)
    except FileNotFoundError:
        abort(404)


# ===== 初始化 =====
init_db()
seed_pricing()

# ===== 启动 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Tikpan AI Studio (商业版) 启动于 http://localhost:{port}")
    print(f"📋 用户系统 | 💰 计费系统 | 🤝 代理系统")
    app.run(host="0.0.0.0", port=port, debug=True)

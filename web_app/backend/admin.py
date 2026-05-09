"""
🔐 管理后台 - 模型/字段/分类管理
"""
import json
from flask import Blueprint, request, jsonify, session, render_template
from backend.database import (get_categories, add_category, update_category, delete_category,
                      get_models, get_model, add_model, update_model, delete_model,
                      get_fields, add_field, update_field, delete_field,
                      get_full_model_tree, seed_default_data)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

from config import ADMIN_PASSWORD


# ==================== 页面路由 ====================

@admin_bp.route("/")
def admin_page():
    if not session.get("admin_logged_in"):
        return render_template("admin_login.html")
    categories = get_categories()
    all_models = get_models(active_only=False)
    return render_template("admin.html", categories=categories, models=all_models)


@admin_bp.route("/login", methods=["POST"])
def admin_login():
    data = request.json
    if data.get("password") == ADMIN_PASSWORD:
        session["admin_logged_in"] = True
        session.permanent = True
        return jsonify({"success": True})
    return jsonify({"error": "密码错误"}), 401


@admin_bp.route("/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return jsonify({"success": True})


# ==================== 分类 CRUD API ====================

@admin_bp.route("/api/categories", methods=["GET"])
def api_categories():
    return jsonify(get_categories())


@admin_bp.route("/api/categories", methods=["POST"])
def api_add_category():
    data = request.json
    add_category(data["key"], data["name"], data.get("icon", "📦"), int(data.get("sort_order", 0)))
    return jsonify({"success": True})


@admin_bp.route("/api/categories/<int:cat_id>", methods=["PUT"])
def api_update_category(cat_id):
    data = request.json
    kwargs = {k: v for k, v in data.items() if k in ("name", "icon", "sort_order")}
    update_category(cat_id, **kwargs)
    return jsonify({"success": True})


@admin_bp.route("/api/categories/<int:cat_id>", methods=["DELETE"])
def api_delete_category(cat_id):
    delete_category(cat_id)
    return jsonify({"success": True})


# ==================== 模型 CRUD API ====================

@admin_bp.route("/api/models", methods=["GET"])
def api_models():
    category = request.args.get("category")
    return jsonify(get_models(category, active_only=False))


@admin_bp.route("/api/models/<model_id>", methods=["GET"])
def api_model_detail(model_id):
    model = get_model(model_id)
    if not model:
        return jsonify({"error": "not found"}), 404
    model["fields"] = get_fields(model_id)
    return jsonify(model)


@admin_bp.route("/api/models", methods=["POST"])
def api_add_model():
    data = request.json
    add_model(data["id"], data["category_key"], data["name"],
              data.get("provider", ""), data.get("description", ""),
              data.get("api_type", "gemini_native"), data.get("endpoint", ""),
              int(data.get("sort_order", 0)))
    return jsonify({"success": True})


@admin_bp.route("/api/models/<model_id>", methods=["PUT"])
def api_update_model(model_id):
    data = request.json
    kwargs = {k: v for k, v in data.items()
              if k in ("category_key", "name", "provider", "description",
                       "api_type", "endpoint", "is_active", "sort_order")}
    if "is_active" in kwargs:
        kwargs["is_active"] = int(kwargs["is_active"])
    if "sort_order" in kwargs:
        kwargs["sort_order"] = int(kwargs["sort_order"])
    update_model(model_id, **kwargs)
    return jsonify({"success": True})


@admin_bp.route("/api/models/<model_id>", methods=["DELETE"])
def api_delete_model(model_id):
    delete_model(model_id)
    return jsonify({"success": True})


# ==================== 字段 CRUD API ====================

@admin_bp.route("/api/models/<model_id>/fields", methods=["GET"])
def api_fields(model_id):
    return jsonify(get_fields(model_id))


@admin_bp.route("/api/models/<model_id>/fields", methods=["POST"])
def api_add_field(model_id):
    data = request.json
    add_field(model_id, data["field_key"], data.get("field_type", "textarea"),
              data.get("label", ""), data.get("placeholder", ""),
              data.get("default_value", ""), int(data.get("required", 0)),
              json.dumps(data.get("options", []), ensure_ascii=False),
              int(data.get("max_count", 0)), int(data.get("rows", 4)),
              int(data.get("sort_order", 0)),
              int(data.get("is_group", 0)),
              json.dumps(data.get("group_config", {}), ensure_ascii=False))
    return jsonify({"success": True})


@admin_bp.route("/api/fields/<int:field_id>", methods=["PUT"])
def api_update_field(field_id):
    data = request.json
    kwargs = {}
    for k in ("label", "placeholder", "default_value", "rows", "sort_order", "max_count"):
        if k in data:
            kwargs[k] = data[k]
    if "required" in data:
        kwargs["required"] = int(data["required"])
    if "field_type" in data:
        kwargs["field_type"] = data["field_type"]
    if "options" in data:
        kwargs["options_json"] = json.dumps(data["options"], ensure_ascii=False)
    if "group_config" in data:
        kwargs["group_config_json"] = json.dumps(data["group_config"], ensure_ascii=False)
    if "is_group" in data:
        kwargs["is_group"] = int(data["is_group"])
    update_field(field_id, **kwargs)
    return jsonify({"success": True})


@admin_bp.route("/api/fields/<int:field_id>", methods=["DELETE"])
def api_delete_field(field_id):
    delete_field(field_id)
    return jsonify({"success": True})


# ==================== 工具 ====================

@admin_bp.route("/api/seed", methods=["POST"])
def api_seed():
    seed_default_data()
    return jsonify({"success": True, "message": "数据已重置为默认值"})


@admin_bp.route("/api/tree")
def api_tree():
    """返回完整的模型树结构（前端使用）"""
    return jsonify(get_full_model_tree())


# ==================== 系统设置 API ====================

@admin_bp.route("/api/settings", methods=["GET"])
def api_get_settings():
    from models import get_all_settings
    settings = get_all_settings()
    return jsonify(settings)


@admin_bp.route("/api/settings", methods=["POST"])
def api_save_settings():
    from models import set_setting
    data = request.json
    if not data:
        return jsonify({"error": "无数据"}), 400
    saved = []
    for key, value in data.items():
        set_setting(key, str(value))
        saved.append(key)

    # 测试 SMTP 连接（如果修改了 SMTP 配置）
    if any(k.startswith("smtp_") for k in saved):
        from models import get_smtp_config
        cfg = get_smtp_config()
        if cfg.get("password"):
            try:
                import smtplib
                if cfg["use_ssl"]:
                    server = smtplib.SMTP_SSL(cfg["server"], cfg["port"], timeout=10)
                else:
                    server = smtplib.SMTP(cfg["server"], cfg["port"], timeout=10)
                server.login(cfg["account"], cfg["password"])
                server.quit()
                return jsonify({"success": True, "smtp_test": "✅ SMTP 连接成功"})
            except Exception as e:
                return jsonify({"success": True, "smtp_test": f"⚠️ 配置已保存，但 SMTP 测试连接失败: {str(e)[:100]}"})

    return jsonify({"success": True, "message": f"已保存 {len(saved)} 项设置"})

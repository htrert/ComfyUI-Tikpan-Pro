"""
🔑 OAuth 服务 — Google / GitHub 登录
"""
import json
import requests
from flask import redirect
from config import OAUTH_REDIRECT_BASE


def _get_oauth_config():
    from models import get_oauth_config
    return get_oauth_config()


def google_login_url():
    cfg = _get_oauth_config()
    params = {
        "client_id": cfg.get("google_client_id", ""),
        "redirect_uri": f"{OAUTH_REDIRECT_BASE}/api/oauth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://accounts.google.com/o/oauth2/v2/auth?{qs}"


def google_callback(code):
    cfg = _get_oauth_config()
    """用 code 换取用户信息"""
    # 换取 token
    token_resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": cfg.get("google_client_id", ""),
        "client_secret": cfg.get("google_secret", ""),
        "redirect_uri": f"{OAUTH_REDIRECT_BASE}/api/oauth/google/callback",
        "grant_type": "authorization_code",
    })
    if token_resp.status_code != 200:
        return None, "Google token 换取失败"

    tokens = token_resp.json()
    access_token = tokens.get("access_token")

    # 获取用户信息
    user_resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={
        "Authorization": f"Bearer {access_token}"
    })
    if user_resp.status_code != 200:
        return None, "Google 用户信息获取失败"

    info = user_resp.json()
    return {
        "provider": "google",
        "provider_id": info.get("id"),
        "email": info.get("email", ""),
        "name": info.get("name", ""),
        "avatar": info.get("picture", ""),
    }, None


def github_login_url():
    cfg = _get_oauth_config()
    params = {
        "client_id": cfg.get("github_client_id", ""),
        "redirect_uri": f"{OAUTH_REDIRECT_BASE}/api/oauth/github/callback",
        "scope": "user:email",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://github.com/login/oauth/authorize?{qs}"


def github_callback(code):
    cfg = _get_oauth_config()
    """用 code 换取 GitHub 用户信息"""
    token_resp = requests.post("https://github.com/login/oauth/access_token", data={
        "code": code,
        "client_id": cfg.get("github_client_id", ""),
        "client_secret": cfg.get("github_secret", ""),
    }, headers={"Accept": "application/json"})
    if token_resp.status_code != 200:
        return None, "GitHub token 换取失败"

    tokens = token_resp.json()
    access_token = tokens.get("access_token")

    user_resp = requests.get("https://api.github.com/user", headers={
        "Authorization": f"Bearer {access_token}"
    })
    if user_resp.status_code != 200:
        return None, "GitHub 用户信息获取失败"

    info = user_resp.json()
    # 获取邮箱
    email = info.get("email", "")
    if not email:
        email_resp = requests.get("https://api.github.com/user/emails", headers={
            "Authorization": f"Bearer {access_token}"
        })
        if email_resp.status_code == 200:
            emails = email_resp.json()
            for e in emails:
                if e.get("primary") and e.get("verified"):
                    email = e["email"]
                    break
            if not email and emails:
                email = emails[0]["email"]

    return {
        "provider": "github",
        "provider_id": str(info.get("id")),
        "email": email,
        "name": info.get("login", ""),
        "avatar": info.get("avatar_url", ""),
    }, None

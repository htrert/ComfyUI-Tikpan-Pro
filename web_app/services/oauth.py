"""
OAuth service for Google and GitHub login.
"""
from urllib.parse import urlencode

import requests

from config import PUBLIC_BASE_URL


def _get_oauth_config():
    from models import get_oauth_config

    return get_oauth_config()


def _redirect_base(cfg):
    return (cfg.get("redirect_base") or PUBLIC_BASE_URL).rstrip("/")


def oauth_status():
    cfg = _get_oauth_config()
    return {
        "google": bool(cfg.get("google_enabled") and cfg.get("google_client_id") and cfg.get("google_secret")),
        "github": bool(cfg.get("github_enabled") and cfg.get("github_client_id") and cfg.get("github_secret")),
        "google_callback": f"{_redirect_base(cfg)}/api/oauth/google/callback",
        "github_callback": f"{_redirect_base(cfg)}/api/oauth/github/callback",
    }


def google_login_url(state):
    cfg = _get_oauth_config()
    if not oauth_status()["google"]:
        raise ValueError("Google 登录尚未配置")
    params = {
        "client_id": cfg.get("google_client_id", ""),
        "redirect_uri": f"{_redirect_base(cfg)}/api/oauth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def google_callback(code):
    cfg = _get_oauth_config()
    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": cfg.get("google_client_id", ""),
            "client_secret": cfg.get("google_secret", ""),
            "redirect_uri": f"{_redirect_base(cfg)}/api/oauth/google/callback",
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    if token_resp.status_code != 200:
        return None, "Google 登录授权失败"

    tokens = token_resp.json()
    access_token = tokens.get("access_token")
    if not access_token:
        return None, "Google 未返回访问令牌"

    user_resp = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20,
    )
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


def github_login_url(state):
    cfg = _get_oauth_config()
    if not oauth_status()["github"]:
        raise ValueError("GitHub 登录尚未配置")
    params = {
        "client_id": cfg.get("github_client_id", ""),
        "redirect_uri": f"{_redirect_base(cfg)}/api/oauth/github/callback",
        "scope": "user:email",
        "state": state,
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


def github_callback(code):
    cfg = _get_oauth_config()
    token_resp = requests.post(
        "https://github.com/login/oauth/access_token",
        data={
            "code": code,
            "client_id": cfg.get("github_client_id", ""),
            "client_secret": cfg.get("github_secret", ""),
            "redirect_uri": f"{_redirect_base(cfg)}/api/oauth/github/callback",
        },
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if token_resp.status_code != 200:
        return None, "GitHub 登录授权失败"

    tokens = token_resp.json()
    access_token = tokens.get("access_token")
    if not access_token:
        return None, "GitHub 未返回访问令牌"

    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
    user_resp = requests.get("https://api.github.com/user", headers=headers, timeout=20)
    if user_resp.status_code != 200:
        return None, "GitHub 用户信息获取失败"

    info = user_resp.json()
    email = info.get("email", "")
    if not email:
        email_resp = requests.get("https://api.github.com/user/emails", headers=headers, timeout=20)
        if email_resp.status_code == 200:
            emails = email_resp.json()
            for item in emails:
                if item.get("primary") and item.get("verified"):
                    email = item.get("email", "")
                    break
            if not email and emails:
                email = emails[0].get("email", "")

    return {
        "provider": "github",
        "provider_id": str(info.get("id")),
        "email": email,
        "name": info.get("name") or info.get("login", ""),
        "avatar": info.get("avatar_url", ""),
    }, None

"""
📧 邮件服务 — SMTP 发送
"""
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.header import Header


def generate_verify_code(length=6):
    return ''.join(random.choices(string.digits, k=length))


def send_email(to_email, subject, body):
    """发送邮件，配置从数据库读取"""
    from models import get_smtp_config
    cfg = get_smtp_config()
    if not cfg.get("password"):
        print(f"[Mail] ⚠️ SMTP 密码未配置，跳过发送: {to_email}", flush=True)
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = cfg["sender"]
    msg["To"] = to_email

    try:
        if cfg["use_ssl"]:
            server = smtplib.SMTP_SSL(cfg["server"], cfg["port"])
        else:
            server = smtplib.SMTP(cfg["server"], cfg["port"])
            server.starttls()

        server.login(cfg["account"], cfg["password"])
        server.sendmail(cfg["sender"], [to_email], msg.as_string())
        server.quit()
        print(f"[Mail] ✅ 发送成功: {to_email}", flush=True)
        return True
    except Exception as e:
        print(f"[Mail] ❌ 发送失败: {e}", flush=True)
        return False


def send_verify_code(to_email, code):
    subject = "Tikpan AI Studio - 邮箱验证码"
    body = f"""您好，

您的 Tikpan AI Studio 验证码是：{code}

验证码 10 分钟内有效，请勿泄露给他人。

Tikpan AI Studio
"""
    return send_email(to_email, subject, body)

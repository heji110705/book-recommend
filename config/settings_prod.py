# -*- coding: utf-8 -*-
"""
生产环境配置（部署用）
用法：
    export DJANGO_SETTINGS_MODULE=config.settings_prod
    或  gunicorn config.wsgi:application -c gunicorn_config.py
关键环境变量：
    SECRET_KEY          必填，Django 密钥
    ALLOWED_HOSTS       逗号分隔的域名，默认 "*"
    CSRF_ORIGINS        逗号分隔的 https 域名（用于 CSRF 信任）
    DATABASE_URL        可选，Postgres 连接串；不填则用 SQLite
"""
import os

from .settings import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-please-set-a-real-secret-key-via-env",
)

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "*").split(",") if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_ORIGINS", "").split(",") if o.strip()
]

# WhiteNoise 静态文件服务（放在 SecurityMiddleware 之后）
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
] + [m for m in MIDDLEWARE if m != "django.middleware.security.SecurityMiddleware"]  # noqa: F405

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# 安全相关（HTTPS 部署后开启）
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
if os.environ.get("ENABLE_HTTPS", "0") == "1":
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# 可选：PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL:
    import re
    match = re.match(
        r"postgres(?:ql)?://(?P<user>[^:]+):(?P<pwd>[^@]+)@(?P<host>[^:/]+)"
        r"(?::(?P<port>\d+))?/(?P<name>.+)", DATABASE_URL)
    if match:
        DATABASES = {  # noqa: F405
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": match.group("name"),
                "USER": match.group("user"),
                "PASSWORD": match.group("pwd"),
                "HOST": match.group("host"),
                "PORT": match.group("port") or "5432",
            }
        }

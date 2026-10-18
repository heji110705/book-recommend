# -*- coding: utf-8 -*-
"""Gunicorn 生产运行配置"""
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "8000")
# CPU 核数 * 2 + 1 是常见经验值；毕设演示取 3 足够
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))
worker_class = "sync"
timeout = 120
graceful_timeout = 30
keepalive = 5
max_requests = 500
max_requests_jitter = 50
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

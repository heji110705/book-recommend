# -*- coding: utf-8 -*-
# 基于混合推荐与评论情感分析的个性化图书推荐系统 —— 生产镜像
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings_prod \
    PORT=8000

# scikit-learn 运行所需
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用 Docker 缓存）
# 若在国内构建较慢，可在下面 pip 命令后追加：-i https://pypi.tuna.tsinghua.edu.cn/simple
COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt -r requirements-prod.txt

# 拷贝项目
COPY . .

# 收集静态文件（whitenoise 提供）
# 构建阶段还没有真实密钥，collectstatic 不依赖它，给一个仅用于构建的占位值即可
RUN SECRET_KEY=build-only-dummy-not-used-at-runtime python manage.py collectstatic --noinput

EXPOSE 8000

# 启动：迁移数据库后以 gunicorn 提供服务
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application -c gunicorn_config.py"]

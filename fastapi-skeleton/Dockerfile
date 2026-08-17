# 使用官方 slim 镜像，体积更小、漏洞面更少
FROM python:3.12-slim

WORKDIR /app

# 避免缓冲导致日志不实时；pip 不写缓存减小镜像层
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 先拷贝依赖清单并安装，利用 Docker 层缓存加速重建
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# 再拷贝源码（源码变动不会使依赖层失效）
COPY . .

EXPOSE 8000

# 生产建议用多 worker：gunicorn -k uvicorn.workers.UvicornWorker
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

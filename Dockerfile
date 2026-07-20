# ============================================================
# AE-Knowledge-Vault Dockerfile
# 多阶段构建：Python 后端 + Node.js 前端 + Nginx
# ============================================================

# ---- Stage 1: 构建前端 ----
FROM node:22-slim AS frontend-builder

WORKDIR /build

COPY ae-dashboard/package.json ae-dashboard/package-lock.json* ./
RUN npm ci --production=false

COPY ae-dashboard/ ./
RUN npm run build

# ---- Stage 2: Python 后端 ----
FROM python:3.11-slim AS backend

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

# 先复制依赖文件利用层缓存
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir fastapi uvicorn pydantic

# 复制后端源码
COPY api_server.py auth_system.py monitoring.py distributed_scheduler.py \
     database.py plugin_system.py batch_queue.py ./
COPY config/ ./config/

# 复制前端构建产物
COPY --from=frontend-builder /build/dist ./ae-dashboard/dist

# 复制测试和脚本
COPY test_api_integration.py ./

# 环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV AEK_ENVIRONMENT=production
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV API_WORKERS=1

# 数据目录
RUN mkdir -p /app/data /app/logs

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# 启动 API 服务
CMD ["python", "-m", "uvicorn", "api_server:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

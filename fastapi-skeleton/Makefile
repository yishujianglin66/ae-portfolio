# 默认目标
.DEFAULT_GOAL := help

.PHONY: help install dev run test docker-up docker-down

help:  ## 显示帮助
	@echo "可用命令:"
	@sed -n 's/^\([a-z-]*\):.*##\(.*\)/  \1  \2/p' $(MAKEFILE_LIST)

install:  ## 安装依赖（优先 uv，回退 pip）
	uv sync || pip install -e ".[dev]"

dev:  ## 开发热重载启动
	uv run uvicorn app.main:app --reload || uvicorn app.main:app --reload

run:  ## 生产式启动
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 || uvicorn app.main:app --host 0.0.0.0 --port 8000

test:  ## 跑测试
	uv run pytest -q || pytest -q

docker-up:  ## 构建并后台启动容器
	docker compose up --build -d

docker-down:  ## 停止并移除容器
	docker compose down

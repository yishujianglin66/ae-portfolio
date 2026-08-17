# FastAPI + Pydantic v2 分层架构骨架

一个可直接运行的 REST API 项目骨架，演示标准的**分层架构**：

```
配置 → 数据库 → 依赖注入 → 仓储(Repository) → 服务(Service) → 路由(API) → 入口
```

技术栈：**FastAPI + Pydantic v2 + SQLAlchemy 2.0(async) + SQLite(aiosqlite)**，零配置即跑。

## 目录结构

```
fastapi-skeleton/
├── src/app/
│   ├── main.py              # 应用入口（lifespan + 注册路由/中间件/异常）
│   ├── config.py            # pydantic-settings 配置
│   ├── database.py          # async engine / session / Base
│   ├── dependencies.py      # 依赖注入装配（session→repo→service）
│   ├── models/              # SQLAlchemy ORM 模型
│   │   └── user.py
│   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── common.py        # 通用分页 Page[T]
│   │   └── user.py
│   ├── repositories/        # 数据访问层（封装所有 SQL）
│   │   └── user.py
│   ├── services/            # 业务逻辑层（规则/校验/哈希）
│   │   └── user.py
│   ├── api/v1/              # 路由层
│   │   ├── router.py        # 聚合 v1 子路由
│   │   └── users.py
│   └── utils/               # 异常、安全工具
│       ├── exceptions.py
│       └── security.py
├── tests/
│   ├── conftest.py          # 测试 fixture（内存库 + 依赖覆盖）
│   ├── test_api/            # 路由端到端测试
│   └── test_services/       # service 单测
├── pyproject.toml           # 依赖与工具配置（hatchling 打包 + pytest）
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── .env.example
└── .gitignore
```

## 快速开始

### 方式一：uv（推荐）
```bash
uv sync
uv run uvicorn app.main:app --reload
```

### 方式二：pip
```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

启动后访问：
- API 文档(Swagger): http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### 跑测试
```bash
uv run pytest -q   # 或 make test
```

### Docker
```bash
docker compose up --build    # 或 make docker-up
```

## User 资源接口（前缀 /api/v1）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/users` | 创建用户（201） |
| GET | `/users?page=1&size=20` | 分页列表（Page[UserRead]） |
| GET | `/users/{id}` | 用户详情 |
| PATCH | `/users/{id}` | 局部更新（name/is_active/password） |
| DELETE | `/users/{id}` | 删除（204） |

统一错误结构：`{"error": {"code": "...", "message": "..."}}`，如重复邮箱返回 409 `conflict`，不存在返回 404 `not_found`。

## 设计要点 / 踩坑提示

1. **密码永不出网**：`UserRead` 不含 `password`/`hashed_password` 字段；存储用 bcrypt 哈希。
2. **依赖倒置**：路由只 `Depends(get_user_service)`，不关心下层如何构造，便于测试替换。
3. **测试隔离**：`conftest` 用 in-memory SQLite + `StaticPool` + `dependency_overrides`，真实库不被触碰。
4. **分页总数与偏移解耦**：`list()` 单独 `count()`，比 `len(result)` 更准确（受 limit 限制）。
5. **`expire_on_commit=False`**：提交后对象属性仍可读，避免意外懒加载。
6. **生产迁移**：当前 `init_db()` 用 `create_all` 仅适合演示；生产请接 **Alembic**。
7. **换数据库**：只需改 `.env` 的 `APP_DATABASE_URL`（如 Postgres 示例），其余代码不动。
8. **密码哈希**：直接用 `bcrypt` 库（未用已停更的 `passlib`，避免其与 bcrypt 5.x 不兼容）。bcrypt 仅取密码前 72 字节；超长密码生产环境建议先 SHA-256 摘要。

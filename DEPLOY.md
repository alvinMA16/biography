# 部署指南

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入真实的 API 密钥和数据库密码。

### 2. 启动服务

```bash
docker compose up -d --build
```

首次启动会自动：
- 创建 PostgreSQL 数据库
- 执行 Alembic 数据库迁移
- 启动后端（Gunicorn + 2 worker）
- 启动 Nginx 反向代理

### 3. 检查状态

```bash
docker compose ps          # 查看服务状态（3 个都应为 healthy/running）
docker compose logs backend # 查看后端日志
curl http://localhost/health # 健康检查
```

### 4. 停止服务

```bash
docker compose down        # 停止并移除容器（数据保留）
docker compose down -v     # 停止并删除数据卷（⚠️ 会清空数据库）
```

## 常用操作

```bash
# 查看实时日志
docker compose logs -f

# 仅重启后端
docker compose restart backend

# 重新构建后端镜像（代码改动后）
docker compose up -d --build backend

# 进入后端容器调试
docker compose exec backend bash
```

## 数据迁移（SQLite → PostgreSQL）

如果有旧的 SQLite 数据需要导入：

```bash
docker compose exec backend python scripts/migrate_data.py \
  --sqlite biography.db \
  --pg postgresql://biography:密码@db:5432/biography
```

先用 `--dry-run` 预览：

```bash
docker compose exec backend python scripts/migrate_data.py \
  --sqlite biography.db \
  --pg postgresql://biography:密码@db:5432/biography \
  --dry-run
```

## 本地开发（SQLite 模式）

不需要 Docker，直接运行：

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端用浏览器直接打开 `web/index.html` 或用任意静态服务器。

## 环境变量说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `POSTGRES_PASSWORD` | 数据库密码 | 必填 |
| `POSTGRES_USER` | 数据库用户 | `biography` |
| `POSTGRES_DB` | 数据库名 | `biography` |
| `WEB_PORT` | 对外端口 | `80` |
| `WORKERS` | 后端 worker 数 | `2` |
| `DASHSCOPE_API_KEY` | 通义千问 API Key | - |
| `DOUBAO_APP_ID` | 豆包应用 ID | - |
| `DOUBAO_ACCESS_KEY` | 豆包 Access Key | - |

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

## 测试环境

生产和测试环境在同一台机器上，通过不同的分支、目录、容器和域名隔离。

```
biography/      (main 分支) → 生产环境 → https://storyofme.cn
biography-test/ (dev 分支)  → 测试环境 → https://test.storyofme.cn
```

### 目录结构

| | 生产环境 | 测试环境 |
|---|---|---|
| 代码目录 | `/root/alvin/biography/` | `/root/alvin/biography-test/`（git worktree） |
| Git 分支 | `main` | `dev` |
| 后端端口 | `127.0.0.1:8001` | `127.0.0.1:8002` |
| 数据库端口 | `127.0.0.1:5432` | `127.0.0.1:5433` |
| 域名 | `storyofme.cn` | `test.storyofme.cn` |
| Compose 文件 | `docker-compose.yml` | `docker-compose.test.yml` |
| 项目名 | `biography` | `biography-test` |
| 环境变量 | `.env` | `.env`（独立，DEBUG=true） |
| 管理台 | `https://storyofme.cn/admin.html` | `https://test.storyofme.cn/admin.html` |

### 日常开发流程

```
biography-test/ (dev分支)    biography/ (main分支)
       │                           │
    改代码                        不动
       │                           │
    部署测试环境                    │
       │                           │
    验证通过 ──── git merge dev ──→ │
                                   │
                              部署生产环境
```

**1. 在测试环境改代码**

所有改动在 `/root/alvin/biography-test/` 下进行（dev 分支）。

**2. 部署测试环境**

```bash
cd /root/alvin/biography-test
./deploy.sh
```

脚本会自动停止旧容器 → 构建镜像 → 启动 → 健康检查，无需手动 `docker compose down`。

访问 `https://test.storyofme.cn` 验证。

**3. 测试通过后同步到生产**

```bash
# 在测试目录提交代码
cd /root/alvin/biography-test
git add .
git commit -m "描述改动"

# 切到生产目录，合并 dev 分支
cd /root/alvin/biography
git merge dev

# 重新部署生产
docker compose up -d --build
```

### 测试环境管理

```bash
cd /root/alvin/biography-test

# 部署（自动 down → build → up → 健康检查）
./deploy.sh

# 查看状态
docker compose -p biography-test -f docker-compose.test.yml ps

# 查看日志
docker compose -p biography-test -f docker-compose.test.yml logs -f backend

# 停止（不影响生产）
docker compose -p biography-test -f docker-compose.test.yml down
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

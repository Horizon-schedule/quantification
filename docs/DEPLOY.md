# StopQuant Docker 部署指南

## 架构说明

```
                    ┌─────────────┐
   用户浏览器 ──────▶│   Nginx     │ :80
                    │  (反向代理)  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Flask App  │ :8000 (Gunicorn)
                    │  (Docker)   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  云数据库    │ PostgreSQL / MySQL
                    │ (外部 RDS)  │
                    └─────────────┘
```

- **Nginx**：对外暴露 80 端口，代理 API 和静态资源，托管回测图表
- **App**：Python 应用容器，通过 Gunicorn 运行
- **云数据库**：使用您已有的 PostgreSQL 或 MySQL，不在 compose 中启动

## 前置条件

1. 服务器已安装 Docker 和 Docker Compose v2
2. 云数据库已创建，并记录连接信息
3. 云数据库安全组/白名单已放行服务器 IP

## 快速部署

### 1. 上传代码到服务器

```bash
git clone <your-repo> stop_quantification
cd stop_quantification
```

### 2. 配置环境变量

```bash
cp .env.example .env
vim .env
```

**PostgreSQL 示例（阿里云 RDS）：**

```env
DATABASE_URL=postgresql+psycopg2://用户名:密码@rm-xxxxx.pg.rds.aliyuncs.com:5432/stopquant
SECRET_KEY=随机长字符串
HTTP_PORT=80
```

**MySQL 示例（腾讯云）：**

```env
DATABASE_URL=mysql+pymysql://用户名:密码@cdb-xxxxx.sql.tencentcdb.com:3306/stopquant?charset=utf8mb4
SECRET_KEY=随机长字符串
HTTP_PORT=80
```

### 3. 启动服务

```bash
docker compose up -d --build
```

### 4. 验证

```bash
# 查看容器状态
docker compose ps

# 健康检查
curl http://localhost/api/health

# 查看日志
docker compose logs -f app
```

浏览器访问 `http://服务器IP/` 即可使用。

## 云数据库配置要点

### PostgreSQL

1. 创建数据库：`CREATE DATABASE stopquant ENCODING 'UTF8';`
2. 创建用户并授权
3. 连接 URL 格式：`postgresql+psycopg2://user:pass@host:5432/stopquant`
4. 首次启动时 App 会自动建表

### MySQL

1. 创建数据库：`CREATE DATABASE stopquant CHARACTER SET utf8mb4;`
2. 连接 URL 格式：`mysql+pymysql://user:pass@host:3306/stopquant?charset=utf8mb4`
3. 首次启动时 App 会自动建表

### 连接 URL 特殊字符

密码中含 `@`、`#` 等特殊字符时需 URL 编码，例如 `@` → `%40`。

## 常用运维命令

```bash
# 重启
docker compose restart

# 停止
docker compose down

# 更新代码后重新部署
git pull
docker compose up -d --build

# 进入容器调试
docker compose exec app bash

# 查看 App 日志
docker compose logs -f app nginx
```

## HTTPS 配置（可选）

生产环境建议在 Nginx 前再加一层 SSL 终止（如宝塔面板、Caddy、或云负载均衡）。

也可在 `nginx/nginx.conf` 中增加 SSL 证书配置，并将 `docker-compose.yml` 中端口改为 `443:443`。

## 环境变量完整列表

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 云数据库连接 URL | SQLite 本地 |
| `SECRET_KEY` | Flask 密钥 | 需修改 |
| `HTTP_PORT` | 对外端口 | 80 |
| `LOG_LEVEL` | 日志级别 | INFO |
| `BACKTEST_INITIAL_CAPITAL` | 默认回测资金 | 100000 |
| `API_REQUEST_INTERVAL` | API 请求间隔(秒) | 0.5 |
| `ALERT_WECHAT_ENABLED` | 微信告警 | false |
| `WECHAT_WEBHOOK` | 企业微信 Webhook | 空 |

## 故障排查

| 问题 | 排查方法 |
|------|----------|
| 数据库连接失败 | 检查 DATABASE_URL、云数据库白名单、端口 |
| 页面 502 | `docker compose logs app` 查看 Gunicorn 是否启动 |
| K 线无数据 | 检查服务器能否访问东方财富 API（出站网络） |
| 健康检查失败 | `curl http://localhost:8000/api/health` 在容器内测试 |

## 本地开发 vs 生产

| 场景 | 数据库 | 启动方式 |
|------|--------|----------|
| 本地开发 | SQLite（默认） | `python main.py` |
| Docker 生产 | 云 PostgreSQL/MySQL | `docker compose up -d` |

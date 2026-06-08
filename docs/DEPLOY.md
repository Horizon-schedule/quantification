# StopQuant Docker 部署指南

## 架构说明

```
用户浏览器
    │
    ▼
ECS 宿主机 Nginx :443（已有，统一管理 SSL）
    │
    ├─ apiself.online              → 127.0.0.1:3000
    ├─ bookkeeping.apiself.online  → 127.0.0.1:8080
    └─ quant.apiself.online        → 127.0.0.1:8000
                                          │
                                   ┌──────▼──────┐
                                   │  Flask App  │ Docker (Gunicorn)
                                   └──────┬──────┘
                                          │
                                   ┌──────▼──────┐
                                   │  云数据库    │ PostgreSQL / MySQL
                                   └─────────────┘
```

- **宿主机 Nginx**：对外暴露 80/443，SSL 终止与反代（项目内不再包含 Nginx 容器）
- **App 容器**：Gunicorn 监听 8000，映射到宿主机 `APP_BIND_PORT`（默认 8000）
- **云数据库**：使用已有的 PostgreSQL 或 MySQL，不在 compose 中启动

> 宿主机 Nginx 配置示例见 [docs/examples/nginx-host-stopquant.conf](examples/nginx-host-stopquant.conf)

## 前置条件

1. 服务器已安装 Docker 和 Docker Compose v2
2. ECS 上已有 Nginx（或计划单独安装）
3. 云数据库已创建，安全组/白名单已放行 ECS IP

## 快速部署

### 1. 上传代码

```bash
git clone https://github.com/Horizon-schedule/quantification.git /opt/stopquant
cd /opt/stopquant
```

### 2. 配置环境变量

```bash
cp .env.example .env
vim .env
```

**MySQL 示例：**

```env
APP_BIND_PORT=8000
SECRET_KEY=随机长字符串

DB_TYPE=mysql
DB_HOST=rm-xxxxx.mysql.rds.aliyuncs.com
DB_PORT=3306
DB_USER=stopquant
DB_PASSWORD=你的密码
DB_NAME=stopquant
```

### 3. 启动应用

```bash
docker compose up -d --build
```

### 4. 配置宿主机 Nginx 反代

将 `docs/examples/nginx-host-stopquant.conf` 中的 HTTPS 段追加到 ECS 现有 Nginx 配置，并 reload：

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 5. 验证

```bash
docker compose ps
curl http://127.0.0.1:8000/api/health
# 期望: {"status":"ok","database":true,...}

curl https://quant.apiself.online/api/health
```

## 常用运维命令

```bash
docker compose restart
docker compose down
git pull && docker compose up -d --build
docker compose logs -f app --tail 100
docker compose exec app bash
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `APP_BIND_PORT` | Docker 映射到宿主机的端口 | 8000 |
| `DATABASE_URL` | 云数据库连接 URL | SQLite 本地 |
| `SECRET_KEY` | Flask 密钥 | 需修改 |
| `LOG_LEVEL` | 日志级别 | INFO |

## 故障排查

| 问题 | 排查方法 |
|------|----------|
| 502 Bad Gateway | `curl http://127.0.0.1:8000/api/health` 确认 App 正常 |
| Nginx 502 | 检查 `proxy_pass` 端口是否为 `APP_BIND_PORT` |
| 数据库连接失败 | 检查 DATABASE_URL、白名单 |
| K 线无数据 | 检查 ECS 出站网络能否访问东方财富 API |

## 本地开发 vs 生产

| 场景 | 数据库 | 启动方式 | 访问 |
|------|--------|----------|------|
| 本地开发 | SQLite | `python main.py` | :5000 |
| Docker 生产 | 云 MySQL/PG | `docker compose up -d` | 宿主机 Nginx → :8000 |

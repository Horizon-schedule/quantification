# 阿里云 ECS + RDS MySQL 部署指南

本文档针对 **ECS 已有 Nginx + RDS MySQL + Docker 仅跑 App** 的场景。

## 架构

```
用户浏览器
    │
    ▼
ECS 宿主机 Nginx :80 / :443
    │
    ├─ apiself.online              → 127.0.0.1:3000   （你的其他服务）
    ├─ bookkeeping.apiself.online  → 127.0.0.1:8080   （你的其他服务）
    └─ quant.apiself.online        → 127.0.0.1:8000   （StopQuant Docker）
                                          │
                                          ▼
                                    RDS MySQL（VPC 内网）
```

StopQuant **不再启动 Docker 内 Nginx**，避免与 ECS 已有 Nginx 抢占 80/443 端口。

## 一、RDS MySQL 准备

与之前相同，详见 `scripts/init_rds_mysql.sql`。

| 配置项 | 建议 |
|--------|------|
| 数据库类型 | MySQL 8.0 |
| 网络 | 与 ECS 同一 VPC |
| 白名单 | 仅 ECS 内网 IP |

连接地址示例：`rm-xxxxxxxx.mysql.rds.aliyuncs.com:3306`

## 二、ECS 准备

| 配置项 | 建议 |
|--------|------|
| 系统 | Ubuntu 22.04 / Alibaba Cloud Linux |
| 规格 | 2核 4G 起 |
| 安全组 | 入方向 **80、443**（Nginx）；**不要**对公网开放 8000、3306 |
| 已有服务 | Nginx 已监听 80/443 |

### 安装 Docker（若未安装）

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker
```

### 拉取代码

```bash
git clone https://github.com/Horizon-schedule/quantification.git /opt/stopquant
cd /opt/stopquant
```

## 三、配置并部署 StopQuant

### 1. `.env`

```bash
cp .env.example .env
vim .env
```

```env
APP_BIND_PORT=8000
SECRET_KEY=随机32位字符串

DB_TYPE=mysql
DB_HOST=rm-xxxxxxxx.mysql.rds.aliyuncs.com
DB_PORT=3306
DB_USER=stopquant
DB_PASSWORD=YourStrongPassword123
DB_NAME=stopquant

BACKTEST_INITIAL_CAPITAL=200000
API_REQUEST_INTERVAL=0.5
```

### 2. 启动 Docker

```bash
chmod +x scripts/deploy_ecs.sh
./scripts/deploy_ecs.sh
```

或：

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/api/health
```

## 四、配置宿主机 Nginx

你当前的 Nginx 已管理 `apiself.online` 与 `bookkeeping.apiself.online`。
StopQuant 只需**追加**一段反代配置。

### 1. 修改 HTTP 80 跳转块

在 `server_name` 中增加 StopQuant 子域：

```nginx
server_name apiself.online bookkeeping.apiself.online quant.apiself.online;
```

### 2. 追加 HTTPS 反代（完整示例见项目内文件）

复制 [docs/examples/nginx-host-stopquant.conf](examples/nginx-host-stopquant.conf) 中的 `server { ... }` 块到 Nginx 配置目录，例如：

```bash
sudo vim /etc/nginx/sites-enabled/stopquant.conf
# 粘贴 HTTPS server 块，proxy_pass 指向 http://127.0.0.1:8000
sudo nginx -t && sudo systemctl reload nginx
```

### 3. SSL 证书

若 `apiself.online` 证书为通配符或 SAN 已含 `quant.apiself.online`，可直接复用。
否则：

```bash
sudo certbot certonly --nginx -d quant.apiself.online
```

### 4. DNS

将 `quant.apiself.online` A 记录指向 ECS 公网 IP。

## 五、验证

```bash
# App 容器
docker compose ps
curl http://127.0.0.1:8000/api/health

# 经 Nginx
curl https://quant.apiself.online/api/health
```

浏览器访问：`https://quant.apiself.online/`

## 六、安全组

| 方向 | 端口 | 说明 |
|------|------|------|
| 入 | 80, 443 | 公网 Web（Nginx） |
| 入 | 22 | SSH（限制来源 IP） |
| **勿开放** | 8000 | 仅本机 Nginx 反代 |
| **勿开放** | 3306 | RDS 仅内网 |

## 七、常用运维

```bash
git pull
docker compose up -d --build
docker compose logs -f app --tail 100
docker compose restart
```

## 八、故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 502 | App 未启动 | `docker compose logs app` |
| 502 | Nginx 端口错 | 确认 `proxy_pass http://127.0.0.1:8000` |
| 端口冲突 | 8000 被占用 | `.env` 改 `APP_BIND_PORT=8001` 并同步 Nginx |
| database: false | RDS 连接失败 | 白名单、账号密码 |
| 80 端口冲突 | 重复 Nginx | 勿在 compose 中再启 Nginx 容器 |

## 九、与本地开发区别

| 项目 | 本地 | ECS 生产 |
|------|------|----------|
| 数据库 | SQLite | RDS MySQL |
| Web | Flask :5000 | Gunicorn :8000 + 宿主机 Nginx |
| 对外端口 | 5000 | 443（Nginx） |

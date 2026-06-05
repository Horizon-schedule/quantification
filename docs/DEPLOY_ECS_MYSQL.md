# 阿里云 ECS + RDS MySQL 部署指南

本文档专门针对 **ECS 云服务器 + RDS for MySQL** 的部署场景。

## 架构

```
用户浏览器
    │
    ▼
ECS 公网 IP :80
    │
    ├─ Nginx 容器（反向代理 + 静态资源）
    │
    └─ App 容器（Gunicorn + Flask）
            │
            ▼ （VPC 内网，推荐）
        RDS MySQL（内网地址）
```

## 一、RDS MySQL 准备

### 1. 创建 RDS 实例

阿里云控制台 → RDS → 创建实例：

| 配置项 | 建议 |
|--------|------|
| 数据库类型 | MySQL 8.0 |
| 系列 | 基础版/高可用版均可 |
| 网络 | 与 ECS **同一 VPC、同一交换机** |
| 字符集 | utf8mb4 |

### 2. 创建数据库和账号

RDS 控制台 → 账号管理 → 创建账号：

- 账号：`stopquant`
- 密码：强密码（记下，写入 .env）
- 授权数据库：`stopquant`（需先在「数据库管理」中创建）

或在 DMS 中执行 `scripts/init_rds_mysql.sql`。

### 3. 配置白名单

RDS 控制台 → 数据安全性 → 白名单：

- 添加 ECS 的**内网 IP**（推荐）
- 或添加 ECS 所在交换机的网段，如 `172.16.0.0/24`

> 不要对 `0.0.0.0/0` 开放 RDS，仅允许 ECS 内网访问。

### 4. 获取连接地址

RDS 控制台 → 数据库连接：

- **内网地址**（ECS 部署必用）：`rm-xxxxxxxx.mysql.rds.aliyuncs.com`
- 端口：`3306`

## 二、ECS 准备

### 1. 推荐配置

| 配置项 | 建议 |
|--------|------|
| 系统 | Ubuntu 22.04 / CentOS 7+ / Alibaba Cloud Linux |
| 规格 | 2核 4G 起 |
| 带宽 | 3Mbps 起（需访问东方财富 API） |
| 安全组 | 入方向放行 **80**（HTTP）、**443**（HTTPS 可选） |

### 2. 安装 Docker

```bash
# 一键安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# 验证
docker --version
docker compose version
```

### 3. 上传代码

```bash
# 方式一：Git
git clone <你的仓库地址> /opt/stopquant
cd /opt/stopquant

# 方式二：SCP 上传压缩包后解压
```

## 三、配置并部署

### 1. 创建配置文件

```bash
cd /opt/stopquant
cp .env.example .env
vim .env
```

**`.env` 示例（阿里云 RDS MySQL）：**

```env
HTTP_PORT=80
SECRET_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

DB_TYPE=mysql
DB_HOST=rm-xxxxxxxx.mysql.rds.aliyuncs.com
DB_PORT=3306
DB_USER=stopquant
DB_PASSWORD=YourStrongPassword123
DB_NAME=stopquant

BACKTEST_INITIAL_CAPITAL=200000
API_REQUEST_INTERVAL=0.5
MONITOR_POLL_INTERVAL=10
```

> 密码含特殊字符（如 `@`、`#`）时，建议使用分项配置（`DB_PASSWORD`），系统会自动 URL 编码。若用 `DATABASE_URL`，需手动编码。

### 2. 一键部署

```bash
chmod +x scripts/deploy_ecs.sh
./scripts/deploy_ecs.sh
```

或手动执行：

```bash
docker compose up -d --build
```

### 3. 验证

```bash
# 容器状态
docker compose ps

# 健康检查（database 应为 true）
curl http://127.0.0.1/api/health

# 预期返回
# {"status":"ok","database":true,"dialect":"mysql"}

# 查看日志
docker compose logs -f app
```

浏览器访问：`http://ECS公网IP/`

## 四、ECS 安全组配置

| 方向 | 协议 | 端口 | 源 | 说明 |
|------|------|------|-----|------|
| 入 | TCP | 80 | 0.0.0.0/0 | Web 访问 |
| 入 | TCP | 443 | 0.0.0.0/0 | HTTPS（可选） |
| 入 | TCP | 22 | 你的IP | SSH 管理 |

**不要**对公网开放 3306（RDS 端口）和 8000（App 内部端口）。

## 五、常用运维

```bash
# 重启
docker compose restart

# 停止
docker compose down

# 更新代码后重新部署
git pull
docker compose up -d --build

# 查看 App 日志
docker compose logs -f app --tail 100

# 进入容器排查
docker compose exec app bash
python -c "from quant_platform.data.db_backend import DatabaseBackend; print(DatabaseBackend.check_connection())"
```

## 六、HTTPS 配置（推荐）

生产环境建议绑定域名并启用 HTTPS：

1. 域名解析到 ECS 公网 IP
2. 使用 Certbot 或阿里云 SSL 证书
3. 修改 `nginx/nginx.conf` 增加 443 监听
4. `docker-compose.yml` 中 nginx 端口增加 `443:443`

## 七、故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| `database: false` | RDS 连接失败 | 检查 DB_HOST、白名单、账号密码 |
| 502 Bad Gateway | App 未启动 | `docker compose logs app` |
| K 线无数据 | ECS 无法访问外网 | 检查安全组出站规则、东方财富 API |
| 表不存在 | 首次启动失败 | 重启 App：`docker compose restart app` |
| Access denied | 账号权限不足 | RDS 控制台检查账号对 stopquant 库的权限 |

### 测试 RDS 连通性（在 ECS 上）

```bash
# 安装 mysql 客户端（可选）
apt install mysql-client -y   # Ubuntu
yum install mysql -y          # CentOS

mysql -h rm-xxx.mysql.rds.aliyuncs.com -u stopquant -p stopquant
```

## 八、与本地开发的区别

| 项目 | 本地开发 | ECS 生产 |
|------|----------|----------|
| 数据库 | SQLite（默认） | RDS MySQL |
| 启动 | `python main.py` | `docker compose up -d` |
| Web 端口 | 5000 | 80（Nginx） |
| 进程 | Flask 开发服务器 | Gunicorn |

本地开发无需配置 `.env` 中的 MySQL，会自动使用 SQLite。

#!/bin/bash
# StopQuant ECS 一键部署脚本
# 适用：阿里云 ECS + RDS MySQL + Docker Compose
#
# 用法：
#   chmod +x scripts/deploy_ecs.sh
#   ./scripts/deploy_ecs.sh

set -e

echo "=========================================="
echo " StopQuant ECS 部署"
echo "=========================================="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "[错误] 未安装 Docker，请先安装："
    echo "  curl -fsSL https://get.docker.com | sh"
    echo "  systemctl enable docker && systemctl start docker"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "[错误] 未安装 Docker Compose v2"
    exit 1
fi

# 检查 .env
if [ ! -f .env ]; then
    echo "[提示] 未找到 .env，从模板复制..."
    cp .env.example .env
    echo ""
    echo "[重要] 请先编辑 .env 填入 RDS MySQL 连接信息："
    echo "  vim .env"
    echo ""
    echo "  必填项："
    echo "    DB_HOST=rm-xxx.mysql.rds.aliyuncs.com"
    echo "    DB_USER=stopquant"
    echo "    DB_PASSWORD=你的密码"
    echo "    DB_NAME=stopquant"
    echo "    SECRET_KEY=随机字符串"
    echo ""
    exit 1
fi

# 校验关键配置
source .env 2>/dev/null || true
if [ -z "$DB_HOST" ] && [ -z "$DATABASE_URL" ]; then
    echo "[错误] .env 中未配置 DB_HOST 或 DATABASE_URL"
    exit 1
fi

echo "[1/4] 拉取基础镜像并构建应用..."
docker compose build --no-cache

echo "[2/4] 启动服务..."
docker compose up -d

echo "[3/4] 等待健康检查..."
sleep 15

echo "[4/4] 验证部署..."
HTTP_PORT=${HTTP_PORT:-80}
if curl -sf "http://127.0.0.1:${HTTP_PORT}/api/health" > /dev/null; then
    echo ""
    echo "=========================================="
    echo " 部署成功！"
    echo " 访问地址: http://$(curl -s ifconfig.me 2>/dev/null || echo '你的ECS公网IP'):${HTTP_PORT}"
    echo " 健康检查: http://127.0.0.1:${HTTP_PORT}/api/health"
    echo "=========================================="
    docker compose ps
else
    echo "[警告] 健康检查未通过，请查看日志："
    echo "  docker compose logs app"
    exit 1
fi

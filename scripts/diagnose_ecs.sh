#!/bin/bash
# ECS 部署故障诊断（Empty reply / 502 时使用）
set -e

PORT=${APP_BIND_PORT:-8000}

echo "========== StopQuant 诊断 =========="
echo "时间: $(date)"
echo "端口: ${PORT}"
echo ""

echo "[1] Docker 容器状态"
docker compose ps 2>/dev/null || docker-compose ps
echo ""

echo "[2] 8000 端口占用"
if command -v ss &>/dev/null; then
    ss -tlnp | grep ":${PORT}" || echo "  无进程监听 ${PORT}"
elif command -v netstat &>/dev/null; then
    netstat -tlnp | grep ":${PORT}" || echo "  无进程监听 ${PORT}"
fi
echo ""

echo "[3] 最近 App 日志（最后 40 行）"
docker compose logs app --tail 40 2>/dev/null || docker-compose logs app --tail 40
echo ""

echo "[4] 容器内存活探针"
docker compose exec -T app python -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=5)
    print('  live:', r.read().decode())
except Exception as e:
    print('  live 失败:', e)
try:
    r = urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=15)
    print('  health:', r.read().decode())
except Exception as e:
    print('  health 失败:', e)
" 2>/dev/null || echo "  无法 exec 进容器（容器可能未运行）"
echo ""

echo "[5] 宿主机 curl"
curl -sv --max-time 10 "http://127.0.0.1:${PORT}/api/health/live" 2>&1 | tail -5 || true
echo ""

echo "[6] .env 数据库配置（隐藏密码）"
if [ -f .env ]; then
    grep -E '^(DB_|DATABASE_|APP_BIND)' .env | sed 's/PASSWORD=.*/PASSWORD=***/'
else
    echo "  未找到 .env"
fi
echo ""

echo "========== 常见原因 =========="
echo "  Empty reply → worker 未就绪或 RDS 连接卡住，查看上方日志"
echo "  database:false → 检查 DB_HOST、RDS 白名单、账号密码"
echo "  端口冲突 → 修改 .env 中 APP_BIND_PORT 并重启"
echo "  修复后执行: git pull && docker compose up -d --build"

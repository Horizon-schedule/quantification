#!/usr/bin/env python3
"""RDS MySQL 连接测试脚本，可在 ECS 上直接运行。"""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
# 加载 .env（若存在）
env_path = os.path.join(ROOT, ".env")
if os.path.exists(env_path):
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

from config.settings import reload_settings
from quant_platform.data.db_backend import DatabaseBackend

reload_settings()

print("=" * 50)
print("StopQuant RDS MySQL 连接测试")
print("=" * 50)

settings = reload_settings()
url = settings.database.url
# 隐藏密码
safe_url = url.split("@")[-1] if "@" in url else url
print(f"连接目标: ...@{safe_url}")
print(f"数据库类型: {DatabaseBackend.dialect_name()}")

if DatabaseBackend.check_connection():
    print("\n[成功] 数据库连接正常")
    DatabaseBackend.init_schema()
    print("[成功] 数据表已就绪（自动建表完成）")
    sys.exit(0)
else:
    print("\n[失败] 无法连接数据库，请检查：")
    print("  1. .env 中 DB_HOST / DB_USER / DB_PASSWORD 是否正确")
    print("  2. RDS 白名单是否包含 ECS 内网 IP")
    print("  3. ECS 与 RDS 是否在同一 VPC")
    sys.exit(1)

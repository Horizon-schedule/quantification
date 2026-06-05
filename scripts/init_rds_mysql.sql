-- StopQuant RDS MySQL 初始化脚本
-- 在阿里云 RDS 控制台 -> DMS 或 mysql 客户端中执行

-- 1. 创建数据库
CREATE DATABASE IF NOT EXISTS stopquant
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

-- 2. 创建专用账号（如已有账号可跳过，直接在 .env 中配置）
-- CREATE USER 'stopquant'@'%' IDENTIFIED BY 'your_strong_password';
-- GRANT ALL PRIVILEGES ON stopquant.* TO 'stopquant'@'%';
-- FLUSH PRIVILEGES;

-- 3. 切换到数据库
USE stopquant;

-- 说明：应用首次启动时会通过 SQLAlchemy 自动建表，无需手动建表。
-- 若需验证连接，可执行：
-- SELECT 1;

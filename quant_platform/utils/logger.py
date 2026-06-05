"""
统一日志模块。
支持控制台与文件双输出，按模块分级记录。
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(
    log_dir: str = "logs",
    level: str = "INFO",
    log_name: str = "stop_quant",
) -> logging.Logger:
    """
    初始化全局日志配置。

    参数:
        log_dir: 日志目录
        level: 日志级别
        log_name: 日志文件名前缀
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("quant_platform")
    if root_logger.handlers:
        return root_logger

    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件输出（单文件最大 10MB，保留 5 个备份）
    file_handler = RotatingFileHandler(
        log_path / f"{log_name}.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取命名日志器。"""
    if name:
        return logging.getLogger(f"quant_platform.{name}")
    return logging.getLogger("quant_platform")

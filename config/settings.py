"""
全局配置模块。
支持环境变量覆盖，适配 Docker 与云数据库部署。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


from urllib.parse import quote_plus


BASE_DIR = Path(__file__).resolve().parent.parent


def _build_database_url() -> str:
    """
    构建数据库连接 URL，优先级：
    1. DATABASE_URL 环境变量（推荐，ECS + RDS 直连）
    2. 分项配置 DB_HOST/DB_USER/DB_PASSWORD/DB_NAME（MySQL RDS）
    3. 默认 SQLite（仅本地开发）
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url

    db_type = os.getenv("DB_TYPE", "sqlite").lower()
    if db_type == "sqlite":
        db_path = os.getenv(
            "SQLITE_PATH", str(BASE_DIR / "data" / "stop_quant.db")
        )
        return f"sqlite:///{db_path}"

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    user = os.getenv("DB_USER", "stopquant")
    password = quote_plus(os.getenv("DB_PASSWORD", ""))
    name = os.getenv("DB_NAME", "stopquant")

    if db_type in ("postgresql", "postgres"):
        port = os.getenv("DB_PORT", "5432")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    if db_type == "mysql":
        return (
            f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"
            f"?charset=utf8mb4&connect_timeout=10"
        )

    return f"sqlite:///{BASE_DIR / 'data' / 'stop_quant.db'}"


@dataclass
class ApiConfig:
    request_interval: float = float(os.getenv("API_REQUEST_INTERVAL", "0.5"))
    timeout: int = int(os.getenv("API_TIMEOUT", "15"))
    max_retries: int = int(os.getenv("API_MAX_RETRIES", "3"))
    retry_delay: float = float(os.getenv("API_RETRY_DELAY", "2.0"))
    circuit_break_threshold: int = 5
    circuit_break_recovery: float = 60.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )


@dataclass
class DatabaseConfig:
    url: str = field(default_factory=_build_database_url)


@dataclass
class AlertConfig:
    sound_enabled: bool = os.getenv("ALERT_SOUND", "false").lower() == "true"
    email_enabled: bool = os.getenv("ALERT_EMAIL_ENABLED", "false").lower() == "true"
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.qq.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "465"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    email_to: List[str] = field(
        default_factory=lambda: [
            e.strip()
            for e in os.getenv("ALERT_EMAIL_TO", "").split(",")
            if e.strip()
        ]
    )
    wechat_enabled: bool = os.getenv("ALERT_WECHAT_ENABLED", "false").lower() == "true"
    wechat_webhook: str = os.getenv("WECHAT_WEBHOOK", "")


@dataclass
class BacktestConfig:
    initial_capital: float = float(os.getenv("BACKTEST_INITIAL_CAPITAL", "100000"))
    commission_rate: float = float(os.getenv("BACKTEST_COMMISSION", "0.0003"))
    slippage: float = float(os.getenv("BACKTEST_SLIPPAGE", "0"))
    position_size: float = float(os.getenv("BACKTEST_POSITION_SIZE", "1.0"))
    stamp_tax_rate: float = float(os.getenv("BACKTEST_STAMP_TAX", "0.001"))
    enable_t1: bool = os.getenv("BACKTEST_T1", "true").lower() == "true"
    enable_limit: bool = os.getenv("BACKTEST_LIMIT", "true").lower() == "true"
    benchmark_code: str = os.getenv("BACKTEST_BENCHMARK", "000300")


@dataclass
class DataSourceConfig:
    """免费数据源模块开关（详见 docs/DATA_SOURCES.md）。"""

    primary: str = os.getenv("DATA_SOURCE_PRIMARY", "eastmoney")
    fallback: str = os.getenv("DATA_SOURCE_FALLBACK", "none")
    enable_minute_kline: bool = os.getenv("ENABLE_MINUTE_KLINE", "true").lower() == "true"
    enable_financial_statements: bool = os.getenv("ENABLE_FINANCIAL_STATEMENTS", "true").lower() == "true"
    enable_analyst_forecast: bool = os.getenv("ENABLE_ANALYST_FORECAST", "true").lower() == "true"
    enable_northbound: bool = os.getenv("ENABLE_NORTHBOUND", "true").lower() == "true"
    enable_dragon_tiger: bool = os.getenv("ENABLE_DRAGON_TIGER", "true").lower() == "true"
    enable_shareholder: bool = os.getenv("ENABLE_SHAREHOLDER", "true").lower() == "true"
    enable_cninfo_link: bool = os.getenv("ENABLE_CNINFO_LINK", "true").lower() == "true"
    enable_level2: bool = os.getenv("ENABLE_LEVEL2", "false").lower() == "true"
    extended_api_interval: float = float(os.getenv("EXTENDED_API_INTERVAL", "0.6"))


@dataclass
class MonitorConfig:
    poll_interval: float = float(os.getenv("MONITOR_POLL_INTERVAL", "5"))
    default_watchlist: List[str] = field(
        default_factory=lambda: ["000001", "600519", "000300"]
    )


@dataclass
class Settings:
    base_dir: Path = BASE_DIR
    api: ApiConfig = field(default_factory=ApiConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    alert: AlertConfig = field(default_factory=AlertConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    data_source: DataSourceConfig = field(default_factory=DataSourceConfig)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_dir: str = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
    output_dir: str = os.getenv("OUTPUT_DIR", str(BASE_DIR / "output"))
    secret_key: str = os.getenv("SECRET_KEY", "stop-quant-change-me-in-production")
    host: str = os.getenv("APP_HOST", "0.0.0.0")
    port: int = int(os.getenv("APP_PORT", "8000"))

    def ensure_dirs(self) -> None:
        for path in [
            self.base_dir / "data",
            Path(self.log_dir),
            Path(self.output_dir),
        ]:
            path.mkdir(parents=True, exist_ok=True)


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings


def reload_settings() -> Settings:
    """重新加载配置（Docker 启动时调用）。"""
    global _settings
    from quant_platform.data.db_backend import DatabaseBackend

    DatabaseBackend.reset_engine()
    _settings = Settings()
    _settings.ensure_dirs()
    return _settings

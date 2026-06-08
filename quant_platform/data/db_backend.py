"""
数据库连接与 DDL 模块。
支持 SQLite（本地开发）、PostgreSQL、MySQL（云数据库）。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Optional

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from config.settings import DatabaseConfig, get_settings
from quant_platform.utils.logger import get_logger

logger = get_logger("data.db_backend")

metadata = MetaData()

quote_snapshot = Table(
    "quote_snapshot",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(20), nullable=False),
    Column("name", String(100)),
    Column("price", Float),
    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("pre_close", Float),
    Column("change_val", Float),
    Column("change_pct", Float),
    Column("volume", Float),
    Column("amount", Float),
    Column("turnover_rate", Float),
    Column("volume_ratio", Float),
    Column("snapshot_time", String(30), nullable=False),
    Column("created_at", String(30)),
    UniqueConstraint("code", "snapshot_time", name="uq_quote_code_time"),
)

kline_history = Table(
    "kline_history",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(20), nullable=False),
    Column("period", String(10), nullable=False, default="101"),
    Column("adjust_type", String(5), nullable=False, default="1"),
    Column("datetime", String(30), nullable=False),
    Column("open", Float),
    Column("close", Float),
    Column("high", Float),
    Column("low", Float),
    Column("volume", Float),
    Column("amount", Float),
    Column("change_pct", Float),
    Column("turnover_rate", Float),
    Column("created_at", String(30)),
    UniqueConstraint("code", "period", "adjust_type", "datetime", name="uq_kline"),
    Index("idx_kline_code_dt", "code", "datetime"),
)

intraday_data = Table(
    "intraday_data",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(20), nullable=False),
    Column("trade_date", String(20), nullable=False),
    Column("time", String(20), nullable=False),
    Column("price", Float),
    Column("volume", Float),
    Column("avg_price", Float),
    Column("created_at", String(30)),
    UniqueConstraint("code", "trade_date", "time", name="uq_intraday"),
)

backtest_records = Table(
    "backtest_records",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("strategy_name", String(100), nullable=False),
    Column("code", String(20), nullable=False),
    Column("start_date", String(20)),
    Column("end_date", String(20)),
    Column("initial_capital", Float),
    Column("final_capital", Float),
    Column("total_return", Float),
    Column("annual_return", Float),
    Column("max_drawdown", Float),
    Column("sharpe_ratio", Float),
    Column("win_rate", Float),
    Column("profit_loss_ratio", Float),
    Column("trade_count", Integer),
    Column("params_json", Text),
    Column("created_at", String(30)),
)

backtest_trades = Table(
    "backtest_trades",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("backtest_id", Integer, nullable=False),
    Column("trade_date", String(20)),
    Column("action", String(10)),
    Column("price", Float),
    Column("shares", Float),
    Column("amount", Float),
    Column("signal_reason", Text),
)

strategy_signals = Table(
    "strategy_signals",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("strategy_name", String(100), nullable=False),
    Column("code", String(20), nullable=False),
    Column("signal_type", String(10), nullable=False),
    Column("signal_time", String(30), nullable=False),
    Column("price", Float),
    Column("reason", Text),
    Column("created_at", String(30)),
    Index("idx_signals_code", "code", "signal_time"),
)

watchlist = Table(
    "watchlist",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(20), nullable=False, unique=True),
    Column("name", String(100)),
    Column("added_at", String(30)),
)

system_logs = Table(
    "system_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("level", String(20)),
    Column("module", String(50)),
    Column("message", Text),
    Column("created_at", String(30)),
)


class DatabaseBackend:
    """SQLAlchemy 数据库后端。"""

    _engine: Optional[Engine] = None

    @classmethod
    def get_engine(cls, config: Optional[DatabaseConfig] = None) -> Engine:
        if cls._engine is None:
            cfg = config or get_settings().database
            engine_kwargs: dict = {
                "pool_pre_ping": True,
                "pool_recycle": 3600,
                "echo": False,
            }
            if cfg.url.startswith("mysql"):
                engine_kwargs["pool_size"] = 5
                engine_kwargs["max_overflow"] = 10
                engine_kwargs["pool_timeout"] = 10
                engine_kwargs["connect_args"] = {
                    "connect_timeout": 10,
                    "read_timeout": 30,
                    "write_timeout": 30,
                }
            cls._engine = create_engine(cfg.url, **engine_kwargs)
        return cls._engine

    @classmethod
    def quote_col(cls, name: str) -> str:
        """MySQL 保留字列名加反引号。"""
        if cls.dialect_name() == "mysql":
            return f"`{name}`"
        return name

    @classmethod
    def reset_engine(cls) -> None:
        if cls._engine is not None:
            cls._engine.dispose()
            cls._engine = None

    @classmethod
    @contextmanager
    def connect(cls) -> Generator[Any, None, None]:
        engine = cls.get_engine()
        conn = engine.connect()
        trans = conn.begin()
        try:
            yield conn
            trans.commit()
        except Exception:
            trans.rollback()
            raise
        finally:
            conn.close()

    @classmethod
    def init_schema(cls) -> None:
        try:
            engine = cls.get_engine()
            metadata.create_all(engine)
            logger.info(
                "数据库表初始化完成 [%s]: %s",
                engine.dialect.name,
                engine.url.render_as_string(hide_password=True),
            )
        except SQLAlchemyError as exc:
            logger.error("数据库表初始化失败（应用仍可启动，请检查 .env）: %s", exc)

    @classmethod
    def check_connection(cls) -> bool:
        try:
            with cls.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as exc:
            logger.error("数据库连接失败: %s", exc)
            return False

    @classmethod
    def dialect_name(cls) -> str:
        return cls.get_engine().dialect.name

    @classmethod
    def upsert_kline_sql(cls) -> str:
        dialect = cls.dialect_name()
        if dialect == "postgresql":
            return """
                INSERT INTO kline_history
                (code, period, adjust_type, datetime, open, close, high, low,
                 volume, amount, change_pct, turnover_rate)
                VALUES
                (:code, :period, :adjust_type, :datetime, :open, :close, :high, :low,
                 :volume, :amount, :change_pct, :turnover_rate)
                ON CONFLICT (code, period, adjust_type, datetime)
                DO UPDATE SET
                    open=EXCLUDED.open, close=EXCLUDED.close, high=EXCLUDED.high,
                    low=EXCLUDED.low, volume=EXCLUDED.volume, amount=EXCLUDED.amount,
                    change_pct=EXCLUDED.change_pct, turnover_rate=EXCLUDED.turnover_rate
            """
        if dialect == "mysql":
            return """
                INSERT INTO kline_history
                (code, period, adjust_type, `datetime`, open, close, high, low,
                 volume, amount, change_pct, turnover_rate)
                VALUES
                (:code, :period, :adjust_type, :datetime, :open, :close, :high, :low,
                 :volume, :amount, :change_pct, :turnover_rate)
                ON DUPLICATE KEY UPDATE
                    open=VALUES(open), close=VALUES(close), high=VALUES(high),
                    low=VALUES(low), volume=VALUES(volume), amount=VALUES(amount),
                    change_pct=VALUES(change_pct), turnover_rate=VALUES(turnover_rate)
            """
        return """
            INSERT OR REPLACE INTO kline_history
            (code, period, adjust_type, datetime, open, close, high, low,
             volume, amount, change_pct, turnover_rate)
            VALUES
            (:code, :period, :adjust_type, :datetime, :open, :close, :high, :low,
             :volume, :amount, :change_pct, :turnover_rate)
        """

    @classmethod
    def upsert_quote_sql(cls) -> str:
        dialect = cls.dialect_name()
        if dialect == "postgresql":
            return """
                INSERT INTO quote_snapshot
                (code, name, price, open, high, low, pre_close, change_val, change_pct,
                 volume, amount, turnover_rate, volume_ratio, snapshot_time)
                VALUES
                (:code, :name, :price, :open, :high, :low, :pre_close, :change_val,
                 :change_pct, :volume, :amount, :turnover_rate, :volume_ratio, :snapshot_time)
                ON CONFLICT (code, snapshot_time) DO UPDATE SET
                    name=EXCLUDED.name, price=EXCLUDED.price, open=EXCLUDED.open,
                    high=EXCLUDED.high, low=EXCLUDED.low, pre_close=EXCLUDED.pre_close,
                    change_val=EXCLUDED.change_val, change_pct=EXCLUDED.change_pct,
                    volume=EXCLUDED.volume, amount=EXCLUDED.amount,
                    turnover_rate=EXCLUDED.turnover_rate, volume_ratio=EXCLUDED.volume_ratio
            """
        if dialect == "mysql":
            return """
                INSERT INTO quote_snapshot
                (code, name, price, open, high, low, pre_close, change_val, change_pct,
                 volume, amount, turnover_rate, volume_ratio, snapshot_time)
                VALUES
                (:code, :name, :price, :open, :high, :low, :pre_close, :change_val,
                 :change_pct, :volume, :amount, :turnover_rate, :volume_ratio, :snapshot_time)
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name), price=VALUES(price), open=VALUES(open),
                    high=VALUES(high), low=VALUES(low), pre_close=VALUES(pre_close),
                    change_val=VALUES(change_val), change_pct=VALUES(change_pct),
                    volume=VALUES(volume), amount=VALUES(amount),
                    turnover_rate=VALUES(turnover_rate), volume_ratio=VALUES(volume_ratio)
            """
        return """
            INSERT OR REPLACE INTO quote_snapshot
            (code, name, price, open, high, low, pre_close, change_val, change_pct,
             volume, amount, turnover_rate, volume_ratio, snapshot_time)
            VALUES
            (:code, :name, :price, :open, :high, :low, :pre_close, :change_val,
             :change_pct, :volume, :amount, :turnover_rate, :volume_ratio, :snapshot_time)
        """

    @classmethod
    def row_to_dict(cls, row: Any) -> dict:
        if row is None:
            return {}
        if hasattr(row, "_mapping"):
            return dict(row._mapping)
        return dict(row)

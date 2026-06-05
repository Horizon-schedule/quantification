"""
实时盯盘模块。
轮询获取标的行情，检测策略信号，触发告警。
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional

from config.settings import MonitorConfig, get_settings
from quant_platform.data.database import DatabaseManager
from quant_platform.data.repository import DataRepository
from quant_platform.monitor.alert import AlertManager
from quant_platform.strategy.base import BaseStrategy, SignalType
from quant_platform.utils.logger import get_logger

logger = get_logger("monitor.watcher")


class MarketWatcher:
    """
    实时盯盘监控器。

    功能：
    - 自定义盯盘池管理
    - 定时轮询行情
    - 策略信号实时检测
    - 多渠道告警推送
    """

    def __init__(
        self,
        repository: Optional[DataRepository] = None,
        alert: Optional[AlertManager] = None,
        config: Optional[MonitorConfig] = None,
    ):
        self.repo = repository or DataRepository()
        self.alert = alert or AlertManager()
        self.config = config or get_settings().monitor
        self.db = DatabaseManager()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._strategies: Dict[str, BaseStrategy] = {}
        self._callbacks: List[Callable] = []

    def add_strategy(self, code: str, strategy: BaseStrategy) -> None:
        """为指定标的绑定监控策略。"""
        self._strategies[code] = strategy

    def on_signal(self, callback: Callable) -> None:
        """注册信号回调函数。"""
        self._callbacks.append(callback)

    def add_watch(self, code: str, name: str = "") -> None:
        """添加盯盘标的。"""
        self.db.add_to_watchlist(code, name)
        logger.info("已添加盯盘: %s %s", code, name)

    def remove_watch(self, code: str) -> None:
        """移除盯盘标的。"""
        self.db.remove_from_watchlist(code)
        self._strategies.pop(code, None)

    def get_watchlist(self) -> List[dict]:
        """获取盯盘池。"""
        return self.db.get_watchlist()

    def start(self) -> None:
        """启动后台盯盘线程。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("盯盘监控已启动，轮询间隔 %.1f 秒", self.config.poll_interval)

    def stop(self) -> None:
        """停止盯盘。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("盯盘监控已停止")

    def _poll_loop(self) -> None:
        """轮询主循环。"""
        while self._running:
            try:
                self._check_all()
            except Exception as exc:
                logger.error("盯盘轮询异常: %s", exc)
            time.sleep(self.config.poll_interval)

    def _check_all(self) -> None:
        """检查所有盯盘标的。"""
        watchlist = self.db.get_watchlist()
        if not watchlist:
            return

        codes = [w["code"] for w in watchlist]
        quotes_df = self.repo.get_realtime_quotes(codes)

        for _, row in quotes_df.iterrows():
            code = row.get("code", "")
            price = row.get("price", 0)
            change_pct = row.get("change_pct", 0)
            name = row.get("name", code)

            # 策略信号检测
            strategy = self._strategies.get(code)
            if strategy:
                self._check_strategy_signal(code, name, strategy, price)

            # 通知回调
            for cb in self._callbacks:
                try:
                    cb(code, name, price, change_pct)
                except Exception as exc:
                    logger.error("回调异常: %s", exc)

    def _check_strategy_signal(
        self,
        code: str,
        name: str,
        strategy: BaseStrategy,
        current_price: float,
    ) -> None:
        """检测策略是否触发信号。"""
        df = self.repo.get_kline_df(code, limit=120)
        if df.empty:
            return

        signal_df = strategy.generate_signals(df)
        last = signal_df.iloc[-1]
        signal = last.get("signal", SignalType.HOLD.value)

        if signal in (SignalType.BUY.value, SignalType.SELL.value):
            reason = last.get("signal_reason", "")
            msg = (
                f"标的: {name}({code})\n"
                f"信号: {'买入' if signal == 'buy' else '卖出'}\n"
                f"价格: {current_price}\n"
                f"原因: {reason}"
            )
            self.alert.send(
                title=f"策略信号 - {strategy.name}",
                message=msg,
            )
            self.db.save_signal(
                {
                    "strategy_name": strategy.name,
                    "code": code,
                    "signal_type": signal,
                    "signal_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "price": current_price,
                    "reason": reason,
                }
            )
            logger.info("策略信号触发: %s %s %s", code, signal, reason)

    def poll_once(self) -> List[dict]:
        """手动执行一次轮询，返回最新行情。"""
        watchlist = self.db.get_watchlist()
        if not watchlist:
            return []
        codes = [w["code"] for w in watchlist]
        df = self.repo.get_realtime_quotes(codes)
        return df.to_dict("records") if not df.empty else []

"""
HTTP 客户端模块。
实现请求限频、异常重试、超时处理、接口熔断机制。
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from config.settings import ApiConfig, get_settings
from quant_platform.utils.logger import get_logger

logger = get_logger("api.client")


class CircuitBreakerOpen(Exception):
    """熔断器打开异常，暂停请求。"""

    pass


class HttpClient:
    """
    带限频、重试、熔断的 HTTP 客户端。

    合规说明：严格控制请求频率，防止对东方财富服务器造成压力。
    """

    def __init__(self, config: Optional[ApiConfig] = None):
        self.config = config or get_settings().api
        self._last_request_time: float = 0.0
        self._consecutive_failures: int = 0
        self._circuit_open_until: float = 0.0
        self._session = requests.Session()
        # 禁用系统代理，避免本地代理导致东方财富接口连接失败
        self._session.trust_env = False
        self._session.headers.update(
            {
                "User-Agent": self.config.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://quote.eastmoney.com/",
            }
        )

    def _check_circuit_breaker(self) -> None:
        """检查熔断器状态。"""
        now = time.time()
        if now < self._circuit_open_until:
            remaining = self._circuit_open_until - now
            raise CircuitBreakerOpen(
                f"接口熔断中，请等待 {remaining:.0f} 秒后重试"
            )
        # 熔断恢复后重置计数
        if self._consecutive_failures >= self.config.circuit_break_threshold:
            self._consecutive_failures = 0

    def _rate_limit(self) -> None:
        """请求限频，确保两次请求间隔不低于配置值。"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.request_interval:
            time.sleep(self.config.request_interval - elapsed)

    def _on_success(self) -> None:
        """请求成功回调，重置失败计数。"""
        self._consecutive_failures = 0

    def _on_failure(self) -> None:
        """请求失败回调，累计失败次数，触发熔断。"""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.config.circuit_break_threshold:
            self._circuit_open_until = (
                time.time() + self.config.circuit_break_recovery
            )
            logger.warning(
                "连续失败 %d 次，触发熔断，暂停请求 %.0f 秒",
                self._consecutive_failures,
                self.config.circuit_break_recovery,
            )

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        发起 GET 请求，带重试与限频。

        参数:
            url: 请求地址
            params: 查询参数

        返回:
            JSON 响应字典

        异常:
            CircuitBreakerOpen: 熔断器打开
            requests.RequestException: 网络异常
        """
        self._check_circuit_breaker()
        last_error: Optional[Exception] = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                self._rate_limit()
                response = self._session.get(
                    url,
                    params=params,
                    timeout=self.config.timeout,
                    **kwargs,
                )
                self._last_request_time = time.time()
                response.raise_for_status()
                data = response.json()
                self._on_success()
                return data
            except CircuitBreakerOpen:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "请求失败 [%d/%d] %s: %s",
                    attempt,
                    self.config.max_retries,
                    url,
                    exc,
                )
                self._on_failure()
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay * attempt)

        raise requests.RequestException(
            f"请求失败，已重试 {self.config.max_retries} 次: {last_error}"
        )

    def close(self) -> None:
        """关闭会话。"""
        self._session.close()

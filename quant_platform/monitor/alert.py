"""
多渠道告警模块。
支持：本地声音、邮件、企业微信 Webhook。
"""

from __future__ import annotations

import platform
import smtplib
import threading
from email.mime.text import MIMEText
from typing import List, Optional

import requests

from config.settings import AlertConfig, get_settings
from quant_platform.utils.logger import get_logger

logger = get_logger("monitor.alert")


class AlertManager:
    """告警管理器，统一调度各告警渠道。"""

    def __init__(self, config: Optional[AlertConfig] = None):
        self.config = config or get_settings().alert

    def send(
        self,
        title: str,
        message: str,
        channels: Optional[List[str]] = None,
    ) -> None:
        """
        发送告警。

        参数:
            title: 告警标题
            message: 告警内容
            channels: 指定渠道列表，None 表示全部已启用渠道
        """
        active = channels or self._active_channels()
        for ch in active:
            try:
                if ch == "sound":
                    self._send_sound()
                elif ch == "email":
                    self._send_email(title, message)
                elif ch == "wechat":
                    self._send_wechat(title, message)
            except Exception as exc:
                logger.error("告警发送失败 [%s]: %s", ch, exc)

    def _active_channels(self) -> List[str]:
        channels = []
        if self.config.sound_enabled:
            channels.append("sound")
        if self.config.email_enabled:
            channels.append("email")
        if self.config.wechat_enabled:
            channels.append("wechat")
        return channels

    def _send_sound(self) -> None:
        """本地声音告警（异步，不阻塞主线程）。"""
        def _beep():
            system = platform.system()
            try:
                if system == "Windows":
                    import winsound
                    winsound.Beep(1000, 500)
                    winsound.Beep(1500, 500)
                else:
                    print("\a")  # 终端蜂鸣
            except Exception:
                print("\a")

        threading.Thread(target=_beep, daemon=True).start()
        logger.info("声音告警已触发")

    def _send_email(self, title: str, message: str) -> None:
        """邮件告警。"""
        if not self.config.smtp_user or not self.config.email_to:
            logger.warning("邮件告警未配置")
            return

        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = f"[StopQuant] {title}"
        msg["From"] = self.config.smtp_user
        msg["To"] = ", ".join(self.config.email_to)

        with smtplib.SMTP_SSL(
            self.config.smtp_host, self.config.smtp_port
        ) as server:
            server.login(self.config.smtp_user, self.config.smtp_password)
            server.sendmail(
                self.config.smtp_user,
                self.config.email_to,
                msg.as_string(),
            )
        logger.info("邮件告警已发送: %s", title)

    def _send_wechat(self, title: str, message: str) -> None:
        """企业微信 Webhook 告警。"""
        if not self.config.wechat_webhook:
            logger.warning("企业微信 Webhook 未配置")
            return

        payload = {
            "msgtype": "text",
            "text": {"content": f"{title}\n{message}"},
        }
        resp = requests.post(
            self.config.wechat_webhook,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("企业微信告警已发送: %s", title)

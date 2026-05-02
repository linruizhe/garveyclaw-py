from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from telegram import Bot
from telegram.error import NetworkError, TelegramError, TimedOut

from hiclaw.config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_RESTART_DELAY_SECONDS,
)
from hiclaw.delivery import DeliveryRouter
from hiclaw.feishu_bot import FeishuBotAdapter, build_event_handler, build_feishu_client
from hiclaw.telegram_bot import TelegramMessageSender, build_application, run_polling_options

logger = logging.getLogger(__name__)


class ChannelStarter(Protocol):
    def start(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ChannelRegistration:
    name: str
    channel_key: str
    enabled: Callable[[], bool]
    register_sender: Callable[[DeliveryRouter], None]
    start: Callable[[], ChannelStarter | None]


class TelegramChannelRunner:
    def start(self) -> None:
        while True:
            try:
                app = build_application()
                app.run_polling(**run_polling_options())
            except KeyboardInterrupt:
                print("Bot stopped.")
                break
            except (TimedOut, NetworkError, TelegramError) as exc:
                logger.warning(
                    "Telegram polling failed: %s. Restarting in %s seconds...",
                    exc.__class__.__name__,
                    TELEGRAM_RESTART_DELAY_SECONDS,
                )
                time.sleep(TELEGRAM_RESTART_DELAY_SECONDS)
            except Exception:
                logger.exception(
                    "Bot crashed unexpectedly. Restarting in %s seconds...",
                    TELEGRAM_RESTART_DELAY_SECONDS,
                )
                time.sleep(TELEGRAM_RESTART_DELAY_SECONDS)


class FeishuChannelRunner:
    def __init__(self, client) -> None:
        self._client = client

    def start(self) -> None:
        import lark_oapi as lark

        event_handler = build_event_handler(self._client)
        ws_client = lark.ws.Client(
            app_id=FEISHU_APP_ID,
            app_secret=FEISHU_APP_SECRET,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
            auto_reconnect=True,
        )
        print("Feishu bot: WebSocket long connection started.")
        ws_client.start()


def _has_telegram_config() -> bool:
    return bool(TELEGRAM_BOT_TOKEN)


def _has_feishu_config() -> bool:
    return bool(FEISHU_APP_ID and FEISHU_APP_SECRET)


def _register_telegram_sender(router: DeliveryRouter) -> None:
    router.register_channel("telegram", TelegramMessageSender(Bot(token=TELEGRAM_BOT_TOKEN)))


def _register_feishu_sender(router: DeliveryRouter) -> None:
    router.register_channel("feishu", FeishuBotAdapter(build_feishu_client()))


def _build_telegram_runner() -> ChannelStarter:
    return TelegramChannelRunner()


def _build_feishu_runner() -> ChannelStarter:
    return FeishuChannelRunner(build_feishu_client())


def get_registered_channels() -> list[ChannelRegistration]:
    return [
        ChannelRegistration(
            name="Telegram",
            channel_key="telegram",
            enabled=_has_telegram_config,
            register_sender=_register_telegram_sender,
            start=_build_telegram_runner,
        ),
        ChannelRegistration(
            name="Feishu",
            channel_key="feishu",
            enabled=_has_feishu_config,
            register_sender=_register_feishu_sender,
            start=_build_feishu_runner,
        ),
    ]


def start_background_channel(name: str, starter: ChannelStarter) -> threading.Thread:
    thread = threading.Thread(target=starter.start, daemon=True, name=f"{name.lower()}-channel")
    thread.start()
    return thread

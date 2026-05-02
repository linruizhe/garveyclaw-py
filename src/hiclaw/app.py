import asyncio
import logging
import threading
import time

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
from hiclaw.scheduler import setup_scheduler
from hiclaw.scheduler_store import init_task_db
from hiclaw.session_store import init_session_db
from hiclaw.telegram_bot import TelegramMessageSender, build_application, run_polling_options

logger = logging.getLogger(__name__)


def _start_feishu_in_thread(client) -> None:
    """在独立线程中启动飞书 WebSocket 长连接。"""

    import lark_oapi as lark

    from hiclaw.config import FEISHU_APP_ID, FEISHU_APP_SECRET

    event_handler = build_event_handler(client)
    ws_client = lark.ws.Client(
        app_id=FEISHU_APP_ID,
        app_secret=FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
        auto_reconnect=True,
    )
    print("Feishu bot: WebSocket long connection started.")
    ws_client.start()


def _has_feishu_config() -> bool:
    return bool(FEISHU_APP_ID and FEISHU_APP_SECRET)


def _has_telegram_config() -> bool:
    return bool(TELEGRAM_BOT_TOKEN)


def _start_scheduler(router: DeliveryRouter) -> tuple[object, asyncio.AbstractEventLoop, threading.Thread]:
    ready = threading.Event()
    state: dict[str, object] = {}

    def run_scheduler_loop() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        scheduler = setup_scheduler(router, event_loop=loop)
        scheduler.start()
        state["loop"] = loop
        state["scheduler"] = scheduler
        ready.set()
        loop.run_forever()

    thread = threading.Thread(target=run_scheduler_loop, daemon=True, name="hiclaw-scheduler")
    thread.start()
    ready.wait()
    return state["scheduler"], state["loop"], thread


def _stop_scheduler(scheduler, loop: asyncio.AbstractEventLoop, thread: threading.Thread) -> None:
    def shutdown_scheduler() -> None:
        scheduler.shutdown(wait=False)
        loop.stop()

    if loop.is_running():
        loop.call_soon_threadsafe(shutdown_scheduler)
    thread.join(timeout=5)
    loop.close()


def _bootstrap_runtime_state() -> None:
    asyncio.run(init_task_db())
    asyncio.run(init_session_db())


def main() -> None:
    """统一入口：检测配置后启动所有已配置的通道。"""

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext._utils.networkloop").setLevel(logging.CRITICAL)
    logging.getLogger("telegram.ext._updater").setLevel(logging.CRITICAL)

    if not _has_feishu_config() and not _has_telegram_config():
        raise RuntimeError("Neither TELEGRAM_BOT_TOKEN nor FEISHU_APP_ID/FEISHU_APP_SECRET is configured.")

    channels = []
    if _has_telegram_config():
        channels.append("Telegram")
    if _has_feishu_config():
        channels.append("Feishu")
    print(f"Starting channels: {', '.join(channels)}")

    _bootstrap_runtime_state()
    router = DeliveryRouter()

    if _has_telegram_config():
        router.register("telegram", TelegramMessageSender(Bot(token=TELEGRAM_BOT_TOKEN)))

    feishu_client = None
    if _has_feishu_config():
        feishu_client = build_feishu_client()
        router.register("feishu", FeishuBotAdapter(feishu_client))

    scheduler, scheduler_loop, scheduler_thread = _start_scheduler(router)

    # 如果同时配置了飞书，在独立线程中启动，不阻塞 Telegram 主循环。
    if _has_feishu_config():
        feishu_thread = threading.Thread(target=_start_feishu_in_thread, args=(feishu_client,), daemon=True, name="feishu-ws")
        feishu_thread.start()
        # 等飞书连接建立，确保线程启动成功。
        time.sleep(2)

    try:
        # Telegram 在主线程中运行（阻塞）。
        if _has_telegram_config():
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
        else:
            # 只有飞书时，阻塞主线程防止退出。
            print("Telegram not configured. Waiting for Feishu...")
            try:
                feishu_thread.join()
            except KeyboardInterrupt:
                print("Bot stopped.")
    finally:
        _stop_scheduler(scheduler, scheduler_loop, scheduler_thread)


if __name__ == "__main__":
    main()

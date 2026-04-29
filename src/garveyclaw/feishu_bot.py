from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody, P2ImMessageReceiveV1

from garveyclaw.agent_client import AgentServiceError, run_agent
from garveyclaw.agent_response import AgentReply
from garveyclaw.config import (
    FEISHU_ALLOWED_CHAT_IDS,
    FEISHU_ALLOWED_OPEN_IDS,
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_REPLY_PROCESSING_MESSAGE,
    FEISHU_SESSION_SCOPE_PREFIX,
)

logger = logging.getLogger(__name__)


def parse_csv_set(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


ALLOWED_OPEN_IDS = parse_csv_set(FEISHU_ALLOWED_OPEN_IDS)
ALLOWED_CHAT_IDS = parse_csv_set(FEISHU_ALLOWED_CHAT_IDS)
SEEN_MESSAGE_IDS: set[str] = set()


@dataclass(slots=True)
class FeishuIncomingMessage:
    message_id: str
    chat_id: str
    sender_open_id: str
    chat_type: str
    text: str


@dataclass(slots=True)
class FeishuBotAdapter:
    client: lark.Client

    async def send_message(self, chat_id: str, text: str) -> None:
        await send_text_message(self.client, chat_id, text)


def ensure_feishu_config() -> None:
    if not FEISHU_APP_ID:
        raise RuntimeError("FEISHU_APP_ID is required when starting the Feishu bot.")
    if not FEISHU_APP_SECRET:
        raise RuntimeError("FEISHU_APP_SECRET is required when starting the Feishu bot.")


def build_feishu_client() -> lark.Client:
    ensure_feishu_config()
    return lark.Client.builder().app_id(FEISHU_APP_ID).app_secret(FEISHU_APP_SECRET).build()


def build_session_scope(message: FeishuIncomingMessage) -> str:
    if message.chat_type == "p2p":
        return f"{FEISHU_SESSION_SCOPE_PREFIX}:p2p:{message.sender_open_id}"
    return f"{FEISHU_SESSION_SCOPE_PREFIX}:chat:{message.chat_id}"


def is_allowed_message(message: FeishuIncomingMessage) -> bool:
    if not ALLOWED_OPEN_IDS and not ALLOWED_CHAT_IDS:
        return True
    return message.sender_open_id in ALLOWED_OPEN_IDS or message.chat_id in ALLOWED_CHAT_IDS


def is_duplicate(message_id: str) -> bool:
    if not message_id:
        return False
    if message_id in SEEN_MESSAGE_IDS:
        return True
    SEEN_MESSAGE_IDS.add(message_id)
    if len(SEEN_MESSAGE_IDS) > 1000:
        SEEN_MESSAGE_IDS.clear()
    return False


def extract_text_content(raw_content: str) -> str:
    try:
        content = json.loads(raw_content or "{}")
    except json.JSONDecodeError:
        return raw_content.strip()

    text = content.get("text")
    return text.strip() if isinstance(text, str) else ""


def get_nested_attr(obj: Any, path: str, default: Any = "") -> Any:
    current = obj
    for name in path.split("."):
        current = getattr(current, name, None)
        if current is None:
            return default
    return current


def parse_incoming_message(data: P2ImMessageReceiveV1) -> FeishuIncomingMessage | None:
    event = getattr(data, "event", None)
    message = getattr(event, "message", None)
    if message is None:
        return None

    message_type = getattr(message, "message_type", "")
    if message_type != "text":
        return None

    return FeishuIncomingMessage(
        message_id=getattr(message, "message_id", ""),
        chat_id=getattr(message, "chat_id", ""),
        sender_open_id=get_nested_attr(event, "sender.sender_id.open_id"),
        chat_type=getattr(message, "chat_type", ""),
        text=extract_text_content(getattr(message, "content", "")),
    )


async def send_text_message(client: lark.Client, chat_id: str, text: str) -> None:
    if not text.strip():
        return

    request = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("text")
            .content(json.dumps({"text": text}, ensure_ascii=False))
            .build()
        )
        .build()
    )

    response = await client.im.v1.message.acreate(request)
    if not response.success():
        raise RuntimeError(f"Feishu send message failed: code={response.code}, msg={response.msg}")


async def reply_agent_result(client: lark.Client, chat_id: str, reply: AgentReply) -> None:
    if reply.text.strip():
        await send_text_message(client, chat_id, reply.text)

    if reply.images:
        await send_text_message(client, chat_id, "当前飞书第一版通道暂不支持发送图片结果，请先在 Telegram 或 TUI 通道查看图片。")


async def handle_message(client: lark.Client, incoming: FeishuIncomingMessage) -> None:
    if is_duplicate(incoming.message_id):
        logger.info("Skip duplicate Feishu message: %s", incoming.message_id)
        return

    if not incoming.text:
        return

    if not is_allowed_message(incoming):
        logger.info("Skip unauthorized Feishu message: sender=%s chat=%s", incoming.sender_open_id, incoming.chat_id)
        return

    if FEISHU_REPLY_PROCESSING_MESSAGE:
        await send_text_message(client, incoming.chat_id, "收到，正在处理...")

    bot = FeishuBotAdapter(client)
    try:
        reply = await run_agent(
            prompt=incoming.text,
            bot=bot,
            chat_id=incoming.chat_id,
            continue_session=True,
            record_text=f"[Feishu] {incoming.text}",
            session_scope=build_session_scope(incoming),
        )
        await reply_agent_result(client, incoming.chat_id, reply)
    except AgentServiceError as exc:
        await send_text_message(client, incoming.chat_id, f"抱歉，这次调用模型服务失败了：{exc}")
    except Exception as exc:
        logger.exception("Feishu message handling failed")
        await send_text_message(client, incoming.chat_id, f"抱歉，飞书通道处理失败了：{exc}")


def build_event_handler(client: lark.Client):
    def on_message(data: P2ImMessageReceiveV1) -> None:
        incoming = parse_incoming_message(data)
        if incoming is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(handle_message(client, incoming))
        else:
            loop.create_task(handle_message(client, incoming))

    return lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(on_message).build()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    client = build_feishu_client()
    event_handler = build_event_handler(client)
    ws_client = lark.ws.Client(
        app_id=FEISHU_APP_ID,
        app_secret=FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
        auto_reconnect=True,
    )
    print("Feishu bot is running with WebSocket long connection...")
    ws_client.start()


if __name__ == "__main__":
    main()

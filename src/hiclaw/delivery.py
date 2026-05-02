from __future__ import annotations

from typing import Protocol

from hiclaw.runtime_types import ConversationRef


class MessageSender(Protocol):
    async def send_text(self, target_id: str, text: str) -> None: ...


async def send_sender_text(sender: MessageSender, target_id: str | int, text: str) -> None:
    await sender.send_text(str(target_id), text)


class DeliveryRouter:
    def __init__(self) -> None:
        self._senders: dict[str, MessageSender] = {}

    def register(self, channel: str, sender: MessageSender) -> None:
        self._senders[channel] = sender

    def unregister(self, channel: str) -> None:
        self._senders.pop(channel, None)

    def has(self, channel: str) -> bool:
        return channel in self._senders

    def get(self, channel: str) -> MessageSender:
        sender = self._senders.get(channel)
        if sender is None:
            raise RuntimeError(f"No sender registered for channel: {channel}")
        return sender

    async def send_text(self, conversation: ConversationRef, text: str) -> None:
        await self.get(conversation.channel).send_text(conversation.target_id, text)

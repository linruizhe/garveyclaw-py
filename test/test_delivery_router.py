from hiclaw.delivery import DeliveryRouter
from hiclaw.runtime_types import ConversationRef


class StubSender:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[tuple[str, str]] = []

    async def send_text(self, target_id: str, text: str) -> None:
        self.sent.append((target_id, text))


def test_delivery_router_prefers_conversation_sender() -> None:
    router = DeliveryRouter()
    channel_sender = StubSender("channel")
    conversation_sender = StubSender("conversation")
    conversation = ConversationRef(channel="tui", target_id="tui:pid1", session_scope="tui:pid1")

    router.register_channel("tui", channel_sender)
    router.register_conversation(conversation, conversation_sender)

    assert router.get(conversation) is conversation_sender


def test_delivery_router_falls_back_to_channel_sender() -> None:
    router = DeliveryRouter()
    channel_sender = StubSender("channel")
    conversation = ConversationRef(channel="telegram", target_id="1001", session_scope="telegram:chat:1001")

    router.register_channel("telegram", channel_sender)

    assert router.get(conversation) is channel_sender
    assert router.has(conversation) is True


def test_delivery_router_has_exact_tui_conversation_only() -> None:
    router = DeliveryRouter()
    sender = StubSender("conversation")
    current = ConversationRef(channel="tui", target_id="tui:pid1", session_scope="tui:pid1")
    other = ConversationRef(channel="tui", target_id="tui:pid2", session_scope="tui:pid2")

    router.register_conversation(current, sender)

    assert router.has(current) is True
    assert router.has(other) is False


def test_delivery_router_owns_only_registered_routes() -> None:
    router = DeliveryRouter()
    current = ConversationRef(channel="tui", target_id="tui:pid1", session_scope="tui:pid1")
    other = ConversationRef(channel="feishu", target_id="oc_123", session_scope="feishu:chat:oc_123")
    router.register_conversation(current, StubSender("conversation"))

    assert router.owns(current) is True
    assert router.owns(other) is False

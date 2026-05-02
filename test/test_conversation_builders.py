from types import SimpleNamespace

from hiclaw.agent_client import build_feishu_conversation, build_telegram_conversation, build_tui_conversation


def test_build_telegram_conversation_uses_chat_scope() -> None:
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=12345),
        effective_user=SimpleNamespace(id=999),
    )

    conversation = build_telegram_conversation(update)

    assert conversation.channel == "telegram"
    assert conversation.target_id == "12345"
    assert conversation.session_scope == "telegram:chat:12345"
    assert conversation.user_id == "999"


def test_build_feishu_conversation_preserves_scope() -> None:
    incoming = SimpleNamespace(chat_id="oc_abc", sender_open_id="ou_user")

    conversation = build_feishu_conversation(incoming, "feishu:chat:oc_abc")

    assert conversation.channel == "feishu"
    assert conversation.target_id == "oc_abc"
    assert conversation.session_scope == "feishu:chat:oc_abc"
    assert conversation.user_id == "ou_user"


def test_build_tui_conversation_uses_instance_scope() -> None:
    conversation = build_tui_conversation("tui:pid1234_abcd")

    assert conversation.channel == "tui"
    assert conversation.target_id == "tui:pid1234_abcd"
    assert conversation.session_scope == "tui:pid1234_abcd"

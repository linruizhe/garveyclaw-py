from hiclaw.channel_registry import ChannelRegistration, get_registered_channels


def test_channel_registry_exposes_telegram_and_feishu_entries() -> None:
    registrations = get_registered_channels()

    assert [registration.channel_key for registration in registrations] == ["telegram", "feishu"]
    assert all(isinstance(registration, ChannelRegistration) for registration in registrations)


def test_channel_registry_entries_expose_required_hooks() -> None:
    registrations = get_registered_channels()

    for registration in registrations:
        assert callable(registration.enabled)
        assert callable(registration.register_sender)
        assert callable(registration.start)

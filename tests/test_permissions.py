from types import SimpleNamespace

from app.bot.permissions import deny_if_not_developer
from app.config.settings import Settings


def test_developer_permission_check():
    settings = Settings(developer_user_ids=[10, 20])
    allowed = SimpleNamespace(user=SimpleNamespace(id=10), guild=None)
    denied = SimpleNamespace(user=SimpleNamespace(id=99), guild=None)
    assert deny_if_not_developer(allowed, settings) is None
    assert deny_if_not_developer(denied, settings) is not None


def test_builtin_owner_id_is_always_a_developer():
    settings = Settings()
    interaction = SimpleNamespace(user=SimpleNamespace(id=733202645002485772), guild=None)
    assert settings.is_developer(733202645002485772) is True
    assert deny_if_not_developer(interaction, settings) is None


def test_server_owner_and_admin_can_manage_training_examples():
    settings = Settings()
    owner = SimpleNamespace(
        user=SimpleNamespace(id=42, guild_permissions=SimpleNamespace(administrator=False, manage_guild=False)),
        guild=SimpleNamespace(owner_id=42),
    )
    admin = SimpleNamespace(
        user=SimpleNamespace(id=99, guild_permissions=SimpleNamespace(administrator=True, manage_guild=False)),
        guild=SimpleNamespace(owner_id=42),
    )
    manager = SimpleNamespace(
        user=SimpleNamespace(id=100, guild_permissions=SimpleNamespace(administrator=False, manage_guild=True)),
        guild=SimpleNamespace(owner_id=42),
    )
    assert deny_if_not_developer(owner, settings) is None
    assert deny_if_not_developer(admin, settings) is None
    assert deny_if_not_developer(manager, settings) is None

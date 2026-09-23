from types import SimpleNamespace

from app.bot.permissions import deny_if_not_developer
from app.config.settings import Settings


def test_developer_permission_check():
    settings = Settings(developer_user_ids=[10, 20])
    allowed = SimpleNamespace(user=SimpleNamespace(id=10))
    denied = SimpleNamespace(user=SimpleNamespace(id=99))
    assert deny_if_not_developer(allowed, settings) is None
    assert deny_if_not_developer(denied, settings) is not None

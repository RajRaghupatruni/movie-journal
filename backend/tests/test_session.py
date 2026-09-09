from types import SimpleNamespace
from unittest.mock import MagicMock

from app.db.session import get_db


def test_session_closes_on_error_without_implicit_commit():
    factory = MagicMock()
    session = factory.return_value.__enter__.return_value
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(session_factory=factory)))
    dependency = get_db(request)
    assert next(dependency) is session
    dependency.close()
    factory.return_value.__exit__.assert_called_once()
    session.commit.assert_not_called()

def test_main_module_imports():
    from inbox_bot import main
    assert callable(main.main)


from unittest.mock import MagicMock
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from inbox_bot.main import register_digest_job


def _settings(enabled: bool):
    return SimpleNamespace(
        digest_enabled=enabled, digest_hour=7, digest_minute=30,
        timezone="Asia/Taipei",
    )


def test_register_digest_job_adds_when_enabled():
    sched = MagicMock()
    assert register_digest_job(sched, _settings(True)) is True
    sched.add_job.assert_called_once()


def test_register_digest_job_skips_when_disabled():
    sched = MagicMock()
    assert register_digest_job(sched, _settings(False)) is False
    sched.add_job.assert_not_called()

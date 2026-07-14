"""config 단위 테스트 — 보안 기본값 검증 포함"""

from src.config import Settings, _parse_id_list


def make_settings(**kwargs) -> Settings:
    # .env 파일의 영향을 받지 않는 순수 기본값
    return Settings(_env_file=None, **kwargs)


def test_api_binds_loopback_by_default():
    settings = make_settings()
    assert settings.api_host == "127.0.0.1"


def test_default_model_is_qwen():
    settings = make_settings()
    assert settings.ollama_model.startswith("qwen3.5")


def test_concurrency_and_threshold_defaults():
    settings = make_settings()
    assert settings.max_concurrent_queries >= 1
    assert 0.0 < settings.min_dense_score < 1.0
    assert settings.query_timeout_seconds > 0


def test_guild_id_parsing():
    assert _parse_id_list("") == []
    assert _parse_id_list("123") == [123]
    assert _parse_id_list("123, 456 ,789") == [123, 456, 789]

    settings = make_settings(discord_guild_ids="111,222")
    assert settings.discord_guild_id_list == [111, 222]
    assert settings.discord_channel_id_list == []

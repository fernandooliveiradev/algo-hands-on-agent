from algo_hands_on.config import Settings


def test_defaults_match_prd() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        deepseek_api_key="test",
    )
    assert settings.history_runs == 3
    assert settings.session_summaries is True
    assert settings.memory is True
    assert settings.stream is True
    assert settings.stream_events is True
    assert settings.debug is False

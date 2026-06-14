from algo_hands_on.agent_factory import build_agent, build_parser_agent
from algo_hands_on.config import Settings


def test_tutor_agent_streams_plain_text(tmp_path) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        deepseek_api_key="test",
        db_path=tmp_path / "aho.db",
        stream=True,
    )

    agent = build_agent(settings)

    assert agent.output_schema is None
    assert agent.parser_model is None


def test_parser_agent_uses_direct_json_mode(tmp_path) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        deepseek_api_key="test",
        db_path=tmp_path / "aho.db",
    )

    agent = build_parser_agent(settings)

    assert agent.output_schema is not None
    assert agent.use_json_mode is True

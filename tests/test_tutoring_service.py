from types import SimpleNamespace

from algo_hands_on.config import Settings
from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.schemas import TutorTurn
from algo_hands_on.services import tutoring


class FakeStreamingAgent:
    def run(self, input_message, **kwargs):
        assert input_message == "oi"
        assert kwargs["stream"] is True
        assert kwargs["stream_events"] is True
        assert kwargs["yield_run_output"] is True
        yield SimpleNamespace(event="RunContent", content="Oi, ", run_id="run-test")
        yield SimpleNamespace(event="RunIntermediateContent", content="Fernando.", run_id="run-test")


class FakeParserAgent:
    def run(self, input_message, **kwargs):
        assert "Resposta do tutor:\nOi, Fernando." in input_message
        assert kwargs["add_dependencies_to_context"] is True
        return SimpleNamespace(content=TutorTurn(message_markdown="texto parser", module_id=0))


def test_streaming_turn_uses_agno_intermediate_events(
    monkeypatch, repository: ProgressRepository, tmp_path
) -> None:
    monkeypatch.setattr(tutoring, "build_agent", lambda settings: FakeStreamingAgent())
    monkeypatch.setattr(tutoring, "build_parser_agent", lambda settings: FakeParserAgent())
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        deepseek_api_key="test",
        db_path=tmp_path / "aho.db",
    )
    service = tutoring.TutoringService(settings, repository)

    events = list(
        service.run_turn_stream(
            student_id="fernando",
            session_id="sessao-stream",
            message="oi",
        )
    )

    assert events[:2] == [
        {"type": "content", "text": "Oi, "},
        {"type": "content", "text": "Fernando."},
    ]
    assert events[-1]["type"] == "final"
    assert events[-1]["turn"].message_markdown == "Oi, Fernando."

    stored_events = repository.export_student("fernando")["events"]
    tutor_turns = [event for event in stored_events if event["event_type"] == "tutor_turn"]
    assert len(tutor_turns) == 1

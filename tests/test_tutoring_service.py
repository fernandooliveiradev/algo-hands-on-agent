from collections.abc import Iterable
from types import SimpleNamespace

from algo_hands_on.config import Settings
from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.schemas import TutorTurn
from algo_hands_on.services import tutoring


class FakeAgent:
    def __init__(self, *, chunks: Iterable[str] = (), plain: str | None = None) -> None:
        self.chunks = list(chunks)
        self.plain = plain

    def run(self, input_message, **kwargs):
        assert input_message == "oi"
        if self.plain is not None:
            return SimpleNamespace(content=self.plain, run_id="run-plain")

        return self._stream(**kwargs)

    def _stream(self, **kwargs):
        assert kwargs["stream"] is True
        assert kwargs["stream_events"] is True
        assert kwargs["yield_run_output"] is True
        for chunk in self.chunks:
            yield SimpleNamespace(event="RunContent", content=chunk, run_id="run-stream")


class FakeParser:
    def __init__(self, *, fail: bool = False, content: object | None = None) -> None:
        self.fail = fail
        self.content = content

    def run(self, input_message, **kwargs):
        if self.fail:
            raise RuntimeError("parser caiu")
        assert "Resposta do tutor:\n" in input_message
        assert kwargs["add_dependencies_to_context"] is True
        content = self.content
        if content is None:
            content = TutorTurn(message_markdown="texto parser", module_id=0)
        return SimpleNamespace(content=content)


def make_service(
    monkeypatch,
    repository: ProgressRepository,
    tmp_path,
    agent: FakeAgent,
    parser: FakeParser | None = None,
) -> tutoring.TutoringService:
    monkeypatch.setattr(tutoring, "build_agent", lambda settings: agent)
    monkeypatch.setattr(tutoring, "build_parser_agent", lambda settings: parser or FakeParser())
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        deepseek_api_key="test",
        db_path=tmp_path / "aho.db",
    )
    return tutoring.TutoringService(settings, repository)


def stream_text(events: list[dict]) -> str:
    return "".join(event["text"] for event in events if event["type"] == "content")


def test_streaming_turn_uses_agno_events_and_persists(
    monkeypatch,
    repository: ProgressRepository,
    tmp_path,
) -> None:
    service = make_service(
        monkeypatch,
        repository,
        tmp_path,
        FakeAgent(chunks=["Oi, ", "Fernando."]),
    )

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
    tutor_turns = [
        event
        for event in repository.export_student("fernando")["events"]
        if event["event_type"] == "tutor_turn"
    ]
    assert len(tutor_turns) == 1


def test_non_streaming_turn_falls_back_when_parser_fails(
    monkeypatch,
    repository: ProgressRepository,
    tmp_path,
) -> None:
    service = make_service(
        monkeypatch,
        repository,
        tmp_path,
        FakeAgent(plain="Resposta bruta."),
        FakeParser(fail=True),
    )

    turn = service.run_turn(
        student_id="fernando",
        session_id="sessao",
        message="oi",
    )

    assert turn.message_markdown == "Resposta bruta."
    assert turn.module_id == 0


def test_streaming_turn_sanitizes_internal_narration_and_emojis(
    monkeypatch,
    repository: ProgressRepository,
    tmp_path,
) -> None:
    service = make_service(
        monkeypatch,
        repository,
        tmp_path,
        FakeAgent(
            chunks=[
                "Vou buscar as orientações para este momento inicial.",
                    "Perfeito! Vamos começar.\U0001f680\U0001f447",
                ]
            ),
        )

    events = list(
        service.run_turn_stream(
            student_id="fernando",
            session_id="sessao-stream",
            message="oi",
        )
    )

    assert stream_text(events) == "Perfeito! Vamos começar."
    assert tutoring.TutoringService._sanitize_tutor_text(
        "Vou buscar as orientações para este momento inicial.\n"
        "Olá! Vamos praticar agora. \U0001f680\U0001f447"
    ) == "Olá! Vamos praticar agora."


def test_streaming_turn_handles_cumulative_content(
    monkeypatch,
    repository: ProgressRepository,
    tmp_path,
) -> None:
    service = make_service(
        monkeypatch,
        repository,
        tmp_path,
        FakeAgent(chunks=["Oi", "Oi, Fernando.", "Oi, Fernando."]),
    )

    events = list(
        service.run_turn_stream(
            student_id="fernando",
            session_id="sessao-stream",
            message="oi",
        )
    )

    assert events[:2] == [
        {"type": "content", "text": "Oi"},
        {"type": "content", "text": ", Fernando."},
    ]
    assert events[-1]["turn"].message_markdown == "Oi, Fernando."


def test_parse_turn_preserves_valid_module_zero(
    monkeypatch,
    repository: ProgressRepository,
    tmp_path,
) -> None:
    service = make_service(monkeypatch, repository, tmp_path, FakeAgent(chunks=["Texto"]))
    repository.create_student("fernando", "Fernando")
    repository.set_current_module("fernando", 2, reason="test")

    turn = service._parse_turn(
        student_id="fernando",
        session_id="sessao",
        message="oi",
        tutor_text="Texto",
        snapshot=repository.get_progress_snapshot("fernando"),
    )

    assert turn.module_id == 0


def test_parse_turn_accepts_json_string_content(
    monkeypatch,
    repository: ProgressRepository,
    tmp_path,
) -> None:
    turn_data = TutorTurn(message_markdown="texto parser", module_id=0)
    service = make_service(
        monkeypatch,
        repository,
        tmp_path,
        FakeAgent(chunks=["Texto"]),
        FakeParser(content=turn_data.model_dump_json()),
    )
    repository.create_student("fernando", "Fernando")

    turn = service._parse_turn(
        student_id="fernando",
        session_id="sessao",
        message="oi",
        tutor_text="Texto",
        snapshot=repository.get_progress_snapshot("fernando"),
    )

    assert turn.message_markdown == "Texto"
    assert turn.module_id == 0

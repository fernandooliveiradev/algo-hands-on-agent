from pathlib import Path

from agno.skills import LocalSkills, Skills

from algo_hands_on.agent_factory import BASE_INSTRUCTIONS, build_agent, build_parser_agent
from algo_hands_on.chat_core import (
    ChatContext,
    handle_chat_command,
    prepare_agent_message,
    turn_history_text,
)
from algo_hands_on.config import Settings
from algo_hands_on.curriculum import MODULES, get_module, next_module_id
from algo_hands_on.db.agno_tables import AGNO_TABLE_NAMES
from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.hooks import post_run_validate, pre_run_context
from algo_hands_on.schemas import (
    AttemptResult,
    EvaluationResult,
    EvidenceKind,
    ExerciseSpec,
    TutorTurn,
)


def test_settings_curriculum_and_schema_defaults() -> None:
    settings = Settings(**{"_env_file": None, "deepseek_api_key": "test"})
    turn = TutorTurn(message_markdown="Continue.", module_id=1, competency_key="Teste De Mesa")

    assert settings.history_runs == 3
    assert settings.session_summaries is True
    assert settings.memory is True
    assert settings.stream is True
    assert [module.id for module in MODULES] == list(range(17))
    assert get_module(6).slug == "textos-colecoes"
    assert next_module_id(16) is None
    assert turn.competency_key == "teste-de-mesa"


def test_agent_contracts(tmp_path) -> None:
    settings = Settings(
        **{
            "_env_file": None,
            "deepseek_api_key": "test",
            "db_path": tmp_path / "aho.db",
            "stream": True,
        },
    )
    tutor = build_agent(settings)
    parser = build_parser_agent(settings)
    instructions = "\n".join(BASE_INSTRUCTIONS).lower()

    assert tutor.output_schema is None
    assert tutor.parser_model is None
    assert tutor.db is not None
    assert tutor.db.session_table_name == AGNO_TABLE_NAMES["session_table"]
    assert tutor.db.schedules_table_name == AGNO_TABLE_NAMES["schedules_table"]
    assert parser.output_schema is not None
    assert parser.use_json_mode is True
    assert "nunca narre ações internas" in instructions
    assert "não use tom de marketing" in instructions
    assert "microatividade diagnóstica" in instructions


def test_hooks_and_skills_are_safe() -> None:
    pre_run_context(user_id="test", session_id="s1")
    pre_run_context(
        user_id="test",
        session_id="s1",
        dependencies={"student_progress": {"current": {"current_module": 5}}},
    )

    turn = TutorTurn(
        message_markdown="ok",
        module_id=1,
        evaluation=EvaluationResult(
            result=AttemptResult.CORRECT,
            score=0.9,
            used_hint=False,
            module_id=1,
            competency_key="teste",
            evidence_kind=EvidenceKind.DIRECT,
        ),
    )
    post_run_validate(content=turn)
    post_run_validate(content=turn.model_dump())
    post_run_validate()

    root = Path(__file__).resolve().parents[1]
    Skills(loaders=[LocalSkills(str(root / "skills"))])


def test_chat_core_commands_and_no_duplicate_exercise(
    repository: ProgressRepository,
    tmp_path,
) -> None:
    settings = Settings(
        **{
            "_env_file": None,
            "deepseek_api_key": "test",
            "db_path": tmp_path / "aho.db",
        },
    )
    student = repository.create_student("fernando", "Fernando")
    context = ChatContext(
        settings=settings,
        repository=repository,
        student=student,
        student_id="fernando",
        session_id="sessao",
        snapshot=repository.get_progress_snapshot("fernando"),
    )
    command = handle_chat_command(context, "/progresso")
    agent_message = prepare_agent_message("/exercicio")

    statement = (
        'Imagine a seguinte situação:\n\n'
        '> **"Você chegou em casa e precisa preparar o jantar."**\n\n'
        "Como você descreveria o objetivo dessa tarefa?"
    )
    turn = TutorTurn(
        message_markdown=f"Vamos treinar.\n\n{statement}",
        module_id=1,
        exercise=ExerciseSpec(
            title="Objetivo da tarefa de jantar",
            statement=statement,
            requires_code=False,
        ),
    )
    rendered = turn_history_text(turn)

    assert command is not None
    assert command.action == "output"
    assert "Módulo: 0" in command.text
    assert agent_message is not None
    assert "novo exercício prático" in agent_message
    assert rendered.count("Você chegou em casa") == 1
    assert "Exercício: Objetivo da tarefa de jantar" not in rendered

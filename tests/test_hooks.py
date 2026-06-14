from algo_hands_on.hooks import post_run_validate, pre_run_context
from algo_hands_on.schemas import AttemptResult, EvaluationResult, EvidenceKind, TutorTurn


def test_pre_hook_no_deps_does_not_crash() -> None:
    pre_run_context(user_id="test", session_id="s1")


def test_pre_hook_with_progress_deps() -> None:
    pre_run_context(
        user_id="test",
        session_id="s1",
        dependencies={"student_progress": {"current": {"current_module": 5}}},
    )


def test_post_hook_with_valid_turn() -> None:
    turn = TutorTurn(message_markdown="ok", module_id=0)
    post_run_validate(content=turn)


def test_post_hook_with_dict_content() -> None:
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
    post_run_validate(content=turn.model_dump())


def test_post_hook_empty_content_does_not_crash() -> None:
    post_run_validate()

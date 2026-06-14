from algo_hands_on.hooks import post_run_validate, pre_run_context
from algo_hands_on.schemas import AttemptResult, EvaluationResult, EvidenceKind, TutorTurn


class _FakeContext:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_pre_hook_no_deps_does_not_crash() -> None:
    ctx = _FakeContext(user_id="test", session_id="s1", dependencies={})
    pre_run_context(ctx)


def test_pre_hook_with_progress_deps() -> None:
    ctx = _FakeContext(
        user_id="test",
        session_id="s1",
        dependencies={"student_progress": {"current": {"current_module": 5}}},
    )
    pre_run_context(ctx)


def test_post_hook_with_valid_turn() -> None:
    turn = TutorTurn(message_markdown="ok", module_id=0)
    ctx = _FakeContext(content=turn)
    post_run_validate(ctx)


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
    ctx = _FakeContext(content=turn.model_dump())
    post_run_validate(ctx)


def test_post_hook_empty_content_does_not_crash() -> None:
    ctx = _FakeContext(content=None)
    post_run_validate(ctx)

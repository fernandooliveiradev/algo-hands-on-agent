from collections.abc import Callable
from pathlib import Path

import pytest

from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.schemas import AttemptResult, EvaluationResult, EvidenceKind


@pytest.fixture
def repository(tmp_path: Path) -> ProgressRepository:
    repo = ProgressRepository(tmp_path / "aho.db")
    repo.initialize()
    return repo


@pytest.fixture
def make_evaluation() -> Callable[..., EvaluationResult]:
    def factory(
        kind: EvidenceKind,
        *,
        module_id: int = 0,
        result: AttemptResult = AttemptResult.CORRECT,
        used_hint: bool = False,
        score: float = 0.9,
    ) -> EvaluationResult:
        return EvaluationResult(
            result=result,
            score=score,
            used_hint=used_hint,
            module_id=module_id,
            competency_key="diagnostico-inicial",
            evidence_kind=kind,
            concepts_demonstrated=["raciocinio"],
            feedback="Bom trabalho.",
        )

    return factory

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TurnType(StrEnum):
    DIAGNOSIS = "diagnosis"
    EXPLANATION = "explanation"
    GUIDED_PRACTICE = "guided_practice"
    EXERCISE = "exercise"
    EVALUATION = "evaluation"
    REMEDIATION = "remediation"
    CHECKPOINT = "checkpoint"
    MODULE_COMPLETION = "module_completion"
    GENERAL = "general"


class AttemptResult(StrEnum):
    CORRECT = "correct"
    CORRECT_WITH_HINT = "correct_with_hint"
    INCORRECT = "incorrect"
    INCOMPLETE = "incomplete"
    NOT_EVALUATED = "not_evaluated"


class EvidenceKind(StrEnum):
    DIRECT = "direct_application"
    INDEPENDENT = "independent_application"
    INTEGRATION = "integration"
    DIAGNOSIS = "diagnosis"
    EXPLANATION_TRANSFER = "explanation_transfer"

    @property
    def display_label(self) -> str:
        labels: dict[str, str] = {
            "direct_application": "Aplicação direta",
            "independent_application": "Aplicação independente",
            "integration": "Integração",
            "diagnosis": "Diagnóstico",
            "explanation_transfer": "Explicação/transferência",
        }
        return labels[self.value]


EVIDENCE_DISPLAY_LABELS: dict[str, str] = {k.value: k.display_label for k in EvidenceKind}


class ExerciseSpec(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    statement: str = Field(min_length=10, description="Enunciado completo em Markdown.")
    expected_concepts: list[str] = Field(default_factory=list, max_length=8)
    constraints: list[str] = Field(default_factory=list, max_length=8)
    requires_code: bool = True
    evidence_kind: EvidenceKind | None = None


class EvaluationResult(BaseModel):
    result: AttemptResult
    score: float = Field(ge=0.0, le=1.0)
    used_hint: bool = False
    module_id: int = Field(ge=0, le=16)
    competency_key: str = Field(min_length=1, max_length=120)
    evidence_kind: EvidenceKind | None = None
    concepts_demonstrated: list[str] = Field(default_factory=list, max_length=10)
    concepts_to_review: list[str] = Field(default_factory=list, max_length=10)
    feedback: str = Field(default="", max_length=2000)


class TutorTurn(BaseModel):
    message_markdown: str = Field(min_length=1, description="Resposta pedagógica exibida ao aluno.")
    turn_type: TurnType = TurnType.GENERAL
    module_id: int = Field(ge=0, le=16)
    competency_key: str | None = Field(default=None, max_length=120)
    exercise: ExerciseSpec | None = None
    evaluation: EvaluationResult | None = None
    suggested_next_action: Literal[
        "continue",
        "attempt_exercise",
        "explain_reasoning",
        "remediate",
        "checkpoint",
        "module_ready",
    ] = "continue"

    @field_validator("competency_key")
    @classmethod
    def normalize_competency(cls, value: str | None) -> str | None:
        return value.strip().lower().replace(" ", "-") if value else None


class StudentCreate(BaseModel):
    student_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{3,64}$")
    display_name: str = Field(min_length=2, max_length=100)


class TutorRequest(BaseModel):
    student_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{3,64}$")
    session_id: str = Field(pattern=r"^[a-zA-Z0-9_.:-]{3,128}$")
    message: str = Field(min_length=1, max_length=20000)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "algo-hands-on"
    version: str

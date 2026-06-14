from __future__ import annotations

import logging

from agno.os import AgentOS
from fastapi import FastAPI, HTTPException, status

from algo_hands_on import __version__
from algo_hands_on.agent_factory import build_agent
from algo_hands_on.config import get_settings
from algo_hands_on.db.repository import ProgressRepository, StudentNotFoundError
from algo_hands_on.schemas import HealthResponse, StudentCreate, TutorRequest, TutorTurn
from algo_hands_on.services.tutoring import TutoringService

settings = get_settings()
repository = ProgressRepository(settings.db_path)
repository.initialize()
service = TutoringService(settings, repository)
logger = logging.getLogger(__name__)

base_app = FastAPI(
    title="Algo Hands-On API",
    version=__version__,
    description="API do tutor adaptativo de pensamento computacional e Python.",
)


@base_app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(version=__version__)


@base_app.post("/api/v1/students", status_code=status.HTTP_201_CREATED, tags=["students"])
def create_student(payload: StudentCreate) -> dict:
    return repository.create_student(payload.student_id, payload.display_name)


@base_app.get("/api/v1/students/{student_id}/progress", tags=["students"])
def get_progress(student_id: str) -> dict:
    try:
        return repository.get_progress_snapshot(student_id)
    except StudentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Aluno não encontrado") from exc


@base_app.post("/api/v1/tutor/turn", response_model=TutorTurn, tags=["tutor"])
def tutor_turn(payload: TutorRequest) -> TutorTurn:
    try:
        return service.run_turn(
            student_id=payload.student_id,
            session_id=payload.session_id,
            message=payload.message,
        )
    except StudentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Aluno não encontrado") from exc
    except Exception as exc:
        logger.exception("Falha ao executar tutor")
        detail = f"Falha ao executar o tutor: {exc}" if settings.debug else "Falha ao executar o tutor."
        raise HTTPException(status_code=502, detail=detail) from exc


@base_app.post("/api/v1/students/{student_id}/reset", tags=["students"])
def reset_progress(student_id: str) -> dict:
    try:
        repository.reset_student(student_id)
        return repository.get_progress_snapshot(student_id)
    except StudentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Aluno não encontrado") from exc


agent_os = AgentOS(
    id="algo-hands-on-os",
    name="Algo Hands-On AgentOS",
    description="AgentOS do tutor Algo Hands-On.",
    agents=[build_agent(settings)],
    db=None,
    base_app=base_app,
    on_route_conflict="preserve_base_app",
    cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    telemetry=settings.telemetry,
)

app = agent_os.get_app()

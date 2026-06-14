from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from algo_hands_on import __version__
from algo_hands_on.curriculum import LAST_MODULE_ID, MODULES, get_module
from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.schemas import EVIDENCE_DISPLAY_LABELS, TutorTurn

UNDEFINED_COMPETENCY = "não definida"

INDEPENDENCE_LABELS: dict[str, str] = {
    "observer": "Observador",
    "guided": "Guiado",
    "independent": "Independente",
    "transfer": "Transferência",
}

COMMANDS_HELP: list[tuple[str, str]] = [
    ("/progresso", "Progresso curricular"),
    ("/checkpoint", "Evidências do módulo atual"),
    ("/modulos", "Listar todos os módulos"),
    ("/historico", "Últimas tentativas e eventos"),
    ("/sessoes", "Listar/continuar sessões"),
    ("/continuar", "Continuar no módulo atual"),
    ("/revisar", "Revisar conteúdo anterior"),
    ("/exercicio", "Solicitar novo exercício"),
    ("/dica", "Pedir uma dica"),
    ("/exemplo", "Pedir um exemplo"),
    ("/config", "Ver preferências"),
    ("/limpar", "Limpar a tela"),
    ("/pular", "Avançar para próximo módulo"),
    ("/sair", "Encerrar sessão"),
]

CONTEXTUAL_PREFIXES: dict[str, str] = {
    "/continuar": "Quero continuar os estudos no módulo atual. Me guie no próximo passo.",
    "/revisar": "Preciso revisar o conteúdo do módulo atual ou anterior. Me ajude a revisar.",
    "/exercicio": "Me dê um novo exercício prático para resolver agora.",
    "/dica": "Preciso de uma dica para resolver o exercício atual, sem revelar a resposta completa.",
    "/exemplo": "Me mostre um exemplo prático relacionado ao conteúdo atual.",
}

LOCAL_COMMANDS = {
    "/ajuda",
    "/checkpoint",
    "/config",
    "/historico",
    "/limpar",
    "/modulos",
    "/progresso",
    "/pular",
    "/sair",
    "/exit",
    "/quit",
    "/sessoes",
}


@dataclass(slots=True)
class ChatContext:
    settings: Any
    repository: ProgressRepository
    student: dict
    student_id: str
    session_id: str
    snapshot: dict

    def refresh(self) -> dict:
        self.snapshot = self.repository.get_progress_snapshot(self.student_id)
        return self.snapshot


@dataclass(frozen=True, slots=True)
class ChatCommandResult:
    action: Literal["output", "clear", "exit", "confirm_skip"]
    text: str = ""


def prepare_agent_message(message: str) -> str | None:
    prefix = CONTEXTUAL_PREFIXES.get(message)
    if prefix:
        return f"{prefix}\n\nMensagem do aluno: {message}"
    if message.startswith("/"):
        return None
    return message


def handle_chat_command(context: ChatContext, message: str, *, confirm_skip: bool = False) -> ChatCommandResult | None:
    if message not in LOCAL_COMMANDS:
        return None
    if message in {"/sair", "/exit", "/quit"}:
        return ChatCommandResult("exit", "Progresso salvo. Até a próxima.")
    if message == "/limpar":
        return ChatCommandResult("clear")
    if message == "/progresso":
        return ChatCommandResult("output", plain_progress(context.refresh()))
    if message == "/checkpoint":
        return ChatCommandResult("output", plain_evidence(context.refresh()))
    if message == "/modulos":
        return ChatCommandResult("output", plain_modules())
    if message == "/historico":
        return ChatCommandResult("output", plain_history(context.student_id, context.repository))
    if message == "/sessoes":
        return ChatCommandResult("output", plain_sessions(context.student_id, context.repository))
    if message == "/config":
        return ChatCommandResult("output", plain_config(context.student, context.settings))
    if message == "/ajuda":
        return ChatCommandResult("output", plain_commands())
    if message == "/pular":
        return _handle_skip(context, confirm_skip=confirm_skip)
    return ChatCommandResult("output", f"Comando: {message} não reconhecido.")


def _handle_skip(context: ChatContext, *, confirm_skip: bool) -> ChatCommandResult:
    current = context.snapshot["current"]
    next_module = current["current_module"] + 1
    if next_module > LAST_MODULE_ID:
        return ChatCommandResult("output", "Último módulo.")

    target = get_module(next_module)
    if not confirm_skip:
        return ChatCommandResult(
            "confirm_skip",
            f"Avançar para {target.title}? Confirme para continuar.",
        )

    context.repository.set_current_module(
        context.student_id,
        next_module,
        reason="skip_in_chat",
        session_id=context.session_id,
    )
    context.refresh()
    return ChatCommandResult("output", f"Avançado: {target.title}")


def plain_commands() -> str:
    return "\n".join(f"{cmd:<12} {desc}" for cmd, desc in COMMANDS_HELP)


def plain_modules() -> str:
    lines = ["ID  Módulo                                      Skill                         Extensão"]
    for module in MODULES:
        lines.append(
            f"{module.id:<3} {module.title:<43} {module.domain_skill:<29} "
            f"{'sim' if module.professional_extension else 'não'}"
        )
    return "\n".join(lines)


def plain_progress(snapshot: dict) -> str:
    current = snapshot["current"]
    lines = [
        f"{current['module_title']}",
        (
            f"Módulo: {current['current_module']} | "
            f"Nível: {current['independence_level']} | "
            f"Competência: {current['current_competency'] or UNDEFINED_COMPETENCY}"
        ),
        "",
        "ID  Estado       Domínio  Título",
    ]
    for row in snapshot["modules"]:
        marker = ">" if row["module_id"] == current["current_module"] else " "
        lines.append(
            f"{marker}{row['module_id']:<3} {row['status']:<12} "
            f"{row['mastery_score'] * 100:>5.0f}%  {row['title']}"
        )
    return "\n".join(lines)


def plain_evidence(snapshot: dict) -> str:
    evidence_by_kind = {item["evidence_kind"]: item for item in snapshot.get("evidence", [])}
    lines = [f"Checkpoint - {snapshot['current']['module_title']}"]
    for kind, label in EVIDENCE_DISPLAY_LABELS.items():
        evidence = evidence_by_kind.get(kind, {"best_score": 0.0, "satisfied": 0})
        status = "sim" if evidence.get("satisfied") else "não"
        lines.append(
            f"{label:<28} nota {evidence.get('best_score', 0.0) * 100:>3.0f}%  "
            f"satisfeita: {status}"
        )
    return "\n".join(lines)


def plain_history(student_id: str, repository: ProgressRepository) -> str:
    attempts = repository.get_progress_snapshot(student_id).get("recent_attempts", [])
    if not attempts:
        return "Nenhuma tentativa registrada ainda."
    lines = ["Módulo  Resultado  Nota  Dica  Competência  Data"]
    for attempt in attempts[:10]:
        lines.append(
            f"{attempt['module_id']:<6} {attempt['result']:<9} "
            f"{attempt['score'] * 100:>3.0f}%  {'sim' if attempt['used_hint'] else 'não':<4} "
            f"{attempt['competency_key']}  {(attempt.get('created_at') or '')[:16]}"
        )
    return "\n".join(lines)


def plain_sessions(student_id: str, repository: ProgressRepository) -> str:
    sessions = repository.list_sessions(student_id)
    if not sessions:
        return "Nenhuma sessão encontrada para este aluno."
    lines = ["#  Session ID                       Mensagens  Última atividade"]
    for index, session in enumerate(sessions, 1):
        lines.append(
            f"{index:<2} {session['session_id']:<32} "
            f"{session.get('message_count', 0):>9}  {(session.get('last_active') or '')[:19]}"
        )
    return "\n".join(lines)


def plain_config(student: dict, settings: Any) -> str:
    rows = [
        ("Student ID", student["student_id"]),
        ("Nome", student["display_name"]),
        ("Streaming", "ativado" if settings.stream else "desativado"),
        ("Resumos", "ativado" if settings.session_summaries else "desativado"),
        ("Memória", "ativada" if settings.memory else "desativada"),
        ("Runs em histórico", str(settings.history_runs)),
        ("Modelo", settings.deepseek_model),
    ]
    rows.extend((f"Pref: {key}", str(value)) for key, value in student.get("preferences", {}).items())
    return "\n".join(f"{key:<18} {value}" for key, value in rows)


def plain_doctor(rows: list[tuple[str, bool, str]]) -> str:
    lines = [f"Algo Hands-On Doctor - v{__version__}", "Componente                 Estado  Detalhe"]
    for component, ok, detail in rows:
        lines.append(f"{component:<26} {'OK' if ok else 'FALHA':<7} {detail}")
    return "\n".join(lines)


def _normalize_rendered_text(text: str) -> str:
    text = re.sub(r"[*_`>#\-]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _contains_rendered_block(message: str, block: str) -> bool:
    if not block:
        return True
    normalized_message = _normalize_rendered_text(message)
    normalized_block = _normalize_rendered_text(block)
    return normalized_block in normalized_message


def turn_history_text(turn: TutorTurn) -> str:
    parts = [turn.message_markdown]
    if turn.exercise and not _contains_rendered_block(turn.message_markdown, turn.exercise.statement):
        parts.append(f"Exercício: {turn.exercise.title}\n{turn.exercise.statement}")
    if turn.evaluation:
        evaluation = turn.evaluation
        parts.append(
            "Avaliação: "
            f"{evaluation.result.value} · nota {evaluation.score:.0%} · "
            f"competência {evaluation.competency_key}"
        )
    return "\n\n".join(parts)

from __future__ import annotations

import json
import logging
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.prompt import Prompt

from algo_hands_on import __version__
from algo_hands_on.config import get_settings
from algo_hands_on.curriculum import LAST_MODULE_ID, MODULES, get_module
from algo_hands_on.db.repository import ProgressRepository, StudentNotFoundError
from algo_hands_on.schemas import EVIDENCE_DISPLAY_LABELS, TutorTurn
from algo_hands_on.services.tutoring import TutoringService

app = typer.Typer(
    name="aho",
    help="Algo Hands-On — tutor adaptativo com Agno e DeepSeek.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

UNDEFINED_COMPETENCY = "não definida"
BRAND_ACCENT = "#1748E8"
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
    "/checkpoint": "Quero fazer uma verificação de checkpoint (evidências) do módulo atual.",
}


# ── helpers de renderização ──────────────────────────────────────────────────

def _configure_logging(settings) -> None:
    level_name = settings.log_level.upper() if settings.debug else "ERROR"
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s", force=True)

    if not settings.debug:
        for logger_name in ("agno", "httpx", "openai"):
            logging.getLogger(logger_name).setLevel(logging.ERROR)


def _plain_commands() -> str:
    return "\n".join(f"{cmd:<12} {desc}" for cmd, desc in COMMANDS_HELP)


def _plain_modules() -> str:
    lines = ["ID  Módulo                                      Skill                         Extensão"]
    for module in MODULES:
        lines.append(
            f"{module.id:<3} {module.title:<43} {module.domain_skill:<29} "
            f"{'sim' if module.professional_extension else 'não'}"
        )
    return "\n".join(lines)


def _plain_progress(snapshot: dict) -> str:
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


def _plain_evidence(snapshot: dict) -> str:
    evidence_by_kind = {item["evidence_kind"]: item for item in snapshot.get("evidence", [])}
    lines = [f"Checkpoint - {snapshot['current']['module_title']}"]
    for kind, label in EVIDENCE_DISPLAY_LABELS.items():
        evidence = evidence_by_kind.get(kind, {"best_score": 0.0, "satisfied": 0})
        status = "sim" if evidence.get("satisfied") else "não"
        lines.append(f"{label:<28} nota {evidence.get('best_score', 0.0) * 100:>3.0f}%  satisfeita: {status}")
    return "\n".join(lines)


def _plain_history(student_id: str, repository: ProgressRepository) -> str:
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


def _plain_sessions(student_id: str, repository: ProgressRepository) -> str:
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


def _plain_config(student: dict, settings) -> str:
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


def _plain_doctor(rows: list[tuple[str, bool, str]]) -> str:
    lines = [f"Algo Hands-On Doctor - v{__version__}", "Componente                 Estado  Detalhe"]
    for component, ok, detail in rows:
        lines.append(f"{component:<26} {'OK' if ok else 'FALHA':<7} {detail}")
    return "\n".join(lines)


def _student_not_found() -> None:
    console.print("[red]Aluno não encontrado.[/red]")
    raise typer.Exit(1) from None


# ── bootstrap ────────────────────────────────────────────────────────────────

def runtime() -> tuple:
    settings = get_settings()
    repository = ProgressRepository(settings.db_path)
    repository.initialize()
    return settings, repository


def _turn_history_text(turn: TutorTurn) -> str:
    parts = [turn.message_markdown]
    if turn.exercise:
        parts.append(f"Exercício: {turn.exercise.title}\n{turn.exercise.statement}")
    if turn.evaluation:
        evaluation = turn.evaluation
        parts.append(
            "Avaliação: "
            f"{evaluation.result.value} · nota {evaluation.score:.0%} · "
            f"competência {evaluation.competency_key}"
        )
    return "\n\n".join(parts)


def _run_rich_chat(
    *,
    settings,
    repository: ProgressRepository,
    service: TutoringService,
    student: dict,
    student_id: str,
    session_id: str,
    snapshot: dict,
) -> None:
    """Chat usando apenas Rich — sem Textual, sem widgets, sem CSS."""
    _console = Console()
    current = snapshot["current"]

    # Cabeçalho
    evidence = snapshot.get("evidence", [])
    evidence_by_kind = {item["evidence_kind"]: item for item in evidence}
    checkpoint = "  ".join(
        f"[green]✓[/] {label}" if evidence_by_kind.get(kind, {}).get("satisfied")
        else f"[dim]○[/] {label}"
        for kind, label in EVIDENCE_DISPLAY_LABELS.items()
    )

    _console.print(f"[bold blue]{current['module_title']}[/]  "
                   f"{INDEPENDENCE_LABELS.get(current['independence_level'], current['independence_level'])}")
    _console.print(f"Checkpoint: {checkpoint}")
    _console.print("[dim]Digite /ajuda para comandos, /sair para encerrar.[/]\n")

    while True:
        try:
            message = Prompt.ask("[bold]Você[/]").strip()
        except (KeyboardInterrupt, EOFError):
            _console.print("\n[dim]Até logo.[/]")
            break

        if not message:
            continue

        if message in {"/sair", "/exit", "/quit"}:
            _console.print("[dim]Progresso salvo. Até a próxima.[/]")
            break

        if message == "/limpar":
            _console.clear()
            continue

        # Comandos locais
        if message == "/progresso":
            snapshot = repository.get_progress_snapshot(student_id)
            _console.print(_plain_progress(snapshot))
            continue
        if message == "/checkpoint":
            snapshot = repository.get_progress_snapshot(student_id)
            _console.print(_plain_evidence(snapshot))
            continue
        if message == "/modulos":
            _console.print(_plain_modules())
            continue
        if message == "/historico":
            _console.print(_plain_history(student_id, repository))
            continue
        if message == "/sessoes":
            _console.print(_plain_sessions(student_id, repository))
            continue
        if message == "/config":
            _console.print(_plain_config(student, settings))
            continue
        if message == "/ajuda":
            _console.print(_plain_commands())
            continue
        if message == "/pular":
            next_module = current["current_module"] + 1
            if next_module > LAST_MODULE_ID:
                _console.print("[dim]Último módulo.[/]")
                continue
            target = get_module(next_module)
            if Prompt.ask(f"[yellow]Avançar para {target.title}?[/]", choices=["s", "n"], default="n") == "s":
                repository.set_current_module(student_id, next_module, reason="skip_in_chat", session_id=session_id)
                snapshot = repository.get_progress_snapshot(student_id)
                current = snapshot["current"]
                _console.print(f"[green]Avançado: {target.title}[/]")
            continue
        if message.startswith("/"):
            _console.print(f"[yellow]Comando: {message} não reconhecido.[/]")
            continue

        # Envia ao agente
        final_message = CONTEXTUAL_PREFIXES.get(message)
        if final_message:
            final_message = f"{final_message}\n\nMensagem do aluno: {message}"
        else:
            final_message = message

        with _console.status("[dim]Pensando...[/]"):
            try:
                turn = service.run_turn(
                    student_id=student_id,
                    session_id=session_id,
                    message=final_message,
                )
            except Exception as exc:
                _console.print(f"[red]Erro: {exc}[/]")
                continue

        _console.print("\n[bold green]Algo Hands-On:[/]")
        _console.print(turn.message_markdown)

        if turn.exercise:
            _console.print(f"\n[yellow]▸ {turn.exercise.title}[/]")
            _console.print(turn.exercise.statement)
            if turn.exercise.constraints:
                _console.print("\n[dim]Regras:[/]")
                for c in turn.exercise.constraints:
                    _console.print(f"  • {c}")

        if turn.evaluation:
            _console.print(
                f"\n[dim]{turn.evaluation.result.value} | "
                f"nota {turn.evaluation.score:.0%} | "
                f"{turn.evaluation.competency_key}[/]"
            )

        snapshot = repository.get_progress_snapshot(student_id)
        current = snapshot["current"]
        _console.print()


def _run_pipe_chat(
    *,
    service: TutoringService,
    student_id: str,
    session_id: str,
) -> None:
    for line in sys.stdin:
        message = line.strip()
        if not message:
            continue
        if message in {"/sair", "/exit", "/quit"}:
            console.print("[dim]Progresso salvo. Até a próxima.[/dim]")
            return
        final_message = CONTEXTUAL_PREFIXES.get(message)
        if final_message:
            final_message = f"{final_message}\n\nMensagem do aluno: {message}"
        elif message.startswith("/"):
            console.print(f"[yellow]Comando interativo indisponível por pipe: {message}[/yellow]")
            continue
        else:
            final_message = message
        try:
            turn = service.run_turn(student_id=student_id, session_id=session_id, message=final_message)
        except Exception as exc:
            console.print(f"Falha ao executar o agente: {exc}")
            continue
        console.print("Algo Hands-On")
        console.print(_turn_history_text(turn))


# ── comandos Typer ───────────────────────────────────────────────────────────

@app.command()
def setup(
    student_id: str = typer.Option(..., "--student-id", "-s", help="Identificador único."),
    name: str = typer.Option(..., "--name", "-n", help="Nome exibido."),
) -> None:
    """Cria ou atualiza um aluno."""
    _, repository = runtime()
    student = repository.create_student(student_id, name)
    console.print(f"[green]Aluno pronto:[/green] {student['display_name']} ({student['student_id']})")


@app.command()
def progress(
    student_id: str = typer.Option(..., "--student-id", "-s"),
) -> None:
    """Mostra a progressão curricular."""
    _, repository = runtime()
    try:
        console.print(_plain_progress(repository.get_progress_snapshot(student_id)))
    except StudentNotFoundError:
        _student_not_found()


@app.command("modules")
def show_modules() -> None:
    """Lista os módulos da trilha."""
    console.print(_plain_modules())


@app.command("students")
def list_students() -> None:
    """Lista alunos cadastrados e oferece ações."""
    settings, repository = runtime()
    rows = repository.list_students()

    if not rows:
        console.print("[yellow]Nenhum aluno cadastrado.[/yellow]")
        if typer.confirm("Deseja criar um agora?"):
            student_id = typer.prompt("ID do aluno (ex: maria, joao123)")
            name = typer.prompt("Nome")
            student = repository.create_student(student_id, name)
            console.print(f"[green]Aluno criado:[/green] {student['display_name']} ({student['student_id']})")
            _offer_actions(settings, repository, student_id)
        return

    _render_student_table(rows)

    if len(rows) == 1:
        student_id = rows[0]["student_id"]
        console.print(f"[dim]Aluno selecionado automaticamente: {student_id}[/dim]")
    else:
        ids = [row["student_id"] for row in rows]
        student_id = _pick_student(ids, rows)
        if student_id is None:
            return

    _offer_actions(settings, repository, student_id)


def _render_student_table(rows: list[dict]) -> None:
    from rich.table import Table

    table = Table(title="Alunos cadastrados")
    table.add_column("#", style="dim", width=3)
    table.add_column("ID")
    table.add_column("Nome")
    table.add_column("Módulo")
    table.add_column("Nível")
    for i, row in enumerate(rows, 1):
        module_title = get_module(row.get("current_module", 0)).title if row.get("current_module") is not None else "—"
        level = INDEPENDENCE_LABELS.get(row.get("independence_level", ""), row.get("independence_level", "—"))
        table.add_row(str(i), row["student_id"], row["display_name"], module_title, level)
    console.print(table)


def _pick_student(ids: list[str], rows: list[dict]) -> str | None:
    console.print("\n[bold]Digite o número ou ID do aluno:[/bold]")
    choice = typer.prompt("Aluno", default="1")

    # Tenta como número
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(ids):
            return ids[idx]
    except ValueError:
        pass

    # Tenta como ID exato
    if choice in ids:
        return choice

    # Tenta match parcial
    matches = [sid for sid in ids if choice.lower() in sid.lower()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        console.print(f"[yellow]Múltiplos matches: {', '.join(matches)}. Seja mais específico.[/yellow]")
        return None

    console.print(f"[red]Aluno '{choice}' não encontrado.[/red]")
    return None


def _offer_actions(settings, repository, student_id: str) -> None:
    student = repository.get_student(student_id)
    snapshot = repository.get_progress_snapshot(student_id)
    current = snapshot["current"]

    console.print(f"\n[bold {BRAND_ACCENT}]Aluno: {student['display_name']} | Módulo: {current['module_title']} | Nível: {INDEPENDENCE_LABELS.get(current['independence_level'], current['independence_level'])}[/]")
    console.print()

    actions = [
        ("Conversar com o tutor", "chat"),
        ("Ver progresso", "progress"),
        ("Exportar histórico", "export"),
        ("Reiniciar progresso", "reset"),
    ]
    for i, (label, _) in enumerate(actions, 1):
        console.print(f"  {i}. {label}")
    console.print("  0. Sair")
    console.print()

    choice = typer.prompt("O que deseja fazer", default="1")

    try:
        idx = int(choice)
    except ValueError:
        console.print("[dim]Até logo.[/dim]")
        return

    if idx == 0:
        console.print("[dim]Até logo.[/dim]")
        return

    if idx == 1:
        # Inicia chat — reusa a lógica do comando chat
        session_id = f"cli-{student_id}-{uuid.uuid4().hex[:10]}"
        service = TutoringService(settings, repository)
        from algo_hands_on.db.repository import StudentNotFoundError

        try:
            student_check = repository.get_student(student_id)
        except StudentNotFoundError:
            console.print(f"[red]Aluno {student_id} não encontrado.[/red]")
            return

        _run_rich_chat(
            settings=settings,
            repository=repository,
            service=service,
            student=student_check,
            student_id=student_id,
            session_id=session_id,
            snapshot=snapshot,
        )
        console.print("[dim]Progresso salvo. Até a próxima.[/dim]")
        return

    if idx == 2:
        console.print(_plain_progress(snapshot))
        return

    if idx == 3:
        output = Path(f"progress-export-{student_id}.json")
        payload = repository.export_student(student_id)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]Exportado:[/green] {output.resolve()}")
        return

    if idx == 4:
        console.print(f"[yellow]ATENÇÃO: Todo o progresso de {student['display_name']} será perdido.[/yellow]")
        if typer.confirm(f"Confirmar reinício de {student_id}?"):
            repository.reset_student(student_id)
            console.print("[green]Progresso reiniciado.[/green]")
        else:
            console.print("[dim]Cancelado.[/dim]")
        return

    console.print("[dim]Opção inválida.[/dim]")


@app.command()
def chat(
    student_id: str = typer.Option(..., "--student-id", "-s"),
    session_id: str | None = typer.Option(None, "--session-id", help="Continua uma conversa existente."),
) -> None:
    """Inicia a CLI interativa do tutor."""
    settings, repository = runtime()
    _configure_logging(settings)
    errors = settings.validate_runtime()
    if errors:
        for error in errors:
            console.print(f"[red]\u2022 {error}[/red]")
        raise typer.Exit(1) from None

    try:
        student = repository.get_student(student_id)
    except StudentNotFoundError:
        name = typer.prompt("Nome do aluno", default=student_id)
        student = repository.create_student(student_id, name)

    if session_id:
        sessions = repository.list_sessions(student_id)
        session_ids = {s["session_id"] for s in sessions}
        if session_id not in session_ids:
            console.print(f"[yellow]Sessão {session_id} não encontrada. Criando nova.[/yellow]")
            session_id = None

    session_id = session_id or f"cli-{student_id}-{uuid.uuid4().hex[:10]}"
    service = TutoringService(settings, repository)

    snapshot = repository.get_progress_snapshot(student_id)
    if sys.stdin.isatty():
        _run_rich_chat(
            settings=settings,
            repository=repository,
            service=service,
            student=student,
            student_id=student_id,
            session_id=session_id,
            snapshot=snapshot,
        )
        return

    _run_pipe_chat(
        service=service,
        student_id=student_id,
        session_id=session_id,
    )


@app.command()
def export(
    student_id: str = typer.Option(..., "--student-id", "-s"),
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("progress-export.json"),
) -> None:
    """Exporta todo o histórico pedagógico em JSON."""
    _, repository = runtime()
    try:
        payload = repository.export_student(student_id)
    except StudentNotFoundError:
        _student_not_found()
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]Exportado:[/green] {output.resolve()}")


@app.command()
def reset(
    student_id: str = typer.Option(..., "--student-id", "-s"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Reinicia o progresso pedagógico do aluno."""
    _, repository = runtime()
    try:
        student = repository.get_student(student_id)
    except StudentNotFoundError:
        _student_not_found()

    console.print(f"[yellow]ATENÇÃO: Todo o progresso de {student['display_name']} será perdido.[/yellow]")
    if not yes and not typer.confirm(f"Confirmar reinício de {student_id}?"):
        raise typer.Abort()

    try:
        repository.reset_student(student_id)
    except StudentNotFoundError:
        _student_not_found()
    console.print("[green]Progresso reiniciado. Auditoria registrada.[/green]")


@app.command()
def skip_module(
    student_id: str = typer.Option(..., "--student-id", "-s"),
    module_id: int = typer.Option(..., "--module", "-m", help="ID do módulo para o qual pular."),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Avança o aluno para um módulo específico (requer confirmação)."""
    _, repository = runtime()
    try:
        student = repository.get_student(student_id)
    except StudentNotFoundError:
        _student_not_found()

    try:
        target = get_module(module_id)
    except ValueError:
        console.print(f"[red]Módulo inválido: {module_id}[/red]")
        raise typer.Exit(1) from None

    snapshot = repository.get_progress_snapshot(student_id)
    current = snapshot["current"]["current_module"]
    console.print(
        f"[yellow]Atenção: {student['display_name']} será movido do "
        f"módulo {current} para o módulo {module_id} ({target.title}).[/yellow]"
    )

    if not yes and not typer.confirm("Confirmar salto de módulo?"):
        raise typer.Abort()

    repository.set_current_module(student_id, module_id, reason="skip_module_command")
    console.print(f"[green]Aluno movido para o módulo {module_id} ({target.title}).[/green]")


@app.command()
def clean() -> None:
    """Limpa TODO o banco de dados — alunos, progresso, memórias. Requer confirmação."""
    settings, repository = runtime()

    students = repository.list_students()
    if not students:
        console.print("[dim]Banco já está vazio.[/dim]")
        return

    console.print(f"[yellow]ATENÇÃO: {len(students)} aluno(s) e todos os dados serão PERDIDOS.[/yellow]")
    for s in students:
        console.print(f"  • {s['student_id']} ({s['display_name']})")

    if not typer.confirm("Confirmar limpeza total do banco?"):
        raise typer.Abort()

    import sqlite3

    conn = sqlite3.connect(str(settings.db_path))
    conn.execute("DELETE FROM aho_exercise_attempts")
    conn.execute("DELETE FROM aho_module_evidence")
    conn.execute("DELETE FROM aho_competency_progress")
    conn.execute("DELETE FROM aho_learning_events")
    conn.execute("DELETE FROM aho_module_progress")
    conn.execute("DELETE FROM aho_student_progress")
    conn.execute("DELETE FROM aho_students")
    conn.execute("DELETE FROM agno_sessions")
    conn.execute("DELETE FROM agno_memories")
    conn.execute("DELETE FROM agno_metrics")
    conn.execute("DELETE FROM agno_evals")
    conn.commit()
    conn.close()
    console.print("[green]Banco limpo. Pronto para começar do zero.[/green]")


@app.command()
def doctor() -> None:
    """Valida ambiente, banco e skills."""
    settings, repository = runtime()
    rows: list[tuple[str, bool, str]] = []
    rows.append(("Python", sys.version_info >= (3, 12), sys.version.split()[0]))
    api_key_ok = bool(settings.deepseek_api_key)
    rows.append(("DEEPSEEK_API_KEY", api_key_ok, "configurada" if api_key_ok else "ausente"))
    rows.append(("SQLite", settings.db_path.exists(), str(settings.db_path)))
    rows.append(("Skills", settings.skills_dir.exists(), str(settings.skills_dir)))

    try:
        from agno.skills import LocalSkills, Skills
        Skills(loaders=[LocalSkills(str(settings.skills_dir))])
        rows.append(("Validação Agno Skills", True, "ok"))
    except Exception as exc:
        rows.append(("Validação Agno Skills", False, str(exc)))

    rows.append(("Streaming Agno", True, "ativado" if settings.stream else "desativado"))
    rows.append(("Resumos", True, "ativado" if settings.session_summaries else "desativado"))
    rows.append(("Memória", True, "ativada" if settings.memory else "desativada"))

    console.print(_plain_doctor(rows))
    if not all(ok for _, ok, _ in rows):
        raise typer.Exit(1) from None


@app.command()
def serve(
    host: str | None = typer.Option(None, "--host"),
    port: int | None = typer.Option(None, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Executa API e AgentOS com Uvicorn."""
    settings = get_settings()
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "algo_hands_on.api:app",
        "--host",
        host or settings.host,
        "--port",
        str(port or settings.port),
    ]
    if reload:
        command.append("--reload")
    raise typer.Exit(subprocess.call(command))


if __name__ == "__main__":
    app()

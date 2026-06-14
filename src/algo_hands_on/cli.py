from __future__ import annotations

import json
import logging
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from algo_hands_on import __version__
from algo_hands_on.config import get_settings
from algo_hands_on.curriculum import MODULES
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

CHAT_HISTORY_LIMIT = 8

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


def _panel(content: Any, title: str = "", border_style: str = "cyan", **kwargs: Any) -> None:
    console.print(Panel(content, title=title, border_style=border_style, **kwargs))


def _markdown_panel(text: str, title: str, border_style: str = "cyan") -> None:
    console.print(Panel(Markdown(text), title=title, border_style=border_style))


def _commands_panel(title: str = "Comandos", border_style: str = "cyan") -> None:
    lines = [f"[cyan]{cmd}[/cyan]  {desc}" for cmd, desc in COMMANDS_HELP]
    console.print(Panel("\n".join(lines), title=title, border_style=border_style, padding=(0, 2)))


def _input_panel() -> Panel:
    return Panel(
        "[bold cyan]Você[/bold cyan]\n[dim]Digite sua mensagem ou um comando. Enter envia.[/dim]",
        title="Entrada",
        border_style="bright_blue",
        padding=(0, 2),
    )


def _student_not_found() -> None:
    console.print("[red]Aluno não encontrado.[/red]")
    raise typer.Exit(1) from None


# ── bootstrap ────────────────────────────────────────────────────────────────

def runtime() -> tuple:
    settings = get_settings()
    repository = ProgressRepository(settings.db_path)
    repository.initialize()
    return settings, repository


def banner() -> None:
    title = Text("ALGO HANDS-ON", style="bold cyan")
    subtitle = Text("Pense. Resolva. Construa.", style="bright_white")
    _panel(Text.assemble(title, "\n", subtitle), border_style="cyan", padding=(1, 4))


# ── telas de informação ──────────────────────────────────────────────────────

def render_home(snapshot: dict, student: dict, session_id: str) -> None:
    current = snapshot["current"]
    evidence = snapshot.get("evidence", [])
    module_progress = next(
        (m for m in snapshot["modules"] if m["module_id"] == current["current_module"]),
        {"mastery_score": 0.0},
    )
    mastery_pct = module_progress.get("mastery_score", 0.0)

    banner()
    info_table = Table(box=None, show_header=False, padding=(0, 2))
    info_table.add_column(style="bold cyan")
    info_table.add_column()
    info_table.add_row("Aluno", f"[bold]{student['display_name']}[/bold]")
    info_table.add_row("Sessão", f"[dim]{session_id}[/dim]")
    info_table.add_row("Módulo atual", f"[bold]{current['module_title']}[/bold]")
    info_table.add_row("Nível", INDEPENDENCE_LABELS.get(current["independence_level"], current["independence_level"]))
    info_table.add_row("Competência", current.get("current_competency") or "a definir")
    console.print(info_table)

    bar = Progress(
        TextColumn("Domínio  "),
        BarColumn(bar_width=40, style="cyan", complete_style="green"),
        TextColumn(f" {mastery_pct * 100:.0f}%"),
        console=console,
    )
    bar.add_task("", total=1.0, completed=mastery_pct)
    with bar:
        pass

    evidence_dict = {e["evidence_kind"]: e for e in evidence}
    ev_parts: list[str] = []
    for kind, label in EVIDENCE_DISPLAY_LABELS.items():
        ev = evidence_dict.get(kind, {"satisfied": 0, "best_score": 0.0})
        icon = "[green]OK[/green]" if ev.get("satisfied") else "[red]X[/red]"
        ev_parts.append(f"{icon} {label}")
    console.print(f"[bold]Checkpoint:[/bold]  {'  '.join(ev_parts)}")

    _commands_panel("Comandos", border_style="dim blue")


def render_chat_screen(snapshot: dict, student: dict, session_id: str, history: list[tuple[str, str]]) -> None:
    console.clear()
    render_home(snapshot, student, session_id)

    if history:
        lines: list[str] = []
        for role, text in history[-CHAT_HISTORY_LIMIT:]:
            label = "[bold cyan]Você[/bold cyan]" if role == "user" else "[bold green]Algo Hands-On[/bold green]"
            body = text.strip()
            if len(body) > 1200:
                body = f"{body[:1200].rstrip()}..."
            lines.append(f"{label}\n{body}")
        console.print(Panel("\n\n".join(lines), title="Conversa", border_style="dim", padding=(1, 2)))

    console.print(_input_panel())


def render_progress(snapshot: dict) -> None:
    current = snapshot["current"]
    _panel(
        f"[bold]{current['module_title']}[/bold]\n"
        f"Módulo: {current['current_module']} · Nível: {current['independence_level']} · "
        f"Competência: {current['current_competency'] or 'a definir'}",
        title=f"Progresso de {snapshot['student']['display_name']}",
        border_style="green",
    )
    table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
    table.add_column("Módulo", justify="right")
    table.add_column("Título")
    table.add_column("Estado")
    table.add_column("Domínio", justify="right")
    for row in snapshot["modules"]:
        marker = ">" if row["module_id"] == current["current_module"] else ""
        table.add_row(
            f"{marker} {row['module_id']}",
            row["title"],
            row["status"],
            f"{row['mastery_score'] * 100:.0f}%",
        )
    console.print(table)


def render_evidence(snapshot: dict) -> None:
    evidence = snapshot.get("evidence", [])
    current = snapshot["current"]
    evidence_dict = {e["evidence_kind"]: e for e in evidence}

    table = Table(title=f"Checkpoint — {current['module_title']}", box=box.ROUNDED)
    table.add_column("Evidência")
    table.add_column("Nota", justify="right")
    table.add_column("Satisfeita")

    for kind, label in EVIDENCE_DISPLAY_LABELS.items():
        ev = evidence_dict.get(kind, {"best_score": 0.0, "satisfied": 0})
        satisfied = "[green]Sim[/green]" if ev.get("satisfied") else "[red]Não[/red]"
        table.add_row(label, f"{ev.get('best_score', 0.0) * 100:.0f}%", satisfied)

    console.print(table)
    mastered = sum(1 for e in evidence if e.get("satisfied"))
    total = len(EVIDENCE_DISPLAY_LABELS)
    console.print(f"\nEvidências concluídas: {mastered}/{total}")


def render_history(student_id: str, repository: ProgressRepository) -> None:
    attempts = repository.get_progress_snapshot(student_id).get("recent_attempts", [])
    if not attempts:
        console.print("[dim]Nenhuma tentativa registrada ainda.[/dim]")
        return

    table = Table(title="Histórico recente", box=box.ROUNDED)
    table.add_column("Módulo", justify="right")
    table.add_column("Competência")
    table.add_column("Resultado")
    table.add_column("Nota", justify="right")
    table.add_column("Dica")
    table.add_column("Data")

    for a in attempts[:10]:
        style = "green" if a["result"] == "correct" else "yellow"
        table.add_row(
            str(a["module_id"]),
            a["competency_key"],
            f"[{style}]{a['result']}[/{style}]",
            f"{a['score'] * 100:.0f}%",
            "sim" if a["used_hint"] else "não",
            (a.get("created_at") or "")[:16],
        )

    console.print(table)


def render_sessions(student_id: str, repository: ProgressRepository) -> None:
    sessions = repository.list_sessions(student_id)
    if not sessions:
        console.print("[dim]Nenhuma sessão encontrada para este aluno.[/dim]")
        return

    table = Table(title=f"Sessões de {student_id}", box=box.ROUNDED)
    table.add_column("#", justify="right")
    table.add_column("Session ID")
    table.add_column("Mensagens", justify="right")
    table.add_column("Última atividade")

    for i, s in enumerate(sessions, 1):
        table.add_row(
            str(i),
            s["session_id"],
            str(s.get("message_count", 0)),
            (s.get("last_active") or "")[:19],
        )

    console.print(table)


def render_config(student: dict, settings) -> None:
    prefs = student.get("preferences", {})
    table = Table(title="Configuração", box=box.ROUNDED)
    table.add_column("Parâmetro")
    table.add_column("Valor")

    table.add_row("Student ID", student["student_id"])
    table.add_row("Nome", student["display_name"])
    table.add_row("Streaming", "ativado" if settings.stream else "desativado")
    table.add_row("Resumos", "ativado" if settings.session_summaries else "desativado")
    table.add_row("Memória", "ativada" if settings.memory else "desativada")
    table.add_row("Runs em histórico", str(settings.history_runs))
    table.add_row("Modelo", settings.deepseek_model)

    if prefs:
        for k, v in prefs.items():
            table.add_row(f"Pref: {k}", str(v))

    console.print(table)


def _show_turn_extras(turn: TutorTurn) -> None:
    if turn.exercise:
        _markdown_panel(turn.exercise.statement, f"Exercício — {turn.exercise.title}", "magenta")
    if turn.evaluation:
        evaluation = turn.evaluation
        style = "green" if evaluation.result.value == "correct" else "yellow"
        console.print(
            f"[{style}]Avaliação: {evaluation.result.value} · "
            f"nota {evaluation.score:.0%} · competência {evaluation.competency_key}[/{style}]"
        )


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


# ── streaming ────────────────────────────────────────────────────────────────

def _run_chat_stream(service, student_id: str, session_id: str, message: str) -> TutorTurn:
    accumulated: list[str] = []
    turn: TutorTurn | None = None
    spinner = console.status("[cyan]Algo Hands-On está pensando...[/cyan]", spinner="dots12")
    spinner.start()
    try:
        for item in service.run_turn_stream(student_id=student_id, session_id=session_id, message=message):
            if item.get("type") == "content":
                accumulated.append(item["text"])
                spinner.stop()
                console.print(Text(item["text"], style="bright_white"), end="")
            elif item.get("type") == "final":
                turn = item["turn"]
                break
    finally:
        if spinner._live.is_started:
            spinner.stop()
    console.print()
    if turn is None:
        combined = "".join(accumulated)
        return TutorTurn(message_markdown=combined or "Sem resposta.", module_id=0)
    _markdown_panel(turn.message_markdown, "Algo Hands-On")
    return turn


def _run_turn_and_display(service, student_id: str, session_id: str, message: str, stream: bool) -> TutorTurn:
    if stream:
        return _run_chat_stream(service, student_id, session_id, message)
    with console.status("[cyan]Algo Hands-On está analisando...[/cyan]", spinner="dots12"):
        turn = service.run_turn(student_id=student_id, session_id=session_id, message=message)
    _markdown_panel(turn.message_markdown, "Algo Hands-On")
    return turn


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
        render_progress(repository.get_progress_snapshot(student_id))
    except StudentNotFoundError:
        _student_not_found()


@app.command("modules")
def show_modules() -> None:
    """Lista os módulos da trilha."""
    table = Table(title="Trilha Canônica AHO", box=box.ROUNDED)
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Módulo")
    table.add_column("Skill")
    table.add_column("Extensão")
    for module in MODULES:
        table.add_row(
            str(module.id),
            module.title,
            module.domain_skill,
            "sim" if module.professional_extension else "não",
        )
    console.print(table)


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
        name = Prompt.ask("Nome do aluno", default=student_id)
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
    chat_history: list[tuple[str, str]] = []
    render_chat_screen(snapshot, student, session_id, chat_history)

    while True:
        try:
            message = Prompt.ask("[bold cyan]Você[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Sessão encerrada.[/dim]")
            return
        if not message:
            continue

        if message in {"/sair", "/exit", "/quit"}:
            console.print("[dim]Progresso salvo. Até a próxima.[/dim]")
            return

        if message == "/limpar":
            chat_history.clear()
            snapshot = repository.get_progress_snapshot(student_id)
            render_chat_screen(snapshot, student, session_id, chat_history)
            continue

        if message == "/progresso":
            render_progress(repository.get_progress_snapshot(student_id))
            console.print(_input_panel())
            continue

        if message == "/checkpoint":
            render_evidence(repository.get_progress_snapshot(student_id))
            console.print(_input_panel())
            continue

        if message == "/modulos":
            show_modules()
            console.print(_input_panel())
            continue

        if message == "/historico":
            render_history(student_id, repository)
            console.print(_input_panel())
            continue

        if message == "/sessoes":
            render_sessions(student_id, repository)
            console.print(_input_panel())
            continue

        if message == "/config":
            render_config(student, settings)
            console.print(_input_panel())
            continue

        if message == "/ajuda":
            _commands_panel("Comandos disponíveis")
            console.print(_input_panel())
            continue

        if message == "/pular":
            snapshot = repository.get_progress_snapshot(student_id)
            cur_id = snapshot["current"]["current_module"]
            nxt = cur_id + 1
            if nxt > 16:
                console.print("[yellow]Você já está no último módulo.[/yellow]")
                continue
            from algo_hands_on.curriculum import get_module

            target = get_module(nxt)
            console.print(f"[yellow]Isso avançará para o módulo {nxt} ({target.title}).[/yellow]")
            if not Confirm.ask("Confirmar salto de módulo?"):
                continue
            repository.set_current_module(student_id, nxt, reason="skip_in_chat", session_id=session_id)
            console.print(f"[green]Avançado para: {target.title}[/green]")
            snapshot = repository.get_progress_snapshot(student_id)
            render_home(snapshot, student, session_id)
            continue

        final_message = message
        if message in CONTEXTUAL_PREFIXES:
            final_message = f"{CONTEXTUAL_PREFIXES[message]}\n\nMensagem do aluno: {message}"
        elif message.startswith("/"):
            console.print(f"[yellow]Comando desconhecido: {message}[/yellow]")
            continue

        try:
            chat_history.append(("user", message))
            turn = _run_turn_and_display(service, student_id, session_id, final_message, settings.stream)
        except Exception as exc:
            _panel(str(exc), "Falha ao executar o agente", border_style="red")
            continue

        chat_history.append(("assistant", _turn_history_text(turn)))
        _show_turn_extras(turn)
        snapshot = repository.get_progress_snapshot(student_id)
        render_chat_screen(snapshot, student, session_id, chat_history)


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
    if not yes and not Confirm.ask(f"Confirmar reinício de {student_id}?"):
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
    from algo_hands_on.curriculum import get_module

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

    if not yes and not Confirm.ask("Confirmar salto de módulo?"):
        raise typer.Abort()

    repository.set_current_module(student_id, module_id, reason="skip_module_command")
    console.print(f"[green]Aluno movido para o módulo {module_id} ({target.title}).[/green]")


@app.command()
def doctor() -> None:
    """Valida ambiente, banco e skills."""
    settings, repository = runtime()
    rows: list[tuple[str, bool, str]] = []
    rows.append(("Python", sys.version_info >= (3, 12), sys.version.split()[0]))
    api_key_ok = bool(settings.deepseek_api_key and settings.deepseek_api_key != "coloque_sua_chave_aqui")
    rows.append(("DEEPSEEK_API_KEY", api_key_ok, "configurada" if api_key_ok else "ausente"))
    rows.append(("SQLite", settings.db_path.exists(), str(settings.db_path)))
    rows.append(("Skills", settings.skills_dir.exists(), str(settings.skills_dir)))

    try:
        from agno.skills import LocalSkills, Skills
        Skills(loaders=[LocalSkills(str(settings.skills_dir))])
        rows.append(("Validação Agno Skills", True, "ok"))
    except Exception as exc:
        rows.append(("Validação Agno Skills", False, str(exc)))

    rows.append(("Streaming", True, "ativado" if settings.stream else "desativado"))
    rows.append(("Resumos", True, "ativado" if settings.session_summaries else "desativado"))
    rows.append(("Memória", True, "ativada" if settings.memory else "desativada"))

    table = Table(title=f"Algo Hands-On Doctor · v{__version__}", box=box.ROUNDED)
    table.add_column("Componente")
    table.add_column("Estado")
    table.add_column("Detalhe")
    for component, ok, detail in rows:
        table.add_row(component, "[green]OK[/green]" if ok else "[red]FALHA[/red]", detail)
    console.print(table)
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

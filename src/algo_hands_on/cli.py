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

from algo_hands_on.chat_core import (
    INDEPENDENCE_LABELS,
    plain_doctor,
    plain_modules,
    plain_progress,
    prepare_agent_message,
    turn_history_text,
)
from algo_hands_on.config import get_settings
from algo_hands_on.curriculum import get_module
from algo_hands_on.db.repository import ProgressRepository, StudentNotFoundError
from algo_hands_on.services.tutoring import AGENT_OPERATIONAL_ERRORS, TutoringService

app = typer.Typer(
    name="aho",
    help="Algo Hands-On — tutor adaptativo com Agno e DeepSeek.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _configure_logging(settings) -> None:
    level_name = settings.log_level.upper() if settings.debug else "ERROR"
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s", force=True)

    if not settings.debug:
        for logger_name in ("agno", "httpx", "openai"):
            logging.getLogger(logger_name).setLevel(logging.ERROR)


def _student_not_found() -> None:
    console.print("[red]Aluno não encontrado.[/red]")
    raise typer.Exit(1) from None


# ── bootstrap ────────────────────────────────────────────────────────────────

def runtime() -> tuple:
    settings = get_settings()
    repository = ProgressRepository(settings.db_path)
    repository.initialize()
    return settings, repository


def _run_pipe_chat(
    *,
    settings,
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
        final_message = prepare_agent_message(message)
        if final_message is None:
            console.print(f"[yellow]Comando interativo indisponível por pipe: {message}[/yellow]")
            continue
        try:
            if settings.stream:
                console.print("Algo Hands-On")
                for event in service.run_turn_stream(
                    student_id=student_id,
                    session_id=session_id,
                    message=final_message,
                ):
                    if event.get("type") == "content":
                        console.print(event.get("text", ""), end="")
                    elif event.get("type") == "final":
                        console.print()
            else:
                turn = service.run_turn(student_id=student_id, session_id=session_id, message=final_message)
                console.print("Algo Hands-On")
                console.print(turn_history_text(turn))
        except AGENT_OPERATIONAL_ERRORS as exc:
            console.print(f"Falha ao executar o agente: {exc}")


def _run_tui_chat(
    *,
    settings,
    repository: ProgressRepository,
    service: TutoringService,
    student: dict,
    student_id: str,
    session_id: str,
    snapshot: dict,
) -> None:
    from algo_hands_on.tui import TutorTui

    TutorTui(
        settings=settings,
        repository=repository,
        service=service,
        student=student,
        student_id=student_id,
        session_id=session_id,
        snapshot=snapshot,
    ).run()


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
        console.print(plain_progress(repository.get_progress_snapshot(student_id)))
    except StudentNotFoundError:
        _student_not_found()


@app.command("modules")
def show_modules() -> None:
    """Lista os módulos da trilha."""
    console.print(plain_modules())


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
        student_id = _pick_student(ids)
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


def _pick_student(ids: list[str]) -> str | None:
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

    console.print(
        f"\n[bold #1748E8]Aluno: {student['display_name']} | "
        f"Módulo: {current['module_title']} | "
        f"Nível: {INDEPENDENCE_LABELS.get(current['independence_level'], current['independence_level'])}[/]"
    )
    console.print()

    actions = [
        "Conversar com o tutor",
        "Ver progresso",
        "Exportar histórico",
        "Reiniciar progresso",
    ]
    for i, label in enumerate(actions, 1):
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

        try:
            student_check = repository.get_student(student_id)
        except StudentNotFoundError:
            console.print(f"[red]Aluno {student_id} não encontrado.[/red]")
            return

        _run_tui_chat(
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
        console.print(plain_progress(snapshot))
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
        _run_tui_chat(
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
        settings=settings,
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
    _, repository = runtime()

    students = repository.list_students()
    if not students:
        console.print("[dim]Banco já está vazio.[/dim]")
        return

    console.print("[yellow]ATENÇÃO: todos os dados locais serão PERDIDOS.[/yellow]")
    console.print(f"[yellow]Alunos AHO encontrados: {len(students)}[/yellow]")
    for s in students:
        console.print(f"  • {s['student_id']} ({s['display_name']})")

    if not typer.confirm("Confirmar limpeza total do banco?"):
        raise typer.Abort()

    repository.clear_all_data()
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
    except (ImportError, RuntimeError, ValueError, OSError) as exc:
        rows.append(("Validação Agno Skills", False, str(exc)))

    rows.append(("Streaming Agno", True, "ativado" if settings.stream else "desativado"))
    rows.append(("Resumos", True, "ativado" if settings.session_summaries else "desativado"))
    rows.append(("Memória da sessão", True, "ativada" if settings.memory else "desativada"))

    console.print(plain_doctor(rows))
    if not all(ok for _, ok, _ in rows):
        raise typer.Exit(1) from None


@app.command()
def serve(
    host: str | None = typer.Option(None, "--host"),
    port: int | None = typer.Option(None, "--port"),
    reload: bool | None = typer.Option(None, "--reload/--no-reload"),
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
    if settings.reload if reload is None else reload:
        command.append("--reload")
    raise typer.Exit(subprocess.call(command))


if __name__ == "__main__":
    app()

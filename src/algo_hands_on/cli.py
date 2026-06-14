from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from algo_hands_on import __version__
from algo_hands_on.config import get_settings
from algo_hands_on.curriculum import MODULES
from algo_hands_on.db.repository import ProgressRepository, StudentNotFoundError
from algo_hands_on.services.tutoring import TutoringService

app = typer.Typer(
    name="aho",
    help="Algo Hands-On — tutor adaptativo com Agno e DeepSeek.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def runtime() -> tuple:
    settings = get_settings()
    repository = ProgressRepository(settings.db_path)
    repository.initialize()
    return settings, repository


def banner() -> None:
    title = Text("ALGO HANDS-ON", style="bold cyan")
    subtitle = Text("Pense. Resolva. Construa.", style="bright_white")
    console.print(Panel.fit(Text.assemble(title, "\n", subtitle), border_style="cyan", padding=(1, 4)))


def render_progress(snapshot: dict) -> None:
    current = snapshot["current"]
    console.print(
        Panel(
            f"[bold]{current['module_title']}[/bold]\n"
            f"Módulo: {current['current_module']} · Nível: {current['independence_level']} · "
            f"Competência: {current['current_competency'] or 'a definir'}",
            title=f"Progresso de {snapshot['student']['display_name']}",
            border_style="green",
        )
    )
    table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
    table.add_column("Módulo", justify="right")
    table.add_column("Título")
    table.add_column("Estado")
    table.add_column("Domínio", justify="right")
    for row in snapshot["modules"]:
        marker = "▶" if row["module_id"] == current["current_module"] else ""
        table.add_row(
            f"{marker} {row['module_id']}",
            row["title"],
            row["status"],
            f"{row['mastery_score'] * 100:.0f}%",
        )
    console.print(table)


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
        console.print("[red]Aluno não encontrado.[/red]")
        raise typer.Exit(1) from None


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
    errors = settings.validate_runtime()
    if errors:
        for error in errors:
            console.print(f"[red]• {error}[/red]")
        raise typer.Exit(1) from None

    try:
        student = repository.get_student(student_id)
    except StudentNotFoundError:
        name = Prompt.ask("Nome do aluno", default=student_id)
        student = repository.create_student(student_id, name)

    session_id = session_id or f"cli-{student_id}-{uuid.uuid4().hex[:10]}"
    service = TutoringService(settings, repository)
    banner()
    console.print(
        f"Aluno: [bold]{student['display_name']}[/bold] · Sessão: [dim]{session_id}[/dim]\n"
        "Digite [cyan]/ajuda[/cyan] para comandos."
    )

    while True:
        try:
            message = Prompt.ask("\n[bold cyan]Você[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Sessão encerrada.[/dim]")
            return
        if not message:
            continue
        if message in {"/sair", "/exit", "/quit"}:
            console.print("[dim]Progresso salvo. Até a próxima.[/dim]")
            return
        if message == "/progresso":
            render_progress(repository.get_progress_snapshot(student_id))
            continue
        if message == "/modulos":
            show_modules()
            continue
        if message == "/ajuda":
            console.print("/progresso · /modulos · /sair")
            continue

        try:
            with console.status("[cyan]Algo Hands-On está analisando...[/cyan]", spinner="dots12"):
                turn = service.run_turn(
                    student_id=student_id,
                    session_id=session_id,
                    message=message,
                )
        except Exception as exc:
            console.print(Panel(str(exc), title="Falha ao executar o agente", border_style="red"))
            continue

        console.print(Panel(Markdown(turn.message_markdown), title="Algo Hands-On", border_style="cyan"))
        if turn.exercise:
            console.print(
                Panel(
                    Markdown(turn.exercise.statement),
                    title=f"Exercício — {turn.exercise.title}",
                    border_style="magenta",
                )
            )
        if turn.evaluation:
            evaluation = turn.evaluation
            style = "green" if evaluation.result.value == "correct" else "yellow"
            console.print(
                f"[{style}]Avaliação: {evaluation.result.value} · "
                f"nota {evaluation.score:.0%} · competência {evaluation.competency_key}[/{style}]"
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
        console.print("[red]Aluno não encontrado.[/red]")
        raise typer.Exit(1) from None
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]Exportado:[/green] {output.resolve()}")


@app.command()
def reset(
    student_id: str = typer.Option(..., "--student-id", "-s"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Reinicia o progresso pedagógico do aluno."""
    _, repository = runtime()
    if not yes and not Confirm.ask(f"Reiniciar todo o progresso de {student_id}?"):
        raise typer.Abort()
    try:
        repository.reset_student(student_id)
    except StudentNotFoundError:
        console.print("[red]Aluno não encontrado.[/red]")
        raise typer.Exit(1) from None
    console.print("[green]Progresso reiniciado.[/green]")


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

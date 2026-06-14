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
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Input, Static, TextArea

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
PLACEHOLDER_READY = "Digite sua mensagem ou /comando..."
PLACEHOLDER_THINKING = "Algo Hands-On está pensando..."

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


class ChatApp(App[None]):
    """TUI do chat com RichLog, status e input."""

    CSS = """
    #status {
        dock: top;
        width: 100%;
        height: auto;
        max-height: 5;
        padding: 1 2;
        border-bottom: solid #1748E8;
    }

    #history {
        width: 100%;
        height: 1fr;
        padding: 0 2;
    }

    #message {
        dock: bottom;
        width: 100%;
        height: 3;
        padding: 0 2;
        border-top: solid #1748E8;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Sair", show=True),
        Binding("ctrl+l", "clear_history", "Limpar tela", show=True),
    ]

    def __init__(
        self,
        *,
        settings,
        repository: ProgressRepository,
        service: TutoringService,
        student: dict,
        student_id: str,
        session_id: str,
        snapshot: dict,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.repository = repository
        self.service = service
        self.student = student
        self.student_id = student_id
        self.session_id = session_id
        self.snapshot = snapshot
        self.pending_skip_module: int | None = None
        self._streaming = False
        self._history_text = ""

    def compose(self) -> ComposeResult:
        yield Static(self._status_text(), id="status")
        yield TextArea(
            "",
            id="history",
            read_only=True,
            soft_wrap=True,
            show_line_numbers=False,
        )
        yield Input(id="message", placeholder="Digite sua mensagem ou /comando...")

    def on_mount(self) -> None:
        self._append("Bem-vindo ao Algo Hands-On!")
        self._append("Digite /ajuda para ver os comandos.")
        self._message.focus()

    @property
    def _history(self) -> TextArea:
        return self.query_one("#history", TextArea)

    @property
    def _message(self) -> Input:
        return self.query_one("#message", Input)

    @property
    def _status(self) -> Static:
        return self.query_one("#status", Static)

    def action_clear_history(self) -> None:
        self._history_text = ""
        self._history.load_text("")
        self._append("Tela limpa. Progresso salvo.")

    def _status_text(self) -> str:
        current = self.snapshot["current"]
        evidence = self.snapshot.get("evidence", [])
        module_progress = next(
            (m for m in self.snapshot["modules"] if m["module_id"] == current["current_module"]),
            {"mastery_score": 0.0},
        )
        mastery_pct = module_progress.get("mastery_score", 0.0) * 100
        bar_filled = int(mastery_pct / 10)
        bar = f"[{"#" * bar_filled}{"·" * (10 - bar_filled)}]"

        evidence_by_kind = {item["evidence_kind"]: item for item in evidence}
        checkpoint = "  ".join(
            f"[bold green]✓[/] {label}"
            if evidence_by_kind.get(kind, {}).get("satisfied")
            else f"[dim]○[/] {label}"
            for kind, label in EVIDENCE_DISPLAY_LABELS.items()
        )
        return (
            f"[bold #58a6ff]{current['module_title']}[/]  "
            f"[dim]Nível:[/] {INDEPENDENCE_LABELS.get(current['independence_level'], current['independence_level'])}  "
            f"[dim]Domínio:[/] {bar} {mastery_pct:.0f}%\n"
            f"[dim]Checkpoint:[/] {checkpoint}"
        )

    def _refresh_status(self) -> None:
        self.snapshot = self.repository.get_progress_snapshot(self.student_id)
        self._status.update(self._status_text())

    # ── escrita ──────────────────────────────────────────────────────────

    def _append(self, text: str) -> None:
        self._history_text += text
        self._history.load_text(self._history_text)
        self._history.scroll_end(animate=False)

    def _write_user(self, message: str) -> None:
        self._append(f"\nVoce: {message}")

    def _write_system(self, message: str) -> None:
        self._append(f"\n{message}")

    def _start_assistant(self) -> None:
        self._append("\nAlgo Hands-On: ")

    def _append_text(self, text: str) -> None:
        self._append(text)

    def _write_exercise(self, turn: TutorTurn) -> None:
        if not turn.exercise:
            return
        ex = turn.exercise
        text = f"\nExercicio: {ex.title}\n{ex.statement}"
        if ex.constraints:
            text += "\n\nRegras:\n" + "\n".join(f"  - {c}" for c in ex.constraints)
        self._append(text)

    def _write_evaluation(self, turn: TutorTurn) -> None:
        if not turn.evaluation:
            return
        ev = turn.evaluation
        self._append(
            f"\n{ev.result.value} | nota {ev.score:.0%} | {ev.competency_key}"
        )

    # ── processamento de mensagens ────────────────────────────────────────

    @on(Input.Submitted, "#message")
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        self._message.value = ""
        if not message:
            return

        if self.pending_skip_module is not None:
            self._handle_skip_confirmation(message)
            return

        if message in {"/sair", "/exit", "/quit"}:
            self.exit()
            return

        if message == "/limpar":
            self.action_clear_history()
            return

        if self._handle_local_command(message):
            return

        final_message = CONTEXTUAL_PREFIXES.get(message)
        if final_message:
            final_message = f"{final_message}\n\nMensagem do aluno: {message}"
        elif message.startswith("/"):
            self._write_system(f"[yellow]Comando desconhecido: {message}[/]")
            return
        else:
            final_message = message

        self._write_user(message)
        self._message.disabled = True
        self._message.placeholder = PLACEHOLDER_THINKING
        self._streaming = False
        self.run_worker(lambda: self._run_agent_turn(final_message), thread=True, exclusive=True)

    def _handle_local_command(self, message: str) -> bool:
        if message == "/progresso":
            self._refresh_status()
            self._write_system(f"[bold]Progresso[/]\n{_plain_progress(self.snapshot)}")
            return True
        if message == "/checkpoint":
            self._refresh_status()
            self._write_system(f"[bold]Checkpoint[/]\n{_plain_evidence(self.snapshot)}")
            return True
        if message == "/modulos":
            self._write_system(f"[bold]Módulos[/]\n{_plain_modules()}")
            return True
        if message == "/historico":
            self._write_system(f"[bold]Histórico[/]\n{_plain_history(self.student_id, self.repository)}")
            return True
        if message == "/sessoes":
            self._write_system(f"[bold]Sessões[/]\n{_plain_sessions(self.student_id, self.repository)}")
            return True
        if message == "/config":
            self._write_system(f"[bold]Configuração[/]\n{_plain_config(self.student, self.settings)}")
            return True
        if message == "/ajuda":
            self._write_system(f"[bold]Comandos[/]\n{_plain_commands()}")
            return True
        if message == "/pular":
            self._start_skip_confirmation()
            return True
        return False

    def _start_skip_confirmation(self) -> None:
        current_module = self.snapshot["current"]["current_module"]
        next_module = current_module + 1
        if next_module > LAST_MODULE_ID:
            self._write_system("Você já está no último módulo.")
            return

        target = get_module(next_module)
        self.pending_skip_module = next_module
        self._write_system(
            f"[yellow]Isso avançará para o módulo {next_module} ({target.title}).[/] "
            "Digite [bold]/sim[/] para confirmar ou [bold]/nao[/] para cancelar."
        )

    def _handle_skip_confirmation(self, message: str) -> None:
        next_module = self.pending_skip_module
        self.pending_skip_module = None
        if message.lower() not in {"/sim", "sim", "s", "yes", "y"}:
            self._write_system("Salto de módulo cancelado.")
            return
        if next_module is None:
            return

        target = get_module(next_module)
        self.repository.set_current_module(
            self.student_id,
            next_module,
            reason="skip_in_chat",
            session_id=self.session_id,
        )
        self._refresh_status()
        self._write_system(f"[green]Avançado para: {target.title}[/]")

    def _run_agent_turn(self, final_message: str) -> None:
        try:
            if self.settings.stream:
                final_turn: TutorTurn | None = None
                for event in self.service.run_turn_stream(
                    student_id=self.student_id,
                    session_id=self.session_id,
                    message=final_message,
                ):
                    event_type = event.get("type")
                    if event_type == "content":
                        if not self._streaming:
                            self._streaming = True
                            self.call_from_thread(self._start_assistant)
                        self.call_from_thread(self._append_text, event["text"])
                    elif event_type == "parsing":
                        pass  # evento interno, não exibe
                    elif event_type == "warning":
                        self.call_from_thread(
                            self._write_system, f"[yellow]Aviso: {event['text']}[/]"
                        )
                    elif event_type == "final":
                        final_turn = event["turn"]
                if final_turn is None:
                    msg = "Streaming terminou sem turno final validado. Tente novamente."
                    raise RuntimeError(msg)
                turn = final_turn
            else:
                turn = self.service.run_turn(
                    student_id=self.student_id,
                    session_id=self.session_id,
                    message=final_message,
                )
        except Exception as exc:
            self.call_from_thread(self._finish_agent_error, exc)
            return
        self.call_from_thread(self._finish_agent_turn, turn)

    def _finish_agent_turn(self, turn: TutorTurn) -> None:
        if not self._streaming:
            self._append(f"\nAlgo Hands-On: {turn.message_markdown}")
        self._write_exercise(turn)
        self._write_evaluation(turn)
        self._refresh_status()
        self._message.disabled = False
        self._message.placeholder = PLACEHOLDER_READY
        self._streaming = False
        self._message.focus()

    def _finish_agent_error(self, exc: Exception) -> None:
        self._write_system(f"[red]Falha ao executar o agente: {exc}[/]")
        self._message.disabled = False
        self._message.placeholder = PLACEHOLDER_READY
        self._streaming = False
        self._message.focus()


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

        ChatApp(
            settings=settings,
            repository=repository,
            service=service,
            student=student_check,
            student_id=student_id,
            session_id=session_id,
            snapshot=snapshot,
        ).run()
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
        ChatApp(
            settings=settings,
            repository=repository,
            service=service,
            student=student,
            student_id=student_id,
            session_id=session_id,
            snapshot=snapshot,
        ).run()
        console.print("[dim]Progresso salvo. Até a próxima.[/dim]")
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

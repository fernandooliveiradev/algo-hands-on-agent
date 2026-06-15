from __future__ import annotations

from typing import Any

from rich.markdown import Markdown as RichMarkdown
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Header, Input, ProgressBar, Static

from algo_hands_on.chat_core import (
    INDEPENDENCE_LABELS,
    UNDEFINED_COMPETENCY,
    ChatContext,
    handle_chat_command,
    module_progress_facts,
    persisted_progress_notice,
    prepare_agent_message,
    turn_history_text,
)
from algo_hands_on.db.repository import ProgressRepository
from algo_hands_on.services.tutoring import AGENT_OPERATIONAL_ERRORS, TutoringService


class TutorTui(App[None]):
    """TUI Textual para conversa com streaming real do agente."""

    CSS = """
    Screen {
        background: #101216;
        color: #e9edf3;
    }

    #top {
        dock: top;
        height: 7;
        padding: 0 1;
        background: #171b22;
        border-bottom: solid #2c3442;
    }

    #status {
        height: 2;
        content-align: left middle;
        text-style: bold;
    }

    #progress {
        height: 1;
        margin: 0 0 1 0;
    }

    #checkpoint {
        height: 2;
        color: #b9c3d1;
    }

    #history {
        padding: 1 2;
        height: 1fr;
    }

    #composer {
        dock: bottom;
        height: 4;
        padding: 0 1;
        background: #171b22;
        border-top: solid #2c3442;
    }

    Input {
        height: 3;
        width: 100%;
    }

    .message {
        width: 100%;
        margin-bottom: 1;
        padding: 1 2;
        border: solid #2c3442;
    }

    .user {
        background: #182134;
        border-title-color: #8fb3ff;
    }

    .assistant {
        background: #151b1a;
        border-title-color: #8fd8b4;
    }

    .system {
        background: #1d1a13;
        color: #f0d58a;
        border-title-color: #f0d58a;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Sair"),
        ("ctrl+l", "clear_history", "Limpar"),
    ]

    def __init__(
        self,
        *,
        settings: Any,
        repository: ProgressRepository,
        service: TutoringService,
        student: dict,
        student_id: str,
        session_id: str,
        snapshot: dict,
    ) -> None:
        super().__init__()
        self.context = ChatContext(
            settings=settings,
            repository=repository,
            student=student,
            student_id=student_id,
            session_id=session_id,
            snapshot=snapshot,
        )
        self.service = service
        self.title = "Algo Hands-On"
        self.sub_title = student["display_name"]
        self._busy = False
        self._pending_skip = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="top"):
            yield Static(id="status")
            yield ProgressBar(total=100, show_eta=False, id="progress")
            yield Static(id="checkpoint")
        yield VerticalScroll(id="history")
        with Container(id="composer"):
            yield Input(placeholder="Digite sua mensagem ou /ajuda", id="input")

    def on_mount(self) -> None:
        self._refresh_header()
        notice = persisted_progress_notice(self.context.snapshot)
        if notice:
            self._add_system(
                f"{notice}\n\nSession ID: {self.context.session_id}"
            )
        else:
            self._add_system(
                "Sessão pronta. Digite /ajuda para comandos, /sair para encerrar.\n\n"
                f"Session ID: {self.context.session_id}"
            )
        self.query_one("#input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        event.input.value = ""

        if not message:
            return
        if self._busy:
            self._add_system("Aguarde a resposta atual terminar antes de enviar outra mensagem.")
            return

        if self._pending_skip:
            if message == "/confirmar-pular":
                self._pending_skip = False
                result = handle_chat_command(self.context, "/pular", confirm_skip=True)
                if result:
                    self._add_system(result.text)
                    self._refresh_header()
                return
            if message == "/cancelar":
                self._pending_skip = False
                self._add_system("Avanço cancelado.")
                return

        command = handle_chat_command(self.context, message)
        if command:
            if command.action == "exit":
                self.exit()
                return
            if command.action == "clear":
                self.action_clear_history()
                return
            if command.action == "confirm_skip":
                self._pending_skip = True
                self._add_system(f"{command.text}\nDigite /confirmar-pular ou /cancelar.")
                return
            self._add_system(command.text)
            self._refresh_header()
            return

        agent_message = prepare_agent_message(message)
        if agent_message is None:
            self._add_system(f"Comando não reconhecido: {message}")
            return

        self._add_user(message)
        self.run_worker(
            lambda: self._run_agent_turn(agent_message),
            name="agent-turn",
            thread=True,
            exclusive=True,
        )

    def action_clear_history(self) -> None:
        history = self.query_one("#history", VerticalScroll)
        history.remove_children()
        self._add_system("Tela limpa. A sessão e o progresso continuam salvos.")

    def _run_agent_turn(self, agent_message: str) -> None:
        self.call_from_thread(self._set_busy, True)
        assistant = self.call_from_thread(self._start_assistant_message)
        chunks: list[str] = []

        try:
            if self.context.settings.stream:
                for event in self.service.run_turn_stream(
                    student_id=self.context.student_id,
                    session_id=self.context.session_id,
                    message=agent_message,
                ):
                    event_type = event.get("type")
                    if event_type == "content":
                        chunks.append(str(event.get("text", "")))
                        self.call_from_thread(self._update_message, assistant, "".join(chunks))
                    elif event_type == "parsing":
                        self.call_from_thread(self._set_input_placeholder, "Validando resposta...")
                    elif event_type == "warning":
                        self.call_from_thread(self._add_system, str(event.get("text", "")))
                    elif event_type == "final":
                        turn = event["turn"]
                        self.call_from_thread(self._update_message, assistant, turn_history_text(turn))
            else:
                turn = self.service.run_turn(
                    student_id=self.context.student_id,
                    session_id=self.context.session_id,
                    message=agent_message,
                )
                self.call_from_thread(self._update_message, assistant, turn_history_text(turn))
        except AGENT_OPERATIONAL_ERRORS as exc:
            self.call_from_thread(self._update_message, assistant, f"Erro ao executar o agente: {exc}")
        finally:
            self.call_from_thread(self.context.refresh)
            self.call_from_thread(self._refresh_header)
            self.call_from_thread(self._set_busy, False)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        input_widget = self.query_one("#input", Input)
        input_widget.disabled = busy
        self._set_input_placeholder(
            "Algo Hands-On está pensando..." if busy else "Digite sua mensagem ou /ajuda"
        )

    def _set_input_placeholder(self, text: str) -> None:
        self.query_one("#input", Input).placeholder = text

    def _refresh_header(self) -> None:
        snapshot = self.context.snapshot
        current = snapshot["current"]
        module_score = self._current_module_score(snapshot)
        level = INDEPENDENCE_LABELS.get(
            current["independence_level"],
            current["independence_level"],
        )
        competency = current["current_competency"] or UNDEFINED_COMPETENCY

        self.query_one("#status", Static).update(
            f"{self.context.student['display_name']} | "
            f"Módulo {current['current_module']}: {current['module_title']} | "
            f"Nível: {level} | Competência: {competency}",
            layout=False,
        )
        self.query_one("#progress", ProgressBar).update(progress=module_score * 100)
        self.query_one("#checkpoint", Static).update(self._checkpoint_line(snapshot), layout=False)

    def _checkpoint_line(self, snapshot: dict) -> str:
        facts = module_progress_facts(snapshot)
        return (
            f"Média atual: {facts['average'] * 100:.0f}% | Meta de avanço: {facts['target'] * 100:.0f}%\n"
            f"Cobertura: {facts['coverage']}/{facts['total']} evidências | "
            f"Na meta: {facts['evidence_at_target']}/{facts['total']}"
        )

    def _current_module_score(self, snapshot: dict) -> float:
        current_module = snapshot["current"]["current_module"]
        for row in snapshot["modules"]:
            if row["module_id"] == current_module:
                return float(row["mastery_score"])
        return 0.0

    def _start_assistant_message(self) -> Static:
        return self._add_message("Algo Hands-On", "Pensando...", "assistant", markdown=True)

    def _add_user(self, text: str) -> None:
        self._add_message("Você", text, "user")

    def _add_system(self, text: str) -> None:
        self._add_message("Sistema", text, "system")

    def _add_message(
        self,
        title: str,
        text: str,
        css_class: str,
        *,
        markdown: bool = False,
    ) -> Static:
        content = RichMarkdown(text) if markdown else text
        widget = Static(content, classes=f"message {css_class}", markup=False)
        widget.border_title = title
        history = self.query_one("#history", VerticalScroll)
        history.mount(widget)
        history.scroll_end(animate=False, force=True)
        return widget

    def _update_message(self, widget: Static, text: str) -> None:
        widget.update(RichMarkdown(text), layout=True)
        self.query_one("#history", VerticalScroll).scroll_end(animate=False, force=True)

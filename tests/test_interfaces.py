import asyncio

import pytest

from algo_hands_on.config import Settings
from algo_hands_on.db.repository import ProgressRepository


class DummyService:
    """Serviço vazio para montar a TUI sem chamar o agente."""


def test_tui_input_fits_bottom_composer(repository: ProgressRepository, tmp_path) -> None:
    asyncio.run(_assert_tui_input_fits_bottom_composer(repository, tmp_path))


async def _assert_tui_input_fits_bottom_composer(
    repository: ProgressRepository,
    tmp_path,
) -> None:
    pytest.importorskip("textual", reason="Textual não está instalado neste runner.")
    from textual.containers import Container
    from textual.widgets import Footer, Input

    from algo_hands_on.tui import TutorTui

    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        deepseek_api_key="test",
        db_path=tmp_path / "aho.db",
    )
    student = repository.create_student("fernando", "Fernando")
    app = TutorTui(
        settings=settings,
        repository=repository,
        service=DummyService(),
        student=student,
        student_id="fernando",
        session_id="sessao",
        snapshot=repository.get_progress_snapshot("fernando"),
    )

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        composer = app.query_one("#composer", Container)
        input_widget = app.query_one("#input", Input)

        assert list(app.query(Footer)) == []
        assert input_widget.has_focus
        assert input_widget.region.height == 3
        assert input_widget.region.y >= composer.content_region.y
        assert input_widget.region.y + input_widget.region.height <= (
            composer.content_region.y + composer.content_region.height
        )


def test_tui_assistant_message_uses_markdown_renderer(
    repository: ProgressRepository,
    tmp_path,
) -> None:
    asyncio.run(_assert_tui_assistant_message_uses_markdown_renderer(repository, tmp_path))


async def _assert_tui_assistant_message_uses_markdown_renderer(
    repository: ProgressRepository,
    tmp_path,
) -> None:
    pytest.importorskip("textual", reason="Textual não está instalado neste runner.")
    from textual.visual import RichVisual

    from algo_hands_on.tui import TutorTui

    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        deepseek_api_key="test",
        db_path=tmp_path / "aho.db",
    )
    student = repository.create_student("maria", "Maria")
    app = TutorTui(
        settings=settings,
        repository=repository,
        service=DummyService(),
        student=student,
        student_id="maria",
        session_id="sessao",
        snapshot=repository.get_progress_snapshot("maria"),
    )

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assistant = app._start_assistant_message()
        app._update_message(assistant, "Texto com **negrito**.")

        assert isinstance(assistant.visual, RichVisual)

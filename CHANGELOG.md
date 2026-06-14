# Changelog

## 0.1.0 — 2026-06-14

- Estrutura inicial com Agno Framework.
- Modelo DeepSeek configurável.
- Skills locais carregadas por `Skills` e `LocalSkills`.
- Sessões persistidas por `SqliteDb`.
- Progresso pedagógico persistido em tabelas SQLite próprias.
- CLI com Typer e Rich.
- API FastAPI integrada ao AgentOS e executável com Uvicorn.
- Saída estruturada com Pydantic e JSON mode.
- Trilha canônica em 17 módulos.

## 0.1.1 - Correção de distribuição

- Removido `uv.lock` gerado em índice privado de build.
- A primeira execução de `uv sync` passa a gerar o lock no ambiente do usuário usando o índice configurado localmente (PyPI por padrão).

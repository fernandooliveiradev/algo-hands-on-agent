# Changelog

## 0.2.0 — CLI 2.0 — 2026-06-14

### Adicionado
- **Tela inicial** com barra de progresso Rich e indicadores das 5 evidências do checkpoint.
- **Streaming** de respostas (`AHO_STREAM=true`): conteúdo aparece progressivamente no terminal.
- **Streaming de eventos** (`AHO_STREAM_EVENTS=true`): estados amigáveis de processamento.
- **11 novos comandos no chat**: `/continuar`, `/revisar`, `/exercicio`, `/dica`, `/exemplo`, `/checkpoint`, `/historico`, `/sessoes`, `/config`, `/limpar`, `/pular`.
- **Listagem e retomada de sessões** por `student_id` com isolamento entre alunos.
- **Resumos automáticos** de sessão (`AHO_SESSION_SUMMARIES=true`, `AHO_HISTORY_RUNS=3`).
- **Memória automática** de preferências do aluno (`AHO_MEMORY=true`).
- **Pre-hooks e post-hooks** (`hooks.py`): validação de contexto pré-execução e auditoria pós-resposta.
- **Confirmações** para ações destrutivas: reset, skip de módulo, pular no chat.
- **Comando `aho skip-module`** para avanço controlado com registro de auditoria.
- **Novos métodos no repositório**: `list_sessions`, `get_recent_events`, `delete_session_events`.
- **Arquivo `HELP.md`** com guia completo de uso e referência de comandos.

### Alterado
- `AHO_HISTORY_RUNS` padrão reduzido de 8 para 3.
- `EVIDENCE_LABELS` movido para `schemas.py` como propriedade `EvidenceKind.display_label`.
- `TutoringService` refatorado com `_finalize_turn()` eliminando duplicação entre `run_turn` e `run_turn_stream`.
- CLI refatorada com helpers `_panel()`, `_markdown_panel()`, `_commands_panel()`, `_student_not_found()`.
- `ensure_student()` simplificado para retornar `None`.
- README atualizado com documentação completa da CLI 2.0.

### Removido
- `MODULE_BY_SLUG` não utilizado em `curriculum.py`.
- `src/algo_hands_on_agent.egg-info/` removido do tracking do Git.
- Duplicações de código na CLI e no serviço de tutoria.

## 0.1.1 — Correção de distribuição — 2026-06-14

- Removido `uv.lock` gerado em índice privado de build.
- A primeira execução de `uv sync` passa a gerar o lock no ambiente do usuário usando o índice configurado localmente (PyPI por padrão).

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

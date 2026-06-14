# Algo Hands-On Agent

**Pense. Resolva. Construa.**

Tutor adaptativo de pensamento computacional, lógica de programação, algoritmos e Python construído com **Agno Framework**, **DeepSeek**, **SQLite**, **FastAPI/Uvicorn**, **Typer**, **Rich** e **Textual**.

## Arquitetura

- **Agno `SqliteDb`**: sessões, memória, resumos e metadados de execução do agente.
- **Tabelas `aho_*`**: progresso curricular, competências, tentativas e evidências (fonte de verdade pedagógica).
- **Skills Agno**: comportamento pedagógico carregado sob demanda.
- **Saída Pydantic**: contrato validado entre o LLM e a aplicação (JSON mode).
- **Serviço de progresso**: única camada autorizada a alterar domínio e avanço.
- **CLI**: interface interativa com streaming, tela inicial com barra de progresso e checkpoints.
- **API + AgentOS**: integração HTTP e endpoints nativos do Agno.

## Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Chave da API DeepSeek

## Instalação

```bash
cp .env.example .env
# edite DEEPSEEK_API_KEY no arquivo .env

uv sync --extra dev
```

O pacote inclui `uv.lock` para instalações reproduzíveis.

## Diagnóstico

```bash
uv run aho doctor
```

## Uso rápido

```bash
# criar aluno
uv run aho setup --student-id fernando --name "Fernando"

# abrir o tutor interativo
uv run aho chat --student-id fernando

# consultar progresso
uv run aho progress --student-id fernando

# continuar uma sessão anterior
uv run aho chat --student-id fernando --session-id cli-fernando-abc123

# pular módulo (requer confirmação)
uv run aho skip-module --student-id fernando --module 3

# exportar histórico completo
uv run aho export --student-id fernando --output progress-export-fernando.json

# reiniciar progresso (requer confirmação)
uv run aho reset --student-id fernando
```

## Comandos dentro do chat

A CLI 2.0 oferece uma tela inicial com progresso, barra de domínio e evidências do checkpoint. Durante a conversa, você pode usar:

| Comando | Ação |
|---------|------|
| `/progresso` | Mostrar progressão curricular completa |
| `/checkpoint` | Ver evidências do módulo atual (5 tipos) |
| `/modulos` | Listar todos os 17 módulos da trilha |
| `/historico` | Últimas tentativas e avaliações |
| `/sessoes` | Listar sessões anteriores do aluno |
| `/continuar` | Continuar estudos no módulo atual |
| `/revisar` | Revisar conteúdo anterior |
| `/exercicio` | Solicitar novo exercício prático |
| `/dica` | Pedir dica sem revelar a resposta |
| `/exemplo` | Pedir exemplo relacionado ao conteúdo |
| `/config` | Ver configurações e preferências |
| `/limpar` | Limpar a tela |
| `/pular` | Avançar para o próximo módulo (requer confirmação) |
| `/ajuda` | Listar todos os comandos |
| `/sair` | Encerrar a sessão |

Veja [HELP.md](HELP.md) para um guia detalhado de uso.

## Streaming e experiência

- As respostas do tutor aparecem **progressivamente** no terminal (streaming).
- A tela inicial mostra módulo atual, nível de independência, barra de domínio e as 5 evidências do checkpoint.
- Eventos internos são traduzidos em feedback curto; logs detalhados exigem `AHO_DEBUG=true`.
- Ações destrutivas (reset, skip, pular) exigem **confirmação explícita**.

## API e AgentOS

```bash
uv run aho serve --reload
```

Documentação Swagger: `http://127.0.0.1:7777/docs`

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Status do serviço |
| `POST` | `/api/v1/students` | Criar aluno |
| `GET` | `/api/v1/students/{id}/progress` | Progresso do aluno |
| `POST` | `/api/v1/tutor/turn` | Enviar mensagem ao tutor |
| `POST` | `/api/v1/students/{id}/reset` | Reiniciar progresso |

O AgentOS registra endpoints nativos adicionais para o agente.

### Exemplo de requisição

```bash
curl -X POST http://127.0.0.1:7777/api/v1/tutor/turn \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "fernando",
    "session_id": "estudo-001",
    "message": "Quero começar do zero"
  }'
```

## Progresso pedagógico

O banco SQLite usa transações, WAL, chaves estrangeiras e migrações idempotentes.

Tabelas do domínio pedagógico (`aho_*`):

- `aho_students` — identidade e preferências
- `aho_student_progress` — posição atual e nível de independência
- `aho_module_progress` — estado e nota de cada módulo
- `aho_competency_progress` — evidências por competência
- `aho_exercise_attempts` — cada tentativa avaliada
- `aho_module_evidence` — 5 evidências por módulo
- `aho_learning_events` — trilha de auditoria

O LLM **não** altera diretamente o banco. Ele retorna uma `TutorTurn` validada por Pydantic. O `TutoringService` valida a evidência e só então grava a transação.

### Regra de domínio

Um módulo é concluído quando as **cinco evidências** abaixo foram demonstradas **sem dica** e com **nota >= 0.8**:

1. Aplicação direta
2. Aplicação independente
3. Integração
4. Diagnóstico
5. Explicação/transferência

Acertos com dica são registrados mas **não** concluem a evidência.

## Configuração

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DEEPSEEK_API_KEY` | (obrigatório) | Chave da API DeepSeek |
| `DEEPSEEK_MODEL` | `deepseek-chat` | Modelo a ser usado |
| `AHO_DB_PATH` | `./data/aho.db` | Caminho do banco SQLite |
| `AHO_SKILLS_DIR` | `./skills` | Diretório de skills |
| `AHO_HISTORY_RUNS` | `3` | Runs mantidos em contexto |
| `AHO_SESSION_SUMMARIES` | `true` | Resumos automáticos de sessão |
| `AHO_MEMORY` | `true` | Memória de preferências do aluno |
| `AHO_STREAM` | `true` | Streaming de resposta |
| `AHO_STREAM_EVENTS` | `true` | Eventos de streaming |
| `AHO_DEBUG` | `false` | Logs detalhados |
| `AHO_HOST` | `127.0.0.1` | Host da API |
| `AHO_PORT` | `7777` | Porta da API |

## Testes

```bash
uv run pytest
uv run ruff check .
```

## Estrutura

```text
algo-hands-on-agent/
├── skills/                    # Skills pedagógicas (Agno LocalSkills)
├── src/algo_hands_on/
│   ├── db/                    # SQLite: schema, conexão, repositório
│   ├── services/              # TutoringService (orquestrador)
│   ├── agent_factory.py       # Construtor do agente Agno
│   ├── api.py                 # FastAPI + AgentOS
│   ├── cli.py                 # CLI com Typer + Rich + Textual
│   ├── config.py              # Configuração (pydantic-settings)
│   ├── curriculum.py          # 17 módulos da trilha
│   ├── hooks.py               # Pre/post hooks de validação
│   └── schemas.py             # Schemas Pydantic (TutorTurn, etc.)
├── tests/
├── scripts/bootstrap.sh       # Setup de primeiro uso
├── TRILHA-AHO.md              # Currículo canônico completo
├── HELP.md                    # Guia detalhado de uso
├── AGENTS.md                  # Contrato do agente
├── pyproject.toml
└── .env.example
```

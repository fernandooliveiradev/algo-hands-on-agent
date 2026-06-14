# Algo Hands-On Agent

**Pense. Resolva. Construa.**

Tutor adaptativo de pensamento computacional, lógica de programação, algoritmos e Python construído com **Agno Framework**, **DeepSeek**, **SQLite**, **FastAPI/Uvicorn**, **Typer** e **Rich**.

## Arquitetura

O projeto separa claramente:

- **Agno `SqliteDb`**: sessões, histórico e metadados de execução do agente;
- **tabelas `aho_*`**: progresso curricular, competências, tentativas e evidências;
- **skills Agno**: comportamento pedagógico carregado sob demanda;
- **saída Pydantic**: contrato validado entre o LLM e a aplicação;
- **serviço de progresso**: única camada autorizada a alterar domínio e avanço;
- **CLI**: interface interativa para estudo local;
- **API + AgentOS**: integração HTTP e endpoints nativos do Agno.

## Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- chave da API DeepSeek

## Instalação

```bash
cp .env.example .env
# edite DEEPSEEK_API_KEY

uv sync --extra dev

> O pacote distribuído não inclui `uv.lock`. Na primeira instalação, o `uv` gera um lock local usando o PyPI público, evitando referências a índices privados do ambiente de build.
```

## Diagnóstico

```bash
uv run aho doctor
```

## Criar aluno

```bash
uv run aho setup --student-id fernando --name "Fernando"
```

## Abrir o tutor no terminal

```bash
uv run aho chat --student-id fernando
```

Comandos dentro do chat:

```text
/progresso
/modulos
/ajuda
/sair
```

## Consultar progresso

```bash
uv run aho progress --student-id fernando
```

## Executar API com Uvicorn

```bash
uv run uvicorn algo_hands_on.api:app --host 127.0.0.1 --port 7777 --reload
```

Ou:

```bash
uv run aho serve --reload
```

Documentação local:

```text
http://127.0.0.1:7777/docs
```

## Endpoints próprios

- `GET /health`
- `POST /api/v1/students`
- `GET /api/v1/students/{student_id}/progress`
- `POST /api/v1/tutor/turn`
- `POST /api/v1/students/{student_id}/reset`

O AgentOS também registra seus endpoints nativos para o agente.

## Exemplo de requisição

```bash
curl -X POST http://127.0.0.1:7777/api/v1/tutor/turn \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "fernando",
    "session_id": "estudo-001",
    "message": "Quero começar do zero"
  }'
```

## Como o progresso é salvo

O banco usa transações, chaves estrangeiras, WAL, `busy_timeout`, índices e migrações idempotentes.

Tabelas principais:

- `aho_students`: identidade e preferências;
- `aho_student_progress`: posição atual e nível de independência;
- `aho_module_progress`: estado e nota de cada módulo;
- `aho_competency_progress`: evidências por competência;
- `aho_exercise_attempts`: cada tentativa avaliada;
- `aho_learning_events`: trilha de auditoria;
- tabelas do Agno: sessões, memórias, métricas e histórico.

O LLM não altera diretamente o banco. Ele retorna uma `TutorTurn` validada por Pydantic. O `ProgressService` valida a evidência e só então grava a transação.

## Regra de domínio

Um módulo é concluído quando as cinco evidências abaixo foram demonstradas sem dica e com nota mínima de 0,8:

1. aplicação direta;
2. aplicação independente;
3. integração;
4. diagnóstico;
5. explicação ou transferência.

Acertos com dica são registrados, mas não concluem a evidência.

## Testes

```bash
uv run pytest
uv run ruff check .
```

## Estrutura

```text
algo-hands-on-agent/
├── skills/
├── src/algo_hands_on/
│   ├── db/
│   ├── services/
│   ├── agent_factory.py
│   ├── api.py
│   ├── cli.py
│   ├── curriculum.py
│   └── schemas.py
├── tests/
├── TRILHA-AHO.md
├── AGENTS.md
├── pyproject.toml
└── .env.example
```

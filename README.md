# Algo Hands-On Agent

**Pense. Resolva. Construa.**

Tutor adaptativo de pensamento computacional, lógica de programação, algoritmos e Python construído com **Agno Framework**, **DeepSeek**, **SQLite**, **FastAPI/Uvicorn**, **Typer**, **Rich** e **Textual**.

## Arquitetura

- **Agno `SqliteDb`**: sessões, memória, resumos e metadados de execução do agente.
- **Tabelas `aho_*`**: progresso curricular, competências, tentativas e evidências (fonte de verdade pedagógica).
- **Skills Agno**: comportamento pedagógico carregado sob demanda.
- **Saída Pydantic**: contrato validado entre o LLM e a aplicação; no chat com streaming, um agente parser interno estrutura o turno após o tutor transmitir a resposta ao aluno.
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

> 💡 **Você escolhe** seu `--student-id` (um apelido curto, tipo `aluno123` ou `maria`) e `--name` (seu nome como quer ser chamado).
> Depois de criado, use o mesmo `--student-id` em todos os comandos.
> Se esquecer qual ID usou, execute `uv run aho students` para listar todos.

```bash
# 1. Primeiro passo: criar seu aluno (escolha seu ID e nome)
uv run aho setup --student-id aluno123 --name "Maria Silva"

# 2. Abrir o tutor interativo
uv run aho chat --student-id aluno123

# 3. Depois, consultar seu progresso
uv run aho progress --student-id aluno123

# 4. Continuar uma sessão anterior (o session-id aparece na tela inicial)
uv run aho chat --student-id aluno123 --session-id cli-aluno123-a1b2c3d4e5

# 5. Pular módulo (requer confirmação)
uv run aho skip-module --student-id aluno123 --module 3

# 6. Exportar histórico completo
uv run aho export --student-id aluno123 --output meu-progresso.json

# 7. Reiniciar progresso (requer confirmação)
uv run aho reset --student-id aluno123

# 8. Limpar TODO o banco para começar do zero (requer confirmação)
uv run aho clean
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

### Comandos do terminal

| Comando | Descrição |
|---------|-----------|
| `aho setup` | Criar ou atualizar um aluno |
| `aho chat` | Iniciar o tutor interativo (TUI Textual) |
| `aho students` | Menu interativo: listar, conversar, progresso, exportar |
| `aho progress` | Consultar progressão curricular |
| `aho modules` | Listar os 17 módulos da trilha |
| `aho skip-module` | Pular para um módulo (requer confirmação) |
| `aho reset` | Reiniciar progresso de um aluno |
| `aho export` | Exportar histórico completo em JSON |
| `aho clean` | Limpar TODO o banco (alunos, progresso, memórias) |
| `aho doctor` | Validar ambiente, banco e skills |
| `aho serve` | Iniciar API REST + AgentOS |

## Streaming e experiência

- TUI construída com **Textual**: status bar com barra de domínio e checkpoint, histórico rolável com scroll automático, input fixo no rodapé.
- As respostas do tutor aparecem **progressivamente** no terminal (streaming).
- Durante o processamento, o placeholder do input muda para "Algo Hands-On está pensando...".
- Atalhos de teclado: `Ctrl+C` sair, `Ctrl+L` limpar tela.
- Ações destrutivas (reset, skip, pular, clean) exigem **confirmação explícita**.
- Eventos internos são traduzidos em feedback curto; logs detalhados exigem `AHO_DEBUG=true`.

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
    "student_id": "aluno123",
    "session_id": "estudo-001",
    "message": "Quero começar do zero"
  }'
```

## Progresso pedagógico

O banco SQLite usa transações, WAL, chaves estrangeiras e migrações idempotentes.

Arquivos locais de banco e histórico ficam fora do GitHub por padrão: `.gitignore` bloqueia `data/*`, `*.db`, `*.db-wal`, `*.db-shm`, exports de progresso/sessão/chat, logs e caches. Apenas `data/.gitkeep` é versionado para manter a pasta no projeto.

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
| `DEEPSEEK_MODEL` | `deepseek-chat` | Modelo DeepSeek (ex: `deepseek-chat`, `deepseek-v4-flash`) |
| `AHO_DB_PATH` | `./data/aho.db` | Caminho do banco SQLite |
| `AHO_SKILLS_DIR` | `./skills` | Diretório de skills pedagógicas |
| `AHO_HISTORY_RUNS` | `3` | Mensagens mantidas em contexto por turno |
| `AHO_MEMORY` | `true` | Memória de preferências do aluno (Agno) |
| `AHO_SESSION_SUMMARIES` | `true` | Resumos automáticos de conversas longas |
| `AHO_STREAM` | `true` | Streaming de resposta no chat |
| `AHO_DEBUG` | `false` | Logs detalhados no terminal |
| `AHO_TELEMETRY` | `false` | Telemetria do Agno |
| `AHO_LOG_LEVEL` | `INFO` | Nível de log (DEBUG, INFO, WARNING, ERROR) |
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
├── skills/                           # 10 skills pedagógicas (Agno LocalSkills)
│   ├── aho-start-here/               #   Módulo 0 — Entrada e diagnóstico
│   ├── aho-stage-router/             #   Roteamento curricular
│   ├── aho-curriculum-path/          #   Planejamento e nivelamento
│   ├── aho-tutor-core/               #   Núcleo pedagógico (todos os módulos)
│   ├── aho-guided-lessons/           #   Motor de prática e checkpoint
│   ├── aho-computational-thinking/   #   Módulo 1 — Pensamento computacional
│   ├── aho-algorithm-representation/ #   Módulo 2 — Algoritmos e pseudocódigo
│   ├── aho-python-foundations/       #   Módulos 3–8 — Fundamentos de Python
│   ├── aho-algorithms-data-structures/ # Módulos 9–10, 13 — Algoritmos
│   └── aho-portfolio-projects/       #   Módulos 11–12, 14–16 — Projetos
├── src/algo_hands_on/
│   ├── db/                           # SQLite: schema, conexão, repositório
│   ├── services/                     # TutoringService (orquestrador)
│   ├── agent_factory.py              # Construtor do agente Agno + parser
│   ├── api.py                        # FastAPI + AgentOS
│   ├── cli.py                        # CLI (Typer) + TUI (Textual)
│   ├── config.py                     # Configuração (pydantic-settings)
│   ├── curriculum.py                 # 17 módulos da trilha
│   ├── hooks.py                      # Pre/post hooks de validação
│   └── schemas.py                    # Schemas Pydantic (TutorTurn, etc.)
├── tests/
├── scripts/bootstrap.sh              # Setup de primeiro uso
├── TRILHA-AHO.md                     # Currículo canônico completo
├── HELP.md                           # Guia detalhado de uso
├── AGENTS.md                         # Contrato do agente
├── pyproject.toml
└── .env.example
```

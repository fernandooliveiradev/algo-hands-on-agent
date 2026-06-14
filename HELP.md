# Guia de Uso — Algo Hands-On CLI 2.0

Guia completo para usar o tutor Algo Hands-On no terminal.

## Índice

- [Primeira execução](#primeira-execução)
- [Comandos do terminal](#comandos-do-terminal)
- [Comandos dentro do chat](#comandos-dentro-do-chat)
- [Tela inicial](#tela-inicial)
- [Checkpoint e evidências](#checkpoint-e-evidências)
- [Sessões](#sessões)
- [Streaming](#streaming)
- [Uso rápido sem sincronização](#uso-rápido-sem-sincronização)
- [Configuração avançada](#configuração-avançada)
- [Resolução de problemas](#resolução-de-problemas)

## Primeira execução

```bash
# 1. Clone o repositório e entre na pasta
git clone https://github.com/fernandooliveiradev/algo-hands-on-agent.git
cd algo-hands-on-agent

# 2. Copie o arquivo de ambiente
cp .env.example .env

# 3. Edite .env e configure sua chave DeepSeek

# 4. Instale as dependências
uv sync --extra dev

# 5. Execute o diagnóstico
uv run aho doctor

# 6. Crie seu aluno
uv run aho setup --student-id maria --name "Maria Silva"

# 7. Inicie o tutor
uv run aho chat --student-id maria
```

## Comandos do terminal

### `aho setup`
Cria um novo aluno ou atualiza um existente.

```bash
uv run aho setup --student-id maria --name "Maria Silva"
```

### `aho chat`
Inicia a CLI interativa do tutor.

```bash
# Nova conversa
uv run aho chat --student-id maria

# Continuar sessão anterior
uv run aho chat --student-id maria --session-id cli-maria-a1b2c3d4e5
```

### `aho progress`
Mostra a progressão curricular completa em tabela.

```bash
uv run aho progress --student-id maria
```

### `aho modules`
Lista os 17 módulos da trilha canônica.

```bash
uv run aho modules
```

### `aho skip-module`
Avança o aluno para um módulo específico. **Requer confirmação.**

```bash
uv run aho skip-module --student-id maria --module 5

# Pular sem confirmação interativa
uv run aho skip-module --student-id maria --module 5 --yes
```

### `aho reset`
Reinicia todo o progresso do aluno. **Requer confirmação.**

```bash
uv run aho reset --student-id maria
uv run aho reset --student-id maria --yes   # sem confirmação
```

### `aho export`
Exporta o histórico pedagógico completo como JSON.

```bash
uv run aho export --student-id maria --output progress-export-maria.json
```

### `aho doctor`
Valida ambiente: Python, chave API, banco SQLite, skills, streaming, resumos, memória.

```bash
uv run aho doctor
```

### `aho serve`
Inicia a API REST e o AgentOS com Uvicorn.

```bash
uv run aho serve --reload
uv run aho serve --host 0.0.0.0 --port 8080
```

## Comandos dentro do chat

Ao executar `aho chat`, você entra em uma conversa interativa com o tutor. A tela inicial mostra seu progresso e os comandos disponíveis.

### Comandos informativos (não passam pelo agente)

| Comando | Descrição |
|---------|-----------|
| `/progresso` | Tabela completa com todos os módulos, estados e percentuais |
| `/checkpoint` | Evidências do módulo atual com notas e status (✓/✗) |
| `/modulos` | Lista os 17 módulos da trilha |
| `/historico` | Últimas 10 tentativas com resultado, nota, e data |
| `/sessoes` | Sessões anteriores do aluno (ID, mensagens, última atividade) |
| `/config` | Configuração atual: streaming, resumos, memória, modelo |
| `/ajuda` | Lista completa de comandos disponíveis |
| `/limpar` | Limpa a tela e reexibe a tela inicial |
| `/sair` | Encerra a sessão (progresso é salvo automaticamente) |

### Comandos de estudo (enviados ao agente)

| Comando | Comportamento |
|---------|---------------|
| `/continuar` | Pede ao tutor para guiar o próximo passo no módulo atual |
| `/revisar` | Solicita revisão de conteúdo do módulo atual ou anterior |
| `/exercicio` | Solicita um novo exercício prático para resolver |
| `/dica` | Pede uma dica sem revelar a resposta completa |
| `/exemplo` | Pede um exemplo prático relacionado ao conteúdo atual |
| `/checkpoint` | Solicita verificação formal de checkpoint do módulo |
| `/pular` | Avança para o próximo módulo (requer confirmação) |

## Tela inicial

Ao abrir o chat, você vê:

```
╭─────────────────────────────────────────╮
│         ALGO HANDS-ON                   │
│      Pense. Resolva. Construa.          │
╰─────────────────────────────────────────╯

Aluno:        Maria Silva
Sessão:       cli-maria-a1b2c3d4e5
Módulo atual: Fundamentos de Python
Nível:        Guiado
Competência:  variáveis

Domínio   ████████░░░░░░░░░░░░░░░░░░░░░░  25%

Checkpoint:  ✗ Aplicação direta  ✗ Aplicação independente
             ✗ Integração  ✗ Diagnóstico  ✗ Explicação/transferência
```

- **Barra de domínio**: progresso percentual do módulo atual baseado nas 5 evidências.
- **Checkpoint**: mostra quais evidências foram satisfeitas (✓ verde) ou não (✗ vermelho).
- **Nível**: Observador → Guiado → Independente → Transferência. Avança automaticamente ao dominar módulos.

## Checkpoint e evidências

Cada módulo possui 5 tipos de evidência que precisam ser demonstradas:

1. **Aplicação direta** — Resolver um exercício guiado corretamente
2. **Aplicação independente** — Resolver sozinho, sem dicas
3. **Integração** — Combinar conceitos do módulo em um problema
4. **Diagnóstico** — Identificar e corrigir erros em código
5. **Explicação/transferência** — Explicar o raciocínio ou aplicar em novo contexto

**Regras importantes:**
- Cada evidência exige nota >= 0.8 **sem dica** para ser satisfeita.
- Acertos com dica (`/dica`) são registrados mas **não** concluem a evidência.
- O módulo só avança quando as 5 evidências estão satisfeitas.
- O progresso é calculado automaticamente pelo SQLite — o agente não decide avanço.

## Sessões

Cada conversa é uma sessão identificada por um `session_id`. O progresso é vinculado ao `student_id`, não à sessão.

### Listar sessões

```bash
# No chat:
/sessoes
```

### Continuar uma sessão

```bash
# Pelo terminal, informe o session_id:
uv run aho chat --student-id maria --session-id cli-maria-a1b2c3d4e5
```

### Criar nova sessão

Basta omitir `--session-id` e uma nova sessão será criada automaticamente.

## Streaming

Por padrão, as respostas do tutor aparecem **progressivamente** no terminal (como um chat real), em vez de aparecerem de uma vez após o processamento completo.

Para desativar o streaming:

```bash
# No .env
AHO_STREAM=false
```

## Uso rápido sem sincronização

Após o primeiro `uv sync`, você pode iniciar sem verificar dependências:

```bash
# Opção 1: pular sincronização
uv run --no-sync aho chat --student-id fernando --session-id estudo-principal

# Opção 2: ativar o ambiente virtual
.venv\Scripts\Activate.ps1   # Windows PowerShell
source .venv/bin/activate    # Linux/macOS
aho chat --student-id fernando
```

## Configuração avançada

Todas as variáveis de ambiente em `.env`:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DEEPSEEK_API_KEY` | — | Chave da API (obrigatório) |
| `DEEPSEEK_MODEL` | `deepseek-chat` | Modelo DeepSeek |
| `AHO_DB_PATH` | `./data/aho.db` | Caminho do banco SQLite |
| `AHO_SKILLS_DIR` | `./skills` | Diretório das skills |
| `AHO_HISTORY_RUNS` | `3` | Mensagens mantidas em contexto |
| `AHO_SESSION_SUMMARIES` | `true` | Resumos automáticos de conversas longas |
| `AHO_MEMORY` | `true` | Memória de preferências do aluno |
| `AHO_STREAM` | `true` | Streaming de resposta |
| `AHO_STREAM_EVENTS` | `true` | Eventos de streaming |
| `AHO_DEBUG` | `false` | Logs detalhados (ativo = mais verboso) |
| `AHO_HOST` | `127.0.0.1` | Host da API |
| `AHO_PORT` | `7777` | Porta da API |

## Resolução de problemas

### `DEEPSEEK_API_KEY não foi configurada`

Edite o arquivo `.env` e defina sua chave:
Preencha `DEEPSEEK_API_KEY` no arquivo `.env`.

### `Módulo inválido: X`

Os módulos válidos vão de 0 a 16. Use `aho modules` para ver a lista completa.

### `Aluno não encontrado`

Crie o aluno primeiro:
```bash
uv run aho setup --student-id maria --name "Maria Silva"
```

### O terminal congela sem resposta

Verifique a conexão com a API DeepSeek. O streaming (`AHO_STREAM=true`) mantém feedback visual durante o processamento.

### Erro ao carregar skills

Execute o diagnóstico:
```bash
uv run aho doctor
```

Verifique se o diretório `skills/` existe e contém as 9 subpastas de skills.

### Quero debug detalhado

```bash
# No .env
AHO_DEBUG=true

# Ou na linha de comando (PowerShell)
$env:AHO_DEBUG="true"; uv run aho chat --student-id fernando
```

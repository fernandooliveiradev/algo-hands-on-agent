from __future__ import annotations

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.deepseek import DeepSeek
from agno.skills import LocalSkills, Skills

from algo_hands_on.config import Settings
from algo_hands_on.hooks import post_run_validate, pre_run_context
from algo_hands_on.schemas import TutorTurn

BASE_INSTRUCTIONS = [
    "Você é o Algo Hands-On, tutor prático de pensamento computacional, lógica, algoritmos e Python.",
    "Responda em português do Brasil.",
    "Antes de ensinar, identifique o módulo atual informado nas dependências.",
    "Carregue a skill de domínio apropriada usando as ferramentas de skills quando necessário.",
    "Crie exercícios dinamicamente; não dependa de listas fixas de enunciados.",
    "VARIE o contexto e o tema a cada novo exercício (jogos, finanças, natureza, cotidiano, esportes, ficção, etc.).",
    "NÃO repita o mesmo problema ou a mesma temática em turnos consecutivos da mesma sessão.",
    "Não introduza conceitos posteriores sem evidência de pré-requisito.",
    "RESPEITE RIGOROSAMENTE a fronteira entre módulos. No Módulo 1 (Pensamento Computacional) NUNCA use pseudocódigo, fluxogramas, teste de mesa, variáveis, código Python ou qualquer notação formal. O Módulo 1 é apenas raciocínio em linguagem natural.",
    "No Módulo 2 (Algoritmos) NUNCA use sintaxe Python. Use apenas linguagem natural, pseudocódigo, fluxogramas e teste de mesa.",
    "Python só é permitido a partir do Módulo 3.",
    "Separe raciocínio, algoritmo e sintaxe ao corrigir.",
    "Quando houver uma resposta do aluno a um exercício, preencha evaluation.",
    "Só marque result=correct quando a solução estiver conceitualmente correta e independente.",
    "Use correct_with_hint quando houve ajuda relevante.",
    "A evidência de checkpoint deve usar exatamente um evidence_kind permitido.",
    "Não afirme que um módulo foi concluído; o aplicativo calculará isso a partir do SQLite.",
    "A mensagem ao aluno deve ser objetiva, prática e adequada ao nível atual.",
    "Mantenha o aluno ativo: peça previsão, tentativa, teste ou explicação antes de revelar tudo.",
    "Nunca exponha nomes de campos internos como message_markdown, module_id, competency_key, exercise ou evaluation.",
]

PARSER_INSTRUCTIONS = [
    "Você converte a resposta final do tutor em TutorTurn válido.",
    "Preserve a resposta ao aluno em message_markdown, sem reescrever estilo ou conteúdo.",
    "Use module_id e competency_key a partir do contexto de progresso quando o texto não trouxer esses campos explicitamente.",
    "Preencha exercise somente quando houver exercício claro no texto do tutor.",
    "Preencha evaluation somente quando a mensagem avaliar uma tentativa do aluno.",
    "Não invente evidências, notas ou conclusão de módulo.",
]


def build_deepseek_model(settings: Settings) -> DeepSeek:
    return DeepSeek(
        id=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        retries=2,
        exponential_backoff=True,
        timeout=120.0,
    )


def build_agent(settings: Settings) -> Agent:
    """Constrói o agente tutor Agno com DeepSeek, skills e persistência de sessão."""

    skills = Skills(loaders=[LocalSkills(str(settings.skills_dir))])
    agno_db = SqliteDb(
        db_file=str(settings.db_path),
        session_table="agno_sessions",
        memory_table="agno_memories",
        metrics_table="agno_metrics",
        eval_table="agno_evals",
        versions_table="agno_schema_versions",
    )
    model = build_deepseek_model(settings)
    base_kwargs: dict = {
        "id": "algo-hands-on",
        "name": "Algo Hands-On",
        "description": "Tutor adaptativo de pensamento computacional, lógica, algoritmos e Python.",
        "model": model,
        "db": agno_db,
        "skills": skills,
        "instructions": BASE_INSTRUCTIONS,
        "add_history_to_context": True,
        "num_history_runs": settings.history_runs,
        "add_dependencies_to_context": True,
        "markdown": True,
        "retries": 2,
        "exponential_backoff": True,
        "debug_mode": settings.debug,
        "telemetry": settings.telemetry,
    }

    if settings.memory:
        base_kwargs["update_memory_on_run"] = True

    if settings.session_summaries:
        base_kwargs["enable_session_summaries"] = True

    base_kwargs["pre_hooks"] = [pre_run_context]
    base_kwargs["post_hooks"] = [post_run_validate]

    return Agent(**base_kwargs)


def build_parser_agent(settings: Settings) -> Agent:
    """Constrói o parser Agno que valida a resposta final em TutorTurn."""

    return Agent(
        id="algo-hands-on-parser",
        name="Algo Hands-On Parser",
        description="Parser estruturado interno para respostas do tutor.",
        model=build_deepseek_model(settings),
        instructions=PARSER_INSTRUCTIONS,
        output_schema=TutorTurn,
        use_json_mode=True,
        add_dependencies_to_context=True,
        markdown=False,
        retries=2,
        exponential_backoff=True,
        debug_mode=settings.debug,
        telemetry=settings.telemetry,
        post_hooks=[post_run_validate],
    )

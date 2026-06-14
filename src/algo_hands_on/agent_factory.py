from __future__ import annotations

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.deepseek import DeepSeek
from agno.skills import LocalSkills, Skills

from algo_hands_on.config import Settings
from algo_hands_on.schemas import TutorTurn

BASE_INSTRUCTIONS = [
    "Você é o Algo Hands-On, tutor prático de pensamento computacional, lógica, algoritmos e Python.",
    "Responda em português do Brasil.",
    "Antes de ensinar, identifique o módulo atual informado nas dependências.",
    "Carregue a skill de domínio apropriada usando as ferramentas de skills quando necessário.",
    "Crie exercícios dinamicamente; não dependa de listas fixas de enunciados.",
    "Não introduza conceitos posteriores sem evidência de pré-requisito.",
    "Separe raciocínio, algoritmo e sintaxe ao corrigir.",
    "Quando houver uma resposta do aluno a um exercício, preencha evaluation.",
    "Só marque result=correct quando a solução estiver conceitualmente correta e independente.",
    "Use correct_with_hint quando houve ajuda relevante.",
    "A evidência de checkpoint deve usar exatamente um evidence_kind permitido.",
    "Não afirme que um módulo foi concluído; o aplicativo calculará isso a partir do SQLite.",
    "A mensagem ao aluno deve ser objetiva, prática e adequada ao nível atual.",
    "Mantenha o aluno ativo: peça previsão, tentativa, teste ou explicação antes de revelar tudo.",
]


def build_agent(settings: Settings) -> Agent:
    """Constrói o agente Agno com DeepSeek, skills e persistência de sessão."""

    skills = Skills(loaders=[LocalSkills(str(settings.skills_dir))])
    agno_db = SqliteDb(
        db_file=str(settings.db_path),
        session_table="agno_sessions",
        memory_table="agno_memories",
        metrics_table="agno_metrics",
        eval_table="agno_evals",
        versions_table="agno_schema_versions",
    )
    model = DeepSeek(
        id=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        retries=2,
        exponential_backoff=True,
        timeout=90.0,
    )
    return Agent(
        id="algo-hands-on",
        name="Algo Hands-On",
        description="Tutor adaptativo de pensamento computacional, lógica, algoritmos e Python.",
        model=model,
        db=agno_db,
        skills=skills,
        instructions=BASE_INSTRUCTIONS,
        output_schema=TutorTurn,
        use_json_mode=True,
        add_history_to_context=True,
        num_history_runs=settings.history_runs,
        add_dependencies_to_context=True,
        markdown=True,
        retries=2,
        exponential_backoff=True,
        debug_mode=settings.debug,
        telemetry=settings.telemetry,
    )

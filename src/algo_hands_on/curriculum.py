from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Module:
    id: int
    slug: str
    title: str
    domain_skill: str
    competencies: tuple[str, ...]
    professional_extension: bool = False


MODULES: tuple[Module, ...] = (
    Module(0, "diagnostico", "Entrada e diagnóstico", "aho-start-here", (
        "objetivo-de-aprendizagem", "experiencia-previa", "nivel-de-independencia", "lacunas",
    )),
    Module(1, "pensamento-computacional", "Pensamento computacional", "aho-computational-thinking", (
        "analise", "decomposicao", "reconhecimento-de-padroes", "abstracao", "generalizacao", "avaliacao-de-solucoes",
    )),
    Module(2, "representacao-de-algoritmos", "Construção e representação de algoritmos", "aho-computational-thinking", (
        "entrada-processamento-saida", "regras-restricoes", "algoritmo-natural", "pseudocodigo", "fluxograma", "teste-de-mesa",
    )),
    Module(3, "fundamentos-python", "Fundamentos de Python", "aho-python-foundations", (
        "sintaxe", "entrada-saida", "variaveis", "tipos", "conversao", "operadores", "expressoes",
    )),
    Module(4, "decisoes", "Decisões e regras de negócio", "aho-python-foundations", (
        "booleanos", "if-elif-else", "condicoes-compostas", "intervalos", "caminhos-alternativos",
    )),
    Module(5, "repeticao", "Repetição e estado", "aho-python-foundations", (
        "for", "while", "range", "contador", "acumulador", "sentinela", "condicao-de-parada", "lacos-aninhados",
    )),
    Module(6, "textos-colecoes", "Textos e coleções", "aho-python-foundations", (
        "strings", "listas", "tuplas", "conjuntos", "dicionarios", "estruturas-aninhadas", "matrizes", "mutacao-copia",
    )),
    Module(7, "funcoes", "Funções e decomposição de código", "aho-python-foundations", (
        "def", "parametros-argumentos", "retorno", "escopo", "contrato", "composicao", "efeitos-colaterais",
    )),
    Module(8, "erros-testes", "Validação, erros, depuração e testes iniciais", "aho-python-foundations", (
        "validacao", "traceback", "excecoes", "depuracao", "casos-de-teste", "assert", "pytest-basico",
    )),
    Module(9, "padroes", "Padrões de resolução de problemas", "aho-algorithms-data-structures", (
        "percurso", "contagem", "acumulacao", "minimo-maximo", "busca", "filtragem", "transformacao", "frequencia", "agrupamento", "deduplicacao",
    )),
    Module(10, "algoritmos-eficiencia", "Algoritmos, estruturas clássicas e eficiência", "aho-algorithms-data-structures", (
        "busca-linear", "ordenacao", "pilhas", "filas", "busca-binaria", "recursividade", "arvores-grafos", "big-o",
    )),
    Module(11, "projetos-persistencia", "Persistência e organização profissional", "aho-portfolio-projects", (
        "txt", "json", "csv", "serializacao", "modulos-pacotes", "ambiente-virtual", "dependencias", "git-github", "readme",
    )),
    Module(12, "oop", "Orientação a objetos aplicada", "aho-portfolio-projects", (
        "classes-objetos", "atributos-metodos", "construtor", "encapsulamento", "composicao", "heranca", "polimorfismo", "responsabilidades",
    )),
    Module(13, "entrevistas", "Integração e preparação para entrevistas", "aho-algorithms-data-structures", (
        "esclarecimento", "forca-bruta", "otimizacao", "dois-ponteiros", "janela-deslizante", "complexidade", "explicacao-tecnica",
    )),
    Module(14, "sql", "SQL e bancos de dados", "aho-portfolio-projects", (
        "modelagem-relacional", "crud-sql", "filtros", "agregacoes", "joins", "transacoes", "integracao-python",
    ), True),
    Module(15, "apis", "Consumo e criação de APIs", "aho-portfolio-projects", (
        "http", "requisicao-resposta", "metodos-status", "json-api", "consumo", "endpoints", "validacao", "autenticacao", "testes-api",
    ), True),
    Module(16, "web", "Aplicações web", "aho-portfolio-projects", (
        "arquitetura-web", "rotas", "formularios", "crud-web", "persistencia-web", "autenticacao-autorizacao", "testes-web", "publicacao",
    ), True),
)

MODULE_BY_ID = {module.id: module for module in MODULES}
MODULE_BY_SLUG = {module.slug: module for module in MODULES}
LAST_MODULE_ID = MODULES[-1].id


def get_module(module_id: int) -> Module:
    try:
        return MODULE_BY_ID[module_id]
    except KeyError as exc:
        raise ValueError(f"Módulo inválido: {module_id}") from exc


def next_module_id(module_id: int) -> int | None:
    return module_id + 1 if module_id < LAST_MODULE_ID else None

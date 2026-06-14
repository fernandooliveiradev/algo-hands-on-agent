# Trilha Canônica do Algo Hands-On — Versão 2

Este arquivo é a fonte única de verdade da progressão curricular do Algo Hands-On.

O objetivo da trilha é desenvolver pensamento computacional, lógica de programação, algoritmos e Python por meio de prática guiada, exercícios adaptativos e projetos progressivos.

Os exercícios não são armazenados de forma fixa nesta trilha. Eles devem ser gerados pelo agente de acordo com:

* o módulo atual;
* os conceitos já dominados;
* os erros anteriores do aluno;
* o nível de independência demonstrado;
* os interesses e contextos do aluno;
* os critérios de domínio definidos neste documento.

---

## 1. Organização da trilha

A trilha é organizada em:

```text
módulos
→ competências
→ práticas guiadas
→ prática independente
→ checkpoint de domínio
→ projeto de consolidação
```

Um módulo reúne conceitos que precisam ser aprendidos em conjunto.

Os subtópicos não devem ser tratados automaticamente como módulos separados.

---

## 2. Ciclo obrigatório de aprendizagem

Para cada módulo, o agente deve seguir este ciclo:

1. Diagnosticar os conhecimentos prévios.
2. Apresentar um problema compatível com o nível atual.
3. Ensinar somente o conceito necessário para avançar.
4. Pedir uma previsão ou explicação antes da execução.
5. Conduzir uma prática guiada.
6. Gerar uma variação para resolução independente.
7. Corrigir raciocínio e código separadamente.
8. Aplicar uma tarefa de transferência.
9. Realizar o checkpoint de domínio.
10. Avançar, reforçar ou retornar ao pré-requisito.

O aluno deve permanecer ativo durante todo o processo.

---

## 3. Geração dinâmica de exercícios

O agente deve criar os exercícios durante a aula.

Cada exercício deve respeitar:

* o conteúdo permitido no módulo;
* os pré-requisitos já dominados;
* o nível de dificuldade atual;
* o histórico de erros do aluno;
* a ausência de conceitos ainda não estudados;
* a possibilidade de verificar objetivamente a resposta.

O agente não deve manter uma lista fechada de exercícios obrigatórios.

### Tipos de prática

Durante um módulo, o agente pode gerar:

* diagnóstico;
* reconhecimento de conceito;
* previsão de execução;
* teste de mesa;
* conclusão de algoritmo;
* correção de erro;
* implementação guiada;
* implementação independente;
* alteração de requisitos;
* comparação entre soluções;
* explicação do raciocínio;
* integração com conceitos anteriores.

---

## 4. Checkpoint de domínio

A bateria final de cada módulo contém cinco evidências:

1. aplicação direta;
2. aplicação independente em outro contexto;
3. integração com um conceito anterior;
4. diagnóstico ou correção de uma solução;
5. explicação, teste de mesa ou tarefa de transferência.

O aluno conclui o módulo quando:

* demonstra as cinco competências;
* resolve a tentativa final sem depender de dica;
* explica o raciocínio com suas palavras;
* testa casos relevantes;
* não apresenta lacunas críticas nos pré-requisitos.

Uma resposta correta após uma dica exige uma nova variação independente.

Quando apenas uma competência falhar, o agente deve remediar aquela competência e aplicar uma nova evidência equivalente. Não é necessário reiniciar todo o módulo.

---

# Formação principal

## Módulo 0 — Entrada e diagnóstico

### Objetivo

Identificar o nível real do aluno e selecionar o ponto inicial adequado.

### Conteúdos

* objetivo de aprendizagem;
* experiência anterior;
* leitura de código;
* explicação de raciocínio;
* resolução de um problema diagnóstico;
* identificação de lacunas.

### Resultado esperado

O agente deve registrar:

```text
módulo inicial
competências demonstradas
competências ausentes
nível de independência
próximo passo
```

### Roteamento

```text
aho-start-here
aho-stage-router
aho-curriculum-path
aho-tutor-core
```

---

## Módulo 1 — Pensamento computacional

### Objetivo

Ensinar o aluno a compreender e estruturar problemas antes de escrever código.

### Competências

* formular claramente o problema;
* identificar o objetivo;
* decompor o problema;
* reconhecer padrões;
* abstrair detalhes irrelevantes;
* generalizar uma solução;
* comparar possíveis estratégias;
* avaliar se uma solução atende ao problema.

### Conteúdos

```text
resolução estruturada de problemas
→ análise
→ decomposição
→ reconhecimento de padrões
→ abstração
→ generalização
→ construção de estratégias
→ avaliação de soluções
```

### Critério de domínio

O aluno deve conseguir receber um problema novo e explicar:

* o que precisa ser resolvido;
* quais partes compõem o problema;
* quais informações são relevantes;
* quais padrões podem ser reutilizados;
* qual estratégia geral seria adotada.

### Roteamento

```text
aho-computational-thinking
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 2 — Construção e representação de algoritmos

### Objetivo

Transformar uma estratégia de solução em passos claros, finitos e verificáveis.

### Competências

* identificar entrada, processamento e saída;
* definir regras e restrições;
* identificar casos normais, limites e inválidos;
* escrever algoritmos em linguagem natural;
* escrever pseudocódigo;
* interpretar fluxogramas;
* construir fluxogramas quando forem úteis;
* realizar teste de mesa;
* rastrear estado e variáveis;
* verificar se o algoritmo termina e produz o resultado esperado.

### Conteúdos

```text
algoritmos em linguagem natural
→ entrada, processamento e saída
→ regras e restrições
→ casos especiais
→ pseudocódigo
→ fluxogramas
→ teste de mesa
→ rastreamento de estado
→ validação do algoritmo
```

### Observação

Fluxogramas são auxiliares. Pseudocódigo e teste de mesa têm prioridade prática.

### Critério de domínio

O aluno deve conseguir representar e rastrear uma solução simples sem depender da sintaxe de Python.

### Roteamento

```text
aho-algorithm-representation
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 3 — Fundamentos de Python

### Objetivo

Usar Python para representar algoritmos sequenciais simples.

### Competências

* compreender a execução sequencial;
* escrever código com sintaxe e indentação corretas;
* receber e apresentar dados;
* criar e atualizar variáveis;
* distinguir valores e tipos;
* converter tipos;
* construir expressões;
* prever o resultado de pequenas sequências de código.

### Conteúdos

```text
execução de um programa
→ sintaxe
→ indentação
→ comentários
→ print
→ input
→ variáveis
→ int
→ float
→ str
→ bool
→ None
→ conversão de tipos
→ operadores aritméticos
→ operadores relacionais
→ operadores lógicos
→ precedência
→ expressões
```

### Critério de domínio

O aluno deve conseguir transformar um algoritmo sequencial simples em código Python executável e explicar o estado das variáveis.

### Roteamento

```text
aho-python-foundations
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 4 — Decisões e regras de negócio

### Objetivo

Fazer o programa escolher caminhos diferentes de acordo com dados e regras.

### Competências

* formular condições booleanas;
* utilizar `if`, `elif` e `else`;
* combinar condições;
* trabalhar com intervalos;
* ordenar condições corretamente;
* utilizar condições aninhadas quando necessário;
* validar caminhos alternativos;
* testar todos os ramos relevantes.

### Conteúdos

```text
valores booleanos
→ comparações
→ if
→ elif
→ else
→ and
→ or
→ not
→ condições compostas
→ intervalos
→ condições aninhadas
→ regras de prioridade
→ validação de caminhos
```

### Critério de domínio

O aluno deve conseguir implementar, rastrear e testar problemas com múltiplos caminhos.

### Roteamento

```text
aho-python-foundations
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 5 — Repetição e estado

### Objetivo

Processar ações repetidas e compreender como o estado muda durante um laço.

### Competências

* escolher entre `for` e `while`;
* utilizar `range`;
* controlar início, continuidade e término;
* criar contadores;
* criar acumuladores;
* utilizar sentinelas;
* validar entradas repetidamente;
* utilizar `break` e `continue` com justificativa;
* trabalhar com laços aninhados;
* detectar laços infinitos;
* realizar teste de mesa por iteração.

### Conteúdos

```text
for
→ while
→ range
→ estado do laço
→ contador
→ acumulador
→ sentinela
→ validação repetida
→ break
→ continue
→ laços aninhados
→ condição de parada
→ teste de mesa de repetição
```

### Critério de domínio

O aluno deve conseguir construir e explicar laços que terminam corretamente e atualizam o estado de forma previsível.

### Marco prático 1

Após este módulo, o agente deve propor um pequeno programa de terminal que combine:

* entrada;
* decisões;
* repetição;
* validação básica.

O tema e os requisitos devem ser gerados dinamicamente.

### Roteamento

```text
aho-python-foundations
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 6 — Textos e coleções

### Objetivo

Representar e processar conjuntos de dados utilizando a estrutura adequada.

### Competências

* percorrer e transformar strings;
* utilizar índices e fatiamento;
* criar e alterar listas;
* compreender listas como a principal estrutura dinâmica equivalente a vetores e arrays em Python;
* utilizar tuplas para dados fixos;
* utilizar conjuntos para unicidade e comparação;
* utilizar dicionários para associação por chave;
* trabalhar com estruturas aninhadas;
* representar matrizes com listas de listas;
* escolher a estrutura de dados de acordo com o problema;
* distinguir valor, índice, chave e posição;
* compreender mutação e cópia.

### Conteúdos

```text
strings
→ índices
→ fatiamento
→ métodos de texto
→ percurso de caracteres
→ listas
→ vetores e arrays conceituais
→ mutação de listas
→ cópia
→ tuplas
→ conjuntos
→ dicionários
→ estruturas aninhadas
→ matrizes
→ escolha de estrutura
```

### Nota sobre arrays

Na formação básica:

* listas são utilizadas como estrutura principal para vetores e arrays dinâmicos;
* o módulo `array` não é obrigatório;
* `numpy.array` pertence a uma futura trilha de dados e computação científica.

### Critério de domínio

O aluno deve conseguir escolher, percorrer, consultar e atualizar a coleção adequada sem introduzir estruturas ainda desnecessárias.

### Roteamento

```text
aho-python-foundations
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 7 — Funções e decomposição de código

### Objetivo

Dividir soluções em unidades reutilizáveis, testáveis e com responsabilidades claras.

### Competências

* definir funções;
* utilizar parâmetros e argumentos;
* retornar valores;
* compreender escopo;
* diferenciar retorno de impressão;
* distinguir funções puras de funções com efeitos colaterais;
* estabelecer contratos de entrada e saída;
* decompor um problema em funções;
* compor funções;
* evitar duplicação;
* documentar o comportamento essencial.

### Conteúdos

```text
def
→ chamada de função
→ parâmetros
→ argumentos
→ retorno
→ escopo
→ variáveis locais
→ parâmetros opcionais
→ contrato
→ responsabilidade única
→ função pura
→ efeito colateral
→ composição
→ decomposição funcional
```

### Critério de domínio

O aluno deve conseguir transformar um programa monolítico em funções pequenas e explicar a responsabilidade de cada uma.

### Roteamento

```text
aho-python-foundations
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 8 — Validação, erros, depuração e testes iniciais

### Objetivo

Ensinar o aluno a prevenir, localizar, explicar e corrigir falhas.

### Competências

* validar dados;
* distinguir erro de sintaxe, execução e lógica;
* interpretar traceback;
* tratar exceções específicas;
* utilizar `try`, `except`, `else` e `finally` quando apropriado;
* reproduzir um erro;
* isolar o menor caso que falha;
* utilizar rastreamento e breakpoint;
* criar casos normais, limites e inválidos;
* utilizar `assert`;
* escrever testes unitários básicos;
* refatorar preservando comportamento.

### Conteúdos

```text
validação
→ programação defensiva
→ erros de sintaxe
→ erros de execução
→ erros lógicos
→ traceback
→ exceções
→ try e except
→ depuração
→ breakpoint
→ reprodução do erro
→ casos de teste
→ assert
→ introdução ao pytest
```

### Critério de domínio

O aluno deve conseguir diagnosticar uma falha, explicar sua causa, corrigir o código e demonstrar a correção por meio de testes.

### Marco prático 2

O agente deve propor uma evolução do marco anterior ou um novo programa que contenha:

* funções;
* validação;
* tratamento de erros;
* testes básicos.

O projeto deve ser gerado de acordo com o nível e os interesses do aluno.

### Roteamento

```text
aho-python-foundations
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 9 — Padrões de resolução de problemas

### Objetivo

Fazer o aluno reconhecer estruturas recorrentes em problemas diferentes.

### Competências

* percorrer;
* contar;
* acumular;
* encontrar maior e menor;
* buscar;
* filtrar;
* transformar;
* calcular frequência;
* agrupar;
* remover duplicados;
* comparar coleções;
* combinar pares de elementos;
* manter estado durante o percurso;
* decompor padrões em funções reutilizáveis.

### Conteúdos

```text
percurso
→ contagem
→ acumulação
→ mínimo e máximo
→ busca
→ filtragem
→ transformação
→ frequência
→ agrupamento
→ deduplicação
→ comparação
→ pares de elementos
→ janelas simples
→ combinação de padrões
```

### Critério de domínio

O aluno deve conseguir identificar o padrão central de um problema novo antes de escrever o código.

### Roteamento

```text
aho-python-foundations
aho-algorithms-data-structures
aho-tutor-core
aho-guided-lessons
```

O roteador pode usar as duas skills de domínio neste módulo, pois ele representa a transição entre fundamentos e algoritmos.

---

## Módulo 10 — Algoritmos, estruturas clássicas e eficiência

### Objetivo

Estudar algoritmos conhecidos, estruturas abstratas e comparação de eficiência.

### Competências

* implementar e explicar busca linear;
* compreender pré-requisitos da busca binária;
* implementar busca binária;
* compreender algoritmos elementares de ordenação;
* utilizar ordenação nativa adequadamente;
* representar pilhas;
* representar filas;
* compreender recursividade;
* definir caso base e passo recursivo;
* compreender árvores e grafos em nível introdutório;
* comparar crescimento de operações;
* analisar tempo e espaço;
* reconhecer complexidades comuns.

### Ordem interna

```text
busca linear
→ análise de operações
→ ordenação elementar
→ ordenação nativa
→ pilhas
→ filas
→ busca binária
→ recursividade
→ árvores e grafos introdutórios
→ Big O
→ comparação entre soluções
```

### Complexidades esperadas

```text
O(1)
O(log n)
O(n)
O(n log n)
O(n²)
```

O aluno não deve decorar rótulos sem relacioná-los às operações realizadas.

### Critério de domínio

O aluno deve conseguir:

* começar por uma solução correta;
* rastrear sua execução;
* identificar o gargalo;
* comparar alternativas;
* justificar uma melhoria;
* indicar complexidade de forma coerente.

### Roteamento

```text
aho-algorithms-data-structures
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 11 — Persistência e organização profissional de projetos

### Objetivo

Transformar programas isolados em projetos organizados, persistentes e versionados.

### Competências

* ler e escrever arquivos;
* trabalhar com caminhos;
* utilizar UTF-8;
* utilizar TXT, JSON e CSV;
* serializar e carregar dados;
* separar responsabilidades;
* criar módulos e pacotes;
* utilizar importações;
* criar função principal;
* organizar diretórios;
* utilizar ambiente virtual;
* declarar dependências;
* escrever README;
* utilizar Git e GitHub;
* criar histórico de commits coerente;
* executar testes em um projeto estruturado.

### Conteúdos

```text
arquivos
→ caminhos
→ with open
→ encoding
→ TXT
→ JSON
→ CSV
→ serialização
→ persistência
→ módulos
→ pacotes
→ importações
→ função main
→ estrutura de projeto
→ ambiente virtual
→ dependências
→ pytest
→ Git
→ GitHub
→ README
```

### Observação sobre Git

Comandos básicos podem ser apresentados desde os primeiros programas. O domínio completo ocorre neste módulo, quando já existe um projeto real para versionar.

### Critério de domínio

O aluno deve entregar um projeto que possa ser clonado, configurado, executado e testado por outra pessoa.

### Marco prático 3

O agente deve gerar um projeto compatível com os conhecimentos dominados, contendo:

* problema definido;
* requisitos;
* persistência;
* módulos;
* validações;
* testes;
* documentação;
* histórico Git.

### Roteamento

```text
aho-python-foundations
aho-portfolio-projects
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 12 — Orientação a objetos aplicada

### Objetivo

Utilizar objetos quando o domínio do problema justificar a combinação de estado e comportamento.

### Competências

* identificar entidades;
* criar classes e objetos;
* definir atributos;
* definir métodos;
* utilizar construtores;
* controlar estado;
* aplicar encapsulamento;
* utilizar composição;
* compreender herança;
* compreender polimorfismo;
* evitar classes sem responsabilidade;
* comparar solução funcional e orientada a objetos.

### Ordem interna

```text
entidade
→ objeto
→ classe
→ atributo
→ método
→ construtor
→ estado
→ encapsulamento
→ composição
→ herança
→ polimorfismo
→ responsabilidades
```

### Critério de domínio

O aluno deve conseguir justificar por que uma classe existe e por que determinada responsabilidade pertence a ela.

Herança e polimorfismo devem ser ensinados como ferramentas opcionais, não como requisitos para todo programa.

### Marco prático 4

O agente deve propor a refatoração de um projeto anterior ou a criação de um projeto novo no qual orientação a objetos produza benefício real.

### Roteamento

```text
aho-portfolio-projects
aho-python-foundations
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 13 — Integração e preparação para entrevistas

### Objetivo

Aplicar os fundamentos em problemas desconhecidos, explicar decisões e trabalhar sob restrições.

### Competências

* esclarecer o enunciado;
* criar exemplos;
* identificar restrições;
* propor força bruta;
* rastrear a solução;
* escolher estruturas;
* reconhecer padrões;
* otimizar quando necessário;
* analisar complexidade;
* escrever testes;
* explicar escolhas;
* adaptar a solução após mudança de requisito.

### Famílias de problemas

```text
strings
→ listas
→ conjuntos
→ dicionários
→ matrizes
→ pilhas
→ filas
→ busca
→ ordenação
→ recursividade
→ árvores e grafos básicos
→ frequência
→ dois ponteiros
→ janela deslizante
→ complexidade
```

Os exercícios devem ser gerados pelo agente. A trilha não deve fixar uma lista imutável de desafios.

### Critério de domínio

O aluno deve conseguir resolver um problema novo seguindo:

```text
compreensão
→ exemplos
→ força bruta
→ teste de mesa
→ implementação
→ testes
→ complexidade
→ melhoria
→ explicação
```

### Roteamento

```text
aho-algorithms-data-structures
aho-tutor-core
aho-guided-lessons
```

---

# Extensão profissional

Os módulos seguintes não fazem parte do núcleo de pensamento computacional e lógica de programação.

Eles aplicam a base na construção de sistemas.

---

## Módulo 14 — SQL e bancos de dados

### Conteúdos

```text
modelagem relacional
→ tabelas
→ registros
→ tipos
→ chaves primárias
→ chaves estrangeiras
→ SELECT
→ WHERE
→ ORDER BY
→ INSERT
→ UPDATE
→ DELETE
→ agregações
→ GROUP BY
→ JOIN
→ transações
→ integração com Python
```

### Roteamento

```text
aho-portfolio-projects
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 15 — Consumo e criação de APIs

### Conteúdos

```text
cliente e servidor
→ HTTP
→ URL
→ requisição
→ resposta
→ métodos HTTP
→ status codes
→ headers
→ JSON
→ consumo de API
→ timeout e erros
→ criação de endpoints
→ validação
→ autenticação
→ testes de API
```

### Roteamento

```text
aho-portfolio-projects
aho-tutor-core
aho-guided-lessons
```

---

## Módulo 16 — Aplicações web

### Conteúdos

```text
arquitetura web
→ rotas
→ camada de apresentação
→ formulários
→ validação
→ CRUD
→ banco de dados
→ autenticação
→ autorização
→ APIs
→ testes
→ configuração
→ publicação
```

### Projeto final

O agente deve ajudar o aluno a construir uma aplicação completa com:

* definição do problema;
* requisitos;
* planejamento;
* implementação incremental;
* banco de dados;
* regras de negócio;
* testes;
* Git;
* documentação;
* publicação;
* apresentação de portfólio.

### Roteamento

```text
aho-portfolio-projects
aho-tutor-core
aho-guided-lessons
```

---

# Mapa resumido

```text
Módulo 0 — Diagnóstico
→ Módulo 1 — Pensamento computacional
→ Módulo 2 — Representação de algoritmos
→ Módulo 3 — Fundamentos de Python
→ Módulo 4 — Decisões
→ Módulo 5 — Repetições
→ Módulo 6 — Textos e coleções
→ Módulo 7 — Funções
→ Módulo 8 — Erros, depuração e testes
→ Módulo 9 — Padrões de resolução
→ Módulo 10 — Algoritmos, estruturas e Big O
→ Módulo 11 — Persistência, projetos e Git
→ Módulo 12 — Orientação a objetos
→ Módulo 13 — Integração e entrevistas
→ Módulo 14 — SQL
→ Módulo 15 — APIs
→ Módulo 16 — Aplicações web
```

---

# Regra de progressão

A progressão não deve ocorrer porque o conteúdo foi apresentado.

Ela deve ocorrer quando o aluno demonstra que consegue:

```text
entender
→ representar
→ prever
→ implementar
→ testar
→ explicar
→ adaptar
```

O objetivo final não é memorizar sintaxe.

O objetivo é aprender a resolver problemas de forma estruturada e transformar as soluções em programas Python corretos, testáveis e compreensíveis.

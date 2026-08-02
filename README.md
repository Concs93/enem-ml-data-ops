# ENEM em foco

[![CI](https://github.com/Concs93/enem-ml-data-ops/actions/workflows/ci.yml/badge.svg)](https://github.com/Concs93/enem-ml-data-ops/actions/workflows/ci.yml)
[![Site e documentação](https://github.com/Concs93/enem-ml-data-ops/actions/workflows/docs.yml/badge.svg)](https://github.com/Concs93/enem-ml-data-ops/actions/workflows/docs.yml)

**Um site gratuito que diz ao estudante do ENEM o que estudar primeiro** —
calculado com o mesmo modelo que o INEP usa para corrigir a prova, sobre os
microdados públicos de 2025.

### 🎯 **[Abrir o site](https://concs93.github.io/enem-ml-data-ops/)**

Sem cadastro, sem servidor, sem coleta: o cálculo roda no navegador de quem
acessa. Quem digita as respostas da prova as vê corrigidas **no próprio
aparelho** — o gabarito desce, as respostas nunca sobem.

---

## O que o site faz

**Para o estudante.** Você coloca a nota (e, se quiser, as 45 respostas de
cada área) e ele responde *o que estudar primeiro para ganhar mais pontos*:

- **A prioridade muda com o seu nível.** Em Matemática, quem está em ~550
  ganha mais estudando "construir significados para os números"; quem está em
  ~700, geometria. Estudar o que você mais erra costuma ser a pior escolha no
  curto prazo — o conteúdo distante quase não devolve ponto, e o site mostra
  por quê.
- **Com o gabarito, ele fica específico**: quais questões estavam ao seu
  alcance, quantos pontos cada erro custou, e onde estão os "pontos baratos".
- **Ele declara o que não sabe.** A prova mede com precisão desigual — ±16
  pontos na nota 700, ±82 na nota 400 — e a tela muda de linguagem onde a
  medida é ruim.

**Análise por estado e cidade.** Busque o seu lugar e veja quantos pontos a
média subiria com **um passo de avanço** no aprendizado, repartido pelas
competências da Matriz — e onde esse passo rende mais. Filtrável por rede
(estadual, privada, federal, municipal).

**Aqui não há ranking.** Nenhum lugar é pintado ou ordenado por desempenho, e
escola individual fica de fora por decisão: é o uso que fez o INEP
descontinuar o "ENEM por Escola" em 2015. O critério de publicação (≥ 3
escolas e ≥ 50 participantes) vale igual para estados e cidades.

---

## O que sustenta os números

O site é a ponta. Atrás dele há um pipeline que vai do CSV bruto do INEP
(2,6 GB) até os 100 KB de JSON que o navegador baixa.

```
CSV bruto (INEP)
  → raw            ingestão via COPY, tudo TEXT, sem interpretação
  → staging        tipagem + schema canônico (dbt)
  → intermediate   explosão das respostas + agregação por item
  → marts          fronteira de consumo — o que o site lê
```

**A validação que sustenta tudo.** A correlação entre o parâmetro de
dificuldade calibrado pelo INEP e a taxa de acerto que o pipeline calcula do
zero, a partir dos vetores de resposta:

| área | correlação | taxa média |
|---|---|---|
| CH | −0,808 | 35,8% |
| CN | −0,799 | 32,6% |
| LC | **−0,910** | 45,1% |
| MT | −0,854 | 31,9% |

São dois caminhos independentes concordando sobre quais itens são difíceis.
Foi assim que um bug de junção em Linguagens apareceu: a correlação vinha
−0,027 e a taxa colada no acaso de 20%. Nenhum outro teste teria pego.

**O motor psicométrico** (TRI de 3 parâmetros) existe como tabela, não como
binário: curva característica e informação de Fisher de cada item, numa grade
de θ. Os parâmetros são os oficiais do INEP — nada é ajustado aqui, só
avaliado —, e por isso o modelo herda versionamento, teste e documentação do
próprio dbt.

**Confirmação cruzada:** re-estimar a nota pelo padrão de respostas de 4.000
participantes dá correlação **0,9907** com a nota oficial.

📊 **[Documentação e lineage do pipeline](https://concs93.github.io/enem-ml-data-ops/pipeline/)**

---

## Três coisas que só apareceram medindo

**1. 184 KB no lugar de 2,6 GB.** Para reunir os itens de seis edições, o
script lê o diretório central de cada ZIP remoto do INEP e pede por *range*
só os bytes do arquivo que interessa. Economia de até **19.074×** numa
edição.

**2. Um NULO apagou uma edição inteira, em silêncio.** O `IN_ITEM_ADAPTADO`
de 2021 vem vazio em vez de `"0"`; `not nulo` é nulo, que não é verdadeiro; o
filtro descartou os 370 itens da edição sem erro nenhum. Contagem não
denuncia esse tipo de defeito — só denuncia quem exige **presença de cada
parte**.

**3. "Acertar uma questão difícil sobe mais" é falso.** Pela equação de
estimação sob o modelo de 3 parâmetros, sem acerto casual trocar erro por
acerto move o **mesmo tanto** em qualquer questão; com o acerto casual real
do ENEM, a fácil move **3,5×** mais. A assimetria inteira é o parâmetro de
chute — e isso virou uma [quarta lente de
verificação](.claude/skills/psicometria/SKILL.md), com referências e uma
lista de frases que soam certas e estão erradas.

---

## Como está testado

Quatro camadas, cada uma respondendo a uma pergunta diferente:

| camada | pergunta | onde |
|---|---|---|
| `dbt test` | meu SQL fez o que eu quis? | 100+ testes sobre 41 modelos |
| Great Expectations | o dado que chegou é o esperado? | fronteira (camada `raw`) |
| `ci/testa_webapp.js` | a conta do navegador está certa? | 47 casos, código real em sandbox |
| skill de psicometria | a **teoria** está certa? | referências + cálculo reproduzível |

A CI roda em três faixas conforme o quanto de dado cada uma precisa — e **não
usa nenhum segredo**, por desenho: o Postgres do job é descartável. Se ela
precisasse de senha real, seria sinal de que está tocando um ambiente que não
deveria.

---

## Como rodar

Windows + PowerShell, Postgres em Docker. Sempre da raiz:

```powershell
.\.venv\Scripts\Activate.ps1
. .\load_env.ps1          # o ponto e o espaço na frente são obrigatórios
docker compose up -d
```

Os microdados vão para `data/raw/` (fora do Git). Depois:

```powershell
python -m ingestion.load_raw
cd dbt; dbt deps; dbt seed
# um modelo por vez -- ver CLAUDE.md, "Restrições de máquina"
dbt run --select stg_itens
...
dbt test
```

O site é estático: `python -m http.server --directory webapp` e abrir
`localhost:8000`.

## Stack

**Postgres** · **dbt** (transformação e testes) · **Great Expectations**
(validação de fronteira) · **Airflow 3** (orquestração) · **Docker** ·
**GitHub Actions** (CI em três faixas + Pages) · HTML/CSS/JS sem framework

## Limitações conhecidas

- **A ordem exata das competências não atravessa edições.** Medido: a
  correlação entre o que 2020–2024 prevê e o que 2025 mostra é **+0,27** (e
  varia por área: LC +0,50 · CH −0,01). O que transfere é a nota (a TRI
  equaliza) e o princípio de que o ganho mora na fronteira do nível; o
  ranking exato, não.
- **Mais da metade das habilidades é medida por um único item** — 62 das 120.
  Por isso o produto trabalha no grão de **competência** (4 a 11 itens por
  medida) e publica sempre o lastro.
- **Perfil socioeconômico não cruza com desempenho.** As bases de
  participantes e resultados são desidentificadas pelo INEP e não são
  relacionáveis — decisão da fonte, respeitada aqui.
- **Só provas regulares.** Acessibilidade, reaplicação e BAM ficam fora —
  62 mil participantes de Belém/Ananindeua/Marituba merecem recorte próprio.
- **A referência é entre concluintes com escola identificada**, não "o Brasil
  inteiro".
- **MLOps foi descartado por decisão**, não por falta de tempo: dado anual,
  sem loop de feedback, sem decisão automatizada. O projeto é DataOps +
  produto analítico. O raciocínio está no [`PLANO.md`](PLANO.md).

## Estrutura

```
├── webapp/       o site (estático; os JSON exportados vivem em dados/)
├── export/       gera os JSON do site a partir dos marts, com validação
├── ingestion/    ingestão e geração dos seeds a partir de artefatos oficiais
├── quality/      suites do Great Expectations (fronteira raw)
├── dbt/          modelos, seeds, testes
├── dags/         DAG do Airflow
├── ci/           utilidades e testes da CI
└── .github/      workflows
```

## Documentação

- [`CLAUDE.md`](CLAUDE.md) — o diário de engenharia: cada armadilha dos dados,
  cada decisão metodológica e o que custou descobrir.
- [`PLANO.md`](PLANO.md) — o plano do produto e o que ficou fora, com o porquê.

## Licença

MIT — ver [LICENSE](LICENSE). Os dados são públicos, do INEP (microdados do
ENEM 2025 e Censo Escolar 2024) e do IBGE (malha territorial).

# enem-ml-data-ops

[![CI](https://github.com/Concs93/enem-ml-data-ops/actions/workflows/ci.yml/badge.svg)](https://github.com/Concs93/enem-ml-data-ops/actions/workflows/ci.yml)
[![Documentação](https://github.com/Concs93/enem-ml-data-ops/actions/workflows/docs.yml/badge.svg)](https://github.com/Concs93/enem-ml-data-ops/actions/workflows/docs.yml)

Pipeline de DataOps sobre os microdados do ENEM 2025 (INEP), do CSV bruto ao
diagnóstico pedagógico por escola — mais um **motor psicométrico** servido
como tabela e a **geografia em cinco níveis** que levam o diagnóstico de
município a país. Construído do zero, com testes nos dois lados da fronteira,
orquestração e documentação publicada. O plano do produto (e o que ficou fora,
com o porquê) está no [`PLANO.md`](PLANO.md).

**📊 [Documentação e lineage do pipeline](https://concs93.github.io/enem-ml-data-ops/)**

---

## O que ele entrega

Dado um `CO_ESCOLA`, o pipeline responde três perguntas:

1. **Onde a escola está** — média na escala oficial e percentil entre escolas
   comparáveis.
2. **O que os alunos dominam e o que precisa ser desenvolvido** — habilidade a
   habilidade, contra a referência nacional.
3. **Quanta confiança cabe em cada número** — quantos alunos, quantos itens, e
   o que não pôde ser medido.

Um recorte real, das maiores lacunas de uma escola em Matemática:

| habilidade | escola | nacional | dif. |
|---|---|---|---|
| H1 — *Reconhecer, no contexto social, diferentes significados e representações dos números e operações* | 8,0% | 59,5% | −51,5 |
| H4 — *Avaliar a razoabilidade de um resultado numérico na construção de argumentos* | 6,0% | 45,6% | −39,6 |
| H20 — *Interpretar gráfico cartesiano que represente relações entre grandezas* | 28,0% | 62,9% | −34,9 |

Duas das três estão na mesma competência de área — o tipo de padrão que a
agregação por competência existe para revelar.

## Arquitetura

```
CSV do INEP (2,6 GB)
  → raw            ingestão via COPY, tudo TEXT, sem interpretação
  → staging        tipagem + schema canônico (absorve drift entre edições)
  → intermediate   explosão das respostas + acerto por item
  → marts          diagnóstico por escola — fronteira de consumo
```

| camada | o que tem |
|---|---|
| `raw` | 4.810.772 resultados · 4.810.772 participantes · 6.105 itens |
| `marts` | 29.265 escolas · 120 habilidades · 30 competências |

**Números do pipeline:** 31 modelos · 76 testes dbt · 22 expectations na
fronteira · 23 tasks orquestradas · execução completa em 43 min.

### A validação que sustenta tudo

A correlação entre o **parâmetro de dificuldade da TRI** (calibrado pelo INEP)
e a **taxa de acerto calculada do zero** a partir dos vetores de resposta:

| área | correlação | taxa média |
|---|---|---|
| CH | −0,808 | 35,8% |
| CN | −0,799 | 32,6% |
| LC | −0,910 | 45,1% |
| MT | −0,854 | 31,9% |

São dois caminhos independentes concordando sobre quais itens são difíceis.
Se essa correlação vier fraca, alguma junção quebrou — e nenhum outro teste
pegaria.

## O motor psicométrico

Os parâmetros de TRI (`a`, `b`, `c`) que o INEP publica viraram um motor
consultável — **como tabela versionada pelo dbt, não como binário**:

- **Curva e informação por item × nível** (`mart_curva_item`): a prioridade de
  estudo ordena pelo **ganho de um passo** — quanto o mesmo avanço de nível
  rende em cada conteúdo — nunca por taxa de erro: a habilidade que a pessoa
  mais erra costuma ser a pior escolha de estudo no curto prazo. A informação
  de Fisher viaja no mart como o fato psicométrico subjacente.
- **Calibração empírica nota → θ efetivo** (`mart_calibracao_nota`), medida
  em 1,27 a 1,33 milhão de participantes por área. Não corrige a escala do
  INEP (`nota = 100·θ + 500` é definição): mede a ponte *nota → acertos
  esperados*, que o INEP não publica. Coincidem no miolo (diferença ~0,2 entre
  450 e 700); afastam-se nas caudas — no topo porque a nota vem do padrão e
  não da contagem, no piso por causa das provas em branco.
- **Distribuição empírica de acertos por nota** (`mart_distribuicao_acertos`):
  valida entrada e responde "entre os participantes com a sua nota, esse
  total está no percentil X" — contagem pura, sem teoria.

E a **geografia em cinco níveis** (município → região imediata IBGE → UF →
região → país), com regra dupla de publicação (≥ 3 escolas e ≥ 50
participantes) aplicada honestamente em todo nível: 45% dos municípios têm
uma escola só, e publicá-los seria publicar a escola com outro rótulo. Quem
não passa não some — sobe de nível com o motivo declarado.

## O que os dados esconderam

O trabalho interessante deste projeto não foi mover dados, foi encontrar o que
estava errado em silêncio:

- **Nota 0 é sentinela, não desempenho.** Existem milhares de notas exatamente
  0 e *nenhuma* entre 0 e 250 — o piso real da escala é ~310. São provas
  entregues em branco. Um `avg()` ingênuo distorcia a média de 218 escolas em
  **até 147,5 pontos**.
- **Uma habilidade que sumia do relatório.** A habilidade 8 de LC é coberta só
  por itens de espanhol; em 1.824 escolas sem alunos de espanhol, a linha
  simplesmente não existia. O mart passou a montar um grid completo e a
  distinguir *não avaliada* de *não administrada*.
- **Um item escorado que o INEP havia descartado.** O `CN 96748` não é anulado,
  mas foi abandonado por falha de convergência da TRI — e escapava do filtro,
  entrando no diagnóstico como item normal.
- **Ingestão que só parecia idempotente.** O `DROP TABLE` funcionava enquanto
  nada dependia da `raw`. A primeira execução orquestrada — a primeira vez que
  o pipeline rodou a *segunda* vez — quebrou na hora.

## Como rodar

Requer Docker e Python 3.12+. Os microdados **não** estão no repositório
(2,6 GB); baixe em [Dados Abertos do INEP](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem)
e coloque em `data/raw/`.

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env          # ajuste as credenciais
. .\load_env.ps1
docker compose up -d

python -m ingestion.load_raw --base itens_prova   --path data/raw/ITENS_PROVA_2025.csv
python -m ingestion.load_raw --base resultados    --path data/raw/RESULTADOS_2025.csv
python -m ingestion.load_raw --base participantes --path data/raw/PARTICIPANTES_2025.csv
python -m quality.expectations_raw

cd dbt; dbt deps; dbt seed
# um modelo por vez -- ver CLAUDE.md, "Restrições de máquina"
```

Ou tudo de uma vez, pelo Airflow:

```powershell
docker compose --profile airflow up -d
docker compose exec airflow airflow pools set banco_pesado 1 "uma varredura por vez"
docker compose exec airflow airflow dags trigger enem_pipeline
```

Os **seeds são versionados** de propósito: dá para clonar e rodar `dbt seed`
sem baixar os microdados.

## Stack

**Postgres** · **dbt** (transformação e testes) · **Great Expectations**
(validação de fronteira) · **Airflow 3** (orquestração) · **Docker** ·
**GitHub Actions** (CI em três faixas + Pages)

## Limitações conhecidas

- **Perfil socioeconômico não cruza com desempenho.** As bases de participantes
  e resultados são desidentificadas pelo INEP e não são relacionáveis — por
  decisão da fonte, respeitada aqui.
- **A referência é entre concluintes com escola identificada**, não "o Brasil
  inteiro". É o peer group correto para diagnóstico de escola, mas precisa ser
  lido assim.
- **Só provas regulares.** Acessibilidade, reaplicação e BAM ficam fora —
  62 mil participantes de Belém/Ananindeua/Marituba merecem recorte próprio.
- **Mais da metade das habilidades é medida por um único item.** Por isso o
  diagnóstico publica `n_itens_validos` e agrega também por competência.

## Estrutura

```
├── ingestion/    ingestão e geração dos seeds a partir de artefatos oficiais
├── quality/      suites do Great Expectations (fronteira raw)
├── dbt/          modelos, seeds, testes
├── dags/         DAG do Airflow
├── ci/           utilidades da CI
└── .github/      workflows
```

O [`CLAUDE.md`](CLAUDE.md) traz as decisões metodológicas, as armadilhas dos
dados e as restrições de máquina — é o diário técnico do projeto.

## Licença

MIT — ver [LICENSE](LICENSE).

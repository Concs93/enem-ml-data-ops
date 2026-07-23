# enem-ml-data-ops

Pipeline de DataOps + MLOps sobre os microdados do ENEM 2025 (INEP). Projeto de
portfólio, construído do zero, do CSV bruto ao modelo servido como API.

**Objetivo do produto:** diagnóstico pedagógico por escola. Dado um `CO_ESCOLA`,
produzir um retrato de desempenho dos seus participantes — percentil, quais
habilidades os alunos dominam e quais precisam ser desenvolvidas — no nível do
item, não só da nota final.

---

## Estado atual

| Etapa | Status |
|---|---|
| 1 — Ingestão (camada raw) | concluída |
| 2 — Staging + schema canônico (dbt) | concluída |
| 3 — Desmembrar respostas + acerto por item | concluída e validada |
| 4 — Marts + diagnóstico por escola | próxima |
| 5 — Qualidade de dados (Great Expectations) | pendente |
| 6 — Orquestração (Airflow) | pendente |
| 7 — CI/CD + docs no GitHub Pages | pendente |
| MLOps | pendente |

### Edições da Etapa 3 (aplicadas e validadas)

Preservar itens anulados/abandonados, tratar `item_abandonado` como não
avaliável, piso de 5% em `taxa_acerto_plausivel` e o novo teste
`item_sem_parametro` — todas **aplicadas** (ver "Itens problemáticos" e
"Validação"). Removido o `where acertou is not null` do `agrega_por_item`; as
flags `item_anulado`/`item_abandonado` sobem até o agregado e a taxa vira nula
via `case when item_anulado or item_abandonado then null`. A correlação
continuou idêntica (CH −0,808 · CN −0,799 · LC −0,910 · MT −0,854) e a MT hab 21
voltou ao agregado como "não avaliada". `dbt test` verde (16/16).

### Decisões em aberto

- **Filtro `co_escola is not null` no macro ou nas camadas de cima?** Hoje está
  nos macros de explode (corta 64% do volume e viabiliza a máquina, filtrando
  antes do `substring`), o que redefine a referência "nacional" como *entre
  concluintes com escola identificada*. Reenquadramento provável: esse recorte é
  o *peer group correto* para um diagnóstico de escola — concluintes, não a
  população inteira do ENEM (treineiros, reingressantes) — não só uma concessão
  à máquina. Se confirmado, deixa de ser dívida e vira decisão.
- **BAM (Belém/Ananindeua/Marituba)** está fora por `is_regular`. São 62 mil
  participantes — nenhuma escola dessas cidades recebe diagnóstico. Merece
  recorte próprio na Etapa 4.

---

## Ambiente

Windows + PowerShell. Postgres em Docker. **Sempre** rodar da raiz do projeto:

```powershell
.\.venv\Scripts\Activate.ps1
. .\load_env.ps1          # o ponto e o espaço na frente são obrigatórios
docker compose up -d
```

`load_env.ps1` carrega o `.env` na sessão e define
`$env:DBT_PROFILES_DIR = (Resolve-Path ".\dbt").Path`. Precisa rodar uma vez por
terminal novo. Sem isso, o dbt não acha o `profiles.yml` nem as credenciais.

Acesso ao banco:

```powershell
docker compose exec postgres psql -U admincroc -d enem2025
```

O `profiles.yml` é versionado e usa `env_var()` — nunca colocar senha nele.

---

## Restrições de máquina — LEIA ANTES DE RODAR QUALQUER COISA

A máquina é limitada e este pipeline já derrubou o Postgres, o Docker Desktop e
encheu o disco do sistema mais de uma vez. Regras não negociáveis:

- **NUNCA rodar `dbt run` sem `--select`.** Ele dispara os modelos em paralelo,
  quatro threads famintas ao mesmo tempo, e derruba o banco. Sempre um modelo
  por vez.
- Os modelos `int_acerto_item_*` levam **minutos** cada. Isso é normal.
- Os `int_respostas_*` são views: reconstroem em segundos.
- Docker está configurado com 8 GB de memória e disco em
  `E:\Projetos\00 - Data Ops, ML Ops e ENEM\docker`. Não mover de volta para o
  `C:` — o `.vhdx` do WSL2 só cresce, nunca encolhe.
- **`Ctrl+C` não cancela a consulta.** O dbt é só o cliente; o Postgres continua
  moendo e consumindo disco. Para cancelar de verdade:

```sql
select pid, state, wait_event_type, wait_event, now() - query_start as duracao
from pg_stat_activity where state != 'idle' and pid != pg_backend_pid();

select pg_cancel_backend(PID);      -- líder = o que tem state=active SEM wait_event
select pg_terminate_backend(PID);   -- se o primeiro não surtir efeito
```

- Se o disco encher: fechar o Docker Desktop pela bandeja e `wsl --shutdown`
  libera o swap (que fica no `C:` mesmo com os dados no `E:`).
- `MessageQueueSend` em workers paralelos é contrapressão normal, não travamento.

---

## Arquitetura

```
CSV bruto (INEP)
  → raw            ingestão via COPY, tudo TEXT, sem interpretação
  → staging        tipagem + schema canônico (dbt, views)
  → intermediate   explosão das respostas + agregação por item
  → marts          diagnóstico por escola (Etapa 4)
```

### Estrutura

```
enem-ml-data-ops/
├── load_env.ps1
├── docker-compose.yml          só Postgres (pgAdmin foi removido)
├── ingestion/
│   ├── config.py               colunas de cada base, separador, encoding
│   ├── load_raw.py             ingestão via COPY, idempotente, em blocos
│   └── build_seeds.py          gera os seeds a partir dos artefatos do INEP
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml            usa env_var, versionado
│   ├── packages.yml            dbt_utils
│   ├── macros/
│   │   ├── util.sql            num, inteiro, grande, booleano
│   │   ├── explode_respostas.sql        CH, CN, MT
│   │   ├── explode_respostas_lc.sql     LC (caso especial)
│   │   └── agrega_por_item.sql
│   ├── seeds/
│   │   ├── dominios.csv        500 pares código→rótulo, 59 variáveis
│   │   └── co_prova.csv        74 versões de prova classificadas
│   ├── models/
│   │   ├── staging/
│   │   │   ├── _sources.yml
│   │   │   ├── _staging.yml
│   │   │   ├── stg_itens.sql
│   │   │   ├── stg_participantes.sql
│   │   │   └── stg_resultados.sql
│   │   └── intermediate/
│   │       ├── _intermediate.yml
│   │       ├── int_respostas_{mt,ch,cn,lc}.sql       views
│   │       ├── int_acerto_item_{mt,ch,cn,lc}.sql     tables
│   │       ├── int_acerto_item_escola.sql
│   │       └── int_acerto_item_nacional.sql
│   └── tests/
│       ├── stg_itens_grao_unico.sql
│       ├── taxa_acerto_plausivel.sql
│       └── item_sem_parametro.sql
└── data/raw/                   CSVs do INEP, fora do Git
```

### Materialização

- `staging` → view, **exceto `stg_resultados`** que é **table** (senão
  reconverte 4,8 milhões de linhas de texto a cada consulta).
- `intermediate` → `int_respostas_*` são **view** (o grão fino nunca toca o
  disco); `int_acerto_item_*` são **table**.
- Os `int_acerto_item_{area}` usam
  `pre_hook="set max_parallel_workers_per_gather = 0"`. Isso **não é opcional**:
  cada worker paralelo recebe sua própria fatia de memória, e é isso que derruba
  o servidor.

### Ordem de construção

```powershell
cd dbt
dbt deps
dbt seed
dbt run --select stg_itens
dbt run --select stg_participantes
dbt run --select stg_resultados

dbt run --select int_respostas_mt
dbt run --select int_respostas_ch
dbt run --select int_respostas_cn
dbt run --select int_respostas_lc

dbt run --select int_acerto_item_mt
dbt run --select int_acerto_item_ch
dbt run --select int_acerto_item_cn
dbt run --select int_acerto_item_lc

dbt run --select int_acerto_item_escola
dbt run --select int_acerto_item_nacional

dbt test
```

---

## Armadilhas dos dados — cada uma custou horas

### As bases de participante e resultado NÃO são relacionáveis

O dicionário é explícito: `NU_SEQUENCIAL` (chave de RESULTADOS) é distinta de
`NU_INSCRICAO` (chave de PARTICIPANTES) e **não pode ser usada para relacionar
as duas bases**. É desidentificação deliberada.

As duas têm exatamente 4.810.772 linhas, o que tenta a ligá-las pela ordem.
**Não fazer isso** — a ordem não é garantida e reconstruir o vínculo contorna
uma proteção intencional. Qualquer análise cruzando perfil socioeconômico com
desempenho individual está fora do escopo desta edição.

### `CO_POSICAO` não é a posição na prova

É um identificador sequencial global do item — começa em centenas, não em 1. A
posição real (1 a 45, ou 1 a 50 em LC) é reconstruída em `stg_itens` com
`row_number() over (partition by CO_PROVA order by CO_POSICAO)`.

Usar o `CO_POSICAO` cru quebra silenciosamente a junção com as respostas.

### Junção item ↔ resposta é SEMPRE por `(co_prova, posicao)`

As quatro cores regulares contêm os mesmos itens **em ordens diferentes**. A
posição 7 é um item na prova Azul e outro na Verde. Juntar só por `posicao`
produz resultado plausível e completamente falso.

### LC: gabarito do participante tem 50 posições, resposta tem 45

Layout da string `gabarito_lc`: inglês em 1–5, espanhol em 6–10, comuns em
11–50. A resposta do aluno tem 45 posições (5 da língua dele + 40 comuns).
Indexar uma pela outra desalinha 40 dos 45 itens.

**Solução:** em LC, o gabarito vem de `stg_itens.gabarito` (catálogo), não da
string. A junção já garante que é o item certo, e as duas fontes usam a mesma
codificação (verificado: 4410/4410 iguais em MT).

No catálogo, as posições 1–10 de LC são os itens de língua estrangeira,
**intercalados** entre inglês e espanhol (não 1–5 / 6–10). A junção filtra por
`(i.cod_lingua is null or i.cod_lingua = p.cod_lingua)` e um `row_number`
particionado por aluno renumera de 1 a 45.

### `NU_INSCRICAO` estoura o `integer`

12 dígitos; o `integer` do Postgres vai até 2.147.483.647. Usar o macro
`grande()` (bigint). Os scripts oficiais do INEP sinalizam isso com
`integer64='character'`.

Nota: o erro **não aparece no `dbt run`** (view só guarda a definição), só quando
alguém consulta ou o `dbt test` roda.

### `substring` não aceita `bigint`

`row_number()` devolve `bigint` e
`substring(texto from bigint for integer)` não existe no Postgres. Sempre
`::int` na posição.

### Duas divergências entre os artefatos oficiais do INEP

O `build_seeds.py` reconcilia automaticamente e reporta:

- `TP_STATUS_REDACAO` — o script R lista 7 níveis para 8 rótulos; falta o
  código 9 ("Parte desconectada"). Resolvido pelo dicionário.
- `TP_COR_RACA` — o dicionário lista 6 categorias, o script R tem 7 (inclui o
  código 6, "Não dispõe da informação"). Mantida a versão mais completa.

Regra do script: quando o dicionário traz *mais* códigos, ele prevalece; quando
traz *menos*, mantém-se o script R e sinaliza (leitura incompleta de planilha
costuma ser falha de parsing, não divergência real).

### Encoding e separador

CSV separado por `;` e em `latin-1` (não UTF-8).

---

## Fatos dos dados (ENEM 2025)

### Volumes

- `raw.resultados_2025` — 4.810.772 linhas, 41 colunas
- `raw.participantes_2025` — 4.810.772 linhas, 35 colunas
- `raw.itens_prova_2025` — 6.105 linhas, 14 colunas

### Cobertura

- 36,1% dos resultados têm `CO_ESCOLA` (1.739.028). É a escola de conclusão do
  ensino médio, vinculada ao Censo Escolar — só quem está concluindo agora tem.
- **17.874 escolas** com 20+ participantes presentes em MT.
- 97,4% dos presentes em MT fizeram prova regular.

### Provas

132 versões (33 por área), 565 itens distintos no total. Dentro das regulares o
conjunto é **idêntico** — as cores são a mesma prova reordenada:

| área | códigos regulares | cores | itens |
|---|---|---|---|
| CH | 1447–1450 | Azul, Amarela, Branca, Verde | 45 |
| CN | 1483–1486 | Azul, Amarela, Verde, Cinza | 45 |
| LC | 1459–1462 | Azul, Amarela, Verde, Branca | 50 |
| MT | 1471–1474 | Azul, Amarela, Verde, Cinza | 45 |

**A quarta cor não é a mesma em todas as áreas** — CH e LC usam Branca, CN e MT
usam Cinza. São dias diferentes de prova.

Tipos de aplicação no seed `co_prova`: `regular` (16), `acessibilidade` (20),
`reaplicacao` (14), `bam` (24). A regra de classificação é durável: é regular
quando o rótulo é só o nome da cor, sem qualificador.

Distribuição de participantes em MT: regular 3.176.917, BAM 62.206,
acessibilidade 20.548, reaplicação 665.

### Língua estrangeira

`cod_lingua = 0` → Inglês, `1` → Espanhol (rótulo oficial).

### Itens problemáticos

**Cinco** itens ficaram **não avaliáveis** (taxa nula no agregado, preservados
no grão para aparecerem como "não avaliados"). Todos os cinco **sem parâmetro de
TRI** — nenhum entrou na escoragem oficial. No fonte do INEP eles vêm com
`IN_ITEM_ABAN` marcado, então `item_abandonado` é o superconjunto e
`item_anulado` (gabarito `X`) é o subconjunto dos anulados — por isso os anulados
aparecem com as **duas** flags verdadeiras.

| co_item | área | hab | gabarito | anulado | motivo |
|---|---|---|---|---|---|
| 141557 | CN | 1  | X | sim | Previamente exposto |
| 141774 | CN | 9  | X | sim | Previamente exposto |
| 31350  | MT | 21 | X | sim | Previamente exposto |
| 96748  | CN | 25 | B | não | Problema de convergência |
| 97593  | MT | 22 | A | não | Problema de convergência |

Os três **anulados** saíram por "Previamente exposto" (item vazado/reaproveitado),
gabarito `X`, sem resposta correta. Os dois de **gabarito válido** saíram por
"Problema de convergência" — a calibração da TRI não convergiu, então não têm
parâmetro e não foram escorados. Mesmo tratamento: não avaliáveis.

**Impacto na cobertura por habilidade:**

- **MT hab 21 — ZERO itens válidos** (o anulado 31350 era o único). Não pode ser
  diagnosticada em 2025. O relatório precisa dizer isso, não omitir.
- **CN hab 9 · CN hab 25 · MT hab 22 — 1 item válido cada** (perderam um item
  para anulado/abandonado). Ficam frágeis: um item não é a medida de uma
  habilidade, é a medida daquele item. Merecem ressalva no relatório.

Nota histórica: até a Etapa 3, o `96748` (abandonado, **não** anulado) escapava
do `where acertou is not null` e entrava no diagnóstico com taxa calculada, como
se fosse item normal — um item que o INEP havia tirado da escoragem. Foi a
preservação de anulados/abandonados que expôs isso; o `96748` sequer estava
documentado antes.

### Itens por habilidade — relevante para a Etapa 4

30 habilidades por área (MT tem 29 após o anulado). Média de itens por
habilidade: CH 1,50 · CN 1,43 · LC 1,67 · MT 1,52.

Consequência: *precisão* não é problema (uma escola com 100 alunos tem 100
respostas por item), mas *validade de conteúdo* é. Um item não representa a
habilidade inteira. Duas saídas combináveis: reportar o número de itens que
embasa cada habilidade, e agregar também no nível de **competência de área**.

**Lacuna conhecida:** os microdados trazem só o *número* da habilidade, não a
descrição nem a competência. Isso está na Matriz de Referência do ENEM, que é
pública mas não vem no pacote — vai precisar de um seed montado à mão e
versionado.

---

## Validação — a verificação que importa

A correlação entre `param_dificuldade` (parâmetro **b** da TRI, calibrado pelo
INEP) e `taxa_acerto_nacional` (calculada do zero a partir dos vetores de
resposta) **tem que ser fortemente negativa**. São dois caminhos independentes
concordando sobre quais itens são difíceis.

```sql
select area,
       round(corr(param_dificuldade, taxa_acerto_nacional)::numeric, 3) as correlacao,
       round(avg(taxa_acerto_nacional), 1) as taxa_media,
       count(*) as itens
from staging.int_acerto_item_nacional
group by 1 order by 1;
```

Valores obtidos e validados:

| área | correlação | taxa média |
|---|---|---|
| CH | −0,808 | 35,8% |
| CN | −0,799 | 32,6% |
| LC | −0,910 | 45,1% |
| MT | −0,854 | 31,9% |

LC vir mais alta é esperado — historicamente é a área de maior acerto no ENEM.

**Se a correlação vier fraca ou positiva, a junção está quebrada.** Foi assim
que o bug de LC foi pego: −0,027 e taxa de 22,6% (colada no acaso de 20%).
Nenhum outro teste teria pego.

### Sobre o limiar de taxa de acerto

Taxa abaixo de 20% **não** indica erro. O parâmetro de acerto casual (`c`)
desses itens fica entre 0,063 e 0,125, então o piso da curva é 6-12%, não 20% —
o aluno não chuta ao acaso, escolhe convictamente o distrator. Itens muito
difíceis chegam legitimamente a 8-15%. O piso do teste é **5%**.

---

## Decisões metodológicas

- **Só provas regulares** entram no diagnóstico. Acessibilidade fica **fora**
  (decisão fechada) — deixa ~20 mil participantes com deficiência fora do
  diagnóstico da própria escola, custo assumido. Reaplicação e BAM têm itens
  próprios e não são comparáveis na mesma métrica.
- **Só participantes presentes** (`cod_presenca = 1`).
- **Só quem tem `CO_ESCOLA`** — participante sem escola não pode ser atribuído a
  escola nenhuma. Consequência documentada: a referência "nacional" é entre
  concluintes com escola identificada.
- **Item anulado sai do cálculo**, sem crédito e sem penalidade. Não é uma
  escolha entre duas opções: em TRI a nota não é contagem de acertos, é
  estimativa de traço latente. Item sem gabarito não carrega informação sobre
  proficiência. Como as notas oficiais foram calculadas assim, excluir mantém o
  diagnóstico na mesma contabilidade da nota que o participante recebeu.
- **Ausência estrutural não é fracasso.** Um aluno que fez inglês não respondeu
  os itens de espanhol — isso é item não administrado, nunca erro. A junção por
  `cod_lingua` resolve na origem.
- **N mínimo para publicar diagnóstico:** definir na Etapa 4 (referência: 20
  participantes). Escola com poucos alunos gera resultado instável e
  potencialmente identificável.
- **Staging faz três coisas e só três:** renomeia, converte tipo, mantém
  um-para-um com a fonte. Sem junções, sem filtros de regra de negócio, sem
  agregação. Filtro de prova regular e de presença é decisão de análise e vive
  na camada intermediate.

---

## Convenções de código

- Modelos dbt em SQL, sem `CREATE TABLE` manual — o dbt materializa.
- Lógica repetida entre áreas vira **macro**, nunca copiar e colar.
- Listas de áreas com laço Jinja (`{% set areas = ['mt','ch','cn','lc'] %}`), para
  que acrescentar uma área seja uma linha.
- Colunas explícitas em `union all`, nunca `select *` entre modelos de origens
  diferentes.
- Decisões de escopo viram **seed versionado**, não `WHERE` com números mágicos.
- Nomes canônicos em português nas camadas acima de raw (`renda_familiar`, não
  `Q007`), para que a troca de edição não propague mudança de nome.
- Prefixo `qtd_` para variáveis de quantidade e `tem_` para binárias no
  questionário socioeconômico.
- **Nunca apagar um teste para o pipeline ficar verde.** Falha de teste é
  descoberta: investigar, entender, e então ajustar o teste documentando o
  porquê.

---

## Não commitar

`.env`, `.venv/`, `data/raw/`, `dbt/target/`, `dbt/logs/`, `logs/`, `docs/`,
`dbt/dbt_packages/`, `dbt/.user.yml`.

`docs/` são os Volumes (narrativa do projeto, HTML) — publicados por outro
caminho, fora do versionamento.

Os seeds em `dbt/seeds/` **devem** ser commitados, mesmo sendo gerados pelo
`build_seeds.py` — é o que permite clonar e rodar `dbt seed` sem baixar 2,6 GB
de microdados, e é o que faz a decisão de escopo aparecer no diff.

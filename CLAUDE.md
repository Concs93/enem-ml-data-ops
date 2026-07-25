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
| 4 — Marts + diagnóstico por escola | concluída e validada |
| 5 — Qualidade de dados (Great Expectations) | concluída e validada |
| 6 — Orquestração (Airflow) | concluída e validada |
| 7 — CI/CD + docs no GitHub Pages | concluída |
| MLOps | pendente |

### Etapa 4 — o que ficou de pé

Schema `marts` (sem prefixo, via `generate_schema_name`), três modelos e quatro
testes singulares novos. `dbt test` verde: **31/31**.

| modelo | linhas | tempo |
|---|---|---|
| `dim_escola` | 29.904 | 3s |
| `mart_escola_area` | 116.906 | 12s |
| `mart_diagnostico_habilidade` | 3.507.180 | ~1min |

O `dim_escola` é maior que as 29.265 escolas do diagnóstico porque cobre **toda**
escola nos resultados, inclusive as que só têm participantes de reaplicação/BAM.
É de propósito: dimensão descreve quem existe, o fato decide quem entra.

### Etapa 5 — o que ficou de pé

Seed da Matriz de Referência derivado do PDF oficial, correção do sentinela das
notas zeradas, mart de competência e a guarda de fronteira com Great
Expectations. `dbt test` verde: **39/39**.

| modelo | linhas |
|---|---|
| `matriz_referencia` (seed) | 120 |
| `mart_diagnostico_competencia` | 876.795 |

A Matriz **não** precisou de transcrição manual — o `build_matriz.py` deriva do
PDF oficial. Aquela pendência do CLAUDE.md ("único dado que não sai de script")
deixou de existir.

### Etapa 6 — o que ficou de pé

DAG `enem_pipeline` com **23 tasks** em quatro grupos, imagem própria (2,98 GB)
e o pool que serializa o que é pesado. Sobe pelo perfil:

```powershell
docker compose --profile airflow up -d          # UI em localhost:8080
docker compose exec airflow airflow pools set `
  banco_pesado 1 "Uma varredura grande do Postgres por vez"
docker compose --profile airflow down           # devolve a memoria
```

A senha do `admin` é gerada no primeiro boot e sai no
`docker compose logs airflow` (e em
`/opt/airflow/simple_auth_manager_passwords.json.generated`).

**Execução completa validada: 23/23 tasks `success` em 43,1 min**, incluindo o
`dbt test` (39/39) no fim. Reconstruiu tudo a partir dos CSVs e reproduziu os
números idênticos — mesmas contagens nos quatro marts e mesmas correlações
(CH −0,808 · CN −0,799 · LC −0,910 · MT −0,854).

O desenho se sustentou na prática, medido no banco de metadados:

- **0 sobreposições** entre tasks do pool `banco_pesado` — a serialização
  funcionou.
- **6 pares simultâneos** entre as `int_respostas_*`, que é C(4,2): as quatro
  views leves rodaram **juntas**. O pool não as atrapalhou.

Tasks mais lentas: `carrega_resultados` 478s · `int_acerto_item_lc` 377s ·
`int_acerto_item_mt` 305s · `stg_resultados` 225s.

Quatro armadilhas que já morderam aqui:

- **`DROP TABLE` da ingestão precisa de `CASCADE`.** Ver a armadilha
  "Idempotência da ingestão" abaixo — foi o único erro real da primeira
  execução completa.
- **O contexto de build é a raiz**, não `airflow/` — o `Dockerfile` precisa
  alcançar o `requirements.txt`. Daí o `.dockerignore`, sem o qual os 2,6 GB
  de `data/raw` iriam para o daemon a cada build.
- **`POSTGRES_HOST`/`PORT` são sobrescritos no serviço do Airflow.** Dentro de
  um container, `localhost` é o próprio container; o banco de dados é
  `postgres:5432` (nome do serviço, porta interna), não o que está no `.env`.
- **dbt em venv separado** (`/home/airflow/projeto-venv`). Airflow e dbt
  disputam versões de `jinja2` e `pydantic`; instalar juntos degrada um dos
  dois e o erro aparece longe da causa.

### Etapa 7 — o que ficou de pé

Dois workflows em `.github/workflows/`, em **três faixas** de verificação
segundo o quanto de dado cada uma precisa:

| faixa | precisa de | pega | onde |
|---|---|---|---|
| 1 | nada | sintaxe, `ref()` quebrado, import do DAG, dependência faltando | CI |
| 2 | Postgres com tabelas vazias | coluna inexistente, tipo, junção | CI |
| 3 | os 2,6 GB | regressão de **lógica** | Airflow, local |

A Faixa 2 usa `ci/cria_raw_vazia.py`, que deriva as tabelas de
`ingestion/config.py` (mesma regra dos seeds: derivar, nunca transcrever) e
depois roda `dbt build` normal — **59 nós verdes em 17s**, porque a fonte
vazia faz o trabalho sozinha.

**Não usar `dbt build --empty`.** A flag embrulha cada ref numa subconsulta
com alias próprio (`_dbt_limit_subq_x`), e o padrão `{{ ref('x') }} r` deste
projeto vira dois aliases em sequência: `syntax error at or near "r"` em 6
modelos. Além de desnecessária — aqui a raw é vazia de verdade.

A CI **não usa nenhum segredo**, e isso é desenho, não descuido: o Postgres do
job é descartável e morre em minutos. Se ela precisasse de senha real, seria
sinal de que está tocando um ambiente que não deveria.

As Data Docs do Great Expectations **não** são publicadas pela CI: elas
relatam uma validação, e num banco vazio não há o que validar.

### Decisões em aberto

- **BAM (Belém/Ananindeua/Marituba)** está fora por `is_regular`. São 62 mil
  participantes — nenhuma escola dessas cidades recebe diagnóstico. Merece
  recorte próprio: o mesmo pipeline com referência própria.
- **Por que CH tem quatro vezes mais prova em branco que LC?** 2.489 contra 663,
  no mesmo dia de aplicação e praticamente a mesma população. Não há explicação
  ainda; registrar a pergunta é melhor que inventar a resposta.

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
- **Recursos reais (medidos em 25/07/2026, não estimados):** máquina com
  **32 GB de RAM** e **4 CPUs**; `C:` com 14,3 GB livres, `E:` com 119,2 GB.
  A VM do Docker tem teto de **20 GB** (`.wslconfig`, `memory=20GB`) e
  devolve o que não usa (`autoMemoryReclaim=gradual`).
  **RAM nunca foi o gargalo — são os 4 núcleos.** Aumentar o teto não torna o
  paralelismo seguro: a regra do `--select` continua valendo igual.
- **Teto por container** no `docker-compose.yml`, dentro dos 20 GB da VM:
  Postgres de dados 13 GB · Airflow 4 GB (e 2 CPUs) · Postgres de metadados
  512 MB. O teto não desconfia do Postgres — **localiza o estrago**: sem ele,
  uma consulta que derrapa leva a VM inteira, que foi como o Docker Desktop
  caiu mais de uma vez.
- O Postgres de dados sobe com `shared_buffers=2GB`,
  `effective_cache_size=8GB`, `work_mem=64MB`. O padrão da imagem
  (128 MB / 4 GB / 4 MB) é para uma máquina qualquer; o `pgdata` inteiro tem
  8,8 GB e cabe em cache.
- Disco do Docker em `E:\Projetos\00 - Data Ops, ML Ops e ENEM\docker`. Não
  mover de volta para o `C:` — o `.vhdx` do WSL2 só cresce, nunca encolhe
  (hoje 19,5 GB para 12,6 GB de conteúdo real).
- **Nada do `.wslconfig` vale até `wsl --shutdown`** com o Docker Desktop
  fechado pela bandeja. Isso já mordeu uma vez: o arquivo dizia
  `memory=16GB` e `swap=8GB` no `E:`, e a VM rodava havia 63 h com os padrões
  do WSL (16 GB de teto por coincidência, 4 GB de swap no `C:`) — a
  configuração estava escrita e **nunca aplicada**. Conferir sempre depois:

```powershell
wsl -d docker-desktop -e sh -c "free -m; cat /proc/swaps"   # swap deve dar 8192
Get-ChildItem E:\wsl                                        # swap.vhdx deve existir aqui
```

- **Fora do `C:` por decisão:** swap do WSL2 (`swapFile=E:\\wsl\\swap.vhdx`),
  disco do Docker e o arquivo de paginação do Windows (`E:\pagefile.sys`, com
  o do `C:` removido). O `C:` é o disco do sistema e vive perto do limite;
  cada um desses arquivos passa de 8 GB.
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
  → marts          diagnóstico por escola — schema próprio, fronteira de consumo
```

O que está em `marts` é contrato com o mundo externo (a futura API); o que está
em `staging` é cozinha interna.

### Estrutura

```
enem-ml-data-ops/
├── load_env.ps1
├── docker-compose.yml          só Postgres (pgAdmin foi removido)
├── .dockerignore               mantem data/raw fora do contexto de build
├── airflow/
│   └── Dockerfile              imagem oficial + venv separado do projeto
├── dags/
│   └── enem_pipeline.py        23 tasks, pool banco_pesado
├── ingestion/
│   ├── config.py               colunas de cada base, separador, encoding
│   ├── load_raw.py             ingestão via COPY, idempotente, em blocos
│   ├── build_seeds.py          gera os seeds a partir dos artefatos do INEP
│   └── build_matriz.py         gera o seed da Matriz a partir do PDF oficial
├── quality/
│   └── expectations_raw.py     Great Expectations na fronteira (camada raw)
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml            usa env_var, versionado
│   ├── packages.yml            dbt_utils
│   ├── macros/
│   │   ├── util.sql            num, inteiro, grande, booleano
│   │   ├── explode_respostas.sql        CH, CN, MT
│   │   ├── explode_respostas_lc.sql     LC (caso especial)
│   │   ├── agrega_por_item.sql
│   │   └── generate_schema_name.sql     marts sem prefixo staging_
│   ├── seeds/
│   │   ├── dominios.csv        500 pares código→rótulo, 59 variáveis
│   │   ├── co_prova.csv        74 versões de prova classificadas
│   │   └── matriz_referencia.csv  120 habilidades → competência + descrição
│   ├── models/
│   │   ├── staging/
│   │   │   ├── _sources.yml
│   │   │   ├── _staging.yml
│   │   │   ├── stg_itens.sql
│   │   │   ├── stg_participantes.sql
│   │   │   └── stg_resultados.sql
│   │   ├── intermediate/
│   │   │   ├── _intermediate.yml
│   │   │   ├── int_respostas_{mt,ch,cn,lc}.sql       views
│   │   │   ├── int_acerto_item_{mt,ch,cn,lc}.sql     tables
│   │   │   ├── int_acerto_item_escola.sql
│   │   │   └── int_acerto_item_nacional.sql
│   │   └── marts/
│   │       ├── _marts.yml
│   │       ├── dim_escola.sql
│   │       ├── mart_escola_area.sql
│   │       ├── mart_diagnostico_habilidade.sql
│   │       └── mart_diagnostico_competencia.sql
│   └── tests/
│       ├── stg_itens_grao_unico.sql
│       ├── taxa_acerto_plausivel.sql
│       ├── item_sem_parametro.sql
│       ├── percentil_publicavel.sql
│       ├── taxa_condiz_com_status.sql
│       ├── habilidades_completas.sql
│       ├── marts_mesma_populacao.sql
│       ├── nota_zero_nao_entra_na_media.sql
│       └── competencia_cobre_habilidades.sql
└── data/raw/                   CSVs do INEP, fora do Git
```

### Materialização

- `staging` → view, **exceto `stg_resultados`** que é **table** (senão
  reconverte 4,8 milhões de linhas de texto a cada consulta).
- `intermediate` → `int_respostas_*` são **view** (o grão fino nunca toca o
  disco); `int_acerto_item_*` são **table**.
- `marts` → **table**, com `+schema: marts` e o `pre_hook` no nível da pasta (no
  `dbt_project.yml`), para que todo mart novo já nasça com paralelismo desligado.
- Os `int_acerto_item_{area}` usam
  `pre_hook="set max_parallel_workers_per_gather = 0"`. Isso **não é opcional**:
  cada worker paralelo recebe sua própria fatia de memória, e é isso que derruba
  o servidor.
- O macro `generate_schema_name` faz o `+schema` valer como está. Sem ele o dbt
  concatena e o schema viraria `staging_marts`.
- `vars: n_minimo_diagnostico: 20` no `dbt_project.yml` — o N mínimo mora num
  lugar só e aparece no diff. Vira seed se um dia ganhar estrutura (N por rede,
  por exemplo).

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

dbt run --select dim_escola
dbt run --select mart_escola_area
dbt run --select mart_diagnostico_habilidade    # depende do mart_escola_area
dbt run --select mart_diagnostico_competencia   # depende do mart_escola_area

dbt test
```

Antes dos marts, o seed da Matriz precisa existir:

```powershell
# uma vez, da raiz (o PDF vai para data/raw/, fora do Git)
curl -o data/raw/matriz_referencia.pdf `
  https://download.inep.gov.br/download/enem/matriz_referencia.pdf
python -m ingestion.build_matriz --pdf data/raw/matriz_referencia.pdf
cd dbt; dbt seed --select matriz_referencia
```

E a guarda de fronteira, uma vez depois da ingestão (não a cada `dbt run` — ela
varre a `raw` inteira):

```powershell
python -m quality.expectations_raw
```

Os marts são baratos (segundos a ~1 min). `dbt build --select marts` também
serve e resolve a ordem de dependência sozinho.

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

### Linha que não existe é omissão silenciosa — LC habilidade 8

A `int_acerto_item_escola` só tem linha para item **respondido**. A habilidade 8
de LC é coberta só por **itens de espanhol** — nenhum comum, nenhum de inglês.
Numa escola sem aluno de espanhol, ninguém respondeu nada dessa habilidade, e a
linha simplesmente não existe: são **1.824 das 29.260 escolas com presença em
LC (6,2%)**.

Um mart que parte das linhas da escola faz a habilidade **sumir** do relatório
dessas escolas. É o mesmo defeito da MT hab 21 por outro caminho — lá a edição
não tinha item válido, aqui a escola não teve quem respondesse.

**Solução:** o `mart_diagnostico_habilidade` monta um **grid completo** escola ×
área × habilidade e distingue os dois casos: `nao_avaliada` (a edição não tem o
que medir) e `nao_administrada` (a escola não teve quem respondesse). O teste
`habilidades_completas` trava a regressão — nenhum teste por linha vê uma linha
que não existe.

As habilidades **5, 6 e 7 de LC** sofrem uma versão mais branda: o lastro varia
com o mix de línguas da escola (1 a 3 itens, contra 2–3 no nacional). Por isso o
mart carrega `n_itens_validos` e `n_itens_validos_nacional` lado a lado.

### Idempotência da ingestão — o `DROP` precisa de `CASCADE`

O `load_raw.py` faz `DROP TABLE IF EXISTS raw.<base>` para ser idempotente.
A partir da Etapa 2 isso **quebra**: `stg_itens` e `stg_participantes` são
**views** sobre as tabelas raw, e o Postgres recusa o drop —
`cannot drop table ... because other objects depend on it`.

O erro ficou escondido por cinco etapas porque, manualmente, a ingestão sempre
rodou **antes** de existir qualquer modelo. Só apareceu na primeira execução
orquestrada, que é a primeira vez que o pipeline roda a *segunda* vez.

Solução: `DROP TABLE IF EXISTS raw.<base> CASCADE`. É seguro porque tudo acima
da raw é derivado e o próprio DAG reconstrói em seguida — derrubar a view e
recriá-la em minutos é correto; manter uma view apontando para uma tabela
recriada do zero é que seria perigoso.

Note que `stg_resultados` **não** dá esse problema: é materializado como
*table*, e tabela não cria dependência com a origem.

Lição além do bug: **"é idempotente" só vale depois de rodar duas vezes.** O
retry automático não salvaria — a falha é determinística, não transitória.

### Nota 0 é sentinela, não desempenho

`NU_NOTA_*` vem **0** para quem esteve presente e entregou a prova
**inteiramente em branco** — verificado: 100% dos zerados têm o vetor de
respostas só com pontos. A TRI estima proficiência a partir do *padrão* de
respostas; sem resposta não há padrão, e o INEP grava 0 porque a coluna precisa
de um número.

O sinal que denuncia: existem milhares de notas **exatamente** 0 e **nenhuma**
entre 0 e 250 — o piso real da escala é 308–320. Distribuição contínua não dá
salto assim.

Um `avg(nota)` ingênuo distorce a média da escola em **até 147,5 pontos**
(218 escolas afetadas em MT, 197 delas publicáveis). O tipo não denuncia: um
`numeric` aceita zero sem reclamar. Solução: `avg(nullif(nota, 0))` e a
contagem exposta em `n_prova_em_branco`.

Provas em branco por área: **CH 2.489 · LC 663 · MT 221 · CN 163** (na população
do diagnóstico).

### Extração de PDF quebra palavras

Extratores que **inferem** o espaço comparando a distância entre glifos com uma
largura de referência quebram palavras em PDF justificado: `signif icados`,
`natur ais`, `argumenta tivas`, `situações -problema`. Calibrar o limiar não
resolve — o sinal é ambíguo por natureza.

Usar extrator que trabalhe com o **posicionamento real** de cada caractere
(`pdfplumber`). A diferença não aparece em teste nenhum — aparece quando alguém
lê "signif icados" no relatório.

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

### Itens por habilidade — o fato que mais pesa no produto

30 habilidades por área, 120 no total. Média de itens **válidos** por
habilidade: CH 1,50 · CN 1,40 · LC 1,67 · MT 1,43.

Distribuição: **1 habilidade com zero** itens válidos (MT 21), **62 com um
único item**, 57 com dois ou mais. Ou seja, **mais da metade das habilidades é
medida por um item só**.

Consequência: *precisão* não é problema (uma escola com 100 alunos tem 100
respostas por item), mas *validade de conteúdo* é. Um item não representa a
habilidade inteira — mede também o enunciado, o distrator, o tema. Duas saídas
combináveis: reportar o número de itens que embasa cada medida (feito — a coluna
`n_itens_validos` e o `status` no mart) e agregar no nível de **competência de
área** (pendente do seed da Matriz).

**Resolvido na Etapa 5:** os microdados trazem só o *número* da habilidade; a
descrição e a competência vêm da Matriz de Referência
(`download.inep.gov.br/download/enem/matriz_referencia.pdf`), derivada pelo
`build_matriz.py`.

Competências por área: **LC 9 · MT 7 · CN 8 · CH 6** (30 no total, 120
habilidades). Agregar no grão da competência dá **4 a 11 itens válidos por
medida** (mínimo por área: CH 6, CN 4, LC 4, MT 4) contra 0–2 por habilidade —
é o que resolve o problema de validade de conteúdo.

Confirmação cruzada: a Competência 2 de LC ("língua estrangeira moderna")
agrupa exatamente H5–H8, que é o conjunto que a Etapa 4 identificou
empiricamente como dependente de língua.

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

### Verificações dos marts (Etapa 4)

```sql
-- os dois casos-limite estao declarados, nao omitidos
select area, habilidade, status, count(*) as escolas
from marts.mart_diagnostico_habilidade
where (area = 'MT' and habilidade = 21) or (area = 'LC' and habilidade = 8)
group by 1,2,3 order by 1,2,3;

-- publicaveis por area
select area, count(*) filter (where publicavel) as publicaveis
from marts.mart_escola_area group by 1 order by 1;
```

Valores obtidos: MT 21 → 29.193 escolas `nao_avaliada`. LC 8 → 1.824
`nao_administrada` + 27.436 `ok`.

O `\dn` deve listar `marts`, nunca `staging_marts`.

### Verificações da Etapa 5

```sql
-- o sentinela saiu da media: esperado ZERO linhas
select area, count(*) from marts.mart_escola_area where media_nota < 300 group by 1;

-- lastro por competencia: esperado minimo >= 4 nas quatro areas
select area, min(n_itens_validos_nacional), round(avg(n_itens_validos_nacional),1)
from marts.mart_diagnostico_competencia group by 1 order by 1;
```

Publicáveis **após** a correção do sentinela: **CH 18.098 · LC 18.108 ·
CN 17.600 · MT 17.600**. Eram 18.115/18.115/17.601/17.601 antes — 26 escolas
perderam publicação por terem 20+ presentes mas menos de 20 notas estimáveis.
CH perdeu 17, coerente com ser a área com muito mais prova em branco.

Lastro por competência: CH mín 6 (média 7,5) · CN mín 4 (5,3) · LC mín 4 (5,6) ·
MT mín 4 (6,1).

### Baseline do Great Expectations

`python -m quality.expectations_raw` → **3 suites, 22 expectations, 100%**
(itens 9 · resultados 9 · notas 4). Leva ~3 min: varre a `raw` inteira, então
rodar **uma vez** depois da ingestão, nunca a cada `dbt run`.

Duas leituras da saída que evitam susto:

- `missing_count` alto em `TX_RESPOSTAS_*` (1,55 mi em CN/MT, 1,35 mi em CH/LC)
  é **esperado** — são os ausentes, que não têm vetor. Expectation de *valor*
  avalia só os não nulos. Já `TP_PRESENCA_*` vem com `missing_count: 0`.
- O `element_count` do query asset das notas já é o total **filtrado** pelo
  `row_condition` (sem os zeros): MT 3.259.443 · CH 3.448.468 · LC 3.455.194 ·
  CN 3.259.561. Somando os zeros de volta reconstrói os presentes — CH e LC
  fecham em 3.457.555, o mesmo dia de prova.

---

## Decisões metodológicas

- **Só provas regulares** entram no diagnóstico. Acessibilidade fica **fora**
  (decisão fechada) — deixa ~20 mil participantes com deficiência fora do
  diagnóstico da própria escola, custo assumido. Reaplicação e BAM têm itens
  próprios e não são comparáveis na mesma métrica.
- **Só participantes presentes** (`cod_presenca = 1`).
- **Só quem tem `CO_ESCOLA`** — participante sem escola não pode ser atribuído a
  escola nenhuma. A consequência deixou de ser dívida e virou **decisão**: a
  referência é *entre concluintes com escola identificada*, e esse é o peer group
  correto para um diagnóstico de escola. Comparar a turma que se forma agora
  contra a população inteira do ENEM (treineiros, quem terminou o médio há dez
  anos) não seria mais rigoroso, seria menos. Limitação a registrar no README: a
  referência representa concluintes vinculados ao Censo, não "o Brasil inteiro".
- **Item anulado sai do cálculo**, sem crédito e sem penalidade. Não é uma
  escolha entre duas opções: em TRI a nota não é contagem de acertos, é
  estimativa de traço latente. Item sem gabarito não carrega informação sobre
  proficiência. Como as notas oficiais foram calculadas assim, excluir mantém o
  diagnóstico na mesma contabilidade da nota que o participante recebeu.
- **Ausência estrutural não é fracasso.** Um aluno que fez inglês não respondeu
  os itens de espanhol — isso é item não administrado, nunca erro. A junção por
  `cod_lingua` resolve na origem.
- **N mínimo para publicar diagnóstico: 20** (`var n_minimo_diagnostico`), e
  exige 20 **presentes** e 20 **com nota**. Escola com poucos alunos gera
  resultado instável e potencialmente identificável. Escolas abaixo do limiar
  **continuam nas tabelas** com `publicavel = false`, sem percentil — excluí-las
  apagaria a informação de que existem; publicá-las exporia o que o N não
  sustenta. O flag viaja nos **dois** marts: quem consome só o de habilidades
  não pode publicar escola pequena sem saber.
- **Percentil pela nota oficial**, não pela taxa de acerto. É a escala pública
  que as escolas conhecem, estimada por TRI (pondera dificuldade, desconta
  acerto casual) e auditável. A taxa de acerto fica com o que só ela faz: abrir
  o desempenho por habilidade. Cada medida no seu posto.
- **Uma régua por área, não por rede.** O percentil compara todas as escolas
  publicáveis da área — Federal e Municipal juntas. Recortar por rede/UF embute
  um juízo sobre o que é comparável e faria "percentil 80" significar coisas
  diferentes em tabelas diferentes. Os atributos de recorte estão na
  `dim_escola`; a API pode *filtrar* o ranking, não recalculá-lo.
- **Taxa ponderada, não média das taxas.** Soma acertos ÷ soma respostas, na
  escola e na referência, simetricamente — agregadas pela mesma regra, são
  comparáveis por construção. Exceção honesta: LC 5–8, onde o conjunto de itens
  varia com o mix de línguas (por isso os dois lastros lado a lado).
- **Nota zero sai da média e é contada à parte.** Não é desempenho, é ausência
  de evidência (ver "Nota 0 é sentinela"). Mesmo princípio do item anulado e da
  habilidade não avaliada: **preservar a linha, anular a métrica, expor a
  contagem**. O contra-argumento — o aluno que entregou em branco faz parte da
  realidade da escola — é legítimo, e por isso a saída não é apagar, é separar e
  mostrar: uma métrica que mistura "foi mal" com "não fez" não mede nem uma coisa
  nem outra.
- **Habilidade e competência convivem.** Habilidade é *acionável* (diz o que
  trabalhar) mas frágil (1–2 itens); competência é *confiável* (4–11 itens) mas
  larga demais para virar plano de aula. Publicar os dois, com
  `n_itens_validos` em ambos, deixa quem lê escolher o peso de cada afirmação.
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
  Escalar solto (o N mínimo) vira `var` no `dbt_project.yml` — seed de uma célula
  é cerimônia; vira seed quando ganhar estrutura.
- **Derivar de artefato oficial, nunca transcrever.** Todo seed sai de script
  (`build_seeds.py`, `build_matriz.py`), e o script **falha alto** em vez de
  gravar resultado parcial. Transcrição manual em volume é onde o erro silencioso
  mora: um seed pela metade vira join, vira relatório, e ninguém percebe porque
  não há com o que comparar.
- **Teste de fronteira ≠ teste de transformação.** O `dbt test` pergunta "meu SQL
  fez o que eu quis?"; o Great Expectations pergunta "o dado que chegou é o que
  eu esperava?". Falha no primeiro = meu código está errado; no segundo = o
  mundo mudou. Pressuposto sobre a fonte vira expectation na `raw`, não teste no
  dbt.
- **Linha ausente é omissão silenciosa.** Onde o grão é "entidade × dimensão",
  montar o **grid completo** e declarar o vazio com um status, em vez de deixar a
  linha faltar. Nenhum teste por linha vê uma linha que não existe — por isso
  também um teste de *completude* (`habilidades_completas`).
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

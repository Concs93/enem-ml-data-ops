{{ config(
    materialized='table',
    pre_hook="set max_parallel_workers_per_gather = 0"
) }}

-- Acertos por municipio x REDE x area x item -- o agregado reaproveitavel da
-- geografia (mesmo padrao do Volume 3: agregar UMA vez no grao mais fino
-- que alguem precisa; regiao imediata, UF, regiao e pais sao somas baratas
-- por cima disto, sem voltar as 5,4 milhoes de linhas de escola x item).
--
-- A REDE SAI DE GRACA. A dependencia administrativa ja viaja em
-- stg_resultados (TP_DEPENDENCIA_ADM_ESC esta na propria base de resultados)
-- e a dim_escola ja e juntada aqui para achar o municipio -- entao a
-- dimensao nova e uma coluna a mais no group by, sem tocar em
-- int_acerto_item_escola, que e o modelo caro.
--
-- 'Todas' E LINHA, NAO CONTA DO CONSUMIDOR. O grouping sets abaixo gera, para
-- cada municipio, uma linha por rede E uma linha com todas somadas. Duas
-- razoes: o gate de publicacao (3 escolas E 50 participantes) precisa valer
-- igual nos dois casos, e o roll-up para UF/regiao/pais passa a funcionar
-- sozinho -- somar as linhas 'Todas' dos municipios de um estado da o
-- 'Todas' do estado, sem grouping sets de novo la em cima.
--
-- CUIDADO AO CONSUMIR: quem somar sem filtrar rede conta cada resposta DUAS
-- vezes. O mart_geografia_habilidade, que nao usa a dimensao, filtra
-- rede = 'Todas' de proposito -- e note que um teste de conservacao
-- municipio x pais NAO pegaria esse defeito, porque os dois lados dobrariam
-- juntos.

select
    d.co_municipio,

    -- grouping() distingue o rollup de um valor nulo de verdade; um coalesce
    -- sozinho confundiria os dois se a dependencia algum dia vier vazia
    case when grouping(d.dependencia) = 1 then 'Todas'
         else coalesce(d.dependencia, 'Sem cadastro') end as rede,

    e.area,
    e.co_item,
    e.habilidade,
    e.item_anulado,
    e.item_abandonado,
    sum(e.n_respostas) as n_respostas,
    sum(e.n_acertos)   as n_acertos

from {{ ref('int_acerto_item_escola') }} e
join {{ ref('dim_escola') }} d
  on d.co_escola = e.co_escola

group by grouping sets (
    (d.co_municipio, d.dependencia, e.area, e.co_item, e.habilidade,
     e.item_anulado, e.item_abandonado),
    (d.co_municipio,                e.area, e.co_item, e.habilidade,
     e.item_anulado, e.item_abandonado)
)

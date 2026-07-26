{{ config(
    materialized='table',
    pre_hook="set max_parallel_workers_per_gather = 0"
) }}

-- Acertos por municipio x area x item -- o agregado reaproveitavel da
-- geografia (mesmo padrao do Volume 3: agregar UMA vez no grao mais fino
-- que alguem precisa; regiao imediata, UF, regiao e pais sao somas baratas
-- por cima disto, sem voltar as 5,4 milhoes de linhas de escola x item).

select
    d.co_municipio,
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

group by 1, 2, 3, 4, 5, 6

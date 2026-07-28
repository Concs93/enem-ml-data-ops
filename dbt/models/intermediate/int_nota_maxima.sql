-- A MAIOR NOTA de cada area nas provas regulares de 2025 -- o teto fisico da
-- escala daquela edicao.
--
-- Por que existe: a calibracao (mart_calibracao_nota) so mantem faixas com
-- n >= 100, entao a curva dela termina onde acaba a AMOSTRA, nao onde acaba a
-- escala. Em CH a ultima faixa calibravel e ~770, mas a maior nota real foi
-- 856,4 -- um usuario conferiu no noticiario e nao achou o numero no site.
-- O site precisa dos dois: a curva para converter, e o maximo real para
-- limitar honestamente o "ou mais" das extrapolacoes.
--
-- Populacao: TODAS as pessoas em prova regular (nao so concluintes com
-- escola) -- o teto e da escala, nao do peer group do diagnostico.

{{ config(
    materialized='table',
    pre_hook="set max_parallel_workers_per_gather = 0"
) }}

with regulares as (

    select co_prova from {{ ref('co_prova') }} where is_regular

),

-- uma unica varredura da tabela grande, com um max por area
maximos as (

    select
        max(nota_ch) filter (where co_prova_ch in (select co_prova from regulares)) as ch,
        max(nota_cn) filter (where co_prova_cn in (select co_prova from regulares)) as cn,
        max(nota_mt) filter (where co_prova_mt in (select co_prova from regulares)) as mt,
        max(nota_lc) filter (where co_prova_lc in (select co_prova from regulares)
                              and cod_lingua = 0)                                   as lc_ing,
        max(nota_lc) filter (where co_prova_lc in (select co_prova from regulares)
                              and cod_lingua = 1)                                   as lc_esp
    from {{ ref('stg_resultados') }}

)

select 'CH' as area, null::int as cod_lingua, ch     as nota_maxima from maximos
union all
select 'CN', null::int, cn     from maximos
union all
select 'MT', null::int, mt     from maximos
union all
select 'LC', 0,         lc_ing from maximos
union all
select 'LC', 1,         lc_esp from maximos

-- A MENOR e a MAIOR nota de cada area nas provas regulares de 2025 -- os dois
-- extremos REAIS da escala daquela edicao.
--
-- Por que existe: a calibracao (mart_calibracao_nota) so mantem faixas com
-- n >= 100, entao a curva dela comeca e termina onde a AMOSTRA fica rala, nao
-- onde a escala acaba. Em CH a ultima faixa calibravel e ~770, mas a maior
-- nota real foi 856,4 -- um usuario conferiu no noticiario e nao achou o
-- numero no site. O site precisa dos dois: a curva para converter, e os
-- extremos reais para (a) limitar honestamente o "ou mais" das extrapolacoes
-- e (b) recusar nota fora do que a edicao produziu.
--
-- POPULACAO: TODAS as pessoas em prova regular -- nao so concluintes com
-- escola. O extremo e da ESCALA, nao do peer group do diagnostico. Isso
-- importa para o minimo tanto quanto para o maximo: usar populacoes
-- diferentes nas duas pontas daria uma faixa que nao existe em lugar nenhum.
--
-- NOTA ZERO FICA DE FORA do minimo. Zero e sentinela de prova entregue em
-- branco (Etapa 5: 100% dos zerados tem o vetor so com pontos), nao
-- desempenho. O piso real da escala fica na casa dos 300 -- e o salto entre 0
-- e ~308, sem ninguem no meio, e justamente o que denuncia o sentinela.

{{ config(
    materialized='table',
    pre_hook="set max_parallel_workers_per_gather = 0"
) }}

with regulares as (

    select co_prova from {{ ref('co_prova') }} where is_regular

),

-- uma unica varredura da tabela grande, com min e max por area
extremos as (

    select
        min(nota_ch) filter (where co_prova_ch in (select co_prova from regulares)
                              and nota_ch > 0)                                     as ch_min,
        max(nota_ch) filter (where co_prova_ch in (select co_prova from regulares)) as ch_max,

        min(nota_cn) filter (where co_prova_cn in (select co_prova from regulares)
                              and nota_cn > 0)                                     as cn_min,
        max(nota_cn) filter (where co_prova_cn in (select co_prova from regulares)) as cn_max,

        min(nota_mt) filter (where co_prova_mt in (select co_prova from regulares)
                              and nota_mt > 0)                                     as mt_min,
        max(nota_mt) filter (where co_prova_mt in (select co_prova from regulares)) as mt_max,

        min(nota_lc) filter (where co_prova_lc in (select co_prova from regulares)
                              and cod_lingua = 0 and nota_lc > 0)                  as lc_ing_min,
        max(nota_lc) filter (where co_prova_lc in (select co_prova from regulares)
                              and cod_lingua = 0)                                  as lc_ing_max,

        min(nota_lc) filter (where co_prova_lc in (select co_prova from regulares)
                              and cod_lingua = 1 and nota_lc > 0)                  as lc_esp_min,
        max(nota_lc) filter (where co_prova_lc in (select co_prova from regulares)
                              and cod_lingua = 1)                                  as lc_esp_max

    from {{ ref('stg_resultados') }}

)

select 'CH' as area, null::int as cod_lingua, ch_min     as nota_minima, ch_max     as nota_maxima from extremos
union all
select 'CN', null::int, cn_min,     cn_max     from extremos
union all
select 'MT', null::int, mt_min,     mt_max     from extremos
union all
select 'LC', 0,         lc_ing_min, lc_ing_max from extremos
union all
select 'LC', 1,         lc_esp_min, lc_esp_max from extremos

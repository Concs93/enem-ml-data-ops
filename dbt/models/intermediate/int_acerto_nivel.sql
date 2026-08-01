{{ config(
    enabled=false,
    materialized='table',
    pre_hook="set max_parallel_workers_per_gather = 0"
) }}

-- APARCADO (01/08/2026, enabled=false): o produto mudou de rumo para a
-- navegacao por grao (Brasil > estado > cidade > rede) com as duas
-- comparacoes simples, que nao precisam desta varredura. O modelo fica
-- porque o residuo contra "alunos com a mesma nota" continua sendo a unica
-- versao SEM o vazamento de nivel ja medido no perfil (MT C6 rho +0,97
-- com o patamar) -- se a leitura comparativa voltar, e por aqui.

-- Acertos por NIVEL DE NOTA, com geografia ate regiao imediata. Uma varredura
-- do grao de resposta que serve os DOIS indicadores da face do gestor e mais
-- o histograma, sem terceira passada:
--
--   n_respostas por theta  = o histograma (ja ponderado por itens, que e o
--                            peso certo para calcular esperado)
--   n_acertos   por theta  = o observado
--
-- Dai saem, contra o int_nivel_nacional:
--   esperado(U,C) = SOMA_theta n_respostas(theta) x taxa_nacional(theta,C)
--   residuo (U,C) = observado - esperado          <- onde a rede foge do padrao
--   ganho   (U,C) = SOMA_theta n(theta) x [taxa_nac(theta+0,5) - taxa_nac(theta)]
--                                                 <- onde avancar meio nivel rende
--
-- POR QUE PARAR NA REGIAO IMEDIATA. No grao de municipio esta tabela passaria
-- de 10 milhoes de linhas, e a leitura por faixa nao se sustenta la de todo
-- jeito: 217 alunos partidos em tres faixas dao ~70 por faixa, margem de
-- 2,2 pp contra um sinal de ~1,1. Regiao imediata (mediana 1.202) e o grao
-- mais fino onde a particao ainda le. Municipio recebe a leitura SEM faixa,
-- pelo caminho barato (int_acerto_item_municipio + esperado agregado).
--
-- co_uf viaja ao lado de co_regiao_imediata de proposito: Boa Esperanca do
-- Norte/MT nao tem regiao imediata (municipio instalado em 2025, fora do
-- Censo 2024), e sem a UF ao lado ele sumiria do roll-up estadual.

{% set areas = ['mt', 'ch', 'cn', 'lc'] %}

with base as (

    {% for a in areas %}
    select
        coalesce(geo.co_uf, d.co_municipio / 100000) as co_uf,
        geo.co_regiao_imediata,
        d.dependencia,
        '{{ a | upper }}' as area,
        {% if a == 'lc' %}i.cod_lingua{% else %}null::int{% endif %} as cod_lingua,
        greatest(-3.00, least(5.00,
            round(((i.nota - 500) / 100.0) / 0.05) * 0.05))::numeric(5,2) as theta,
        i.habilidade,
        i.acertou
    -- a nota vem NA VIEW (ver explode_respostas.sql): juntar stg_resultados
    -- aqui seria junta-la com ela mesma, sondada 220 mi de vezes
    from {{ ref('int_respostas_' ~ a) }} i
    join {{ ref('dim_escola') }} d
      on d.co_escola = i.co_escola
    left join {{ ref('int_municipio_geografia') }} geo
      on geo.co_municipio = d.co_municipio
    where not i.item_anulado
      and not i.item_abandonado
      and d.co_municipio is not null
      -- nota 0 e sentinela de prova em branco: sem padrao de resposta nao ha
      -- nivel, e incluir jogaria essas pessoas num "nivel 300 que erra tudo"
      and i.nota > 0
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

)

select
    b.co_uf,
    b.co_regiao_imediata,

    case when grouping(b.dependencia) = 1 then 'Todas'
         else coalesce(b.dependencia, 'Sem cadastro') end as rede,

    b.area,
    b.cod_lingua,
    b.theta,
    m.competencia,

    count(*)                          as n_respostas,
    count(*) filter (where b.acertou) as n_acertos

from base b
join {{ ref('matriz_referencia') }} m
  on m.area = b.area and m.habilidade = b.habilidade

group by grouping sets (
    (b.co_uf, b.co_regiao_imediata, b.dependencia, b.area, b.cod_lingua,
     b.theta, m.competencia),
    (b.co_uf, b.co_regiao_imediata,                b.area, b.cod_lingua,
     b.theta, m.competencia)
)

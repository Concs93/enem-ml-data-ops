{{ config(
    materialized='table',
    pre_hook="set max_parallel_workers_per_gather = 0"
) }}

-- Quantos alunos cada MUNICIPIO x REDE tem em cada nivel de nota -- os
-- pesos do potencial de crescimento por cidade, mesmo desenho do
-- int_uf_nivel (municipio e rede vem direto do stg_resultados; rede
-- 'Todas' e LINHA via grouping sets; lingua de LC com sentinela -1).
--
-- Grao de COMPUTO para todas as cidades; quais publicam e decisao do gate
-- no mart_geografia_area, aplicada no export.

{% set areas = ['mt', 'ch', 'cn', 'lc'] %}

with alunos as (

    {% for a in areas %}
    select
        r.co_municipio_escola as co_municipio,
        d.rotulo              as rede,
        '{{ a | upper }}'     as area,
        {% if a == 'lc' %}r.cod_lingua{% else %}-1{% endif %} as cod_lingua,
        greatest(-3.00, least(5.00,
            round(((r.nota_{{ a }} - 500) / 100.0) / 0.05) * 0.05))::numeric(5,2) as theta
    from {{ ref('stg_resultados') }} r
    join {{ ref('co_prova') }} p
      on p.co_prova = r.co_prova_{{ a }} and p.sg_area = '{{ a | upper }}'
    join {{ ref('dominios') }} d
      on d.variavel = 'TP_DEPENDENCIA_ADM_ESC'
     and d.codigo = r.cod_dependencia_escola::text
    where r.cod_presenca_{{ a }} = 1
      and p.is_regular
      and r.co_escola is not null
      and r.co_municipio_escola is not null
      -- nota 0 e sentinela de prova em branco: sem nivel estimavel
      and r.nota_{{ a }} > 0
      {% if a == 'lc' %}and r.cod_lingua is not null{% endif %}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

)

select
    co_municipio,
    case when grouping(rede) = 1 then 'Todas' else rede end as rede,
    area,
    cod_lingua,
    theta,
    count(*) as n
from alunos
group by grouping sets (
    (co_municipio, rede, area, cod_lingua, theta),
    (co_municipio,       area, cod_lingua, theta)
)

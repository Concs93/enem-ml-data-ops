{{ config(materialized='table') }}

{% set areas = ['mt', 'ch', 'cn', 'lc'] %}

with todas as (
    {% for a in areas %}
    select * from {{ ref('int_acerto_item_' ~ a) }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    area,
    co_item,
    habilidade,
    param_dificuldade,
    item_anulado,
    item_abandonado,
    sum(n_respostas) as n_respostas,
    sum(n_acertos)   as n_acertos,
    case
        when item_anulado or item_abandonado then null
        else round(100.0 * sum(n_acertos) / nullif(sum(n_respostas), 0), 2)
    end as taxa_acerto_nacional

from todas
group by 1, 2, 3, 4, 5, 6
{{ config(materialized='table') }}

{% set areas = ['mt', 'ch', 'cn', 'lc'] %}

with todas as (
    {% for a in areas %}
    select * from {{ ref('int_acerto_item_' ~ a) }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    co_escola,
    area,
    co_item,
    habilidade,
    param_dificuldade,
    item_anulado,
    item_abandonado,
    n_respostas,
    n_acertos,
    n_branco,
    n_dupla,
    case
        when item_anulado or item_abandonado then null
        else round(100.0 * n_acertos / nullif(n_respostas, 0), 2)
    end as taxa_acerto

from todas
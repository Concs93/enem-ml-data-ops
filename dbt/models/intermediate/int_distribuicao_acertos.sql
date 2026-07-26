{{ config(materialized='table') }}

{% set areas = ['mt', 'ch', 'cn', 'lc'] %}

with todas as (
    {% for a in areas %}
    select * from {{ ref('int_distribuicao_acertos_' ~ a) }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    area,
    cod_lingua,
    nota_faixa,
    acertos,
    n
from todas

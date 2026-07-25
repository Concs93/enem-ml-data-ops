{% macro agrega_por_item(sigla) %}

select
    co_escola,
    area,
    co_item,
    habilidade,
    param_dificuldade,
    item_anulado,
    item_abandonado,
    count(*)                               as n_respostas,
    count(*) filter (where acertou)        as n_acertos,
    count(*) filter (where em_branco)      as n_branco,
    count(*) filter (where dupla_marcacao) as n_dupla

from {{ ref('int_respostas_' ~ sigla | lower) }}
group by 1, 2, 3, 4, 5, 6, 7

{% endmacro %}
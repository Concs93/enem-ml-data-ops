{% macro explode_respostas(sigla, n_itens) %}

{%- set s = sigla | lower -%}

with participantes as (

    select
        r.id_resultado,
        r.co_escola,
        r.co_prova_{{ s }}   as co_prova,
        r.respostas_{{ s }}  as respostas,
        r.gabarito_{{ s }}   as gabarito
    from {{ ref('stg_resultados') }} r
    join {{ ref('co_prova') }} p
      on p.co_prova = r.co_prova_{{ s }}
     and p.sg_area  = '{{ sigla | upper }}'
    where r.cod_presenca_{{ s }} = 1
      and p.is_regular
      and r.co_escola is not null

),

explodido as (

    select
        p.id_resultado,
        p.co_escola,
        p.co_prova,
        pos.posicao,
        substring(p.respostas from pos.posicao for 1) as resposta,
        substring(p.gabarito  from pos.posicao for 1) as gabarito
    from participantes p
    cross join generate_series(1, {{ n_itens }}) as pos(posicao)

)

select
    e.id_resultado,
    e.co_escola,
    '{{ sigla | upper }}'  as area,
    i.co_item,
    i.habilidade,
    i.param_dificuldade,
    i.item_anulado,
    i.item_abandonado,
    e.resposta,
    e.gabarito,

    case
        when i.item_anulado   then null
        when e.resposta = '.' then false
        when e.resposta = '*' then false
        else e.resposta = e.gabarito
    end as acertou,

    e.resposta = '.' as em_branco,
    e.resposta = '*' as dupla_marcacao

from explodido e
join {{ ref('stg_itens') }} i
  on i.co_prova = e.co_prova
 and i.posicao  = e.posicao

{% endmacro %}
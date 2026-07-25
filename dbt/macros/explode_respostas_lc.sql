{% macro explode_respostas_lc() %}

with participantes as (

    select
        r.id_resultado,
        r.co_escola,
        r.co_prova_lc  as co_prova,
        r.cod_lingua,
        r.respostas_lc as respostas
    from {{ ref('stg_resultados') }} r
    join {{ ref('co_prova') }} p
      on p.co_prova = r.co_prova_lc
     and p.sg_area  = 'LC'
    where r.cod_presenca_lc = 1
      and p.is_regular
      and r.co_escola is not null
      and r.cod_lingua is not null

),

-- os itens que cada aluno viu: os da sua lingua + os 40 comuns,
-- renumerados de 1 a 45 na ordem da prova, para casar com a resposta
itens_do_aluno as (

    select
        p.id_resultado,
        p.co_escola,
        p.respostas,
        i.co_item,
        i.habilidade,
        i.param_dificuldade,
        i.item_anulado,
        i.item_abandonado,
        i.gabarito,
        (row_number() over (
            partition by p.id_resultado
            order by i.posicao
        ))::int as posicao_resposta
    from participantes p
    join {{ ref('stg_itens') }} i
      on i.co_prova = p.co_prova
     and (i.cod_lingua is null or i.cod_lingua = p.cod_lingua)

),

avaliado as (

    select
        a.*,
        substring(a.respostas from a.posicao_resposta for 1) as resposta
    from itens_do_aluno a

)

select
    id_resultado,
    co_escola,
    'LC' as area,
    co_item,
    habilidade,
    param_dificuldade,
    item_anulado,
    item_abandonado,
    resposta,
    gabarito,

    case
        when item_anulado   then null
        when resposta = '.' then false
        when resposta = '*' then false
        else resposta = gabarito
    end as acertou,

    resposta = '.' as em_branco,
    resposta = '*' as dupla_marcacao

from avaliado

{% endmacro %}
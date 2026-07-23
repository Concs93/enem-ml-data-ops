with fonte as (
    select * from {{ source('raw', 'itens_prova_2025') }}
)

select
    {{ inteiro('"CO_ITEM"') }}          as co_item,
    {{ inteiro('"CO_PROVA"') }}         as co_prova,
    row_number() over (
        partition by {{ inteiro('"CO_PROVA"') }}
        order by {{ inteiro('"CO_POSICAO"') }}
    )                                   as posicao,
    {{ inteiro('"CO_POSICAO"') }}       as co_posicao_global,
    "SG_AREA"                           as area,
    "TX_COR"                            as cor_prova,
    {{ inteiro('"TP_LINGUA"') }}        as cod_lingua,
    "TX_GABARITO"                       as gabarito,
    {{ inteiro('"CO_HABILIDADE"') }}    as habilidade,
    {{ num('"NU_PARAM_A"') }}           as param_discriminacao,
    {{ num('"NU_PARAM_B"') }}           as param_dificuldade,
    {{ num('"NU_PARAM_C"') }}           as param_acerto_casual,
    {{ booleano('"IN_ITEM_ABAN"') }}    as item_abandonado,
    {{ booleano('"IN_ITEM_ADAPTADO"') }} as item_adaptado,
    "TX_MOTIVO_ABAN"                    as motivo_abandono,
    "TX_GABARITO" = 'X'                 as item_anulado

from fonte
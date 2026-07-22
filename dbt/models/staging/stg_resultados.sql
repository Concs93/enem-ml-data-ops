with fonte as (
    select * from {{ source('raw', 'resultados_2025') }}
)

select
    {{ inteiro('"NU_SEQUENCIAL"') }}    as id_resultado,
    {{ inteiro('"NU_ANO"') }}           as ano,

    -- escola
    {{ inteiro('"CO_ESCOLA"') }}        as co_escola,
    {{ inteiro('"CO_MUNICIPIO_ESC"') }} as co_municipio_escola,
    "NO_MUNICIPIO_ESC"                  as municipio_escola,
    {{ inteiro('"CO_UF_ESC"') }}        as co_uf_escola,
    "SG_UF_ESC"                         as uf_escola,
    {{ inteiro('"TP_DEPENDENCIA_ADM_ESC"') }} as cod_dependencia_escola,
    {{ inteiro('"TP_LOCALIZACAO_ESC"') }}     as cod_localizacao_escola,
    {{ inteiro('"TP_SIT_FUNC_ESC"') }}        as cod_situacao_escola,

    -- aplicacao
    {{ inteiro('"CO_MUNICIPIO_PROVA"') }} as co_municipio_prova,
    {{ inteiro('"CO_UF_PROVA"') }}        as co_uf_prova,
    "SG_UF_PROVA"                         as uf_prova,
    {{ inteiro('"TP_LINGUA"') }}        as cod_lingua,

    -- presenca
    {{ inteiro('"TP_PRESENCA_CN"') }}   as cod_presenca_cn,
    {{ inteiro('"TP_PRESENCA_CH"') }}   as cod_presenca_ch,
    {{ inteiro('"TP_PRESENCA_LC"') }}   as cod_presenca_lc,
    {{ inteiro('"TP_PRESENCA_MT"') }}   as cod_presenca_mt,

    -- versao de prova
    {{ inteiro('"CO_PROVA_CN"') }}      as co_prova_cn,
    {{ inteiro('"CO_PROVA_CH"') }}      as co_prova_ch,
    {{ inteiro('"CO_PROVA_LC"') }}      as co_prova_lc,
    {{ inteiro('"CO_PROVA_MT"') }}      as co_prova_mt,

    -- notas
    {{ num('"NU_NOTA_CN"') }}           as nota_cn,
    {{ num('"NU_NOTA_CH"') }}           as nota_ch,
    {{ num('"NU_NOTA_LC"') }}           as nota_lc,
    {{ num('"NU_NOTA_MT"') }}           as nota_mt,

    -- vetores (desmembrados na Etapa 3)
    "TX_RESPOSTAS_CN"                   as respostas_cn,
    "TX_RESPOSTAS_CH"                   as respostas_ch,
    "TX_RESPOSTAS_LC"                   as respostas_lc,
    "TX_RESPOSTAS_MT"                   as respostas_mt,
    "TX_GABARITO_CN"                    as gabarito_cn,
    "TX_GABARITO_CH"                    as gabarito_ch,
    "TX_GABARITO_LC"                    as gabarito_lc,
    "TX_GABARITO_MT"                    as gabarito_mt,

    -- redacao
    {{ inteiro('"TP_STATUS_REDACAO"') }} as cod_status_redacao,
    {{ num('"NU_NOTA_REDACAO"') }}      as nota_redacao,
    {{ num('"NU_NOTA_COMP1"') }}        as nota_comp1,
    {{ num('"NU_NOTA_COMP2"') }}        as nota_comp2,
    {{ num('"NU_NOTA_COMP3"') }}        as nota_comp3,
    {{ num('"NU_NOTA_COMP4"') }}        as nota_comp4,
    {{ num('"NU_NOTA_COMP5"') }}        as nota_comp5

from fonte
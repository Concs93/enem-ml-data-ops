with fonte as (
    select * from {{ source('raw', 'participantes_2025') }}
)

select
    {{ inteiro('"NU_INSCRICAO"') }}     as id_inscricao,
    {{ inteiro('"NU_ANO"') }}           as ano,

    -- perfil
    {{ inteiro('"TP_FAIXA_ETARIA"') }}  as cod_faixa_etaria,
    "TP_SEXO"                           as cod_sexo,
    {{ inteiro('"TP_COR_RACA"') }}      as cod_cor_raca,
    {{ inteiro('"TP_ST_CONCLUSAO"') }}  as cod_situacao_conclusao,
    {{ inteiro('"TP_ANO_CONCLUIU"') }}  as cod_ano_conclusao,
    {{ inteiro('"TP_ENSINO"') }}        as cod_tipo_ensino,
    {{ booleano('"IN_TREINEIRO"') }}    as treineiro,

    -- local de aplicacao
    {{ inteiro('"CO_MUNICIPIO_PROVA"') }} as co_municipio_prova,
    {{ inteiro('"CO_UF_PROVA"') }}        as co_uf_prova,
    "SG_UF_PROVA"                         as uf_prova,

    -- escolaridade e ocupacao dos responsaveis
    "Q001"                              as escolaridade_pai,
    "Q002"                              as escolaridade_mae,
    "Q003"                              as grupo_ocupacional_pai,
    "Q004"                              as grupo_ocupacional_mae,

    -- domicilio e renda
    "Q005"                              as pessoas_domicilio,
    "Q006"                              as possui_renda,
    "Q007"                              as renda_familiar,
    "Q008"                              as freq_empregado_domestico,

    -- bens do domicilio: quantidade (nao / sim, um / sim, dois...)
    "Q009"                              as qtd_banheiro,
    "Q010"                              as qtd_quarto,
    "Q011"                              as qtd_carro,
    "Q012"                              as qtd_motocicleta,
    "Q013"                              as qtd_geladeira,
    "Q018"                              as qtd_televisao,
    "Q021"                              as qtd_computador,
    "Q022"                              as qtd_celular,

    -- bens do domicilio: sim ou nao
    "Q014"                              as tem_freezer,
    "Q015"                              as tem_maquina_lavar,
    "Q016"                              as tem_microondas,
    "Q017"                              as tem_aspirador,
    "Q019"                              as tem_tv_assinatura,
    "Q020"                              as tem_internet,

    -- trajetoria escolar
    "Q023"                              as tipo_escola_declarado

from fonte
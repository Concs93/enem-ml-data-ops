-- Cadastro de escolas do Censo Escolar 2024, um-para-um com a fonte.
--
-- Papel no produto: dar NOME ao co_escola (ninguem sabe o proprio codigo
-- INEP de cabeca) e trazer a geografia do IBGE -- a microrregiao e o nivel
-- para onde um municipio pequeno demais sobe em vez de sumir.
--
-- Staging faz tres coisas e so tres: renomeia, converte tipo, mantem 1:1.
-- Nenhum filtro: escola fora do ENEM tambem entra, e o join decide.

with fonte as (
    select * from {{ source('raw', 'censo_escolar_2024') }}
)

select
    -- CO_ENTIDADE e o mesmo codigo que o ENEM chama de CO_ESCOLA
    {{ inteiro('"CO_ENTIDADE"') }}              as co_escola,
    "NO_ENTIDADE"                               as nome_escola,
    {{ inteiro('"NU_ANO_CENSO"') }}             as ano_censo,
    {{ inteiro('"TP_SITUACAO_FUNCIONAMENTO"') }} as cod_situacao_funcionamento,

    -- geografia (IBGE)
    {{ inteiro('"CO_REGIAO"') }}                as co_regiao,
    {{ inteiro('"CO_UF"') }}                    as co_uf,
    "SG_UF"                                     as uf,
    {{ inteiro('"CO_MUNICIPIO"') }}             as co_municipio,
    "NO_MUNICIPIO"                              as municipio,
    {{ inteiro('"CO_MESORREGIAO"') }}           as co_mesorregiao,
    {{ inteiro('"CO_MICRORREGIAO"') }}          as co_microrregiao,
    {{ inteiro('"TP_LOCALIZACAO"') }}           as cod_localizacao,

    -- rede
    {{ inteiro('"TP_DEPENDENCIA"') }}           as cod_dependencia,
    {{ inteiro('"TP_CATEGORIA_ESCOLA_PRIVADA"') }} as cod_categoria_privada,

    -- porte no ensino medio (o publico do ENEM)
    {{ booleano('"IN_MED"') }}                  as tem_ensino_medio,
    {{ inteiro('"QT_MAT_MED"') }}               as qtd_matriculas_medio,
    {{ inteiro('"QT_DOC_MED"') }}               as qtd_docentes_medio,
    {{ inteiro('"QT_TUR_MED"') }}               as qtd_turmas_medio,
    {{ inteiro('"QT_SALAS_UTILIZADAS"') }}      as qtd_salas,

    -- infraestrutura
    {{ booleano('"IN_INTERNET"') }}             as tem_internet,
    {{ booleano('"IN_BIBLIOTECA"') }}           as tem_biblioteca,
    {{ booleano('"IN_LABORATORIO_INFORMATICA"') }} as tem_lab_informatica,
    {{ booleano('"IN_LABORATORIO_CIENCIAS"') }} as tem_lab_ciencias,
    {{ booleano('"IN_QUADRA_ESPORTES"') }}      as tem_quadra,
    {{ booleano('"IN_AGUA_POTAVEL"') }}         as tem_agua_potavel,
    {{ booleano('"IN_ENERGIA_REDE_PUBLICA"') }} as tem_energia_rede,
    {{ booleano('"IN_ESGOTO_REDE_PUBLICA"') }}  as tem_esgoto_rede,
    {{ booleano('"IN_ACESSIBILIDADE_INEXISTENTE"') }} as acessibilidade_inexistente

from fonte

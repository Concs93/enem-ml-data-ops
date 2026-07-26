{{ config(materialized='table') }}

-- O mapa municipio -> hierarquia do IBGE, derivado do cadastro do Censo.
--
-- Um municipio pertence inteiro a uma regiao imediata, que pertence inteira
-- a uma UF (containment do IBGE) -- entao o grao e uma linha por municipio,
-- e o teste de unicidade no yml e o que denuncia se algum dia o cadastro
-- vier contradizendo isso.
--
-- Por que do Censo e nao de uma tabela avulsa do IBGE: os 215 mil enderecos
-- de escola cobrem essencialmente todos os municipios com escola, e derivar
-- da fonte que ja esta no pipeline evita uma segunda fonte de verdade.

select
    co_municipio,
    max(municipio)                 as municipio,
    max(co_regiao_imediata)        as co_regiao_imediata,
    max(nome_regiao_imediata)      as nome_regiao_imediata,
    max(co_regiao_intermediaria)   as co_regiao_intermediaria,
    max(nome_regiao_intermediaria) as nome_regiao_intermediaria,
    max(co_uf)                     as co_uf,
    max(uf)                        as uf,
    max(nome_uf)                   as nome_uf,
    max(co_regiao)                 as co_regiao,
    max(nome_regiao)               as nome_regiao

from {{ ref('stg_censo_escola') }}
where co_municipio is not null
group by 1

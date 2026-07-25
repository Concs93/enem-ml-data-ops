-- Quem e a escola. Consumida pela aplicacao, nao pelos fatos: nenhum mart
-- depende dela. Cobre toda escola presente nos resultados, inclusive as que
-- so tem participantes de reaplicacao ou BAM e nao recebem diagnostico --
-- dimensao descreve quem existe; quem entra no diagnostico e decisao do fato.

with escolas as (

    select
        co_escola,
        max(co_municipio_escola)    as co_municipio,
        max(municipio_escola)       as municipio,
        max(uf_escola)              as uf,
        max(cod_dependencia_escola) as cod_dependencia,
        max(cod_localizacao_escola) as cod_localizacao
    from {{ ref('stg_resultados') }}
    where co_escola is not null
    group by 1

)

select
    e.co_escola,
    e.co_municipio,
    e.municipio,
    e.uf,
    dep.rotulo as dependencia,
    loc.rotulo as localizacao

from escolas e

-- o seed guarda codigo como texto; o staging tipou como inteiro
left join {{ ref('dominios') }} dep
  on dep.base     = 'resultados'
 and dep.variavel = 'TP_DEPENDENCIA_ADM_ESC'
 and dep.codigo   = e.cod_dependencia::text

left join {{ ref('dominios') }} loc
  on loc.base     = 'resultados'
 and loc.variavel = 'TP_LOCALIZACAO_ESC'
 and loc.codigo   = e.cod_localizacao::text

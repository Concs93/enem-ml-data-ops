-- Quem e a escola. Consumida pela aplicacao, nao pelos fatos: nenhum mart
-- depende dela. Cobre toda escola presente nos resultados, inclusive as que
-- so tem participantes de reaplicacao ou BAM e nao recebem diagnostico --
-- dimensao descreve quem existe; quem entra no diagnostico e decisao do fato.
--
-- Desde a Etapa 8 (PLANO.md, Passo 1) ela cruza com o Censo Escolar 2024:
-- nome (sem ele ninguem se acha num relatorio), microrregiao do IBGE (o nivel
-- para onde municipio pequeno sobe) e contexto de porte/infraestrutura.
-- O cadastro e de 2024 por necessidade -- o Censo do ano do ENEM nao existe
-- ainda -- e o custo foi medido: 0,4% das publicaveis sem nome. Por isso o
-- join e LEFT: escola sem cadastro continua existindo, so nao tem nome.

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

    -- do Censo: a identidade consultavel
    c.nome_escola,

    -- geografia: a do ENEM e a canonica (existe para todas); a microrregiao
    -- so o Censo tem, e e a chave do roll-up geografico
    e.co_municipio,
    e.municipio,
    e.uf,
    c.co_regiao_imediata,
    c.nome_regiao_imediata,
    c.co_mesorregiao,
    c.co_microrregiao,

    dep.rotulo as dependencia,
    loc.rotulo as localizacao,

    -- porte no ensino medio e infraestrutura (contexto, nao metrica)
    c.qtd_matriculas_medio,
    c.qtd_docentes_medio,
    c.qtd_turmas_medio,
    c.qtd_salas,
    c.tem_internet,
    c.tem_biblioteca,
    c.tem_lab_informatica,
    c.tem_lab_ciencias,
    c.tem_quadra,
    c.tem_agua_potavel,
    c.tem_energia_rede,
    c.tem_esgoto_rede,
    c.acessibilidade_inexistente,

    c.co_escola is not null as tem_cadastro

from escolas e

left join {{ ref('stg_censo_escola') }} c
  on c.co_escola = e.co_escola

-- o seed guarda codigo como texto; o staging tipou como inteiro
left join {{ ref('dominios') }} dep
  on dep.base     = 'resultados'
 and dep.variavel = 'TP_DEPENDENCIA_ADM_ESC'
 and dep.codigo   = e.cod_dependencia::text

left join {{ ref('dominios') }} loc
  on loc.base     = 'resultados'
 and loc.variavel = 'TP_LOCALIZACAO_ESC'
 and loc.codigo   = e.cod_localizacao::text

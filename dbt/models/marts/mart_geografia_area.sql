-- A face do gestor, nivel area: presenca e media em CINCO niveis geograficos
-- numa tabela so -- municipio, regiao imediata (IBGE 2017), UF, regiao, pais.
--
-- Regra dupla de publicacao (PLANO.md): >= 3 escolas E >= 50 participantes.
-- Os dois criterios respondem perguntas diferentes -- estabilidade e
-- privacidade: 45% dos municipios tem UMA escola, e publicar o municipio
-- seria publicar aquela escola com outro rotulo. Quem nao passa NAO some:
-- a linha existe com publicavel = false, e codigo_pai aponta o nivel acima
-- para onde a API sobe (mesmo principio de MT 21 / LC 8: preservar a linha,
-- declarar o motivo).
--
-- Aplicada em TODO nivel, honestamente: ate UF e pais passam pela mesma
-- conta em vez de ganhar isencao.
--
-- Caso de borda real: Boa Esperanca do Norte/MT, municipio instalado em
-- 2025, existe no ENEM mas nao no Censo 2024 -- logo nao tem regiao
-- imediata. UF e regiao saem do proprio codigo IBGE (2 primeiros digitos =
-- UF; 1o digito = regiao), o municipio permanece, e apenas o nivel
-- regiao_imediata nao o contem (a divisao de 2024 realmente nao o continha).

{% set niveis = [
    ('municipio',       'g.co_municipio',       'g.municipio',            'g.co_regiao_imediata'),
    ('regiao_imediata', 'g.co_regiao_imediata', 'g.nome_regiao_imediata', 'g.co_uf'),
    ('uf',              'g.co_uf',              'g.nome_uf',              'g.co_regiao'),
    ('regiao',          'g.co_regiao',          'g.nome_regiao',          '0'),
    ('pais',            '0',                    "'Brasil'",               'null::int'),
] %}

with base as (

    select
        m.area,
        m.n_presentes,
        m.n_com_nota,
        m.n_prova_em_branco,
        m.media_nota,

        d.co_municipio,
        coalesce(geo.municipio, d.municipio) as municipio,
        geo.co_regiao_imediata,
        geo.nome_regiao_imediata,
        -- fallback pela estrutura do codigo IBGE, para municipio novo
        coalesce(geo.co_uf, d.co_municipio / 100000)              as co_uf,
        geo.nome_uf,
        coalesce(geo.co_regiao,
                 coalesce(geo.co_uf, d.co_municipio / 100000) / 10) as co_regiao,
        geo.nome_regiao

    from {{ ref('mart_escola_area') }} m
    join {{ ref('dim_escola') }} d
      on d.co_escola = m.co_escola
     and d.co_municipio is not null
    left join {{ ref('int_municipio_geografia') }} geo
      on geo.co_municipio = d.co_municipio

)

{% for nivel, codigo, nome, pai in niveis %}
select
    '{{ nivel }}'            as nivel,
    {{ codigo }}             as codigo,
    max({{ nome }})          as nome,
    max({{ pai }})           as codigo_pai,
    g.area,

    count(*)                                as n_escolas,
    sum(g.n_presentes)                      as n_presentes,
    sum(g.n_com_nota)                       as n_com_nota,
    sum(g.n_prova_em_branco)                as n_prova_em_branco,
    -- ponderada por quem TEM nota, nunca por presentes: o sentinela da
    -- prova em branco ja esta fora da media de cada escola (Etapa 5)
    round(sum(g.n_com_nota * g.media_nota)
        / nullif(sum(g.n_com_nota), 0), 1)  as media_nota,

    count(*) >= 3 and sum(g.n_presentes) >= 50 as publicavel

from base g
{% if nivel == 'regiao_imediata' %}
where g.co_regiao_imediata is not null
{% endif %}
group by 2, 5
{% if not loop.last %}union all{% endif %}
{% endfor %}

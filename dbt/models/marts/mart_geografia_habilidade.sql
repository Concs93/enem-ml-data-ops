-- A face do gestor, nivel habilidade: taxa vs nacional nos cinco niveis
-- geograficos, com grid completo por unidade -- linha ausente e omissao
-- silenciosa, e ja mordeu tres vezes (MT 21, LC 8, e agora seria qualquer
-- regiao imediata inteira sem aluno de espanhol).
--
-- O pipeline: agrega o item por unidade em cada nivel, monta a grade
-- unidade x area x habilidade a partir do nacional, e so entao calcula --
-- a mesma receita do mart_diagnostico_habilidade, generalizada para os
-- cinco niveis numa passada.

{% set niveis = [
    ('municipio',       'g.co_municipio',       'g.municipio'),
    ('regiao_imediata', 'g.co_regiao_imediata', 'g.nome_regiao_imediata'),
    ('uf',              'g.co_uf',              'g.nome_uf'),
    ('regiao',          'g.co_regiao',          'g.nome_regiao'),
    ('pais',            '0',                    "'Brasil'"),
] %}

with base as (

    select
        i.area, i.co_item, i.habilidade, i.item_anulado, i.item_abandonado,
        i.n_respostas, i.n_acertos,
        i.co_municipio,
        coalesce(geo.municipio, i.co_municipio::text)             as municipio,
        geo.co_regiao_imediata,
        geo.nome_regiao_imediata,
        coalesce(geo.co_uf, i.co_municipio / 100000)              as co_uf,
        geo.nome_uf,
        coalesce(geo.co_regiao,
                 coalesce(geo.co_uf, i.co_municipio / 100000) / 10) as co_regiao,
        geo.nome_regiao
    from {{ ref('int_acerto_item_municipio') }} i
    left join {{ ref('int_municipio_geografia') }} geo
      on geo.co_municipio = i.co_municipio

),

-- item por unidade, nos cinco niveis empilhados
unidade_item as (

    {% for nivel, codigo, nome in niveis %}
    select
        '{{ nivel }}'   as nivel,
        {{ codigo }}    as codigo,
        max({{ nome }}) as nome,
        g.area, g.co_item, g.habilidade, g.item_anulado, g.item_abandonado,
        sum(g.n_respostas) as n_respostas,
        sum(g.n_acertos)   as n_acertos
    from base g
    {% if nivel == 'regiao_imediata' %}
    where g.co_regiao_imediata is not null
    {% endif %}
    group by 2, 4, 5, 6, 7, 8
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

),

agregado as (

    select
        nivel, codigo, max(nome) as nome, area, habilidade,
        count(*) filter (where not item_anulado and not item_abandonado)
            as n_itens_validos,
        sum(n_respostas) filter (where not item_anulado and not item_abandonado)
            as n_respostas,
        sum(n_acertos) filter (where not item_anulado and not item_abandonado)
            as n_acertos
    from unidade_item
    group by 1, 2, 4, 5

),

nacional as (

    select
        area, habilidade,
        count(*) filter (where not item_anulado and not item_abandonado)
            as n_itens_validos,
        sum(n_respostas) filter (where not item_anulado and not item_abandonado)
            as n_respostas,
        sum(n_acertos) filter (where not item_anulado and not item_abandonado)
            as n_acertos
    from {{ ref('int_acerto_item_nacional') }}
    group by 1, 2

),

-- toda unidade presente numa area recebe TODAS as habilidades da area
grade as (

    select p.nivel, p.codigo, p.nome, p.area, n.habilidade
    from (select distinct nivel, codigo, nome, area from agregado) p
    join nacional n
      on n.area = p.area

)

select
    g.nivel,
    g.codigo,
    g.nome,
    g.area,
    g.habilidade,
    m.competencia,
    m.descricao_habilidade,

    coalesce(a.n_itens_validos, 0) as n_itens_validos,
    n.n_itens_validos              as n_itens_validos_nacional,
    coalesce(a.n_respostas, 0)     as n_respostas,
    coalesce(ga.publicavel, false) as publicavel,

    case
        when n.n_itens_validos = 0              then 'nao_avaliada'
        when coalesce(a.n_itens_validos, 0) = 0 then 'nao_administrada'
        when a.n_itens_validos = 1              then 'um_item'
        else 'ok'
    end as status,

    round(100.0 * a.n_acertos / nullif(a.n_respostas, 0), 2) as taxa_acerto,
    round(100.0 * n.n_acertos / nullif(n.n_respostas, 0), 2) as taxa_acerto_nacional,
    round(100.0 * a.n_acertos / nullif(a.n_respostas, 0)
        - 100.0 * n.n_acertos / nullif(n.n_respostas, 0), 2) as diferenca

from grade g

join nacional n
  on n.area = g.area and n.habilidade = g.habilidade

left join agregado a
  on a.nivel = g.nivel and a.codigo = g.codigo
 and a.area = g.area and a.habilidade = g.habilidade

-- a governanca viaja: quem consome so este mart recebe o gate do N minimo
left join {{ ref('mart_geografia_area') }} ga
  on ga.nivel = g.nivel and ga.codigo = g.codigo and ga.area = g.area

-- left join: habilidade sem correspondencia na Matriz nao pode sumir
left join {{ ref('matriz_referencia') }} m
  on m.area = g.area and m.habilidade = g.habilidade

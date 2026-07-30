-- A face do gestor no grao que sustenta decisao: competencia de area.
--
-- POR QUE COMPETENCIA E NAO HABILIDADE. No nivel UF a precisao nunca e o
-- problema (milhoes de respostas por item), mas a VALIDADE DE CONTEUDO e:
-- 62 das 120 habilidades sao medidas por um item so, e ai a medida e daquele
-- item -- do enunciado, do distrator, do tema --, nao da habilidade. Agregar
-- por competencia da 4 a 11 itens por medida. Mesma decisao da Etapa 5.
--
-- A COLUNA QUE MUDA O PRODUTO: `perfil`. A `diferenca` crua contra o nacional
-- e 80% "este estado vai melhor/pior em TUDO" (medido no nivel UF: desvio
-- 3,52 do patamar da unidade contra 3,93 do total). Um mapa pintado por ela e
-- ranking disfarcado, e da a todo estado o mesmo conselho -- "voce esta atras
-- em tudo" --, que nao e conselho. O `perfil` desconta o patamar da propria
-- unidade naquela area e responde a pergunta acionavel: DADO o nivel geral
-- desta rede, qual competencia fica desproporcionalmente para tras.

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

-- a competencia de cada habilidade vem da Matriz; sem ela o item nao pode
-- ser agregado (e um inner join de proposito: habilidade fora da Matriz e
-- defeito de seed, e somar num balde "nulo" esconderia isso)
item_comp as (

    select u.*, m.competencia
    from unidade_item u
    join {{ ref('matriz_referencia') }} m
      on m.area = u.area and m.habilidade = u.habilidade

),

agregado as (

    select
        nivel, codigo, max(nome) as nome, area, competencia,
        count(*) filter (where not item_anulado and not item_abandonado)
            as n_itens_validos,
        sum(n_respostas) filter (where not item_anulado and not item_abandonado)
            as n_respostas,
        sum(n_acertos) filter (where not item_anulado and not item_abandonado)
            as n_acertos
    from item_comp
    group by 1, 2, 4, 5

),

-- o patamar da unidade na area inteira: a media ponderada de todas as
-- competencias. E o que o `perfil` desconta
patamar as (

    select nivel, codigo, area,
           100.0 * sum(n_acertos) / nullif(sum(n_respostas), 0) as taxa_area
    from agregado
    group by 1, 2, 3

),

nacional as (

    select
        m.area, m.competencia,
        count(*) filter (where not n.item_anulado and not n.item_abandonado)
            as n_itens_validos,
        sum(n.n_respostas) filter (where not n.item_anulado and not n.item_abandonado)
            as n_respostas,
        sum(n.n_acertos) filter (where not n.item_anulado and not n.item_abandonado)
            as n_acertos
    from {{ ref('int_acerto_item_nacional') }} n
    join {{ ref('matriz_referencia') }} m
      on m.area = n.area and m.habilidade = n.habilidade
    group by 1, 2

),

patamar_nacional as (

    select area,
           100.0 * sum(n_acertos) / nullif(sum(n_respostas), 0) as taxa_area
    from nacional
    group by 1

),

-- grade completa: toda unidade presente numa area recebe TODAS as
-- competencias da area
grade as (

    select p.nivel, p.codigo, p.nome, p.area, n.competencia
    from (select distinct nivel, codigo, nome, area from agregado) p
    join nacional n
      on n.area = p.area

),

calculado as (

    select
        g.nivel,
        g.codigo,
        g.nome,
        g.area,
        g.competencia,
        m.descricao_competencia,

        coalesce(a.n_itens_validos, 0) as n_itens_validos,
        n.n_itens_validos              as n_itens_validos_nacional,
        coalesce(a.n_respostas, 0)     as n_respostas,
        coalesce(ga.publicavel, false) as publicavel,

        case
            when n.n_itens_validos = 0              then 'nao_avaliada'
            when coalesce(a.n_itens_validos, 0) = 0 then 'nao_administrada'
            else 'ok'
        end as status,

        100.0 * a.n_acertos / nullif(a.n_respostas, 0) as taxa,
        100.0 * n.n_acertos / nullif(n.n_respostas, 0) as taxa_nac,
        p.taxa_area,
        pn.taxa_area                                   as taxa_area_nac

    from grade g

    join nacional n
      on n.area = g.area and n.competencia = g.competencia

    left join agregado a
      on a.nivel = g.nivel and a.codigo = g.codigo
     and a.area = g.area and a.competencia = g.competencia

    left join patamar p
      on p.nivel = g.nivel and p.codigo = g.codigo and p.area = g.area

    join patamar_nacional pn
      on pn.area = g.area

    -- a governanca viaja: quem consome so este mart recebe o gate do N minimo
    left join {{ ref('mart_geografia_area') }} ga
      on ga.nivel = g.nivel and ga.codigo = g.codigo and ga.area = g.area

    -- left join: competencia sem descricao na Matriz nao pode sumir
    left join (
        select distinct area, competencia, descricao_competencia
        from {{ ref('matriz_referencia') }}
    ) m
      on m.area = g.area and m.competencia = g.competencia

)

select
    nivel, codigo, nome, area, competencia, descricao_competencia,
    n_itens_validos, n_itens_validos_nacional, n_respostas, publicavel, status,

    round(taxa, 2)                          as taxa_acerto,
    round(taxa_nac, 2)                      as taxa_acerto_nacional,
    round(taxa - taxa_nac, 2)               as diferenca,

    round(taxa_area, 2)                     as taxa_area,
    round(taxa_area - taxa_area_nac, 2)     as diferenca_area,

    -- o numero que o mapa pinta: a diferenca DEPOIS de descontar o patamar
    -- da unidade. Positivo = esta competencia vai melhor do que o resto da
    -- area nesta rede; negativo = fica para tras alem do nivel geral
    round((taxa - taxa_nac) - (taxa_area - taxa_area_nac), 2) as perfil

from calculado

-- O produto do projeto: o que os alunos da escola dominam e o que precisa ser
-- desenvolvido, habilidade a habilidade, contra a referencia nacional.
--
-- O modelo parte de um GRID COMPLETO escola x area x habilidade. Nao e
-- preciosismo: linha ausente e omissao silenciosa, e omissao ja mordeu duas
-- vezes nesta base.
--   MT hab 21 -- a edicao nao tem item valido (o unico foi anulado).
--   LC hab 8  -- coberta so por itens de espanhol; escola sem aluno de
--               espanhol nao tem linha nenhuma em int_acerto_item_escola.
-- Sao coisas diferentes e recebem status diferentes: 'nao_avaliada' (a edicao
-- nao tem o que medir) e 'nao_administrada' (a escola nao teve quem
-- respondesse). Ausencia estrutural nao e fracasso.

with escola as (

    select
        co_escola,
        area,
        habilidade,
        count(*) as n_itens,
        count(*) filter (where not item_anulado and not item_abandonado)
            as n_itens_validos,
        sum(n_respostas) filter (where not item_anulado and not item_abandonado)
            as n_respostas,
        sum(n_acertos) filter (where not item_anulado and not item_abandonado)
            as n_acertos
    from {{ ref('int_acerto_item_escola') }}
    group by 1, 2, 3

),

nacional as (

    select
        area,
        habilidade,
        count(*) filter (where not item_anulado and not item_abandonado)
            as n_itens_validos,
        sum(n_respostas) filter (where not item_anulado and not item_abandonado)
            as n_respostas,
        sum(n_acertos) filter (where not item_anulado and not item_abandonado)
            as n_acertos
    from {{ ref('int_acerto_item_nacional') }}
    group by 1, 2

),

-- toda escola presente numa area recebe TODAS as habilidades da area
grade as (

    select
        p.co_escola,
        p.area,
        n.habilidade
    from (select distinct co_escola, area from escola) p
    join nacional n
      on n.area = p.area

)

select
    g.co_escola,
    g.area,
    g.habilidade,

    coalesce(e.n_itens, 0)         as n_itens,
    coalesce(e.n_itens_validos, 0) as n_itens_validos,
    -- o lastro da referencia ao lado do da escola: nas habilidades de lingua
    -- (LC 5-8) o da escola depende do mix de ingles e espanhol dos alunos dela
    n.n_itens_validos              as n_itens_validos_nacional,
    coalesce(e.n_respostas, 0)     as n_respostas,

    -- o gate do N minimo viaja com o dado: quem consome so este mart nao pode
    -- publicar escola pequena sem saber
    coalesce(ea.publicavel, false) as publicavel,

    case
        when n.n_itens_validos = 0              then 'nao_avaliada'
        when coalesce(e.n_itens_validos, 0) = 0 then 'nao_administrada'
        when e.n_itens_validos = 1              then 'um_item'
        else 'ok'
    end as status,

    -- taxa ponderada (soma acertos / soma respostas), simetrica na escola e na
    -- referencia -- e nao media das taxas por item
    round(100.0 * e.n_acertos / nullif(e.n_respostas, 0), 2)
        as taxa_acerto,
    round(100.0 * n.n_acertos / nullif(n.n_respostas, 0), 2)
        as taxa_acerto_nacional,
    round(100.0 * e.n_acertos / nullif(e.n_respostas, 0)
        - 100.0 * n.n_acertos / nullif(n.n_respostas, 0), 2)
        as diferenca

from grade g

join nacional n
  on n.area       = g.area
 and n.habilidade = g.habilidade

left join escola e
  on e.co_escola  = g.co_escola
 and e.area       = g.area
 and e.habilidade = g.habilidade

left join {{ ref('mart_escola_area') }} ea
  on ea.co_escola = g.co_escola
 and ea.area      = g.area

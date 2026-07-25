-- Mesma pergunta do mart de habilidade, num grao mais grosso.
--
-- Por que existe: 62 das 120 habilidades sao medidas por UM item so, e uma
-- (MT 21) por nenhum. Nao e falta de precisao -- uma escola com 100 alunos tem
-- 100 respostas por item -- e falta de validade de conteudo: um item mede a
-- habilidade, mas mede junto o enunciado, o distrator e o tema daquele item.
--
-- A competencia de area resolve por agregacao: 4 a 11 itens validos por medida.
-- Nao substitui o mart de habilidade. Habilidade e acionavel (diz o que
-- trabalhar na segunda-feira) mas fragil; competencia e confiavel mas larga
-- demais para virar plano de aula. Os dois juntos dao o que nenhum da sozinho.

with escola as (

    select
        e.co_escola,
        e.area,
        m.competencia,
        count(*) filter (where not e.item_anulado and not e.item_abandonado)
            as n_itens_validos,
        sum(e.n_respostas) filter (where not e.item_anulado and not e.item_abandonado)
            as n_respostas,
        sum(e.n_acertos) filter (where not e.item_anulado and not e.item_abandonado)
            as n_acertos
    from {{ ref('int_acerto_item_escola') }} e
    join {{ ref('matriz_referencia') }} m
      on m.area       = e.area
     and m.habilidade = e.habilidade
    group by 1, 2, 3

),

nacional as (

    select
        n.area,
        m.competencia,
        max(m.descricao_competencia) as descricao,
        count(*) filter (where not n.item_anulado and not n.item_abandonado)
            as n_itens_validos,
        sum(n.n_respostas) filter (where not n.item_anulado and not n.item_abandonado)
            as n_respostas,
        sum(n.n_acertos) filter (where not n.item_anulado and not n.item_abandonado)
            as n_acertos
    from {{ ref('int_acerto_item_nacional') }} n
    join {{ ref('matriz_referencia') }} m
      on m.area       = n.area
     and m.habilidade = n.habilidade
    group by 1, 2

),

-- grid completo, pela mesma razao da Etapa 4: linha ausente e omissao
-- silenciosa, e este pipeline ja foi mordido duas vezes por isso
grade as (

    select
        p.co_escola,
        p.area,
        n.competencia
    from (select distinct co_escola, area from escola) p
    join nacional n
      on n.area = p.area

)

select
    g.co_escola,
    g.area,
    g.competencia,
    n.descricao                    as descricao_competencia,

    coalesce(e.n_itens_validos, 0) as n_itens_validos,
    n.n_itens_validos              as n_itens_validos_nacional,
    coalesce(e.n_respostas, 0)     as n_respostas,
    coalesce(ea.publicavel, false) as publicavel,

    round(100.0 * e.n_acertos / nullif(e.n_respostas, 0), 2)
        as taxa_acerto,
    round(100.0 * n.n_acertos / nullif(n.n_respostas, 0), 2)
        as taxa_acerto_nacional,
    round(100.0 * e.n_acertos / nullif(e.n_respostas, 0)
        - 100.0 * n.n_acertos / nullif(n.n_respostas, 0), 2)
        as diferenca

from grade g

join nacional n
  on n.area        = g.area
 and n.competencia = g.competencia

left join escola e
  on e.co_escola   = g.co_escola
 and e.area        = g.area
 and e.competencia = g.competencia

left join {{ ref('mart_escola_area') }} ea
  on ea.co_escola = g.co_escola
 and ea.area      = g.area

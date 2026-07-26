-- O perfil de estudo por nivel de habilidade -- a face do aluno (PLANO.md).
--
-- Para cada theta, area (e lingua, em LC) e habilidade: quanto se espera
-- acertar e quanta INFORMACAO os itens daquela habilidade carregam naquele
-- nivel. A prioridade ordena por informacao, nao por taxa de erro -- e esta
-- e a tese do produto: a habilidade que a pessoa mais erra costuma ser a
-- pior escolha de estudo no curto prazo (esta longe demais do nivel dela);
-- o ganho mora na fronteira, onde o resultado e genuinamente incerto.
--
-- Limite declarado (PLANO.md): a TRI do ENEM e unidimensional. Isto diz
-- "onde a prova mais distingue pessoas do seu nivel", e a ponte para
-- "estude isso" e uma heuristica pedagogica razoavel, nao uma previsao do
-- modelo. A API comunica nesses termos, e n_itens viaja junto porque 62 das
-- 120 habilidades tem um unico item -- medida fragil continua fragil.

with base as (

    -- fora de LC, todo participante ve os mesmos itens
    select theta, area, null::int as cod_lingua, habilidade,
           prob_acerto, informacao
    from {{ ref('mart_curva_item') }}
    where area != 'LC'

    union all

    -- em LC cada lingua tem seu proprio conjunto: 40 comuns + os 5 dela
    select c.theta, c.area, l.cod_lingua, c.habilidade,
           c.prob_acerto, c.informacao
    from {{ ref('mart_curva_item') }} c
    join (values (0), (1)) l(cod_lingua)
      on c.cod_lingua is null
      or c.cod_lingua = l.cod_lingua
    where c.area = 'LC'

),

agregado as (

    select
        theta,
        area,
        cod_lingua,
        habilidade,
        count(*)                          as n_itens,
        round(avg(prob_acerto) * 100, 1)  as acerto_esperado,
        round(sum(informacao), 4)         as informacao_total
    from base
    group by 1, 2, 3, 4

)

select
    a.theta,
    a.area,
    a.cod_lingua,
    a.habilidade,
    m.competencia,
    m.descricao_habilidade,
    m.descricao_competencia,
    a.n_itens,
    a.acerto_esperado,
    a.informacao_total,

    -- 1 = onde o esforco mais converte em ponto, neste nivel
    rank() over (
        partition by a.theta, a.area, a.cod_lingua
        order by a.informacao_total desc
    ) as prioridade

from agregado a

-- left join: habilidade sem correspondencia na Matriz nao pode sumir
-- (regra da Etapa 5; o teste competencia_cobre_habilidades denuncia)
left join {{ ref('matriz_referencia') }} m
  on m.area = a.area
 and m.habilidade = a.habilidade

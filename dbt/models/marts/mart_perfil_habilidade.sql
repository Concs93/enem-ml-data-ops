-- O perfil de estudo por nivel de habilidade -- a face do aluno (PLANO.md).
--
-- Para cada theta, area (e lingua, em LC) e habilidade: quanto se espera
-- acertar e quanta INFORMACAO os itens daquela habilidade carregam naquele
-- nivel. A tese do produto: a habilidade que a pessoa mais erra costuma ser
-- a pior escolha de estudo no curto prazo (esta longe demais do nivel dela);
-- o ganho mora na fronteira, onde o resultado e genuinamente incerto.
--
-- NOTA DE SINCRONIA (ver CLAUDE.md, "A ordem da tela"): o SITE nao ordena
-- pela coluna prioridade deste mart. Ele ordena pelo GANHO DE UM PASSO
-- (diferenca de acerto_esperado entre theta e theta+0,5, convertida em
-- pontos), porque e esse o numero exibido -- ordem e numero nao podem se
-- contradizer. A prioridade por informacao segue aqui como fato
-- psicometrico; quem consumir este mart direto deve saber das duas.
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

),

-- GRID COMPLETO: toda combinacao nivel x area(x lingua) recebe TODAS as 30
-- habilidades da Matriz. Os dois fantasmas do projeto exigem isto aqui
-- tambem: MT 21 nao tem item valido na edicao, e LC 8 nao e medivel para
-- quem fez ingles (so espanhol a ve). Linha ausente e omissao silenciosa --
-- o perfil declara o vazio com n_itens = 0 e prioridade nula, e o site
-- mostra "nao mediavel" em vez de fingir que a habilidade nao existe.
grade as (

    select g.theta, g.area, g.cod_lingua, m.habilidade
    from (select distinct theta, area, cod_lingua from agregado) g
    join {{ ref('matriz_referencia') }} m
      on m.area = g.area

)

select
    g.theta,
    g.area,
    g.cod_lingua,
    g.habilidade,
    m.competencia,
    m.descricao_habilidade,
    m.descricao_competencia,
    coalesce(a.n_itens, 0)           as n_itens,
    a.acerto_esperado,
    coalesce(a.informacao_total, 0)  as informacao_total,

    -- 1 = onde o esforco mais converte em ponto, neste nivel.
    -- Habilidade nao mediavel nao entra na fila: prioridade nula, nunca um
    -- numero fingido no fim da lista (teste perfil_prioridade_condiz)
    case when coalesce(a.n_itens, 0) > 0 then
        rank() over (
            partition by g.theta, g.area, g.cod_lingua
            order by (coalesce(a.n_itens, 0) = 0),
                     coalesce(a.informacao_total, 0) desc
        )
    end as prioridade

from grade g

left join agregado a
  on a.theta = g.theta
 and a.area  = g.area
 and a.cod_lingua is not distinct from g.cod_lingua
 and a.habilidade = g.habilidade

-- left join: habilidade sem correspondencia na Matriz nao pode sumir
-- (regra da Etapa 5; o teste competencia_cobre_habilidades denuncia)
left join {{ ref('matriz_referencia') }} m
  on m.area = g.area
 and m.habilidade = g.habilidade

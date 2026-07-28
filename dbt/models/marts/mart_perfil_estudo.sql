-- RECOMENDACAO DE ESTUDO baseada no historico do ENEM (2020-2025).
--
-- Irmao do mart_perfil_habilidade, e a diferenca e a PERGUNTA:
--
--   mart_perfil_habilidade -> "o que rendia na prova de 2025"  (diagnostico)
--   mart_perfil_estudo     -> "o que costuma render no seu nivel" (preparacao)
--
-- Sao respostas diferentes de verdade, nao duas versoes da mesma: medido, as
-- tres primeiras competencias coincidem em media 1,5 de 3. Por isso as duas
-- viajam para o site, cada uma no seu cartao.
--
-- Por que a historia e a base melhor para PREPARACAO: a ordem tirada de
-- metade dos itens de 2025 correlaciona +0,19 com a da outra metade (quase
-- nada); as cinco edicoes REGULARES anteriores preveem 2025 com +0,27. Melhor
-- que uma edicao sozinha, e so um pouco -- uma prova e, em boa parte, sorteio
-- de itens, e seis provas ainda sao poucas.
--
-- Numero honesto por area (rho medio 2020-24 -> 2025):
--     LC +0,50 · CN +0,42 · MT +0,16 · CH -0,01
-- Em CH nao ha transferencia mensuravel entre edicoes. A tela diz isso.
--
-- E O TAMANHO DA MEDIDA, declarado (auditoria adversarial): cada rho e
-- calculado sobre APENAS 6-9 competencias, entao os IC95% dos quatro
-- atravessam o zero e se sobrepoem quase por inteiro -- a escada LC>CN>MT>CH
-- e tendencia ordinal, nao ranking estabelecido. O 1o lugar exato da
-- configuracao embarcada acerta 2/20 entre edicoes (nivel do acaso ~2,7/20).
-- Por isso a tela trata a ordem como GRUPO de apostas, sem selo dourado, e
-- diz "tendeu a se repetir", nunca "e a que mais se repete".
--
-- CUSTO DA PUREZA, registrado: com TODAS as aplicacoes (reaplicacao, digital,
-- acessibilidade) o lastro ia a ~22 itens por habilidade e o rho subia para
-- +0,44, com o 1o lugar previsto em 9 de 20 casos contra 2 de 20 aqui. Foi
-- decisao de produto usar so regular -- a recomendacao descreve a prova que a
-- pessoa vai fazer -- e o preco esta medido, nao suposto.
--
-- A NORMALIZACAO NAO E DETALHE. O banco tem seis edicoes e, dentro de cada
-- uma, 12 a 18 versoes de prova (regular, reaplicacao, acessibilidade, BAM) --
-- entao ha ~20x mais itens que numa prova. Somar cru transformaria a lista num
-- ranking de "quantas vezes o conteudo apareceu". O certo e
--
--     rendimento POR QUESTAO  x  quantas questoes o conteudo costuma ter
--
-- e o segundo fator vem da PROPORCAO de itens da area dedicados aquele
-- conteudo, multiplicada pelas 45 questoes que a pessoa responde. Proporcao,
-- e nao contagem por edicao, porque assim o numero nao depende de quantas
-- versoes de prova o banco contem -- que varia de 12 a 18 por ano. Resultado
-- na mesma unidade do mart de 2025 (acertos a mais numa prova), e os dois
-- cartoes ficam comparaveis.
--
-- SO PROVAS REGULARES, igual ao mart de 2025. A recomendacao de estudo tem de
-- descrever a prova que a pessoa vai fazer, e reaplicacao, ENEM Digital,
-- segunda oportunidade e acessibilidade sao aplicacoes proprias, com itens
-- proprios. O seed co_prova_banco classifica as 400 versoes das seis edicoes
-- pela mesma regra do co_prova de 2025 -- 16 regulares por edicao, sempre.
--
-- Custo assumido: o lastro cai de ~20 para ~5 itens por habilidade. Ainda e
-- 3x o de uma edicao isolada (1,5), que era o problema a resolver.
--
-- Item individualmente ADAPTADO continua fora. O coalesce NAO e defensivo por
-- gosto: em 2021 o IN_ITEM_ADAPTADO vem VAZIO (nao "0"), o macro booleano()
-- devolve nulo, e `not nulo` e nulo -- o que fez a edicao inteira ser
-- descartada em silencio, 370 itens, sem erro nenhum. Achado so ao conferir
-- edicao por edicao; o teste banco_cobre_edicoes trava a regressao.

{{ config(
    materialized='table',
    pre_hook="set max_parallel_workers_per_gather = 0"
) }}

with grade as (

    select distinct theta from {{ ref('mart_curva_item') }}

),

valido as (

    select
        edicao, co_item, area, cod_lingua, habilidade,
        param_discriminacao as a,
        param_dificuldade   as b,
        param_acerto_casual as c
    from {{ ref('stg_itens_banco') }}
    where item_valido
      and is_regular
      and not coalesce(item_adaptado, false)
      and habilidade is not null

),

-- Em LC cada lingua ve 40 comuns + os 5 dela. Sem esta uniao, o mart teria um
-- terceiro grupo (cod_lingua nulo) que nao corresponde a participante nenhum,
-- e as habilidades 5-8 sumiriam de quem fez a outra lingua. Mesma regra do
-- mart_perfil_habilidade
itens as (

    select edicao, co_item, area, null::int as cod_lingua, habilidade, a, b, c
    from valido
    where area != 'LC'

    union all

    select v.edicao, v.co_item, v.area, l.cod_lingua, v.habilidade, v.a, v.b, v.c
    from valido v
    join (values (0), (1)) l(cod_lingua)
      on v.cod_lingua is null
      or v.cod_lingua = l.cod_lingua
    where v.area = 'LC'

),

-- quantas questoes daquela habilidade uma prova costuma ter, pela PROPORCAO
-- de itens da area (nao pela contagem por edicao, que depende de quantas
-- versoes de prova o banco tem). x 45 = as questoes que a pessoa responde
lastro as (

    select
        area,
        cod_lingua,
        habilidade,
        count(*)                                     as n_itens_banco,
        count(distinct edicao)                       as n_edicoes,
        45.0 * count(*)
            / sum(count(*)) over (partition by area, cod_lingua)
                                                     as itens_por_prova
    from itens
    group by 1, 2, 3

),

-- ganho de UM PASSO (theta -> theta + 0,5) por item, a mesma medida que a
-- tela mostra. Fica aqui e nao no site porque e conta de banco: 2.660 itens
-- x 161 niveis
por_item as (

    select
        g.theta,
        i.area,
        i.cod_lingua,
        i.habilidade,
        (i.c + (1 - i.c) / (1 + exp(-1.7 * i.a * ((g.theta + 0.5) - i.b))))
      - (i.c + (1 - i.c) / (1 + exp(-1.7 * i.a * ( g.theta        - i.b))))
            as ganho_passo,
        (i.c + (1 - i.c) / (1 + exp(-1.7 * i.a * (g.theta - i.b))))
            as prob_acerto
    from grade g
    cross join itens i

),

agregado as (

    select
        p.theta,
        p.area,
        p.cod_lingua,
        p.habilidade,
        avg(p.ganho_passo)   as ganho_por_questao,
        avg(p.prob_acerto)   as prob_media
    from por_item p
    group by 1, 2, 3, 4

),

-- GRID COMPLETO, mesma regra do mart_perfil_habilidade: nenhuma habilidade
-- da Matriz pode sumir da lista por nao ter item. Aqui isso quase nao ocorre
-- (o banco cobre todas), mas a garantia vale igual -- linha ausente e omissao
-- silenciosa
gradecompleta as (

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

    coalesce(l.n_itens_banco, 0)                       as n_itens_banco,
    coalesce(l.n_edicoes, 0)                           as n_edicoes,
    round(coalesce(l.itens_por_prova, 0), 2)           as itens_por_prova,

    round(coalesce(a.prob_media, 0)::numeric * 100, 1) as acerto_esperado,

    -- rendimento por questao x questoes tipicas = ganho na escala de UMA prova
    round((coalesce(a.ganho_por_questao, 0)
           * coalesce(l.itens_por_prova, 0))::numeric, 4)
                                                       as ganho_passo,

    case when coalesce(l.n_itens_banco, 0) > 0 then
        rank() over (
            partition by g.theta, g.area, g.cod_lingua
            order by (coalesce(a.ganho_por_questao, 0)
                      * coalesce(l.itens_por_prova, 0)) desc
        )
    end                                                as prioridade

from gradecompleta g

left join agregado a
  on a.theta = g.theta
 and a.area  = g.area
 and a.cod_lingua is not distinct from g.cod_lingua
 and a.habilidade = g.habilidade

left join lastro l
  on l.area = g.area
 and l.cod_lingua is not distinct from g.cod_lingua
 and l.habilidade = g.habilidade

left join {{ ref('matriz_referencia') }} m
  on m.area = g.area
 and m.habilidade = g.habilidade

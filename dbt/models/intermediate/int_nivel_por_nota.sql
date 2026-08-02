{{ config(materialized='table') }}

-- A ponte nota -> nivel como tabela de consulta: para CADA faixa de 10
-- pontos que a edicao produziu, o theta_efetivo daquela faixa.
--
-- POR QUE EXISTE (02/08/2026). Os pesos de UF e municipio derivavam o nivel
-- pela formula da escala, (nota - 500) / 100. Ela nao esta "errada" -- e a
-- DEFINICAO da escala do INEP, exata por construcao -- mas e OUTRA
-- QUANTIDADE, e a errada para este uso. O ganho de um passo sai do
-- mart_perfil_habilidade, cujo acerto_esperado(theta) e a TCC; o
-- theta_efetivo e, por definicao, o ponto da TCC que reproduz o acerto
-- OBSERVADO daquela faixa (ver mart_calibracao_nota). Como o export soma o
-- ganho ao acerto observado do lugar, as duas pontas da conta precisam do
-- mesmo theta -- senao mede-se a derivada num ponto da curva onde aquelas
-- pessoas nao estao. Em MT 515 a diferenca e concreta: a formula da escala
-- da theta 0,15 (modelo preve ~10,2 acertos) contra 0,57 do theta_efetivo
-- (observado ~12,6).
--
-- Medido sobre a distribuicao nacional, o total do passo em pontos:
--   MT +51 -> +66 · CH +51 -> +67 · CN +51 -> +64
-- O +51 identico nas tres areas era sinal do problema, nao de saude: com
-- theta = (nota-500)/100, meio passo vale 50 pontos quase por construcao.
--
-- COBERTURA COMPLETA POR CONSTRUCAO. As faixas vem dos extremos FISICOS da
-- edicao (int_nota_extremos, populacao mais ampla que a do diagnostico), nao
-- da calibracao -- que descarta faixa com n < 100. Faixa sem calibracao
-- propria herda a da faixa calibrada mais proxima, e a coluna
-- theta_de_vizinha diz quais sao. Sem isso o join a jusante seria um INNER
-- que some com gente em silencio, a familia de defeito que este projeto ja
-- conhece por outros nomes.

with faixas as (

    select
        area,
        cod_lingua,
        generate_series((floor(nota_minima / 10) * 10)::int,
                        (floor(nota_maxima / 10) * 10)::int,
                        10) as nota_faixa
    from {{ ref('int_nota_extremos') }}

),

cal as (

    select area, cod_lingua, nota_faixa, theta_efetivo
    from {{ ref('mart_calibracao_nota') }}

)

select
    f.area,
    -- sentinela -1 fora de LC: o join a jusante e por igualdade, e nulo nao
    -- e igual a nulo (mesma convencao do int_estudo_referencia)
    coalesce(f.cod_lingua, -1)                       as cod_lingua,
    f.nota_faixa,
    coalesce(c.theta_efetivo, v.theta_efetivo)       as theta,
    (c.theta_efetivo is null)                        as theta_de_vizinha

from faixas f

left join cal c
  on c.area = f.area
 and c.cod_lingua is not distinct from f.cod_lingua
 and c.nota_faixa = f.nota_faixa

-- as pontas: a amostra acaba antes da escala (o having n >= 100 da
-- calibracao). Herdar a vizinha calibrada preserva a pessoa e assume o
-- nivel da faixa mais proxima que tem lastro -- explicito, nao silencioso
left join lateral (
    select c2.theta_efetivo
    from cal c2
    where c2.area = f.area
      and c2.cod_lingua is not distinct from f.cod_lingua
    order by abs(c2.nota_faixa - f.nota_faixa), c2.nota_faixa
    limit 1
) v on true

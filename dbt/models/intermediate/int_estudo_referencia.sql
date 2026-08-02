{{ config(
    materialized='table',
    pre_hook="set max_parallel_workers_per_gather = 0"
) }}

-- A REFERENCIA do potencial de crescimento: para cada (area, lingua, theta
-- da grade, competencia), quantos acertos um passo de avanco (theta+0,5)
-- devolve NAQUELA competencia. E o motor da face do aluno como tabela --
-- ~6 mil linhas, subsegundo.
--
-- MATERIALIZADA de proposito (licao cara de 02/08/2026): como CTE ao lado
-- de um join grande, o planejador nao tem estatistica, estima rows=1 e cai
-- em laco aninhado com varredura por linha -- duas versoes canceladas (51 e
-- 20+ min). Tabela real tem estatistica real, e o hash join volta sozinho.
--
-- cod_lingua viaja com sentinela -1 (nulo nao e hasheavel em igualdade):
-- fora de LC nao ha lingua, e -1 nunca colide com os codigos reais (0/1).

with perfil as (

    select area, cod_lingua, theta, competencia,
           sum(n_itens)                                  as n_itens,
           sum(n_itens * acerto_esperado) / sum(n_itens) as acerto
    from {{ ref('mart_perfil_habilidade') }}
    group by 1, 2, 3, 4

)

-- no topo da grade (theta+0,5 alem de 5,00) o ganho e zero: nao ha
-- observacao que sustente prever alem do que existe
select
    p.area,
    coalesce(p.cod_lingua, -1) as cod_lingua,
    p.theta,
    p.competencia,
    coalesce(q.n_itens * (q.acerto - p.acerto) / 100.0, 0) as ganho

from perfil p
left join perfil q
  on q.area = p.area
 and q.cod_lingua is not distinct from p.cod_lingua
 and q.competencia = p.competencia
 and q.theta = p.theta + 0.5

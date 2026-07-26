-- Toda escola PUBLICAVEL precisa de nome -- e o que torna o diagnostico
-- consultavel. O descasamento ENEM 2025 x Censo 2024 foi medido em 0,4%
-- (66 de 17.600 em MT); o teste trava em 1% para acusar regressao real
-- (cadastro errado, join quebrado, ano trocado) sem alarmar pelo residuo
-- conhecido e documentado no PLANO.md.
with publicaveis as (
    select distinct m.co_escola
    from {{ ref('mart_escola_area') }} m
    where m.publicavel
),
sem_nome as (
    select p.co_escola
    from publicaveis p
    join {{ ref('dim_escola') }} d using (co_escola)
    where d.nome_escola is null
)
select
    (select count(*) from sem_nome)   as publicaveis_sem_nome,
    (select count(*) from publicaveis) as publicaveis
where (select count(*) from sem_nome)::numeric
    > 0.01 * (select count(*) from publicaveis)

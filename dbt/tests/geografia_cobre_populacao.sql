-- Conservacao de populacao na geografia, com igualdade EXATA:
--   pais == soma das escolas (nenhum participante some ao subir de nivel)
--   municipio == pais (nenhum municipio caiu no join com o mapa)
--
-- A regiao imediata fica DE FORA de proposito: Boa Esperanca do Norte/MT
-- (municipio de 2025) nao pertence a nenhuma regiao imediata na divisao de
-- 2024, entao aquele nivel legitimamente nao soma o pais -- e uma diferenca
-- documentada, nao um vazamento.
with esperado as (
    select area, sum(n_presentes) as presentes
    from {{ ref('mart_escola_area') }} m
    where exists (select 1 from {{ ref('dim_escola') }} d
                  where d.co_escola = m.co_escola and d.co_municipio is not null)
    group by 1
),
por_nivel as (
    select nivel, area, sum(n_presentes) as presentes
    from {{ ref('mart_geografia_area') }}
    where nivel in ('pais', 'municipio', 'uf', 'regiao')
    group by 1, 2
)
select n.nivel, n.area, n.presentes, e.presentes as esperado
from por_nivel n
join esperado e using (area)
where n.presentes != e.presentes

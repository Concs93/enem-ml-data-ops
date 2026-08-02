-- Conservacao de populacao na geografia, com igualdade EXATA:
--   pais == soma das escolas (nenhum participante some ao subir de nivel)
--   uf e regiao == pais (nenhuma unidade caiu no join com o cadastro)
-- (municipio e regiao imediata sairam do mart em 02/08/2026 -- a
-- conservacao municipio->uf continua garantida na origem, porque a UF e
-- somada a partir do proprio int_acerto_item_municipio)
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
    -- o mart passou a ter uma linha por rede MAIS uma com todas somadas;
    -- somar sem filtrar contaria cada participante duas vezes nos DOIS lados
    -- da comparacao, e o teste passaria verde escondendo o defeito
    where rede = 'Todas'
      and nivel in ('pais', 'uf', 'regiao')
    group by 1, 2
)
select n.nivel, n.area, n.presentes, e.presentes as esperado
from por_nivel n
join esperado e using (area)
where n.presentes != e.presentes

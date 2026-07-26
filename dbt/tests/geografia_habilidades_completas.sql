-- Toda unidade geografica presente numa area tem TODAS as habilidades da
-- area -- a versao para a geografia do habilidades_completas da Etapa 4.
-- Nenhum teste por linha ve uma linha que nao existe.
with esperado as (
    select area, count(distinct habilidade) as n_habilidades
    from {{ ref('int_acerto_item_nacional') }}
    group by 1
)
select g.nivel, g.codigo, g.area,
       count(*)             as n_no_mart,
       min(e.n_habilidades) as n_esperado
from {{ ref('mart_geografia_habilidade') }} g
join esperado e using (area)
group by 1, 2, 3
having count(*) != min(e.n_habilidades)

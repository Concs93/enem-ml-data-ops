-- Os dois fatos descrevem a mesma populacao de (escola, area). Chegaram la por
-- caminhos diferentes -- um pelas notas do stg_resultados, outro pelos
-- agregados de resposta da Etapa 3 -- mas com os mesmos filtros: presente,
-- prova regular, escola identificada.
--
-- Divergencia significa filtro vazando de um lado, e o flag publicavel herdado
-- pelo diagnostico perderia o sentido.
with escola_area as (
    select distinct co_escola, area from {{ ref('mart_escola_area') }}
),

diagnostico as (
    select distinct co_escola, area from {{ ref('mart_diagnostico_habilidade') }}
)

select
    coalesce(a.co_escola, b.co_escola) as co_escola,
    coalesce(a.area, b.area)           as area,
    a.co_escola is null                as falta_no_escola_area,
    b.co_escola is null                as falta_no_diagnostico
from escola_area a
full outer join diagnostico b
  on b.co_escola = a.co_escola
 and b.area      = a.area
where a.co_escola is null
   or b.co_escola is null

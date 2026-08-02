-- Todo participante do peer group tem de virar PESO.
--
-- O nivel de cada aluno passou a vir de um JOIN (int_nivel_por_nota, em
-- 02/08/2026) em vez de uma conta na propria linha. Isso abre uma porta
-- nova para a familia de defeito que este projeto ja conhece por outros
-- nomes: se faltar uma faixa naquela tabela, o INNER join descarta aquelas
-- pessoas sem erro nenhum, o modelo constroi, os totais seguem plausiveis e
-- ninguem percebe. Contagem por si nao denuncia -- so denuncia quem exige a
-- populacao INTEIRA de volta.
--
-- Recomputa direto do stg_resultados com os mesmos filtros e exige
-- igualdade EXATA. Cada modelo com o SEU filtro de chave geografica
-- (int_uf_nivel exige co_uf_escola; int_municipio_nivel exige
-- co_municipio_escola) -- usar o mesmo nos dois inventaria uma diferenca
-- que nao e do que este teste guarda.
--
-- A rede 'Todas' e LINHA de grouping sets: filtrar por ela le a populacao
-- uma vez, nunca duas.

{% set areas = ['mt', 'ch', 'cn', 'lc'] %}

with direto as (

    {% for a in areas %}
    select
        '{{ a | upper }}' as area,
        count(*) filter (where r.co_uf_escola is not null)        as n_uf,
        count(*) filter (where r.co_municipio_escola is not null) as n_mun
    from {{ ref('stg_resultados') }} r
    join {{ ref('co_prova') }} p
      on p.co_prova = r.co_prova_{{ a }} and p.sg_area = '{{ a | upper }}'
    join {{ ref('dominios') }} d
      on d.variavel = 'TP_DEPENDENCIA_ADM_ESC'
     and d.codigo = r.cod_dependencia_escola::text
    where r.cod_presenca_{{ a }} = 1
      and p.is_regular
      and r.co_escola is not null
      and r.nota_{{ a }} > 0
      {% if a == 'lc' %}and r.cod_lingua is not null{% endif %}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

),

por_uf as (
    select area, sum(n) as n from {{ ref('int_uf_nivel') }}
    where rede = 'Todas' group by 1
),

por_mun as (
    select area, sum(n) as n from {{ ref('int_municipio_nivel') }}
    where rede = 'Todas' group by 1
)

select
    d.area,
    d.n_uf                 as esperado_uf,
    coalesce(u.n, 0)       as no_int_uf_nivel,
    d.n_mun                as esperado_municipio,
    coalesce(m.n, 0)       as no_int_municipio_nivel
from direto d
left join por_uf  u on u.area = d.area
left join por_mun m on m.area = d.area
where d.n_uf  is distinct from coalesce(u.n, 0)
   or d.n_mun is distinct from coalesce(m.n, 0)

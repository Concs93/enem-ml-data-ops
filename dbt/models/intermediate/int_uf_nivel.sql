{{ config(
    materialized='table',
    pre_hook="set max_parallel_workers_per_gather = 0"
) }}

-- Quantos alunos cada UF x REDE tem em cada NIVEL de nota -- os pesos do
-- potencial de crescimento por estado. Sao as notas reais dos alunos como
-- distribuicao, nunca a media: theta(media) != media(theta) (ja medido:
-- nota 805 da 2,35 pela TCC contra 3,05 pela escala), e 93,4% da variacao
-- de nota vive DENTRO das unidades.
--
-- O NIVEL vem do int_nivel_por_nota (theta_efetivo da faixa), nao de
-- (nota-500)/100 -- ver o cabecalho daquele modelo para o porque e para o
-- que a troca mudou. O join e por igualdade contra uma tabela de algumas
-- centenas de linhas, com cobertura completa da escala por construcao.
--
-- A UF e a rede vem DIRETO do stg_resultados (co_uf_escola e
-- cod_dependencia_escola estao na propria base de resultados) -- sem junta
-- com dim_escola. A rede 'Todas' e LINHA (grouping sets): o consumidor que
-- somar sem filtrar conta cada aluno duas vezes.

{% set areas = ['mt', 'ch', 'cn', 'lc'] %}

with alunos as (

    {% for a in areas %}
    select
        r.co_uf_escola as co_uf,
        d.rotulo       as rede,
        '{{ a | upper }}' as area,
        {% if a == 'lc' %}r.cod_lingua{% else %}-1{% endif %} as cod_lingua,
        nv.theta
    from {{ ref('stg_resultados') }} r
    join {{ ref('co_prova') }} p
      on p.co_prova = r.co_prova_{{ a }} and p.sg_area = '{{ a | upper }}'
    join {{ ref('int_nivel_por_nota') }} nv
      on nv.area = '{{ a | upper }}'
     and nv.cod_lingua = {% if a == 'lc' %}r.cod_lingua{% else %}-1{% endif %}
     and nv.nota_faixa = (floor(r.nota_{{ a }} / 10) * 10)::int
    -- o rotulo da rede sai do seed de dominios (derivar, nunca transcrever)
    join {{ ref('dominios') }} d
      on d.variavel = 'TP_DEPENDENCIA_ADM_ESC'
     and d.codigo = r.cod_dependencia_escola::text
    where r.cod_presenca_{{ a }} = 1
      and p.is_regular
      and r.co_escola is not null
      and r.co_uf_escola is not null
      -- nota 0 e sentinela de prova em branco: sem nivel estimavel
      and r.nota_{{ a }} > 0
      {% if a == 'lc' %}and r.cod_lingua is not null{% endif %}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

)

select
    co_uf,
    case when grouping(rede) = 1 then 'Todas' else rede end as rede,
    area,
    cod_lingua,
    theta,
    count(*) as n
from alunos
group by grouping sets (
    (co_uf, rede, area, cod_lingua, theta),
    (co_uf,       area, cod_lingua, theta)
)

{#
    Distribuicao do numero de acertos por faixa de nota (Passo 2 do PLANO.md).

    Grao de saida: area x lingua x faixa de 10 pontos x n de acertos -> contagem.
    E a estatistica suficiente do Passo 0: media, desvio e percentil empirico
    saem todos daqui, sem persistir 3,2 milhoes de linhas por pessoa.

    So itens validos (anulado/abandonado fora), so nota > 0 (o zero e
    sentinela de prova em branco -- Etapa 5). Em LC a lingua entra no grao:
    quem fez ingles respondeu itens diferentes de quem fez espanhol, e as
    curvas caracteristicas nao se misturam.
#}

{% macro distribui_acertos(sigla, com_lingua=false) %}

{%- set s = sigla | lower -%}

with pessoa as (

    select
        r.id_resultado,
        count(*) filter (where r.acertou) as acertos
    from {{ ref('int_respostas_' ~ s) }} r
    where not r.item_anulado
      and not r.item_abandonado
    group by 1

),

com_nota as (

    select
        p.acertos,
        {% if com_lingua %}s.cod_lingua,{% endif %}
        s.nota_{{ s }} as nota
    from pessoa p
    join {{ ref('stg_resultados') }} s using (id_resultado)
    where s.nota_{{ s }} > 0

)

select
    '{{ sigla | upper }}'          as area,
    {% if com_lingua %}cod_lingua{% else %}null::int as cod_lingua{% endif %},
    (floor(nota / 10) * 10)::int   as nota_faixa,
    acertos,
    count(*)                       as n
from com_nota
group by 1, 2, 3, 4

{% endmacro %}

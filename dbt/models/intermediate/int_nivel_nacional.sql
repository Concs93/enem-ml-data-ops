{{ config(
    materialized='table',
    pre_hook="set max_parallel_workers_per_gather = 0"
) }}

-- A REFERENCIA DA FACE DO GESTOR: quanto o Brasil acerta em cada competencia,
-- POR NIVEL DE NOTA. Uma varredura do grao de resposta, saida minuscula
-- (~4 mil linhas), e dela saem os DOIS indicadores da tela:
--
--   esperado(unidade, comp) = SOMA_theta  n_unidade(theta) x taxa_nacional(theta, comp)
--   ganho(unidade, comp)    = SOMA_theta  n_unidade(theta) x [taxa(theta+0,5) - taxa(theta)]
--
-- O primeiro responde "onde ficamos abaixo de quem tem a mesma nota"; o
-- segundo, "onde avancar meio nivel mais rende". Os dois sao CONTAGEM contra
-- CONTAGEM -- nenhum parametro de TRI entra aqui.
--
-- POR QUE EMPIRICO E NAO O 3PL. O mart_perfil_habilidade tem o acerto
-- previsto pelo modelo e serviria; mas a frase que a tela precisa dizer e
-- "do que alunos com a mesma nota", e essa e literal so na versao observada.
-- O Brasil tem 1,27 a 1,33 mi de pessoas por area, entao a faixa de 5 pontos
-- de nota junta ~9 mil pessoas: ruido nao e problema. A versao 3PL fica como
-- confirmacao cruzada -- se as duas discordarem, a discordancia diz onde o
-- modelo nao serve aquele subgrupo.
--
-- theta = (nota - 500)/100 e DEFINICAO da escala do INEP (Procedimentos de
-- Analise), nao aproximacao. A grade de 0,05 e a mesma do mart_curva_item,
-- para que as duas versoes se joguem sem interpolacao.

{% set areas = ['mt', 'ch', 'cn', 'lc'] %}

with respostas as (

    {% for a in areas %}
    select
        '{{ a | upper }}'  as area,
        {% if a == 'lc' %}i.cod_lingua{% else %}null::int{% endif %} as cod_lingua,
        -- a grade e limitada a faixa que o mart_perfil_habilidade cobre;
        -- fora dela nao ha com o que cruzar
        greatest(-3.00, least(5.00,
            round(((i.nota - 500) / 100.0) / 0.05) * 0.05))::numeric(5,2) as theta,
        i.habilidade,
        i.acertou
    -- a nota vem NA PROPRIA VIEW (explode_respostas): juntar stg_resultados
    -- aqui seria junta-la com ela mesma, sondada 220 mi de vezes -- foi o
    -- que fez a primeira construcao custar 44,9 min
    from {{ ref('int_respostas_' ~ a) }} i
    where not i.item_anulado
      and not i.item_abandonado
      -- nota 0 e sentinela de prova em branco, nao desempenho (Etapa 5).
      -- Quem entregou em branco nao tem nivel estimavel e sairia como um
      -- "nivel 300 que erra tudo", achatando a referencia inteira
      and i.nota > 0
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

),

por_competencia as (

    select
        r.area,
        r.cod_lingua,
        r.theta,
        m.competencia,
        count(*)                        as n_respostas,
        count(*) filter (where acertou) as n_acertos
    from respostas r
    join {{ ref('matriz_referencia') }} m
      on m.area = r.area and m.habilidade = r.habilidade
    group by 1, 2, 3, 4

)

select
    area,
    cod_lingua,
    theta,
    competencia,
    n_respostas,
    n_acertos,
    round(100.0 * n_acertos / nullif(n_respostas, 0), 4) as taxa_nacional
from por_competencia
-- piso de lastro: abaixo disso a faixa e rara demais e a taxa vira ruido que
-- se propaga para TODA unidade que tiver alguem ali. Mesmo criterio do
-- having n >= 100 da calibracao
where n_respostas >= 400

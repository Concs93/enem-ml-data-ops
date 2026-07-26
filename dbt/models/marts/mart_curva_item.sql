-- O motor psicometrico como TABELA (PLANO.md, Passo 2).
--
-- Para cada item valido das provas regulares e cada nivel de habilidade
-- (theta, grade de 0,05), a curva caracteristica do 3PL e a informacao de
-- Fisher. Os parametros a, b, c vieram calibrados pelo INEP -- nao ha nada a
-- ajustar, so funcoes conhecidas a avaliar. Pre-computar da ao modelo o mesmo
-- versionamento, teste e documentacao que o resto do pipeline ja tem: sem
-- binario serializado, sem servidor de modelo.
--
-- Validacao que sustenta isto (Volume 8 / PLANO.md): integrar P sobre a
-- distribuicao de theta reproduz a taxa observada por item com r >= 0,95
-- nas quatro areas.
--
-- cod_lingua viaja porque em LC as curvas nao se misturam: quem fez ingles
-- respondeu 40 comuns + 5 de ingles; quem fez espanhol, outros 5.

{% set theta_min = -3.0 %}
{% set theta_max = 5.0 %}
{% set passo = 0.05 %}

with itens as (

    select distinct
        i.co_item,
        i.area,
        i.habilidade,
        i.cod_lingua,
        i.param_discriminacao as a,
        i.param_dificuldade   as b,
        i.param_acerto_casual as c
    from {{ ref('stg_itens') }} i
    join {{ ref('co_prova') }} p
      on p.co_prova = i.co_prova
     and p.sg_area  = i.area
    -- so provas regulares: reaplicacao e BAM tem itens proprios que nao
    -- entram no diagnostico (mesma regra de todo o pipeline)
    where p.is_regular
      -- item sem parametro nao foi escorado pelo INEP: nao tem curva
      and i.param_dificuldade is not null
      and not i.item_anulado
      and not i.item_abandonado

),

grade as (

    select round(({{ theta_min }} + {{ passo }} * g)::numeric, 2) as theta
    from generate_series(0, {{ ((theta_max - theta_min) / passo) | round | int }}) g

),

curva as (

    select
        i.co_item, i.area, i.habilidade, i.cod_lingua,
        g.theta, i.a, i.c,
        i.c + (1 - i.c) / (1 + exp(-1.7 * i.a * (g.theta - i.b))) as p
    from itens i
    cross join grade g

)

select
    co_item,
    area,
    habilidade,
    cod_lingua,
    theta,
    round(p::numeric, 4) as prob_acerto,

    -- informacao de Fisher do 3PL. Zera nos dois extremos: item facil demais
    -- (p -> 1) e dificil demais (p -> c) nao distinguem ninguem naquele nivel
    round((power(1.7 * a, 2)
           * power((p - c) / nullif(1 - c, 0), 2)
           * (1 - p) / nullif(p, 0))::numeric, 6) as informacao

from curva

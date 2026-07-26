-- A calibracao empirica nota -> theta (PLANO.md, Passo 0/2).
--
-- O Passo 0 mostrou que o mapeamento ingenuo theta = (nota - 500) / 100
-- falha nas caudas: na base da escala o observado fica ABAIXO do piso de
-- chute do 3PL (quem esta ali deixa em branco, e branco nao chuta); no topo,
-- nota 700 corresponde a ~5 acertos a menos que o teorico. Este mart resolve
-- pelo caminho empirico: para cada faixa de nota, os acertos MEDIDOS em 1,27
-- milhao de participantes, e o theta_efetivo = o ponto da curva caracteristica
-- do teste (TCC) que reproduz esses acertos.
--
-- E o theta_efetivo -- nao a formula -- que a API usa para posicionar a
-- pessoa nas curvas de informacao.

with faixas as (

    select
        area,
        cod_lingua,
        nota_faixa,
        sum(n) as n,
        sum(acertos::numeric * n) / sum(n) as acertos_medio,
        -- desvio a partir da frequencia agrupada: E[X^2] - E[X]^2
        sqrt(sum(n * power(acertos, 2))::numeric / sum(n)
             - power(sum(acertos::numeric * n) / sum(n), 2)) as dp_acertos
    from {{ ref('int_distribuicao_acertos') }}
    group by 1, 2, 3
    -- calibracao e curva, nao censo: faixa com pouca gente vira ruido na
    -- inversa da TCC. As faixas descartadas seguem inteiras no
    -- mart_distribuicao_acertos, que e contagem pura
    having sum(n) >= 100

),

-- curva caracteristica do teste: soma das probabilidades dos itens que
-- AQUELA pessoa responde. Em LC, 40 comuns + os 5 da lingua dela
tcc as (

    select c.area, l.cod_lingua, c.theta,
           sum(c.prob_acerto) as acertos_esperados
    from {{ ref('mart_curva_item') }} c
    join (values (null::int), (0), (1)) l(cod_lingua)
      on (c.area != 'LC' and l.cod_lingua is null)
      or (c.area  = 'LC' and l.cod_lingua is not null
          and (c.cod_lingua is null or c.cod_lingua = l.cod_lingua))
    group by 1, 2, 3

)

select
    f.area,
    f.cod_lingua,
    f.nota_faixa,
    f.n,
    round(f.acertos_medio, 2) as acertos_medio,
    round(f.dp_acertos, 2)    as dp_acertos,
    t.theta                   as theta_efetivo,
    round(t.acertos_esperados::numeric, 1) as acertos_na_curva

from faixas f

-- TCC inversa: o theta da grade cuja TCC mais se aproxima dos acertos
-- observados. Valida porque toda discriminacao e positiva (a_min = 0,67),
-- logo a TCC e estritamente crescente -- e o teste calibracao_monotona
-- trava a regressao disso
cross join lateral (
    select theta, acertos_esperados
    from tcc t
    where t.area = f.area
      and t.cod_lingua is not distinct from f.cod_lingua
    order by abs(t.acertos_esperados - f.acertos_medio), t.theta
    limit 1
) t

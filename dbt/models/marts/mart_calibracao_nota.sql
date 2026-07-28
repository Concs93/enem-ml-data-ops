-- A calibracao empirica nota -> theta_efetivo (PLANO.md, Passo 0/2).
--
-- ALINHAMENTO COM O INEP, dito com precisao. A relacao nota = 100*theta + 500
-- e DEFINICAO DE ESCALA do INEP (documento "ENEM - Procedimentos de Analise":
-- proficiencia estimada por EAP na escala de 2009, grupo de referencia normal
-- padrao, equalizacao por itens comuns pre-testados). Ela e exata por
-- construcao, e este mart NAO a corrige.
--
-- O theta_efetivo e OUTRA quantidade: o ponto da curva caracteristica do teste
-- (TCC) que reproduz o total MEDIO de acertos observado naquela faixa de nota.
-- Responde "quantas questoes espera acertar quem tem esta nota" -- ponte que o
-- INEP nao publica e que o produto precisa.
--
-- As duas coincidem no miolo da escala: entre 450 e 700 a diferenca media e de
-- ~0,2 nas quatro areas (em MT, faixa 610: ambas dao 1,15). Isso e validacao
-- do modelo, nao divergencia. Elas se afastam nas caudas, por dois motivos:
--   topo  -- a nota vem do PADRAO de respostas, nao da contagem, e a TCC e
--            concava ali: a media dos acertos de um grupo fica abaixo do
--            acerto previsto para o theta medio do grupo (Jensen);
--   piso  -- prova entregue em branco. Quem deixa em branco nao chuta, entao
--            o observado cai abaixo do piso de acerto casual do 3PL, e o
--            theta_efetivo satura em -3,00 (a saturacao e honesta e o site a
--            declara em tela).

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
    round(t.acertos_esperados::numeric, 1) as acertos_na_curva,

    -- o teto FISICO da escala na edicao (maior nota real em prova regular).
    -- Diferente do topo da curva: o having n >= 100 corta as faixas raras,
    -- entao a curva termina onde acaba a AMOSTRA (~770 em CH), mas a escala
    -- vai alem (856,4 em CH). O site usa este valor para limitar o "ou mais"
    mx.nota_maxima            as nota_maxima_area

from faixas f

left join {{ ref('int_nota_maxima') }} mx
  on mx.area = f.area
 and mx.cod_lingua is not distinct from f.cod_lingua

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

-- Distribuicao empirica completa de acertos por faixa de nota -- contagem
-- pura sobre 2025, sem teoria (PLANO.md, o que sobreviveu do "nivel 2").
--
-- Dois usos na API:
-- 1. Validacao de entrada do nivel 3: total informado fora do envelope da
--    faixa indica area errada, prova errada ou contagem errada -- avisar
--    ANTES de calcular um diagnostico errado.
-- 2. A frase empirica: "entre os N participantes de 2025 com a sua nota,
--    esse total esta no percentil X". Percentil de contagem, nao de modelo.
--
-- O que este mart NAO autoriza (Passo 0): interpretar a CAUSA do desvio.
-- Chute, discriminacao e perfil de conteudo produzem a mesma evidencia;
-- diagnostico de causa so no nivel 3, com o vetor de respostas.

select
    area,
    cod_lingua,
    nota_faixa,
    acertos,
    n,
    sum(n) over w_faixa as n_faixa,

    -- percentil ate este valor, inclusive: P(acertos <= k | faixa)
    round(100.0 * (sum(n) over w_acumulado)
        / (sum(n) over w_faixa), 2) as percentil_ate

from {{ ref('int_distribuicao_acertos') }}

window
    w_faixa as (partition by area, cod_lingua, nota_faixa),
    w_acumulado as (partition by area, cod_lingua, nota_faixa
                    order by acertos
                    rows between unbounded preceding and current row)

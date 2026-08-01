{{ config(enabled=false) }}

-- APARCADO junto com o mart_geografia_diagnostico (ver a nota la).

-- A faixa 'todas' e uma LINHA gerada por grouping sets, nao a soma que o
-- consumidor faz. Entao ela precisa bater com a soma das tres faixas: se
-- divergir, ou o corte por nota mudou de definicao no meio do caminho, ou
-- alguem caiu fora das tres (nota exatamente na fronteira, por exemplo).
--
-- Este teste tambem e a guarda contra o defeito irmao do 'Todas' da rede:
-- consumir sem filtrar faixa conta cada resposta DUAS vezes, e uma checagem
-- relativa nao denunciaria porque os dois lados dobrariam juntos.

with somas as (
    select nivel, codigo, rede, area, competencia,
           sum(n_respostas) filter (where faixa = 'todas')  as agregado,
           sum(n_respostas) filter (where faixa <> 'todas') as soma_das_faixas
    from {{ ref('mart_geografia_diagnostico') }}
    group by 1, 2, 3, 4, 5
)

select *, agregado - soma_das_faixas as diferenca
from somas
where agregado is distinct from soma_das_faixas

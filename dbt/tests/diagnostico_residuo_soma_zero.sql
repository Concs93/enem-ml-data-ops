{{ config(enabled=false) }}

-- APARCADO junto com o mart_geografia_diagnostico (ver a nota la).

-- O `residuo` e o desvio de cada competencia DEPOIS de descontar o
-- deslocamento da unidade inteira naquela area e faixa. Por construcao, a
-- media ponderada pelas respostas tem de dar zero dentro de cada
-- (nivel, codigo, rede, area, faixa) -- e derivavel:
--
--   residuo_area = SOMA n_c (obs_c - esp_c) / SOMA n_c   (media ponderada)
--   SOMA n_c (residuo_bruto_c - residuo_area) = 0        (por definicao)
--
-- Se sobrar residuo, parte do deslocamento geral da rede ainda esta vazando
-- para a lista de conteudo -- que e exatamente o defeito que este mart existe
-- para corrigir no `perfil`.
--
-- Tolerancia 0,05: as colunas sao gravadas com round(...,2) e somar ate 11
-- competencias de valores arredondados acumula centesimos. O defeito que o
-- teste pega (centragem na particao errada, ou faixa misturada com 'todas')
-- desloca a soma em unidades.

select
    nivel, codigo, rede, area, faixa,
    round(sum(residuo * n_respostas) / nullif(sum(n_respostas), 0), 4) as residuo
from {{ ref('mart_geografia_diagnostico') }}
group by 1, 2, 3, 4, 5
having abs(sum(residuo * n_respostas) / nullif(sum(n_respostas), 0)) > 0.05

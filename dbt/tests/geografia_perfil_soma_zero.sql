-- O `perfil` e a diferenca contra o nacional DEPOIS de descontar o patamar
-- da propria unidade na area. Por construcao, a media ponderada pelas
-- respostas tem de dar zero dentro de cada unidade x area: se sobrasse
-- residuo, parte do nivel geral da rede ainda estaria vazando para o mapa --
-- que e exatamente o ranking disfarcado que a coluna existe para remover.
--
-- Tolerancia 0,05: as colunas sao gravadas com round(...,2) e somar ate 11
-- competencias de valores arredondados acumula alguns centesimos. O defeito
-- que o teste pega (patamar errado ou junta trocada) desloca a soma em
-- unidades inteiras, nao em centesimos.

select
    nivel, codigo, area,
    round(sum(perfil * n_respostas) / nullif(sum(n_respostas), 0), 4) as residuo
from {{ ref('mart_geografia_competencia') }}
where status = 'ok'
group by 1, 2, 3
having abs(sum(perfil * n_respostas) / nullif(sum(n_respostas), 0)) > 0.05

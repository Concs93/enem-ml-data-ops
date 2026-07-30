-- Linha ausente e omissao silenciosa -- ja mordeu tres vezes neste projeto
-- (MT 21, LC 8, regiao imediata sem aluno de espanhol). Nenhum teste por
-- linha ve uma linha que nao existe, entao a completude precisa de teste
-- proprio: toda unidade presente numa area tem TODAS as competencias
-- daquela area (LC 9 · MT 7 · CN 8 · CH 6).

with esperado as (
    select area, count(distinct competencia) as n
    from {{ ref('matriz_referencia') }}
    group by 1
),

observado as (
    select nivel, codigo, rede, area, count(*) as n
    from {{ ref('mart_geografia_competencia') }}
    group by 1, 2, 3, 4
)

select o.nivel, o.codigo, o.rede, o.area, o.n as tem, e.n as deveria_ter
from observado o
join esperado e on e.area = o.area
where o.n <> e.n

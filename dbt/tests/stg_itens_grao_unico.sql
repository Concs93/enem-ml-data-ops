select co_prova, posicao, count(*)
from {{ ref('stg_itens') }}
group by 1, 2
having count(*) > 1
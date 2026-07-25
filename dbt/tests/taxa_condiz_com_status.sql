-- Taxa nula se e somente se nao ha o que medir: a edicao nao tem item valido
-- (nao_avaliada) ou a escola nao teve quem respondesse (nao_administrada).
--
-- Uma taxa nula com status 'ok' -- ou uma taxa calculada num status de
-- ausencia -- significa que alguma agregacao acima divergiu do tratamento de
-- itens anulados/abandonados.
select co_escola, area, habilidade, status, n_itens_validos, taxa_acerto
from {{ ref('mart_diagnostico_habilidade') }}
where (status in ('nao_avaliada', 'nao_administrada'))
   != (taxa_acerto is null)

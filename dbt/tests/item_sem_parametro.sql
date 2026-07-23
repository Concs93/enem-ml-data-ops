-- Um item sem parametro de TRI (param_dificuldade nulo) nao entrou na
-- escoragem oficial do INEP - a calibracao nao convergiu - e por isso NAO pode
-- aparecer no diagnostico como avaliavel. O tratamento correto e taxa nula,
-- via a flag item_abandonado (ver MT 97593, motivo "Problema de convergencia").
--
-- Este teste falha se algum item sem parametro escapou desse tratamento e
-- ainda carrega uma taxa calculada - sinal de que um item nao escorado passou
-- pelo filtro, ou de que existe um item sem parametro que nao esta flagado
-- como abandonado nem anulado (merece investigacao).
select area, co_item, param_dificuldade, taxa_acerto_nacional
from {{ ref('int_acerto_item_nacional') }}
where param_dificuldade is null
  and taxa_acerto_nacional is not null

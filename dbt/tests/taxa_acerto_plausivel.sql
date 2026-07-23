-- Piso de 5% (nao 15%): itens muito dificeis chegam legitimamente a 8-15%
-- porque o parametro de acerto casual (c) desses itens fica em 0.06-0.12 - o
-- aluno nao chuta ao acaso, escolhe convictamente o distrator. Abaixo de 5% e
-- implausivel e sugere junção item<->resposta quebrada (foi assim que o bug de
-- LC foi pego: taxa de 22,6% colada no acaso de 20%).
--
-- Itens anulados/abandonados tem taxa_acerto_nacional nula e sao ignorados
-- automaticamente (null < 5 e null, nao entra no resultado).
select area, co_item, taxa_acerto_nacional
from {{ ref('int_acerto_item_nacional') }}
where taxa_acerto_nacional < 5 or taxa_acerto_nacional > 99

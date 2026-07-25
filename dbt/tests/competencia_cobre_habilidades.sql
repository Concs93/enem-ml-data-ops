-- Toda habilidade que aparece nos itens tem competencia na Matriz.
--
-- Uma habilidade orfa sumiria da agregacao por competencia sem qualquer aviso
-- -- o mesmo tipo de omissao silenciosa que ja custou caro duas vezes (MT 21 e
-- LC 8). Como o mart_diagnostico_competencia parte de um join com o seed, o
-- que nao casa simplesmente nao existe no resultado.
--
-- Falha aqui significa uma de duas coisas: o seed foi gerado a partir de um
-- PDF diferente, ou a edicao passou a usar habilidades fora de 1..30.
select distinct n.area, n.habilidade
from {{ ref('int_acerto_item_nacional') }} n
left join {{ ref('matriz_referencia') }} m
  on m.area       = n.area
 and m.habilidade = n.habilidade
where m.habilidade is null

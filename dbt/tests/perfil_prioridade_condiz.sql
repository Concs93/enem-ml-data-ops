-- Prioridade nula se e somente se a habilidade nao e mediavel naquele
-- contexto (n_itens = 0): MT 21 em qualquer lingua, LC 8 para ingles.
-- Prioridade numerica numa habilidade sem item seria um numero fingido;
-- prioridade nula numa habilidade mediavel seria linha quebrada.
select theta, area, cod_lingua, habilidade, n_itens, prioridade
from {{ ref('mart_perfil_habilidade') }}
where (n_itens = 0) != (prioridade is null)

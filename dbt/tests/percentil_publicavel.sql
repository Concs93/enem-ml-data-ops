-- O percentil existe se e somente se a escola e publicavel na area.
-- Percentil sem publicacao vazaria a posicao de uma escola com N insuficiente;
-- publicavel sem percentil seria linha quebrada.
select co_escola, area, n_presentes, n_com_nota, percentil, publicavel
from {{ ref('mart_escola_area') }}
where (publicavel and percentil is null)
   or (not publicavel and percentil is not null)

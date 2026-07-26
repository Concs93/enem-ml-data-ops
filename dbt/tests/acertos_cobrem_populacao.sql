-- A distribuicao de acertos e o mart de escolas descrevem a MESMA populacao:
-- presentes em prova regular, com escola, com nota estimavel (> 0). Chegam la
-- por caminhos diferentes -- um explode os vetores de resposta, o outro conta
-- notas -- e a igualdade EXATA das contagens e o que prova que nenhum filtro
-- vazou de um lado.
with distribuicao as (
    select area, sum(n) as pessoas
    from {{ ref('int_distribuicao_acertos') }}
    group by 1
),
escolas as (
    select area, sum(n_com_nota) as pessoas
    from {{ ref('mart_escola_area') }}
    group by 1
)
select d.area,
       d.pessoas as na_distribuicao,
       e.pessoas as no_mart_escola
from distribuicao d
join escolas e using (area)
where d.pessoas != e.pessoas

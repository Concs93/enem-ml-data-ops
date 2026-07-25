-- Toda escola presente numa area tem TODAS as habilidades daquela area.
--
-- Linha ausente e omissao silenciosa, e omissao ja mordeu duas vezes: a MT
-- hab 21 (sem item valido na edicao) e a LC hab 8 (so itens de espanhol, some
-- em escola sem aluno de espanhol). Nenhum teste por linha pega uma linha que
-- nao existe -- por isso este conta.
with esperado as (

    select area, count(distinct habilidade) as n_habilidades
    from {{ ref('int_acerto_item_nacional') }}
    group by 1

)

select
    d.co_escola,
    d.area,
    count(*)             as n_no_mart,
    min(e.n_habilidades) as n_esperado
from {{ ref('mart_diagnostico_habilidade') }} d
join esperado e
  on e.area = d.area
group by 1, 2
having count(*) != min(e.n_habilidades)

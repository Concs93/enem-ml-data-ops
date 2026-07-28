-- Cada caderno regular precisa estar INTEIRO (45 questoes; 50 em LC, que
-- carrega as duas linguas) e com o numero certo de itens validos por area:
-- CH 45, CN 42, LC 50, MT 43 -- os cinco nao avaliaveis da edicao, nem um a
-- mais nem a menos. Um caderno incompleto no mart corrigiria o cartao do
-- participante em silencio, marcando como erro uma questao que ele acertou.

with por_prova as (

    select
        area,
        co_prova,
        count(*)                              as questoes,
        count(*) filter (where item_valido)   as validas
    from {{ ref('mart_item_prova') }}
    group by 1, 2

)

select area, co_prova, questoes, validas
from por_prova
where questoes != case area when 'LC' then 50 else 45 end
   or validas  != case area when 'CH' then 45 when 'CN' then 42
                            when 'LC' then 50 when 'MT' then 43 end

union all

-- 4 areas x 4 cores: 16 cadernos, sempre
select 'TOTAL', null, count(*), null
from por_prova
having count(*) != 16

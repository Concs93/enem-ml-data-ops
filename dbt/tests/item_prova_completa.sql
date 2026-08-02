{{ config(tags=['precisa_dado']) }}

-- FAIXA 3, nao FAIXA 2 (marcado em 02/08/2026). Este teste afirma PRESENCA
-- -- e por isso ele existe --, entao ele reprova por construcao num banco
-- vazio. A CI e a documentacao rodam sobre a raw vazia para perguntar "o
-- SQL executa?", nao "o dado esta certo?"; a segunda pergunta e do Airflow,
-- com os 2,6 GB. Afrouxar o teste para passar vazio (um `having count > 0`)
-- destruiria justamente o defeito que ele pega: a edicao que contribui
-- ZERO em silencio.

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

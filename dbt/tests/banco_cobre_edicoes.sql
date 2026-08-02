{{ config(tags=['precisa_dado']) }}

-- FAIXA 3, nao FAIXA 2 (marcado em 02/08/2026). Este teste afirma PRESENCA
-- -- e por isso ele existe --, entao ele reprova por construcao num banco
-- vazio. A CI e a documentacao rodam sobre a raw vazia para perguntar "o
-- SQL executa?", nao "o dado esta certo?"; a segunda pergunta e do Airflow,
-- com os 2,6 GB. Afrouxar o teste para passar vazio (um `having count > 0`)
-- destruiria justamente o defeito que ele pega: a edicao que contribui
-- ZERO em silencio.

-- Toda edicao do banco tem de entregar a PROVA REGULAR INTEIRA: 45 itens em
-- CH, CN e MT, 50 em LC (as duas linguas). Nem um a mais, nem um a menos.
--
-- Este teste nasceu de um bug que passou despercebido e ganhou forma final
-- depois de um segundo. Os dois eram silenciosos:
--
-- 1. Em 2021 o IN_ITEM_ADAPTADO vem VAZIO em vez de "0"; o macro booleano()
--    devolve nulo, `not nulo` e nulo, e a edicao inteira saiu do banco -- 370
--    itens, sem erro, sem contagem obviamente errada.
--
-- 2. A desduplicacao por (edicao, co_item) escolhia o menor co_prova, que para
--    centenas de itens era uma versao de contingencia sem rotulo no script do
--    R. O item existia na prova regular e mesmo assim ficava com is_regular
--    nulo, sumindo pelo filtro.
--
-- Contagem frouxa (">= 30 itens") nao pegaria o segundo. Exigir o numero
-- EXATO da prova pega os dois, e pega tambem o dia em que uma classificacao
-- nova aparecer no INEP e cair no lugar errado.
--
-- Item sem classificacao NAO e erro: o ITENS_PROVA traz versoes que nao
-- constam no script do R por nao terem participante na base de resultados
-- (contingencia, PPL). Sao nao-regulares por construcao, e o proprio
-- build_co_prova_banco valida que as 16 regulares de cada edicao estao todas
-- la -- e o conjunto completo que importa, nao a ausencia de sobras.

with por_edicao as (

    select
        edicao,
        area,
        count(*) filter (where is_regular) as itens_regulares
    from {{ ref('stg_itens_banco') }}
    where area is not null
    group by 1, 2

)

select edicao, area, itens_regulares,
       case area when 'LC' then 50 else 45 end as esperado
from por_edicao
where itens_regulares != case area when 'LC' then 50 else 45 end

union all

-- e nenhuma edicao pode faltar por inteiro (a tabela nem chegou a existir)
select edicao, 'EDICAO AUSENTE', 0, 0
from (values (2020), (2021), (2022), (2023), (2024), (2025)) e(edicao)
where edicao not in (select distinct edicao from {{ ref('stg_itens_banco') }})

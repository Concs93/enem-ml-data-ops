-- AS QUESTOES CONCRETAS de cada habilidade, nas seis edicoes (2020-2025).
--
-- Existe para o cartao "o que estudar para a proxima": recomendar um conteudo
-- e util, mas a pessoa precisa de um endereco para praticar. "Q7 - ENEM 2022"
-- e esse endereco -- ela acha a questao em qualquer banco de provas.
--
-- CADERNO AZUL, em todas as edicoes. O stg_itens_banco elege uma versao por
-- item (preferindo regular) e o resultado e Azul nas seis -- verificado. As
-- outras cores sao a mesma prova reordenada, entao a posicao muda com a cor:
-- citar o numero sem citar a cor daria endereco errado em tres de quatro
-- cadernos. O site diz a cor.
--
-- SO PROVAS REGULARES e SO ITENS VALIDOS: a mesma regra do mart_perfil_estudo,
-- que e quem consome isto. Questao anulada nao tem resposta certa e nao serve
-- para praticar; item de reaplicacao nao descreve a prova que a pessoa vai
-- fazer.
--
-- LC entra nas DUAS linguas, como no resto do projeto: o item comum aparece
-- para ingles e para espanhol, o item de lingua so para a sua. Sem isso, quem
-- fez espanhol nao veria as questoes das habilidades 5 a 8.

{{ config(materialized='table') }}

with valido as (

    select
        edicao, area, cod_lingua, habilidade, posicao,
        param_dificuldade as b
    from {{ ref('stg_itens_banco') }}
    where item_valido
      and is_regular
      and not coalesce(item_adaptado, false)
      and habilidade is not null
      and posicao is not null

),

-- lingua_item preserva o que a uniao apagaria: se a questao e da secao de
-- lingua estrangeira (5 por prova) ou uma das 40 comuns. A pessoa precisa
-- disso para saber o que esta abrindo -- "Q3 ENEM 2024" em LC pode ser de
-- ingles, de espanhol ou comum, e sao coisas diferentes
por_lingua as (

    select edicao, area, null::int as cod_lingua, habilidade, posicao, b,
           null::int as lingua_item
    from valido
    where area != 'LC'

    union all

    select v.edicao, v.area, l.cod_lingua, v.habilidade, v.posicao, v.b,
           v.cod_lingua as lingua_item
    from valido v
    join (values (0), (1)) l(cod_lingua)
      on v.cod_lingua is null
      or v.cod_lingua = l.cod_lingua
    where v.area = 'LC'

)

select
    area,
    cod_lingua,
    habilidade,
    edicao,
    posicao,
    lingua_item,
    round(b, 2) as param_dificuldade,
    -- ordena da mais recente para a mais antiga, e dentro do ano pela posicao:
    -- prova recente e mais parecida com a proxima, e e mais facil de achar
    row_number() over (
        partition by area, cod_lingua, habilidade
        order by edicao desc, posicao
    ) as ordem
from por_lingua

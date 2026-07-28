-- O BANCO DE ITENS multiedicao: um item por linha, seis edicoes do ENEM.
--
-- Existe porque a "dificuldade de uma habilidade" medida numa edicao so e, em
-- boa parte, a dificuldade dos itens daquela edicao: 62 das 120 habilidades
-- tem UM item na prova regular de 2025. Medido: a ordem de estudo derivada de
-- metade dos itens de 2025 correlaciona +0,19 com a da outra metade -- ou
-- seja, quase nada. Reunindo 2020-2025 sao ~22 itens por habilidade, e as
-- cinco edicoes anteriores preveem a ordem de 2025 com +0,44.
--
-- Somar edicoes e legitimo porque o INEP equaliza todas no MESMO banco de
-- itens: b medio entre 1,10 e 1,26 e c medio entre 0,175 e 0,181 nas seis
-- (verificado antes de construir isto). Um b = 1,5 de 2021 significa o mesmo
-- que um b = 1,5 de 2025.
--
-- Nao substitui stg_itens: aquele responde "o que caiu na prova de 2025" (e
-- sustenta a correcao do cartao de respostas); este responde "o que costuma
-- cair", que e outra pergunta. Ver mart_perfil_estudo.
--
-- Aqui NAO ha posicao na prova: o grao e o item, nao o item-dentro-do-caderno.
-- Posicao so faz sentido para casar com o vetor de respostas, que existe
-- unicamente para 2025.

{% set edicoes = [2020, 2021, 2022, 2023, 2024, 2025] %}

with fonte as (

{% for ano in edicoes %}
    select
        {{ ano }}                            as edicao,
        {{ inteiro('"CO_ITEM"') }}           as co_item,
        {{ inteiro('"CO_PROVA"') }}          as co_prova,
        "SG_AREA"                            as area,
        {{ inteiro('"TP_LINGUA"') }}         as cod_lingua,
        "TX_GABARITO"                        as gabarito,
        {{ inteiro('"CO_HABILIDADE"') }}     as habilidade,
        {{ num('"NU_PARAM_A"') }}            as param_discriminacao,
        {{ num('"NU_PARAM_B"') }}            as param_dificuldade,
        {{ num('"NU_PARAM_C"') }}            as param_acerto_casual,
        {{ booleano('"IN_ITEM_ABAN"') }}     as item_abandonado,
        {{ booleano('"IN_ITEM_ADAPTADO"') }} as item_adaptado,
        "TX_GABARITO" = 'X'                  as item_anulado
    from {{ source('raw', 'itens_prova_' ~ ano) }}
    {% if not loop.last %}union all{% endif %}
{% endfor %}

),

-- classifica ANTES de desduplicar. co_prova e unico entre edicoes (2020:
-- 567-699 ... 2025: 1447-1573, zero sobreposicao), entao a juncao dispensa a
-- edicao. LEFT join porque prova sem rotulo no seed nao pode derrubar o item:
-- ha versoes no ITENS_PROVA que nao aparecem no script do R por nao terem
-- participante na base de resultados (contingencia, PPL). Sao nao-regulares
-- por construcao -- o seed valida 16 regulares por edicao, o conjunto completo
classificado as (

    select f.*, p.tipo_aplicacao, p.is_regular
    from fonte f
    left join {{ ref('co_prova_banco') }} p
      on p.co_prova = f.co_prova
    where f.co_item is not null

),

-- O mesmo item aparece nas QUATRO CORES da mesma edicao -- as cores sao a
-- mesma prova reordenada. O banco quer o ITEM, nao a aparicao dele.
--
-- A ordem do distinct on NAO e arbitraria: precisa preferir a versao REGULAR.
-- Ordenar por co_prova (o menor codigo) escolhia, para varios itens, uma
-- versao de contingencia sem rotulo no seed -- e o item, que existe na prova
-- regular, ficava com is_regular nulo e sumia do banco pelo filtro. O sintoma
-- eram centenas de itens "sem classificacao" numa edicao inteira
distintos as (

    select distinct on (edicao, co_item)
        edicao, co_item, co_prova, area, cod_lingua, gabarito, habilidade,
        param_discriminacao, param_dificuldade, param_acerto_casual,
        item_abandonado, item_adaptado, item_anulado,
        tipo_aplicacao, is_regular
    from classificado
    order by edicao, co_item,
             (is_regular is not true),        -- regular primeiro
             (tipo_aplicacao is null),        -- depois qualquer classificada
             co_prova

)

select
    *,
    -- mesmo criterio de validade do resto do projeto: entra no calculo o item
    -- que o INEP escorou. Sem parametro nao ha curva; anulado nao tem resposta
    (not item_anulado
     and not item_abandonado
     and param_discriminacao is not null) as item_valido
from distintos

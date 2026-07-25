-- Onde a escola esta: presenca, media da nota oficial e percentil por area.
--
-- A posicao usa a nota oficial (TRI), nao a taxa de acerto: e a escala publica
-- que as escolas ja conhecem, pondera dificuldade e desconta acerto casual.
-- A taxa de acerto fica com o que so ela faz -- abrir o desempenho por
-- habilidade, no mart_diagnostico_habilidade.

{% set areas = ['mt', 'ch', 'cn', 'lc'] %}

with presentes as (

    -- mesmo recorte da Etapa 3: presente, prova regular, escola identificada.
    -- os dois marts precisam descrever a MESMA populacao, ou o relatorio se
    -- contradiz internamente (ver teste marts_mesma_populacao)
    {% for a in areas %}
    select
        r.co_escola,
        '{{ a | upper }}' as area,
        r.nota_{{ a }}    as nota
    from {{ ref('stg_resultados') }} r
    join {{ ref('co_prova_que_nao_existe') }} p
      on p.co_prova = r.co_prova_{{ a }}
     and p.sg_area  = '{{ a | upper }}'
    where r.cod_presenca_{{ a }} = 1
      and p.is_regular
      and r.co_escola is not null
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

),

por_escola as (

    select
        co_escola,
        area,
        count(*)                         as n_presentes,
        -- nota 0 e sentinela para "sem padrao de resposta para estimar":
        -- sao provas entregues inteiramente em branco. A TRI nao tem o que
        -- estimar, e o INEP grava 0 porque a coluna precisa de um numero.
        -- Virar null e o que ela sempre significou -- do contrario a media
        -- da escola desaba (ate 147 pontos) sem nada denunciar.
        count(nullif(nota, 0))           as n_com_nota,
        count(*) filter (where nota = 0) as n_prova_em_branco,
        round(avg(nullif(nota, 0)), 1)   as media_nota
    from presentes
    group by 1, 2

),

-- percentil calculado APENAS entre escolas publicaveis: a posicao de quem tem
-- N suficiente nao deve oscilar com a entrada de escolas instaveis.
-- as duas contagens precisam passar do minimo -- 20 presentes dos quais so 15
-- tem nota nao sustentam um percentil que promete 20
publicaveis as (

    select
        co_escola,
        area,
        round((100 * percent_rank() over (
            partition by area
            order by media_nota
        ))::numeric, 1) as percentil
    from por_escola
    where n_presentes >= {{ var('n_minimo_diagnostico') }}
      and n_com_nota  >= {{ var('n_minimo_diagnostico') }}

)

select
    e.co_escola,
    e.area,
    e.n_presentes,
    e.n_com_nota,
    e.n_prova_em_branco,
    e.media_nota,
    p.percentil,
    p.co_escola is not null as publicavel

from por_escola e
left join publicaveis p using (co_escola, area)

{{ config(enabled=false) }}

-- APARCADO (01/08/2026): ver a nota no int_acerto_nivel -- o produto mudou
-- para a navegacao por grao com comparacoes simples. O desenho abaixo fica
-- como esta para o dia em que a leitura por residuo voltar.

-- A face do gestor, versao que remove o efeito de NIVEL -- e o mart que
-- substitui a leitura do `perfil` onde ela e confundida.
--
-- O PROBLEMA QUE ELE RESOLVE. O `perfil` do mart_geografia_competencia
-- desconta o patamar da unidade como um deslocamento unico na area. Medido,
-- isso tira o nivel da MEDIA mas o devolve competencia a competencia: em MT,
-- o perfil da C6 correlaciona +0,97 com o patamar da unidade e o da C2 -0,94.
-- A causa e a forma da curva do item -- numa questao muito acima de todo
-- mundo, (P-c) vai a zero e a diferenca entre redes comprime; numa mais
-- facil, a mesma diferenca de nivel abre dez vezes mais. Resultado pratico:
-- a rede estadual do MA aparecia com a C1 como segunda maior lacuna quando
-- ela e, na verdade, a maior FORCA dela.
--
-- OS DOIS INDICADORES, ambos por CONTAGEM (nenhum parametro de TRI entra):
--
--   residuo = observado - esperado
--     "quanto esta rede acerta a mais ou a menos do que alunos com a mesma
--      nota, neste conteudo"        <- o que distingue esta rede
--
--   ganho   = SOMA_theta n(theta) x [taxa_nac(theta+0,5) - taxa_nac(theta)]
--     "onde avancar meio nivel mais rende"
--                                   <- quase constante entre redes (medido:
--                                      1 a 3 respostas distintas em 27 UFs),
--                                      logo e contexto, nao diagnostico
--
-- O CRUZAMENTO e o produto: conteudo com residuo negativo E ganho alto e a
-- unica recomendacao que os dois sustentam juntos.
--
-- CENTRAGEM. O residuo bruto carrega um deslocamento da unidade inteira: a
-- rede estadual do MA acerta +1,9 pp acima do previsto em TODA a area de MT
-- (sinal de que mais acertos dela "parecem chute" para a TRI, que desconta).
-- Nacionalmente o residuo e +0,29 pp -- ou seja, o modelo ajusta e o desvio e
-- real, do subgrupo. Como esse deslocamento nao diz o que ensinar, ele e
-- descontado e exposto a parte em `residuo_area`.
--
-- FAIXA. O conselho muda ao longo da escala (em MT, C1 ate a nota 550 e C2 em
-- 700), e uma rede ocupa uma faixa larga -- a privada vai de ~490 a ~750.
-- Uma lista so e a media de gente que precisa de coisas opostas, entao a
-- faixa viaja como coluna. 'todas' e uma LINHA como as outras (grouping sets).

{% set niveis = [
    ('regiao_imediata', 'co_regiao_imediata'),
    ('uf',              'co_uf'),
    ('regiao',          'co_uf / 10'),
    ('pais',            '0'),
] %}

with cobertura as (

    -- a referencia nacional so existe onde ha lastro (>= 400 respostas na
    -- faixa). Derivar os limites, nunca transcrever -- e grampear theta neles
    -- em vez de deixar a junta descartar a linha em silencio
    select area, cod_lingua, competencia,
           min(theta) as th_min, max(theta) as th_max
    from {{ ref('int_nivel_nacional') }}
    group by 1, 2, 3

),

com_referencia as (

    select
        a.co_uf,
        a.co_regiao_imediata,
        a.rede,
        a.area,
        a.competencia,
        -- nota = 500 + 100*theta, entao 450 e -0,50 e 650 e 1,50
        case when a.theta < -0.50 then 'ate_450'
             when a.theta >  1.50 then 'acima_650'
             else 'de_450_a_650' end                as faixa,
        a.n_respostas,
        a.n_acertos,
        n.taxa_nacional,
        -- sem faixa meio passo acima (topo da escala) o ganho e zero: nao ha
        -- observacao que sustente prever alem do que foi observado
        coalesce(p.taxa_nacional, n.taxa_nacional)  as taxa_um_passo

    from {{ ref('int_acerto_nivel') }} a

    join cobertura c
      on c.area = a.area
     and c.cod_lingua is not distinct from a.cod_lingua
     and c.competencia = a.competencia

    join {{ ref('int_nivel_nacional') }} n
      on n.area = a.area
     and n.cod_lingua is not distinct from a.cod_lingua
     and n.competencia = a.competencia
     and n.theta = greatest(c.th_min, least(c.th_max, a.theta))

    left join {{ ref('int_nivel_nacional') }} p
      on p.area = a.area
     and p.cod_lingua is not distinct from a.cod_lingua
     and p.competencia = a.competencia
     and p.theta = greatest(c.th_min, least(c.th_max, a.theta)) + 0.50

),

-- os quatro niveis geograficos empilhados, ainda no grao fino de theta
empilhado as (

    {% for nivel, codigo in niveis %}
    select
        '{{ nivel }}' as nivel,
        {{ codigo }}  as codigo,
        rede, area, competencia, faixa,
        n_respostas, n_acertos, taxa_nacional, taxa_um_passo
    from com_referencia
    {% if nivel == 'regiao_imediata' %}
    where co_regiao_imediata is not null
    {% endif %}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

),

agregado as (

    select
        nivel,
        codigo,
        rede,
        area,
        competencia,
        case when grouping(faixa) = 1 then 'todas' else faixa end as faixa,

        sum(n_respostas)                            as n_respostas,
        sum(n_acertos)                              as n_acertos,
        -- o esperado e a media da taxa nacional PONDERADA pelo histograma da
        -- unidade: n_respostas por theta e exatamente esse peso
        sum(n_respostas * taxa_nacional)
            / nullif(sum(n_respostas), 0)           as esperado,
        -- ganho de um passo, na mesma unidade (pontos percentuais de acerto)
        sum(n_respostas * (taxa_um_passo - taxa_nacional))
            / nullif(sum(n_respostas), 0)           as ganho

    from empilhado
    group by grouping sets (
        (nivel, codigo, rede, area, competencia, faixa),
        (nivel, codigo, rede, area, competencia)
    )

),

com_residuo as (

    select
        a.*,
        100.0 * a.n_acertos / nullif(a.n_respostas, 0)                as observado,
        100.0 * a.n_acertos / nullif(a.n_respostas, 0) - a.esperado   as residuo_bruto,
        -- o deslocamento da unidade inteira naquela area e faixa: e o que
        -- sera descontado, e ele vai para a tela a parte
        sum(a.n_acertos) over w * 100.0 / nullif(sum(a.n_respostas) over w, 0)
          - sum(a.n_respostas * a.esperado) over w
            / nullif(sum(a.n_respostas) over w, 0)                    as residuo_area
    from agregado a
    window w as (partition by a.nivel, a.codigo, a.rede, a.area, a.faixa)

)

select
    r.nivel,
    r.codigo,
    r.rede,
    r.area,
    r.competencia,
    r.faixa,

    r.n_respostas,
    round(r.observado, 2)                       as taxa_acerto,
    round(r.esperado, 2)                        as taxa_esperada,
    round(r.residuo_area, 2)                    as residuo_area,

    -- O NUMERO DA TELA
    round(r.residuo_bruto - r.residuo_area, 2)  as residuo,
    round(r.ganho, 3)                           as ganho,

    -- erro-padrao da taxa observada: a tela para de ordenar quando ele engole
    -- a distancia entre os itens da lista (mesma regra ja em uso na rede
    -- municipal)
    round(100.0 * sqrt(
        (r.observado / 100.0) * (1 - r.observado / 100.0)
        / nullif(r.n_respostas, 0)), 3)         as margem,

    coalesce(ga.publicavel, false)              as publicavel

from com_residuo r

-- a governanca viaja, por rede como no resto da geografia
left join {{ ref('mart_geografia_area') }} ga
  on ga.nivel = r.nivel and ga.codigo = r.codigo
 and ga.area = r.area and ga.rede = r.rede

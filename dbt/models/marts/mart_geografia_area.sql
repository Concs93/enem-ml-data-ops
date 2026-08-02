-- A face do gestor, nivel area: presenca e media em CINCO niveis geograficos
-- numa tabela so -- municipio, regiao imediata (IBGE 2017), UF, regiao, pais.
--
-- Regra dupla de publicacao (PLANO.md): >= 3 escolas E >= 50 participantes.
-- Os dois criterios respondem perguntas diferentes -- estabilidade e
-- privacidade: 45% dos municipios tem UMA escola, e publicar o municipio
-- seria publicar aquela escola com outro rotulo. Quem nao passa NAO some:
-- a linha existe com publicavel = false, e codigo_pai aponta o nivel acima
-- para onde a API sobe (mesmo principio de MT 21 / LC 8: preservar a linha,
-- declarar o motivo).
--
-- Aplicada em TODO nivel, honestamente: ate UF e pais passam pela mesma
-- conta em vez de ganhar isencao. E aplicada tambem POR REDE: a rede
-- municipal tem 205 escolas no pais inteiro, entao ela reprova o gate na
-- maior parte das UFs -- isso e a regra funcionando, nao defeito.
--
-- REDE: 'Todas' e uma linha como as outras (grouping sets no fim), pelo mesmo
-- motivo do int_acerto_item_municipio -- o gate precisa valer igual para o
-- agregado e para cada rede. Quem consome sem filtrar rede conta duas vezes;
-- o teste geografia_cobre_populacao filtra 'Todas' de proposito.
--
-- Caso de borda real: Boa Esperanca do Norte/MT, municipio instalado em
-- 2025, existe no ENEM mas nao no Censo 2024 -- logo nao tem regiao
-- imediata. UF e regiao saem do proprio codigo IBGE (2 primeiros digitos =
-- UF; 1o digito = regiao), o municipio permanece, e apenas o nivel
-- regiao_imediata nao o contem (a divisao de 2024 realmente nao o continha).

-- SO TRES NIVEIS por decisao do dono do produto (02/08/2026, "simple is
-- best"): municipio e regiao imediata sairam do PRODUTO -- o grao fino
-- convida ao uso que o INEP ja viu ("ENEM por Escola", descontinuado) e a
-- analise vive bem por estado e competencia. O co_municipio continua sendo
-- o grao de COMPUTO (int_acerto_item_municipio); o que sumiu e a linha
-- publicada, nao a soma.
{% set niveis = [
    ('uf',     'g.co_uf',     'g.nome_uf',     'g.co_regiao'),
    ('regiao', 'g.co_regiao', 'g.nome_regiao', '0'),
    ('pais',   '0',           "'Brasil'",      'null::int'),
] %}

with base as (

    select
        m.area,
        m.n_presentes,
        m.n_com_nota,
        m.n_prova_em_branco,
        m.media_nota,

        d.dependencia as rede,
        d.co_municipio,
        coalesce(geo.municipio, d.municipio) as municipio,
        geo.co_regiao_imediata,
        geo.nome_regiao_imediata,
        -- fallback pela estrutura do codigo IBGE, para municipio novo
        coalesce(geo.co_uf, d.co_municipio / 100000)              as co_uf,
        geo.nome_uf,
        coalesce(geo.co_regiao,
                 coalesce(geo.co_uf, d.co_municipio / 100000) / 10) as co_regiao,
        geo.nome_regiao

    from {{ ref('mart_escola_area') }} m
    join {{ ref('dim_escola') }} d
      on d.co_escola = m.co_escola
     and d.co_municipio is not null
    left join {{ ref('int_municipio_geografia') }} geo
      on geo.co_municipio = d.co_municipio

)

-- os cinco niveis empilhados AINDA no grao da escola: a agregacao acontece
-- uma vez so, depois, para que o grouping sets da rede nao precise ser
-- repetido cinco vezes (e para nao esbarrar no `0` do nivel pais, que num
-- GROUP BY seria lido como referencia posicional, nao como constante)
, expandido as (

    {% for nivel, codigo, nome, pai in niveis %}
    select
        '{{ nivel }}' as nivel,
        {{ codigo }}  as codigo,
        {{ nome }}    as nome,
        {{ pai }}     as codigo_pai,
        g.area, g.rede,
        g.n_presentes, g.n_com_nota, g.n_prova_em_branco, g.media_nota
    from base g
    {% if nivel == 'regiao_imediata' %}
    where g.co_regiao_imediata is not null
    {% endif %}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

)

select
    nivel,
    codigo,
    max(nome)      as nome,
    max(codigo_pai) as codigo_pai,
    area,

    case when grouping(rede) = 1 then 'Todas'
         else coalesce(rede, 'Sem cadastro') end as rede,

    count(*)                                as n_escolas,
    sum(n_presentes)                        as n_presentes,
    sum(n_com_nota)                         as n_com_nota,
    sum(n_prova_em_branco)                  as n_prova_em_branco,
    -- ponderada por quem TEM nota, nunca por presentes: o sentinela da
    -- prova em branco ja esta fora da media de cada escola (Etapa 5)
    round(sum(n_com_nota * media_nota)
        / nullif(sum(n_com_nota), 0), 1)    as media_nota,

    count(*) >= 3 and sum(n_presentes) >= 50 as publicavel

from expandido
group by grouping sets (
    (nivel, codigo, area, rede),
    (nivel, codigo, area)
)

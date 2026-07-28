-- O caderno de prova como objeto publico -- a base do nivel 3 (PLANO.md).
--
-- Uma linha por questao de cada prova REGULAR: posicao no caderno, gabarito,
-- parametros oficiais da TRI e habilidade. Com isso o site corrige o cartao
-- do participante NO NAVEGADOR -- as respostas dele nunca sobem; e o caderno
-- que desce ate ele. Tudo aqui ja e publico nos artefatos do INEP (gabaritos
-- e microdados); este mart so muda o formato.
--
-- Em LC o caderno tem 50 posicoes (as 10 primeiras alternam ingles e
-- espanhol); o participante responde 45. O recorte por lingua e feito no
-- consumo, filtrando cod_lingua -- a mesma regra do int_respostas_lc.

with regulares as (

    select co_prova, cor
    from {{ ref('co_prova') }}
    where tipo_aplicacao = 'regular'

)

select
    i.area,
    i.co_prova,
    r.cor,
    i.posicao,
    i.cod_lingua,
    i.gabarito,
    i.habilidade,
    i.param_discriminacao,
    i.param_dificuldade,
    i.param_acerto_casual,

    -- entra na correcao: nem anulado, nem abandonado, com parametros.
    -- E o mesmo filtro dos int_acerto_item_* -- quem nao pontuou na
    -- escoragem oficial nao pontua aqui
    (not i.item_anulado
     and not i.item_abandonado
     and i.param_discriminacao is not null)  as item_valido,

    -- POR QUE nao vale ponto. Nao basta dizer "fora da conta": os motivos sao
    -- diferentes e o participante respondeu aquela questao.
    --   anulada       -> gabarito X, sem resposta correta (item vazado)
    --   sem_calibracao-> gabarito valido, mas a TRI nao convergiu e o INEP
    --                    tirou da escoragem. Quem acertou nao ganhou nada
    -- O texto oficial do INEP viaja junto, para nao inventarmos motivo
    i.item_anulado,
    i.motivo_abandono,
    case
        when not i.item_anulado
         and not i.item_abandonado
         and i.param_discriminacao is not null then null
        when i.item_anulado                    then 'anulada'
        else 'sem_calibracao'
    end                                        as motivo_fora

from {{ ref('stg_itens') }} i
join regulares r
  on r.co_prova = i.co_prova

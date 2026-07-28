-- O ganho do banco historico tem que estar na escala de UMA prova, senao os
-- dois cartoes do site (2025 x historico) mostram numeros incomparaveis e o
-- estudante conclui que o historico "vale mais pontos" -- quando a diferenca
-- seria so o tamanho do banco.
--
-- A invariante que garante isso: os itens_por_prova de todas as habilidades
-- de um mesmo (nivel, area, lingua) somam 45 -- as questoes que a pessoa
-- responde. E consequencia direta da normalizacao por proporcao; se alguem
-- trocar por contagem por edicao, a soma vira ~120 e este teste denuncia.
--
-- Cobre tambem o descuido de LC: se a uniao por lingua sumir, aparece um
-- grupo com cod_lingua nulo, que nao corresponde a participante nenhum.
--
-- TOLERANCIA: 0,25 e nao zero. A coluna e gravada com round(...,2) porque o
-- que ela significa e "3,49 questoes", e somar 30 valores arredondados acumula
-- ate 30 x 0,005 = 0,15 de deriva -- LC/espanhol da 44,96, e esta certo. A
-- primeira versao deste teste usava 0,01 e reprovava 322 linhas por isso;
-- afrouxar aqui e corrigir a regua, nao afrouxar a exigencia: o erro que o
-- teste existe para pegar (normalizar por edicao em vez de por proporcao)
-- levaria a soma para ~120, longe de qualquer tolerancia de arredondamento.

select
    theta,
    area,
    cod_lingua,
    round(sum(itens_por_prova), 2) as soma_itens,
    count(*)                       as habilidades
from {{ ref('mart_perfil_estudo') }}
group by 1, 2, 3
having abs(sum(itens_por_prova) - 45) > 0.25
    or count(*) != 30
    or (area = 'LC' and cod_lingua is null)

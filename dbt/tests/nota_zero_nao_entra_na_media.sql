-- A media so pode se apoiar em notas estimaveis.
--
-- Nota 0 e sentinela para prova entregue em branco (ver Volume 5, secao 2):
-- nao ha padrao de resposta e a TRI nao tem o que estimar. Se ela voltar a
-- entrar na media, a distorcao chega a 147 pontos e nada denuncia.
--
-- Duas asercoes: a soma tem que fechar (todo presente ou tem nota estimavel
-- ou entregou em branco), e escola sem nenhuma nota estimavel nao pode ter
-- media.
select co_escola, area, n_presentes, n_com_nota, n_prova_em_branco, media_nota
from {{ ref('mart_escola_area') }}
where n_presentes != n_com_nota + n_prova_em_branco
   or (n_com_nota = 0 and media_nota is not null)

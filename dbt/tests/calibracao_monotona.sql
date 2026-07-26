-- Nota maior tem que corresponder a theta_efetivo maior ou igual, dentro de
-- cada area (e lingua, em LC). A TCC e estritamente crescente (toda
-- discriminacao e positiva), entao uma quebra de monotonia aqui significa
-- inversa quebrada, faixa contaminada por N baixo, ou dado novo que mudou de
-- forma -- nunca um resultado legitimo.
with seq as (
    select area, cod_lingua, nota_faixa, theta_efetivo,
           lag(theta_efetivo) over (
               partition by area, cod_lingua
               order by nota_faixa
           ) as theta_anterior
    from {{ ref('mart_calibracao_nota') }}
)
select area, cod_lingua, nota_faixa, theta_anterior, theta_efetivo
from seq
where theta_efetivo < theta_anterior

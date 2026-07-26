# Plano — produto analítico sobre o pipeline (pós-Etapa 7)

Decidido em 26/07/2026, depois de descartar MLOps. Este arquivo é o contrato
do que vem a seguir; o CLAUDE.md continua sendo o diário do que já foi feito.

## O que este projeto é

**DataOps + produto analítico com motor psicométrico.** Não é MLOps, por
decisão: dado anual, sem loop de feedback, sem decisão automatizada — os três
"nãos" que a disciplina exige. Forçar a sigla diluiria o que o projeto tem de
forte (o rigor com o dado). Se um dia houver apetite por MLOps, é projeto
separado com cadência rápida (ex.: preços ANP, semanal).

## As duas dores

1. **Aluno** — "tirei essas notas; o que estudo para subir?" Ninguém responde
   com dado. Os simulados dizem quanto errou; nenhum diz onde o esforço
   converte em ponto.
2. **Gestor** (escola/rede, qualquer cargo) — "onde alocar esforço?" No nível
   de **cidade**, subindo até país.

A distinção que dá originalidade: "quais habilidades mais **faltam**" (menor
taxa — qualquer painel mostra) ≠ "quais mais **penalizaram a nota**" (maior
informação perdida — ninguém mostra).

## Face do aluno — três níveis de entrada

| nível | ele informa | recebe | amparo |
|---|---|---|---|
| 1 | as 4 notas | fronteira de estudo por habilidade/competência; em qual área a próxima hora rende mais | função de informação (Fisher) — sólido |
| 2 | + total de acertos | "seu total é atípico para essa nota" (percentil exato) | Lord–Wingersky 1984 — sólido, mas **sem afirmar o porquê**; **condicional ao Passo 0** |
| 3 | + vetor de respostas, cor da prova e língua (LC) | diagnóstico item a item; ajuste de pessoa (lz) e erros de Guttman | Drasgow, Levine & Williams 1985 — método publicado |

Regras duras da face do aluno:

- **Nada é persistido.** Entra, calcula, sai. Sem cadastro, sem dado pessoal.
- Nível 1 diz "pessoas com a sua nota", nunca "você" — não temos as respostas
  dele (bases desidentificadas).
- Nível 2 **não** interpreta a causa do desvio (chute, discriminação e perfil
  produzem a mesma evidência). A leitura "conhecimento vs execução" só é
  permitida no nível 3, onde há método publicado.
- Nível 3 exige **cor da prova** e, em LC, **língua** — sem isso o vetor não
  mapeia para item nenhum (armadilha central da Etapa 3).

## Face do gestor

- Hierarquia: escola → município → **microrregião (IBGE)** → UF → região → país.
- Busca por **nome** (Censo Escolar; 99,6% das publicáveis nomeadas).
- **Regra dupla de publicação: ≥ 3 escolas E ≥ 50 participantes.** Os dois
  critérios respondem perguntas distintas (estabilidade × privacidade); 45%
  dos municípios têm UMA escola — publicá-los seria publicar a escola com
  outro rótulo. Medido: a regra cobre 87% dos participantes em 35% dos
  municípios.
- Quem não passa **não some**: sobe para a microrregião com status e motivo
  (mesmo princípio da MT 21 / LC 8: preservar a linha, anular a métrica,
  dizer por quê). Registrado: os excluídos têm nota média 23 pontos MENOR —
  a proteção cala quem mais precisa de atenção, e é por isso que o roll-up é
  obrigatório, não cosmético.
- Os dois rankings lado a lado (falta × custo em nota) e o achado regional
  (H15 universal; Norte afunda em estatística/probabilidade, Sul/Sudeste em
  geometria/argumentação; no Norte o problema é de nível, no Sul de perfil).

## Passos

- **Passo 0 — medição que decide o nível 2.** Dispersão teórica de acertos
  dado θ (Poisson-binomial) × dispersão observada dado a NOTA. A observada
  tende a ser mais estreita (a nota é estimada das mesmas respostas); se for
  estreita demais, o nível 2 morre e o produto pula do 1 ao 3.
- **Passo 1 — fundação.** `stg_censo_escola`; `dim_escola` ganha nome,
  microrregião e infraestrutura.
- **Passo 2 — motor.** `mart_curva_item` (P e informação por item × grade de
  θ, ~25 mil linhas — o modelo é uma TABELA versionada pelo dbt, não um
  binário); `mart_perfil_habilidade`; `mart_distribuicao_acertos`
  (condicional ao Passo 0).
- **Passo 3 — geografia.** `mart_diagnostico_municipio` e níveis acima, com a
  regra dupla e o roll-up.
- **Passo 4 — fechamento.** Testes no padrão dos 39; Volume 8 reposicionado
  (motor psicométrico, não MLOps); README/roadmap ajustados.
- **Volume 9 — API e site.** As duas faces. O lz calcula na API (depende do
  input do usuário), não em mart.

## Fora de escopo, por decisão

| o quê | por quê |
|---|---|
| MLOps | cadência anual, sem feedback, sem decisão automatizada |
| TRI multidimensional (θ por competência) | exigiria mirt; 4–11 itens por competência não sustentam |
| Valor agregado / predição | ML legítimo (sinal medido: alunos/sala r=−0,43; estadual×privada 138 pts), mas não é a dor escolhida |
| Cruzamento indivíduo × socioeconômico | desidentificação deliberada do INEP |
| Acessibilidade, reaplicação, BAM | itens próprios, não comparáveis |

## Fundamentos técnicos já validados

- 3PL com `P = c + (1−c)/(1+exp(−1,7·a·(θ−b)))`; escala `nota = 500 + 100·θ`.
- Integrar P sobre a distribuição de θ reproduz a taxa observada por item:
  r = 0,977 (MT) · 0,964 (LC) · 0,959 (CH) · 0,949 (CN). Viés de CH/CN vem de
  usar θ da população regular inteira — corrigir usando a população do
  diagnóstico.
- Informação de Fisher: `I = 1,7²·a²·[(P−c)/(1−c)]²·(1−P)/P`.
- Distribuição de acertos dado θ: Poisson-binomial via convolução
  (Lord–Wingersky). Média = ΣP; variância = ΣP(1−P).

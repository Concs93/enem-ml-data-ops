# enem-ml-data-ops

Pipeline de DataOps + MLOps sobre os microdados do ENEM 2025 (INEP). Projeto de
portfólio, construído do zero, do CSV bruto ao modelo servido como API.

**Objetivo do produto:** diagnóstico pedagógico por escola. Dado um `CO_ESCOLA`,
produzir um retrato de desempenho dos seus participantes — percentil, quais
habilidades os alunos dominam e quais precisam ser desenvolvidas — no nível do
item, não só da nota final.

---

## Estado atual

| Etapa | Status |
|---|---|
| 1 — Ingestão (camada raw) | concluída |
| 2 — Staging + schema canônico (dbt) | concluída |
| 3 — Desmembrar respostas + acerto por item | concluída e validada |
| 4 — Marts + diagnóstico por escola | concluída e validada |
| 5 — Qualidade de dados (Great Expectations) | concluída e validada |
| 6 — Orquestração (Airflow) | concluída e validada |
| 7 — CI/CD + docs no GitHub Pages | concluída |
| Produto analítico (motor psicométrico + geografia) | em curso — ver `PLANO.md` |

**MLOps foi descartado por decisão** (26/07/2026): dado anual, sem loop de
feedback, sem decisão automatizada. O projeto é DataOps + produto analítico.
O plano vigente — dores, funcionalidades, amparo científico e o que ficou
fora — está no **`PLANO.md`**, na raiz.

### Produto analítico — Passos 0 a 2 concluídos e validados

`dbt test` verde: **61/61** (27 modelos). O motor psicométrico existe como
tabela, não como binário:

| modelo | grão | linhas |
|---|---|---|
| `int_distribuicao_acertos` | área × língua × faixa × acertos | ~14 mil |
| `mart_curva_item` | item × θ (passo 0,05) | ~29 mil |
| `mart_calibracao_nota` | área × língua × faixa de nota | ~250 |
| `mart_distribuicao_acertos` | + percentil acumulado | ~14 mil |
| `mart_perfil_habilidade` | θ × área × língua × habilidade | ~24 mil |

A `dim_escola` ganhou **nome** (Censo 2024), microrregião e infraestrutura.

**A calibração empírica não é detalhe** — e não é correção da escala do
INEP. `nota = 100·θ + 500` é **definição** ("ENEM — Procedimentos de Análise":
EAP na escala de 2009, grupo de referência normal padrão, equalização por itens
comuns). O `theta_efetivo` é **outra quantidade**: o θ cuja TCC reproduz o total
médio de acertos observado na faixa — a ponte "nota → acertos esperados", que o
INEP não publica e o produto precisa.

As duas **coincidem no miolo da escala**: entre 450 e 700 a diferença média é
~0,2 nas quatro áreas (MT faixa 610: ambas dão 1,15) — validação do modelo, não
divergência. Afastam-se nas caudas: no topo (nota 805 → 2,35 medido contra 3,05
da escala) porque a nota vem do *padrão* de respostas e a TCC é côncava ali —
a média dos acertos de um grupo fica abaixo do acerto previsto para o θ médio;
no piso (≤ ~380, saturando em −3,00) porque prova em branco não chuta e o
observado cai abaixo do piso de acerto casual do 3PL. Comportamento esperado e
declarado em tela, não bug.

**A prioridade muda com o nível** (a tese do produto): em MT, θ=0,5 → H4/H10/
H25; θ=2,0 → H28 dominante (informação 7,3). E H28 é a mesma habilidade em
que o Norte mais afunda — lacuna regional e fronteira dos níveis altos
coincidem.

### Produto analítico — Passo 3 (geografia) concluído e validado

`dbt test` verde: **76/76** (31 modelos). `mart_geografia_area` e
`mart_geografia_habilidade`: cinco níveis (município → **região geográfica
imediata**, IBGE 2017 → UF → região → país) numa tabela, com `codigo_pai`
apontando a subida.

- Regra dupla (≥3 escolas E ≥50 participantes) em **todo** nível:
  **1.942 municípios publicáveis** (o número exato do desenho da regra) e as
  **510 regiões imediatas todas publicáveis** — o roll-up nunca dá em beco.
- **Boa Esperança do Norte/MT**: município instalado em 2025, existe no ENEM
  mas não no Censo 2024 — logo sem região imediata. Preservado com UF/região
  derivadas do próprio código IBGE (2 primeiros dígitos = UF, 1º = região).
  O teste `geografia_cobre_populacao` compara município↔país com igualdade
  exata; a região imediata fica documentadamente fora dessa soma.
- `int_acerto_item_municipio` é o agregado reaproveitável: uma varredura das
  5,4 mi de linhas, e os níveis acima somam por cima.

Passo 4 (fechamento) feito: Volume 8 reposicionado com a Seção 4 nova ("A
medição que mudou o motor" — Poisson-binomial, morte do nível 2, calibração
empírica), código real nos blocos (incluindo o join `is_regular` que o
rascunho não tinha), e README com o motor e a geografia.

### Face do aluno — site estático, com o nível 3 dentro

`dbt test` verde: **83/83** (32 modelos). Não há API: o site é estático e o
cálculo roda no navegador. `export/export_site.py` gera `webapp/dados/motor.json`
(0,6 MB) a partir dos marts, com validação de conservação que **falha antes de
gravar**.

O `mart_item_prova` (740 linhas) é o caderno das 16 provas regulares — posição,
gabarito, parâmetros e habilidade. Com ele o **nível 3** existe sem servidor: a
pessoa cola as 45 respostas no formulário e **a correção acontece no aparelho
dela**; o caderno desce, as respostas nunca sobem. Tudo ali já é público nos
artefatos do INEP; o mart só muda o formato.

O que o vetor muda no produto: o "vale até +X pontos" deixa de usar a média de
quem tem aquela nota e passa a **contar as questões que a pessoa errou**; as
questões aparecem numeradas como no caderno real (LC 1–45 · CH 46–90 ·
CN 91–135 · MT 136–180); e o destaque de **pontos baratos** (erro em questão que
≥60% do nível acerta) vira o conselho mais acionável da tela.

O teste `item_prova_completa` trava caderno incompleto: 45 questões (50 em LC,
que carrega as duas línguas) e válidas exatas por área — **CH 45 · CN 42 ·
LC 50 · MT 43**, os cinco não avaliáveis da edição.

**Medido com vetor individual (4.000 participantes de MT):** re-estimar a nota
pelo padrão de respostas dá correlação **0,9907** com a oficial. A fórmula
`500 + 100·θ` **não** reproduz a unidade — erra ~80 pontos no topo, e o desvio
não se move ao trocar o priori: é a régua de equalização do INEP, não a receita
do estimador. Ajustando dois parâmetros (`nota = 487,7 + 135,4·θ`) o erro cai
para **±13 pontos**, com viés ~zero em todas as faixas. Confirmação cruzada:
essa reta dá θ 2,31 para nota 800, contra **2,35** da calibração empírica do
Passo 0 — dois caminhos independentes, mesma resposta.

### A ordem da tela: ganho de um passo, não informação de Fisher

Erro de desenho pego olhando a tela pronta: a lista era **ordenada por
informação** e **rotulada com o teto** (ganho de dominar tudo). São duas
medidas diferentes, e elas divergem forte — em LC 583 a competência em 1º
tinha teto **+5** e a em 6º tinha **+25**; em MT 612 o maior teto (+70) caía
em 6º. Para quem lê, a ordem parecia invertida. Estava mesmo: **ordem e número
em destaque não podem se contradizer.**

Solução: o número em destaque passou a ser o **ganho de um passo** — o mesmo
avanço de θ (0,5) aplicado a todo conteúdo, medindo onde ele devolve mais
acerto e, pela calibração, mais nota. A lista desce por ele, por construção. O
teto continua visível ao lado, rotulado como tal.

Por que isso **não** trai a tese do produto: o ganho de um passo é a derivada
da curva característica restrita àquela competência, e ela também zera nas duas
pontas (conteúdo dominado não tem o que ganhar; conteúdo distante tem curva
plana). Em MT 450, a competência com informação 0,0 — a mais distante — fica em
**último** por essa métrica, e a de informação mais alta fica em primeiro. A
proteção contra "estude o que você mais erra" continua de pé.

Onde a métrica nova é **melhor** que a informação: informação mede *precisão
de medida*, não *ponto disponível*. LC C2 (língua estrangeira, 3–5 itens) tinha
a maior informação da área e quase nada a entregar. O ganho de um passo pesa o
número de questões naturalmente.

Verificado em **60 casos** (4 áreas × 2 línguas × 6 faixas de nota × com e sem
vetor): ordem e números exibidos monotônicos em todos.

Bug irmão, achado no mesmo teste: a curva empírica **acaba** onde os dados
acabam (LC em 745, CH em 775, CN em 795, MT em 965). Quem digitava acima disso
saturava e via **+0 em tudo**. O `notaPorAcertos` agora estende o topo pela
inclinação dos últimos trechos (janela de 4 pontos) e marca o trecho como
extrapolado — o rótulo vira "+X pontos ou mais".

### Tom: oportunidade, nunca comparação — e o topo também recebe resposta

A tela falava por comparação: *"escaparam questões que a maioria do seu nível
acerta"*, *"menos acertos que o comum"*, *"de cada 100 pessoas no seu nível"*.
Tecnicamente correto e pedagogicamente ruim: o mesmo dado, dito assim, vira
veredito sobre a pessoa. Auditoria completa do texto visível — **17 trechos**
reescritos.

A régua adotada, que vale para todo texto novo:

- **Nunca comparar a pessoa com outras pessoas.** O dado da população entra
  como método (na seção "como é calculado"), nunca como julgamento na tela.
- **Nomear a oportunidade, não o déficit.** "questões com ótima oportunidade
  de ganho" no lugar de "questões que escaparam".
- **Nenhum rótulo negativo.** Ganho ~zero tem duas causas opostas, e a tela diz
  qual: *"você já domina — mantenha em dia"* (esperado ≥ 80%) ou *"rende mais
  depois dos primeiros da lista"* (conteúdo ainda distante). Antes era um
  genérico "sem ganho a esta altura", que soava como porta fechada.
- **Quem acerta tudo não fica sem resposta.** Não há lista a dar, e a tela
  passa a dizer o que fazer: *lapidar o que já domina* — manter o conteúdo em
  dia, treinar precisão e tempo para que o desempenho se repita no dia da
  prova. Vale nos três níveis: habilidade, competência e área — e também para
  quem tem nota alta **sem** ter colado respostas (gatilho: ganho total da
  área < 12 pontos).

Vocabulário unificado (a mesma ideia com o mesmo nome em toda a tela): *ao seu
alcance* · *oportunidade de ganho* · *você já domina* · *lapidar*. As classes
CSS acompanharam (`.qtag.barato` → `.qtag.chance`, `.destaque-barato` →
`.destaque-oportunidade`), porque nome interno que contradiz o produto é dívida
de leitura.

### Crivo de UX — 42 achados confirmados, 4 descartados

Três revisores independentes (hierarquia, cor, responsividade), cada achado
passando por um verificador cético contra o arquivo. O que era **medível** eu
tinha calculado antes; o crivo pegou o resto.

**Contraste — duas falhas reais.** No tema escuro o accent é *claro*
(`#2dd4bf`), então `color:#fff` sobre ele dava **1,86** — o botão principal e
os selos eram ilegíveis. A causa é conceitual: **o accent que funciona como
traço não é o que funciona como fundo de texto.** Viraram dois tokens,
`--accent-fill` e `--sobre-accent`, que trocam de valor entre os temas
(5,47 no claro · 9,54 no escuro). O código `H21` a 13px negrito dava 3,74 e
passou a `--accent-deep` (7,58).

**A correção que não pegou.** `.hab .pos` foi corrigida na regra genérica, mas
todos os `.hab` renderizados vivem dentro de `details.compbloco`, cuja regra
vence por especificidade — a cor nova nunca chegou à tela. Só apareceu porque
o revisor conferiu o DOM em vez do CSS. **Corrigir a regra errada tem a mesma
aparência de sucesso que corrigir a certa.**

**Semântica de cor: uma ideia, uma cor.** "Você acertou" saía em quatro cores
na mesma tela, e o mesmo conjunto de questões recebia verde no bloco e âmbar
na etiqueta a 20px de distância. Pior, o gradiente estava **invertido**:
vermelho (a cor mais alarmante) marcava erro em conteúdo *avançado* —
exatamente o que o método manda **não** priorizar. Agora: verde = você domina ·
âmbar = oportunidade ao seu alcance · vermelho = **só** erro de entrada · erro
em conteúdo distante = neutro.

**Hierarquia invertida.** Havia regra para `.hab .meta b` (teal) e **nenhuma**
para `.cmeta b`: o "+25 pontos" da competência ficava cinza a 12,5px enquanto
o "+7 pontos" da habilidade *filha* ficava em destaque. E o número que ordena
a página inteira vivia **dentro** do `<details>` — nos oito blocos fechados o
leitor via a fila numerada e nada que a justificasse. O valor subiu para o
`summary`.

**O único overflow horizontal real** era o `summary`: `flex` sem `flex-wrap` e
`.ctit` com `min-width:auto` travando na maior palavra da Matriz.

**Celular** (metade dos acessos): campos abaixo de 16px disparam zoom
automático no Safari do iOS **e ele não desfaz**; o campo das 45 respostas
mostrava 26 e escondia o resto num scroll sem indicação (virou `textarea`); o
`maxlength` truncava em silêncio quem colava com separadores; e 106px de recuo
antes do texto eram **27% de uma tela de 390px**.

**Sistemas, no lugar de valores avulsos:** 13 tamanhos de fonte (seis deles
entre 11 e 13,5px, com meio-pixel que ninguém distingue) viraram **6 degraus**;
9 raios viraram **4 papéis**. Restou um único `px` literal — os 16px que
impedem o zoom do iOS.

**Acessibilidade:** `:focus-visible` global (existia só nos campos de nota),
`prefers-reduced-motion`, o comparativo virou `<button>` com `aria-pressed`
(era `div`, fora da ordem de Tab — e é a navegação principal), `tabular-nums`
nas colunas de número, e rolagem até o resultado (no celular ele nascia abaixo
da dobra e a tela parecia não responder).

### Auditoria adversarial do racional (27/07/2026) — o veredito e as correções

Quatro lentes (psicometria, estatística, verificação numérica, lógica de
produto) atacaram a corrente de raciocínio inteira; cada ataque passou por um
juiz cético com acesso ao código e ao banco. **Veredito por elo:** as
validações (E8) se sustentam; a espinha dorsal é séria; **três erros de conta
e cinco violações de texto**, todos na camada do site — o mart documentava
honestamente as próprias limitações e a tela as consumia sem herdar as
ressalvas. Não por coincidência, o site era a única camada sem testes.

**Os três erros de conta, todos corrigidos:**

1. **O piso saturado quebrava a conversão em pontos.** As faixas 310–360
   saturam em θ=−3,00 (região de prova em branco — 225 mil participantes), a
   curva nota↔acertos via TCC ficava **plana** ali, e inverter curva plana
   transformava milésimos de acerto em **"+40 pontos" fantasma**, com teto
   extrapolado de "+654" (nota implícita 969). Correção: a curva passou a
   inverter o **acertos_medio observado** (terceiro elemento da calibração no
   motor.json — estritamente crescente, 4,11→7,28 no piso), a base ancora na
   **nota digitada**, segmentos degenerados são colapsados mantendo a maior
   nota, e a extrapolação tem teto de escala (+10 da última faixa). A região
   do piso ganhou ressalva na tela e **sai do ranking "comece aqui"**.
2. **Clamp de θ em 3,00 contra grade que vai a 5,00** zerava os ganhos de MT
   900–950 — a tela dizia "você não deixou pontos na mesa" a quem deixou ~36.
   Correção: `TH_MIN/TH_MAX` derivados da grade do motor.json no boot (regra
   da casa: derivar, nunca transcrever).
3. **A guarda do vetor só pegava gabarito errado em nota alta** (na metade de
   baixo da escala o mínimo observado é ≤9, nível do acaso — o vetor de outra
   edição passava). Correção: guarda de **padrão** (`padraoSuspeito`): vetor
   real tem gradiente fáceis≫difíceis; vetor corrigido contra gabarito errado
   é plano (~20%) nos dois grupos. Detecção parcial declarada (~74% com 5
   itens fáceis; <3% de falso positivo, recuperável).

**As violações de texto, todas corrigidas:** `montaPercentil` inferia causa
individual que o PLANO.md proíbe no nível 2 (sobre uma zona neutra com largura
de UM acerto) — virou fato empírico com a ressalva "±1–2 acertos mudam essa
posição"; "você acertaria ~X%" virou "acerto típico no seu nível" (o SE(θ) com
45 itens é 0,30–0,96 — 11 a 14 itens trocam de classe verbal dentro de ±1 SE);
o banner "Comece por estas" ganhou **guarda binomial** (errar ~Σ(1−P) das
fáceis é o que o próprio 3PL espera — até a média+1 DP é ruído de prova, não
lacuna); o comentário que citava ρ=+0,44 (configuração descartada) passou a
citar +0,27 com proveniência; e a escada de confiança por área declarou o
tamanho do n (ρ sobre 6–9 competências, ICs que se cruzam, 1º lugar no nível
do acaso) — selo dourado removido do cartão de estudo, "tendeu a se repetir"
no lugar de "é a que mais se repete".

**A camada ganhou testes: `ci/testa_webapp.js`** — carrega o **código real**
da página num sandbox de vm com DOM falso (não uma réplica que deriva) e roda
15 casos, cada um um bug que já existiu: curvas estritamente crescentes,
milésimo não vira ponto, MT 905 > 0, teto de extrapolação, piso marcado,
vetor plano recusado, vetor coerente aceito. Requer o motor.json exportado.
`node ci/testa_webapp.js` → **15/15**.

Nota de conduta da correção do piso: o ganho mostrado ali agora usa o
gradiente observado (~15–18 pts/acerto), e o passo de área inteira no meio da
escala vale ~+70–90 pontos — coerente com a reta de equalização (135×0,5≈68).
O teste de regressão guarda contra 0 e contra absurdo, não contra o valor
legítimo.

### Um número por conteúdo, e a ordem virou linguagem (27/07/2026)

Feedback do dono do produto: passo E teto em cada linha era informação demais,
e quem somava as habilidades não encontrava o teto da competência ("em uma
área o teto vai até +47, mas dentro aparecem +6, +5 e não bate"). O redesenho
resolve as duas coisas e de quebra implementa a pendência das **faixas de
prioridade** que a medição de estabilidade recomendava:

- **Um número só**: "dá para ganhar até +X pontos" (o teto). O passo sumiu da
  tela — vive no motor, decidindo os grupos.
- **A ordem virou linguagem, não número**: três grupos — *"Comece por aqui —
  é onde o estudo rende mais rápido no seu nível"* · *"Na sequência"* ·
  *"Mais distante por enquanto — rende depois de avançar nos primeiros"*
  (limiares: ≥55% e ≥22% do maior passo; com respostas, competência fechada
  vira o grupo *"Você já fechou"*). O porquê da ordem está no título do
  grupo; dentro de cada grupo a lista desce pelo número exibido. É o que os
  dados sustentam: grupos, não ranking de 1ª a 7ª.
- **As somas fecham**: o teto da competência é convertido UMA vez e repartido
  entre as habilidades na proporção das questões recuperáveis (resto do
  arredondamento vai para a maior fatia). Antes, cada valor era convertido
  "partindo de hoje" separadamente, e a não-linearidade da curva fazia a soma
  divergir do total — matematicamente honesto, mas inconferível. Somar é
  exatamente a conferência que o leitor faz; agora ela fecha, e o teste
  `confereSomas` no `ci/testa_webapp.js` trava isso (17 casos no total).
- O comparativo de áreas manteve o passo ("seu próximo passo vale ~+X") com o
  selo "comece aqui" — área não ganhou teto porque o teto de área é
  "gabaritar a prova" (+350), número verdadeiro e inútil.

A tese sobrevive visível: em MT 613, a C2 tem o maior prêmio (+69) e **não**
abre a lista — abre o grupo onde o estudo converte agora. Ordenar pelo prêmio
seria "estude o que você mais erra", o conselho que o produto existe para
corrigir; a diferença é que agora essa lógica está num título de grupo que
uma pessoa de 17 anos lê, não em dois números que ela precisa reconciliar.

### Página "Como funciona" (metodo.html) — e o crivo que a corrigiu

A pedido do dono do produto, a trilha completa do mérito virou página própria
(`webapp/metodo.html`, no nav e no fim do expansível): as dez seções percorrem
da calibração às fontes, incluindo "revisar ≠ estudar" e onde o peso fino por
questão entra ou não. **Página de método com erro seria pior que nenhuma**,
então três verificadores conferiram cada afirmação contra o código e os dados
— e acharam **13 problemas, todos corrigidos**. Os que ensinam:

- **Eu tinha a direção da curva errada.** Escrevi "no topo, a escala
  comprime"; medido no motor.json, perto do topo cada acerto vale **mais**
  (16–28 pts), e o trecho lento é o **meio** (7–14). A compressão do topo é em
  *acertos por nota*; em *pontos por acerto* — o que a frase afirmava — é o
  inverso. Corrigido também o "±15 a 25" que eu repetia sem nunca ter medido
  (o registrado é ±13 na conversão nível↔nota, mais o sorteio de questões).
- **"A soma de todos os tetos leva ao topo" era falso em geral.** Verdade por
  coincidência em MT 613; em MT 500 a soma dos tetos dá 640 (nota implícita
  1140). Fechar tudo *de uma vez* leva ao topo; somar cenários separados,
  não — a página agora explica com a analogia dos cupons.
- **O piso de "+1" por habilidade quebrava as somas** em 16% dos casos
  (205/1.287 combinações testadas): fatia que arredondava a zero virava 1 e a
  soma passava do cabeçalho. Consertado no código: o piso agora desconta da
  maior fatia, e o teste de somas apertou para ±1.
- "1,27 milhão por área" só vale em MT/CN; CH e LC têm 1,32–1,33 (corrigido
  aqui, no README e no expansível). "Quem acertou todas" só existe em MT — nas
  outras áreas o topo observado não corresponde a gabarito perfeito. A guarda
  do vetor é **unilateral** (só abaixo do mínimo) e a página agora diz isso.

### O teto da curva não era o teto da escala (achado de usuário)

O dono do produto conferiu no noticiário: a maior nota de CH em 2025 foi
**856,4** — e o site dizia que o topo da área era ~775. Os dois números são
verdadeiros e medem coisas diferentes: o `having n >= 100` da calibração corta
as faixas raras, então **a curva calibrável termina onde acaba a amostra**
(~770 em CH), mas a escala vai além. O site limitava o "ou mais" no fim da
curva — dizendo *menos* do que a escala realmente pagou.

Correção na estrutura, não no texto: `int_nota_extremos` (uma varredura, 5
linhas) leva a maior nota real por área/língua ao `mart_calibracao_nota`
(colunas `nota_minima_area` e `nota_maxima_area`), que viajam no motor.json
(`minNota`/`maxNota`) e viram o
teto físico das extrapolações. Os máximos reais de 2025, prova regular:
**MT 980,3 · CN 858,7 · CH 856,4 · LC 794,5**. O mesmo modelo leva o **piso**
real (MT 315,0 · CN 324,2 · CH 325,6 · LC 316,5 inglês / 314,2 espanhol), e a
faixa aceita no formulário sai dos dois — antes o site aceitava nota que não
existe, porque usava a primeira faixa da calibração (mais baixa que o piso: em
CH, 320 contra 325,6). A página do método agora cita
esses números e explica a diferença entre curva calibrável e escala.

No mesmo episódio, o usuário somou **tudo** que dizia "até +X" na tela (~803):
competências + habilidades, nos dois cartões — quádrupla contagem (habilidades
já somam as competências; os dois cartões são dois cenários sobre as mesmas 45
questões). Os dois cartões agora dizem: *"valores de conteúdos diferentes não
se somam — cada um parte da sua nota de hoje"*. E o vetor usado no teste não
era de CH/2025 (6–12 acertos em todas as cores, contra 22–32 esperados para a
nota) — a guarda de coerência o recusou corretamente; o caso confirmou que ela
funciona, e que o aviso precisa ser notado: ele aparece sob o campo da área.

### A partição completa: o mapa virou o caminho até o topo (27/07/2026)

Segundo achado do mesmo usuário testando somas: convertendo cada competência
como cenário separado, a soma das competências **estourava a nota máxima**
(cupons de desconto). E ele formulou o alvo do produto melhor que nós: *"o
ideal é o que o aluno teria que estudar para atingir a nota máxima, e qual a
ordem"*.

O desenho final: **"fechar tudo" é convertido UMA única vez** (com o teto
físico da escala) e o total é **repartido** — competência recebe sua fatia na
proporção das questões recuperáveis; habilidade, a fatia dentro da
competência. Tudo telescopa: habilidades somam a competência, competências
somam o total, e a linha nova *"Fechando tudo: até +X — da sua nota N para
~M"* dá o número conferível no topo do cartão. Nos dois cartões (2025 e
histórico).

Exemplo real (CH 565): total +272 → chegada ~837, abaixo do máximo real
856,4; as seis competências (74+42+40+36+33+47) somam exatamente 272. A ordem
continua dos grupos (rendimento do passo); o valor é a fatia do caminho.

O significado do número por competência mudou de "se eu fechasse só isto,
partindo de hoje" para **"a parte desta competência no caminho até o topo"**
— mais simples, somável, e é a pergunta que o usuário fazia. Três testes novos
travam a partição nos dois cartões (`ci/testa_webapp.js`, 22 casos).

### Cada cartão tem a sua moeda (27/07/2026)

Terceiro achado do mesmo usuário, e o mais conceitual: *"pra próxima, essa
pontuação está almejando o quê?"* — e a resposta honesta era **nada
defensável**. Pontos no cartão do histórico miravam uma prova que não existe,
com a curva de conversão de 2025 e uma transferência de ordem medida como
fraca (ρ +0,27; CH −0,01). Precisão fabricada.

Decisão: **cada cartão fala na moeda que a sua fonte mede bem.**

| cartão | moeda | por quê | soma |
|---|---|---|---|
| Diagnóstico (2025) | **pontos** | a prova existe, a escala é a dela | até o topo real |
| Próxima (2020–2025) | **questões** | peso típico do conteúdo é o que 6 edições medem | as 45 da prova |

O cartão da próxima agora mostra "~7,0 questões" por competência (fatias que
somam 45,0), com grupos por rendimento e o selo "✓ também em 2025" — e o
subtítulo diz onde os pontos moram e por quê. Os testes trocaram junto: o
cartão de estudo **não pode** conter "pontos" nem "Fechando tudo" (22 casos).

**Link externo: só para a fonte do conteúdo.** A tela mostra os códigos `C3` e
`H8`, e agora aponta para a
[Matriz de Referência do INEP](https://download.inep.gov.br/download/enem/matriz_referencia.pdf)
— sem ano na URL, então o link acompanha a edição vigente sozinho. Isso não
contradiz a decisão de tirar todo vínculo com GitHub/código aberto: aquilo
expunha *como o site é feito*; isto dá ao estudante a **fonte oficial do que
ele está lendo**. Único link externo da página (auditado).

Termo corrigido: **probabilidade**, não "chance". Em estatística *chance*
traduz *odds* (p/(1−p)); o que a tela mostra é P. Custa uma palavra mais longa
e ganha precisão — e "probabilidade" não é jargão para quem está no ensino
médio.

### Auditoria por lentes de leitor — 29 confirmados, 25 descartados

Três leitores independentes leram o texto visível: um estudante de nota baixa
(gatilho), um de nota alta (o site fala com ele?) e um professor de português
(concordância e consistência). Cada achado passou por um verificador cético.
O que só a leitura pela lente do topo pegou:

- **Quem gabarita via `+0 pontos` nas quatro áreas** com "— comece aqui"
  colado num zero, e o selo de ouro indo para LC por acidente (o `sort` é
  estável e todos empatam em 0). Agora existe **modo manutenção**: sem selo,
  sem barra, sem numeração, com o texto de lapidação no lugar da fila.
- **A lista contradizia o próprio cabeçalho**: depois de "não há o que
  corrigir aqui" vinham 30 habilidades numeradas por prioridade. Ordenar
  conteúdos empatados em zero inventa urgência — virou inventário.
- **`montaPercentil` dizia o oposto do insight** logo acima. Suprimido no modo
  manutenção.
- **Total de acertos acima do máximo observado era acusado como erro.**
  É o contrário: desempenho no extremo. Só o caso *abaixo do mínimo* continua
  como suspeita de erro.
- Seis plurais quebrados que só aparecem com n=1: `+1 pontos`, `✓ 1 acertos`,
  `as 1 que ainda podem`, `das 7` (sem substantivo).
- **`nome.split(" ")[0]`** fazia CH e CN aparecerem as duas como "Ciências"
  nas linhas do gabarito — duas linhas idênticas, convite a colar as respostas
  na área errada. Virou um mapa `CURTO` de nome único por área.
- "cole suas respostas" — em boca de estudante, **colar é trapacear**.
  Padronizado em "preencher".

### Fallback de edição: a nota atravessa anos, o acerto não

Alguém pode trazer nota e acertos de **outra edição** do ENEM. O que vale para
cada entrada:

| entrada | atravessa edições? | por quê |
|---|---|---|
| nota | **sim** | a TRI equaliza todas as edições na mesma escala |
| total de acertos | **não** | cada ano tem prova própria; E(θ) muda com os itens |
| vetor de respostas | **não** | o gabarito é de 2025 |

Consequência de produto: **a nota sozinha já monta o mapa** — é o fallback, e
ele já funcionava por construção (sem acertos, a tela usa só a nota). O que
faltava era *dizer isso*. Agora a mensagem de fora de faixa oferece as duas
leituras: confira a área/contagem, **ou** é de outra edição e seguimos com a
nota.

Guarda nova no vetor: se o total derivado cair **abaixo do mínimo já observado**
para aquela nota, o cartão é recusado com explicação. Um vetor de outra edição
(ou da cor errada) é corrigido contra o gabarito errado e cai no nível do
acaso — corrigir mesmo assim daria um mapa confiante e completamente falso.
A guarda pega bem no topo e pouco na base (onde a faixa observada é larga), e
isso está documentado aqui de propósito: é detecção parcial, não garantia.

Ressalva que fica: as prioridades refletem o **mix de itens da prova de 2025**.
A Matriz é a mesma entre edições, então o conselho por competência transfere
razoavelmente; a ordem exata, não. **Quanto?** Medido abaixo.

### A ordem das competências é menos firme do que a tela sugere — medido

Pergunta levantada revisando o produto: a dificuldade de cada habilidade é
propriedade do *conteúdo* ou dos *itens daquele ano*? Dá para testar **dentro
de 2025**, partindo os itens ao meio e vendo se as duas metades concordam.
Três medidas, nos 180 itens válidos distintos das provas regulares:

**1. Split-half da ordem (correlação de postos entre as duas metades):**

| área | ρ por θ (0,0 · 0,5 · 1,0 · 1,5 · 2,0) | mesmo 1º lugar |
|---|---|---|
| CH | −0,71 · +0,14 · −0,03 · +0,37 · +0,14 | 0 de 5 |
| CN | +0,07 · −0,31 · +0,24 · +0,67 · +0,55 | 1 de 5 |
| LC | +0,14 · +0,48 · +0,19 · +0,81 · +0,76 | 1 de 5 |
| MT | +0,18 · −0,25 · +0,04 · +0,18 · +0,04 | 2 de 5 |

Metade dos itens discorda da outra metade sobre o que estudar primeiro.

**2. Os itens de uma mesma habilidade nem sempre concordam entre si.**
Amplitude do parâmetro *b* **dentro** da habilidade: mediana 0,38 (LC) a 1,03
(CN) — mas o **máximo** chega a 2,70 em CH (que é a amplitude inteira da área)
e 2,99 em MT. Duas questões da mesma habilidade podem estar em extremos opostos
de dificuldade: a habilidade não é uma unidade coerente de dificuldade.

**3. Bootstrap — quanta confiança há no "1ª parada"?** (400 reamostragens dos
itens dentro de cada competência)

| caso | vencedora | acaso |
|---|---|---|
| MT θ=0,5 | C1 **52%** · C6 22% · C3 21% | 14% |
| MT θ=1,5 | C7 **58%** · C3 17% · C4 10% | 14% |
| CH θ=0,5 | C6 **46%** · C4 32% · C5 10% | 17% |
| CH θ=1,5 | C5 **86%** · C3 12% | 17% |

**A leitura correta das três medidas juntas:** há sinal real — 46 a 86% contra
14 a 17% de acaso é muito acima de ruído. Mas o sinal sustenta um **grupo de
melhores apostas**, não um ranking de sete posições. O split-half é o teste mais
duro (corta a evidência pela metade, sem correção de Spearman-Brown) e por isso
parece pior; o bootstrap é o mais justo para a pergunta "confio nesta ordem com
estes itens?".

No nível da **área**, a confiança varia com θ: MT em θ=2,0 vence 96% das
reamostragens (firme), mas em θ=0,0 é cara ou coroa entre LC (52%) e CH (48%).

**E isto tudo é dentro de 2025.** Entre edições os itens mudam por completo, e
62 das 120 habilidades são medidas por **um item só** — logo a instabilidade
entre anos é no mínimo desta ordem, provavelmente maior.

O que **sobrevive** a troca de edição: a nota → θ (a TRI equaliza), a Matriz, e
o princípio de que o ganho mora na fronteira do nível. O que **não** sobrevive:
qual competência específica está na fronteira, e quanto ela vale em pontos.

**Mas quanto custa errar a ordem?** É a pergunta que importa, e a resposta é
tranquilizadora: escolhendo a 1ª competência com metade dos itens e medindo o
ganho real pelo conjunto completo, a perda é de **30%** da vantagem disponível —
e em **11 de 20 casos** a escolha foi exatamente a melhor. Nunca pior que
sorteio. A correlação horrível acima media a coisa errada: ela tenta resolver a
ordem completa de 6 a 8 competências, e as do meio estão genuinamente
empatadas (1ª rende de 45% a 100% mais que a mediana; da 2ª à 5ª a diferença é
de poucos pontos).

Consequência para a tela (pendente de decisão): apresentar **faixas de
prioridade** em vez de 1º a 7º, e escopar a afirmação à edição ("no ENEM 2025").
O `n_itens` já viaja em todos os marts — o lastro está exposto; falta a
apresentação parar de prometer uma precisão que a medida não tem.

### Banco de itens multiedição — 6 edições por 184 KB de download

`ingestion/baixa_itens.py` baixa **apenas o `ITENS_PROVA`** de cada edição, sem
puxar o ZIP inteiro. O truque: o servidor do INEP responde `Accept-Ranges:
bytes`, então o script lê o diretório central no fim do ZIP, localiza a entrada
e pede por *range* só os bytes dela.

| edição | ZIP remoto | baixado | economia |
|---|---|---|---|
| 2020 | 592 MB | 32 KB | 19.074× |
| 2021 | 475 MB | 29 KB | 16.547× |
| 2022 | 592 MB | 35 KB | 17.468× |
| 2023 | 524 MB | 55 KB | 9.734× |
| 2024 | 502 MB | 33 KB | 15.371× |

**184 KB no lugar de 2,6 GB.** Os parâmetros de TRI só são publicados a partir
de 2020 — o script confere o cabeçalho e recusa a edição que não os tiver, em
vez de gravar um arquivo inútil.

Compatibilidade verificada, e ela sustenta o pooling:

- **Mesmas 14 colunas** em todas as edições (2020 traz `TP_VERSAO_DIGITAL` a
  mais, do ENEM digital daquele ano). Nenhuma coluna falta.
- **Parâmetros na mesma escala**: *b* médio entre 1,10 e 1,26 · p10 entre −0,00
  e 0,21 · p90 entre 2,16 e 2,41 · *c* médio entre 0,175 e 0,181 nas seis
  edições. É o que a equalização sobre banco de itens comum deve produzir —
  confirmação empírica de que somar edições é legítimo.

**O teste decisivo — as 5 edições anteriores preveem a ordem de 2025?**
Ranqueando as competências com 2020–2024 e conferindo contra 2025:

| | correlação média | 1º lugar previsto |
|---|---|---|
| passado (5 edições) → 2025 | **+0,44** | 9 de 20 |
| metade de 2025 → outra metade | +0,19 | — |

O passado prevê 2025 **melhor do que metade de 2025 prevê a outra metade**.
Há sinal cross-edição real. E ele **varia muito por área**: LC acerta o 1º
lugar em **5 de 5** níveis (ρ 0,45–0,83); CH e MT quase não transferem. Isso
autoriza dizer a confiança **por área** em vez de fingir precisão uniforme.

Lastro por habilidade no banco reunido: de ~4,5 itens (2025, todos os tipos de
prova) para **~22**. Nenhuma habilidade com um item só.

### Dois cartões, duas perguntas — `mart_perfil_estudo`

Ingerido e construído. `dbt test` verde: **88/88** (34 modelos). A decisão de
desenho: **não é uma fonte ou outra, são as duas**, porque respondem a
perguntas diferentes e o site mostra as duas em cartões separados.

| cartão | fonte | pergunta |
|---|---|---|
| Diagnóstico da sua prova de 2025 | `mart_perfil_habilidade` (itens de 2025) | o que aconteceu na prova que eu fiz |
| O que estudar para a próxima | `mart_perfil_estudo` (banco 2020–2025) | o que costuma render no meu nível |

Não são versões da mesma resposta: as três primeiras competências coincidem
em média **1,5 de 3**. Se coincidissem 3/3 o segundo cartão seria redundante.

`EDICOES_ITENS` no `ingestion/config.py` é a fonte única da lista de edições —
a ingestão, a CI (`cria_raw_vazia`) e as sources derivam dela, então
acrescentar 2026 é uma linha. O `load_raw.py` já era parametrizado por ano e
não precisou mudar.

**A normalização é onde um pooling ingênuo erraria feio.** O banco tem seis
edições e, dentro de cada uma, **12 a 18 versões de prova** (regular,
reaplicação, acessibilidade, BAM) — ~20× mais itens que numa prova. Somar cru
transformaria a lista num ranking de "quantas vezes o conteúdo apareceu". O
mart usa **rendimento por questão × proporção de itens da área × 45**, e o
teste `estudo_escala_de_uma_prova` trava a invariante: os `itens_por_prova` de
um nível somam 45. Assim os dois cartões ficam na mesma unidade e são
comparáveis lado a lado.

Duas armadilhas que morderam ao construir:

- **LC precisa da união por língua também aqui.** Sem ela aparece um terceiro
  grupo com `cod_lingua` nulo, que não corresponde a participante nenhum, e as
  habilidades 5–8 somem para quem fez a outra língua. Mesma regra do
  `mart_perfil_habilidade`.
- **Tolerância do teste ≠ afrouxar a exigência.** A primeira versão do
  `estudo_escala_de_uma_prova` usava 0,01 e reprovou 322 linhas: a coluna é
  gravada com `round(...,2)`, e somar 30 valores arredondados acumula até 0,15
  (LC/espanhol dá 44,96, e está certo). A tolerância virou 0,25 — o erro que o
  teste existe para pegar levaria a soma para ~120.

### Banco só com provas regulares — e o preço medido da pureza

Decisão do dono do produto: o banco de estudo usa **só provas regulares**,
igual ao mart de 2025. A recomendação descreve a prova que a pessoa vai fazer.

Para isso o `co_prova_banco.csv` (400 linhas, versionado) classifica as versões
das seis edições pela mesma regra do `co_prova` de 2025. O
`build_co_prova_banco.py` baixa de cada ZIP **apenas o script `INPUT_R`**
(~3 KB de um pacote de 500 MB), pelo mesmo truque de range — e valida
**16 provas regulares por edição, 4 por área**, falhando alto se não der.

**Três armadilhas, todas silenciosas, todas encontradas pela validação:**

- **ENEM Digital (2020 e 2021).** Rótulo `"Azul (Digital)"` — sem `" - "`,
  sem `"Reaplica"` — caía em `regular` no `classifica_prova`. A edição
  aparecia com 8 provas regulares por área.
- **"Segunda oportunidade" (2021).** Data extra da pandemia, mesmo defeito.
- **A causa raiz das duas:** o classificador terminava em `return "regular"`,
  ou seja, **qualificador desconhecido virava prova regular em silêncio**.
  Agora qualquer parêntese não reconhecido cai em `outra_aplicacao` — o
  default errа para o lado seguro e o nome novo aparece no resumo.

**E uma quarta, no SQL:** o `distinct on (edicao, co_item)` escolhia o menor
`co_prova`, que para centenas de itens era uma versão de contingência sem
rótulo no script do R. O item **existia na prova regular** e mesmo assim ficava
com `is_regular` nulo, sumindo pelo filtro. A ordenação agora prefere a versão
regular. Sintoma antes da correção: 211 itens "sem classificação" em 2020.

O teste `banco_cobre_edicoes` passou a exigir o número **exato** da prova —
45 itens em CH/CN/MT, 50 em LC — em vez de um piso frouxo. A contagem frouxa
não teria pego a quarta armadilha.

**O preço, medido e não suposto:**

| | lastro por habilidade | ρ (2020-24 → 2025) | 1º lugar previsto |
|---|---|---|---|
| todas as aplicações | ~22 itens | +0,44 | 9 de 20 |
| **só regulares** | ~9 itens (mín. 5) | **+0,27** | 2 de 20 |

Filtrar custou poder preditivo — menos itens, estimativa mais ruidosa. Ainda é
melhor que uma edição sozinha (+0,19), e só um pouco. Por área:
**LC +0,50 · CN +0,42 · MT +0,16 · CH −0,01** — em Humanas não há
transferência mensurável entre edições, e a tela passou a dizer isso com todas
as letras em vez de rotular a área como "confiança baixa".

`dbt test` verde: **89/89**.

### Tipo de prova: como os dois marts divergiam (histórico)

Pergunta que expôs isso: *"aqui estamos usando só as versões regulares?"* — a
resposta era **não, e por descuido**. Agora é decisão medida:

| mart | tipos de prova | por quê |
|---|---|---|
| `mart_curva_item` → diagnóstico 2025 | **só regular** (`is_regular`) | tem de bater com a prova que a pessoa fez |
| `mart_perfil_estudo` → banco | **todas** | a pergunta é "qual a dificuldade típica"; mais item, melhor medida |

Medido em 2025 (única edição com os tipos classificados — o `TX_COR` do
arquivo de itens traz **só a cor**; o qualificador de reaplicação vem do
dicionário, que não baixamos para as outras edições):

| tipo | itens | b médio | a médio |
|---|---|---|---|
| regular | 180 | 1,17 | 2,27 |
| reaplicação | 184 | 1,13 | 2,18 |
| acessibilidade | 186 | 1,16 | 2,26 |

Viés por habilidade entre −0,12 e +0,12. As outras aplicações são **outra
amostra do mesmo desenho**, não uma prova mais fácil — incluir triplica o
lastro sem enviesar. Item individualmente **adaptado** continua fora.

### O NULO que apagou uma edição inteira, em silêncio

Na mesma investigação: **2021 estava contribuindo zero itens**. O
`IN_ITEM_ADAPTADO` daquela edição vem **vazio** em vez de `"0"`; o macro
`booleano()` devolve nulo; e `not nulo` é nulo — que não é verdadeiro. O
filtro descartou os 370 itens da edição sem erro nenhum, e as outras cinco
davam totais plausíveis o bastante para não chamar atenção.

É a família de defeito que o projeto já conhece — *linha ausente é omissão
silenciosa* — num disfarce novo: aqui não é a linha que falta na origem, é o
**nulo num filtro booleano** que a descarta. Contagem por si não denuncia; só
denuncia quem exige **presença de cada parte**.

Solução: `not coalesce(item_adaptado, false)` e o teste
`banco_cobre_edicoes`, que reprova se qualquer edição contribuir menos de 30
itens úteis em qualquer área. `dbt test` verde: **89/89**.

Resultado no lastro depois da correção: **mínimo de 13 itens por habilidade**
(média ~20), contra 0 a 2 na prova regular de 2025.

O cartão de estudo mostra a **confiança por área** medida acima — LC "esta
ordem se repetiu em todos os níveis testados", CH e MT "trate as primeiras
como um grupo de boas apostas, não como fila exata" — e marca com
**"✓ também em 2025"** a competência que aparece no topo das duas leituras.
A discordância medida virou confiança visível, em vez de ressalva genérica.

### A prova não mede todo mundo com a mesma precisão (28/07/2026)

Pergunta que ninguém tinha feito: **o conselho sobrevive à incerteza da própria
nota?** O erro-padrão de θ varia **9×** ao longo da escala — ±16 pontos na nota
700, ±82 na nota 400. A causa é estrutural e não tem conserto no código: quase
toda questão está *acima* do nível de quem tira nota baixa, e questão muito
acima quase não informa (o acerto vira chute). A prova separa mal quem está em
401 de quem está em 499.

O site calculava tudo num ponto e falava com a **mesma confiança** em toda a
escala. Medido antes da correção: **11,7%** das competências abaixo de 500
pulavam de *"comece por aqui"* para *"mais distante"* dentro de um erro-padrão,
contra **0,3%** entre 505 e 700. E ali estão **2,0 milhões de participantes
(42,8%)** — o maior grupo isolado de usuários.

**A correção é integrar, não remendar:** o ganho passou a ser a média ponderada
sobre a faixa plausível da nota (7 nós, pesos com média 0 e variância 1), em vez
do valor num ponto. Não muda a tela — mesmos grupos, mesmo formato — e muda os
números só onde a medida é ruim: **até 24%** em CH 400, **0–5%** no miolo.

Duas alternativas foram medidas e **reprovadas**, e o motivo de cada uma ensina:

| regra | contradições ≤500 | por quê falhou |
|---|---|---|
| fundir em 2 grupos | 38,3% | o grupo do meio **amortece**; sem ele todo deslocamento brando vira contradição |
| reatribuir por estabilidade | 26,1% | a reatribuição depende de θ, que é justamente o que está incerto — amplifica |
| **integrar sobre a incerteza** | **~0%** | — |

Verificação contra alisamento excessivo (o risco oposto): a tese sobrevive —
**12 de 20** trocas de 1º lugar entre notas vizinhas, e MT em θ≈2,0 continua
dando **H28 dominante**, o caso registrado acima.

**O bug que rodou, passou nos testes e não fazia nada.** A grade do perfil é
discreta (passo 0,05, derivado no boot). `θ + z·SE` não cai nela, `grade()`
devolvia `undefined`, os nós eram descartados **em silêncio** e sobrava o
central — a média virava o valor pontual. Os 22 testes ficaram verdes porque
nada havia mudado. É a família *"linha ausente é omissão silenciosa"* num
disfarce novo: aqui o descartado é o **nó de quadratura**.

**E o teste que travava isso era falso.** A primeira versão exigia só que o
resultado *diferisse* do cálculo pontual. Não bastava: sem o encaixe,
`toFixed(2)` arredonda para 0,01 contra grade de 0,05, então ~1 em 5 nós
sobrevive por coincidência — o número muda, com pesos errados. Reintroduzindo o
bug, a suíte inteira ficava verde. O teste que funciona **refaz a quadratura por
fora e exige igualdade**. Lição: *teste que aceita "mudou" não trava
"mudou certo"*.

**O ±X pontos estava errado por até 2×.** A ressalva convertia o erro-padrão em
pontos com `100·SE` — a constante da escala **oficial** aplicada à curva
**empírica** do site, cuja inclinação vai de **57 a 200** pontos por unidade de
θ conforme a faixa. Mesmo erro de categoria entre θ e `theta_efetivo` que o
projeto já documenta. Em CN 400 o número caiu de 49 para **34**. Agora sai da
própria tabela de calibração, por interpolação.

Dois bugs **anteriores** a esta mudança, achados de passagem e corrigidos: o
troféu *"você já está no alto desta área"* aparecia em nota de **piso**
(310–360), dizendo o oposto da realidade; e no topo real da grade (MT ≥ 955,
onde o par de níveis é medido para trás) o `tetoHab` media a folga **meio passo
abaixo** da pessoa, inflando o teto ~4× — o cartão de quem acerta as 43 questões
válidas oferecia +14 pontos a fechar (agora +7, dentro do cartão de topo).

`node ci/testa_webapp.js` → **38/38**.

### A quarta lente: teoria

As três lentes existentes conferem **números e código** — `dbt test` ("meu SQL
fez o que eu quis?"), Great Expectations ("o dado que chegou é o esperado?") e
`ci/testa_webapp.js` ("a conta do navegador está certa?"). Nenhuma confere
**teoria**, e foi por aí que passaram dois erros conceituais que sobreviveram a
três rodadas de verificação.

`.claude/skills/psicometria/` é a quarta lente: procedimento (página de
referência, conta reproduzível, ou ressalva explícita — não há quarta opção),
os invariantes deriváveis com página, uma lista de **9 frases que soam certas e
estão erradas**, e `scripts/verifica.py`, que calcula sobre os itens reais.

Obtidas legitimamente (em `referencias/`, fora do Git; só o `INDICE.md` é
versionado): **Andrade, Tavares & Valle (2000)** — a que o próprio INEP cita, com
o cap. 7.3 sobre equalização no BILOG-MG — e **Baker (2001)**, de distribuição
gratuita autorizada pelo ERIC, mais o material de aula do Dalton (UFSC) sobre
escala de habilidade.

A lente já pagou o custo dela. A afirmação *"acertar uma questão difícil sobe
mais do que acertar uma fácil"* virou derivação, não só medição: pela eq. 5-1 do
Baker (p. 85), sob 3PL o peso de cada resposta é
`1,7·a·(P−c)/(P(1−c))`. Sem acerto casual (`c=0`) trocar erro por acerto move o
**mesmo tanto em qualquer questão** — medido, +0,1389 em todas. Com o `c` do
ENEM, a fácil move **3,5×** mais. **A assimetria inteira é o parâmetro de acerto
casual.** Corolário: a frase original não é só imprecisa — sob Rasch é *vazia*,
sob 3PL é *invertida*.

**Próximo: face do gestor** (exportar `mart_geografia_*`), página de apoio e o
Volume 9.

### Etapa 4 — o que ficou de pé

Schema `marts` (sem prefixo, via `generate_schema_name`), três modelos e quatro
testes singulares novos. `dbt test` verde: **31/31**.

| modelo | linhas | tempo |
|---|---|---|
| `dim_escola` | 29.904 | 3s |
| `mart_escola_area` | 116.906 | 12s |
| `mart_diagnostico_habilidade` | 3.507.180 | ~1min |

O `dim_escola` é maior que as 29.265 escolas do diagnóstico porque cobre **toda**
escola nos resultados, inclusive as que só têm participantes de reaplicação/BAM.
É de propósito: dimensão descreve quem existe, o fato decide quem entra.

### Etapa 5 — o que ficou de pé

Seed da Matriz de Referência derivado do PDF oficial, correção do sentinela das
notas zeradas, mart de competência e a guarda de fronteira com Great
Expectations. `dbt test` verde: **39/39**.

| modelo | linhas |
|---|---|
| `matriz_referencia` (seed) | 120 |
| `mart_diagnostico_competencia` | 876.795 |

A Matriz **não** precisou de transcrição manual — o `build_matriz.py` deriva do
PDF oficial. Aquela pendência do CLAUDE.md ("único dado que não sai de script")
deixou de existir.

### Etapa 6 — o que ficou de pé

DAG `enem_pipeline` com **23 tasks** em quatro grupos, imagem própria (2,98 GB)
e o pool que serializa o que é pesado. Sobe pelo perfil:

```powershell
docker compose --profile airflow up -d          # UI em localhost:8080
docker compose exec airflow airflow pools set `
  banco_pesado 1 "Uma varredura grande do Postgres por vez"
docker compose --profile airflow down           # devolve a memoria
```

A senha do `admin` é gerada no primeiro boot e sai no
`docker compose logs airflow` (e em
`/opt/airflow/simple_auth_manager_passwords.json.generated`).

**Execução completa validada: 23/23 tasks `success` em 43,1 min**, incluindo o
`dbt test` (39/39) no fim. Reconstruiu tudo a partir dos CSVs e reproduziu os
números idênticos — mesmas contagens nos quatro marts e mesmas correlações
(CH −0,808 · CN −0,799 · LC −0,910 · MT −0,854).

O desenho se sustentou na prática, medido no banco de metadados:

- **0 sobreposições** entre tasks do pool `banco_pesado` — a serialização
  funcionou.
- **6 pares simultâneos** entre as `int_respostas_*`, que é C(4,2): as quatro
  views leves rodaram **juntas**. O pool não as atrapalhou.

Tasks mais lentas: `carrega_resultados` 478s · `int_acerto_item_lc` 377s ·
`int_acerto_item_mt` 305s · `stg_resultados` 225s.

Quatro armadilhas que já morderam aqui:

- **`DROP TABLE` da ingestão precisa de `CASCADE`.** Ver a armadilha
  "Idempotência da ingestão" abaixo — foi o único erro real da primeira
  execução completa.
- **O contexto de build é a raiz**, não `airflow/` — o `Dockerfile` precisa
  alcançar o `requirements.txt`. Daí o `.dockerignore`, sem o qual os 2,6 GB
  de `data/raw` iriam para o daemon a cada build.
- **`POSTGRES_HOST`/`PORT` são sobrescritos no serviço do Airflow.** Dentro de
  um container, `localhost` é o próprio container; o banco de dados é
  `postgres:5432` (nome do serviço, porta interna), não o que está no `.env`.
- **dbt em venv separado** (`/home/airflow/projeto-venv`). Airflow e dbt
  disputam versões de `jinja2` e `pydantic`; instalar juntos degrada um dos
  dois e o erro aparece longe da causa.

### Etapa 7 — o que ficou de pé

Dois workflows em `.github/workflows/`, em **três faixas** de verificação
segundo o quanto de dado cada uma precisa:

| faixa | precisa de | pega | onde |
|---|---|---|---|
| 1 | nada | sintaxe, `ref()` quebrado, import do DAG, dependência faltando | CI |
| 2 | Postgres com tabelas vazias | coluna inexistente, tipo, junção | CI |
| 3 | os 2,6 GB | regressão de **lógica** | Airflow, local |

A Faixa 2 usa `ci/cria_raw_vazia.py`, que deriva as tabelas de
`ingestion/config.py` (mesma regra dos seeds: derivar, nunca transcrever) e
depois roda `dbt build` normal — **59 nós verdes em 17s**, porque a fonte
vazia faz o trabalho sozinha.

**Não usar `dbt build --empty`.** A flag embrulha cada ref numa subconsulta
com alias próprio (`_dbt_limit_subq_x`), e o padrão `{{ ref('x') }} r` deste
projeto vira dois aliases em sequência: `syntax error at or near "r"` em 6
modelos. Além de desnecessária — aqui a raw é vazia de verdade.

A CI **não usa nenhum segredo**, e isso é desenho, não descuido: o Postgres do
job é descartável e morre em minutos. Se ela precisasse de senha real, seria
sinal de que está tocando um ambiente que não deveria.

As Data Docs do Great Expectations **não** são publicadas pela CI: elas
relatam uma validação, e num banco vazio não há o que validar.

### Decisões em aberto

- **BAM (Belém/Ananindeua/Marituba)** está fora por `is_regular`. São 62 mil
  participantes — nenhuma escola dessas cidades recebe diagnóstico. Merece
  recorte próprio: o mesmo pipeline com referência própria.
- **Por que CH tem quatro vezes mais prova em branco que LC?** 2.489 contra 663,
  no mesmo dia de aplicação e praticamente a mesma população. Não há explicação
  ainda; registrar a pergunta é melhor que inventar a resposta.

---

## Ambiente

Windows + PowerShell. Postgres em Docker. **Sempre** rodar da raiz do projeto:

```powershell
.\.venv\Scripts\Activate.ps1
. .\load_env.ps1          # o ponto e o espaço na frente são obrigatórios
docker compose up -d
```

`load_env.ps1` carrega o `.env` na sessão e define
`$env:DBT_PROFILES_DIR = (Resolve-Path ".\dbt").Path`. Precisa rodar uma vez por
terminal novo. Sem isso, o dbt não acha o `profiles.yml` nem as credenciais.

Acesso ao banco:

```powershell
docker compose exec postgres psql -U admincroc -d enem2025
```

O `profiles.yml` é versionado e usa `env_var()` — nunca colocar senha nele.

---

## Restrições de máquina — LEIA ANTES DE RODAR QUALQUER COISA

A máquina é limitada e este pipeline já derrubou o Postgres, o Docker Desktop e
encheu o disco do sistema mais de uma vez. Regras não negociáveis:

- **NUNCA rodar `dbt run` sem `--select`.** Ele dispara os modelos em paralelo,
  quatro threads famintas ao mesmo tempo, e derruba o banco. Sempre um modelo
  por vez.
- Os modelos `int_acerto_item_*` levam **minutos** cada. Isso é normal.
- Os `int_respostas_*` são views: reconstroem em segundos.
- **Recursos reais (medidos em 25/07/2026, não estimados):** máquina com
  **32 GB de RAM** e **4 CPUs**; `C:` com 14,3 GB livres, `E:` com 119,2 GB.
  A VM do Docker tem teto de **20 GB** (`.wslconfig`, `memory=20GB`) e
  devolve o que não usa (`autoMemoryReclaim=gradual`).
  **RAM nunca foi o gargalo — são os 4 núcleos.** Aumentar o teto não torna o
  paralelismo seguro: a regra do `--select` continua valendo igual.
- **Teto por container** no `docker-compose.yml`, dentro dos 20 GB da VM:
  Postgres de dados 13 GB · Airflow 4 GB (e 2 CPUs) · Postgres de metadados
  512 MB. O teto não desconfia do Postgres — **localiza o estrago**: sem ele,
  uma consulta que derrapa leva a VM inteira, que foi como o Docker Desktop
  caiu mais de uma vez.
- O Postgres de dados sobe com `shared_buffers=2GB`,
  `effective_cache_size=8GB`, `work_mem=64MB`. O padrão da imagem
  (128 MB / 4 GB / 4 MB) é para uma máquina qualquer; o `pgdata` inteiro tem
  8,8 GB e cabe em cache.
- Disco do Docker em `E:\Projetos\00 - Data Ops, ML Ops e ENEM\docker`. Não
  mover de volta para o `C:` — o `.vhdx` do WSL2 só cresce, nunca encolhe
  (hoje 19,5 GB para 12,6 GB de conteúdo real).
- **Nada do `.wslconfig` vale até `wsl --shutdown`** com o Docker Desktop
  fechado pela bandeja. Isso já mordeu uma vez: o arquivo dizia
  `memory=16GB` e `swap=8GB` no `E:`, e a VM rodava havia 63 h com os padrões
  do WSL (16 GB de teto por coincidência, 4 GB de swap no `C:`) — a
  configuração estava escrita e **nunca aplicada**. Conferir sempre depois:

```powershell
wsl -d docker-desktop -e sh -c "free -m; cat /proc/swaps"   # swap deve dar 8192
Get-ChildItem E:\wsl                                        # swap.vhdx deve existir aqui
```

- **Fora do `C:` por decisão:** swap do WSL2 (`swapFile=E:\\wsl\\swap.vhdx`),
  disco do Docker e o arquivo de paginação do Windows (`E:\pagefile.sys`, com
  o do `C:` removido). O `C:` é o disco do sistema e vive perto do limite;
  cada um desses arquivos passa de 8 GB.
- **`Ctrl+C` não cancela a consulta.** O dbt é só o cliente; o Postgres continua
  moendo e consumindo disco. Para cancelar de verdade:

```sql
select pid, state, wait_event_type, wait_event, now() - query_start as duracao
from pg_stat_activity where state != 'idle' and pid != pg_backend_pid();

select pg_cancel_backend(PID);      -- líder = o que tem state=active SEM wait_event
select pg_terminate_backend(PID);   -- se o primeiro não surtir efeito
```

- Se o disco encher: fechar o Docker Desktop pela bandeja e `wsl --shutdown`
  libera o swap (que fica no `C:` mesmo com os dados no `E:`).
- `MessageQueueSend` em workers paralelos é contrapressão normal, não travamento.

---

## Arquitetura

```
CSV bruto (INEP)
  → raw            ingestão via COPY, tudo TEXT, sem interpretação
  → staging        tipagem + schema canônico (dbt, views)
  → intermediate   explosão das respostas + agregação por item
  → marts          diagnóstico por escola — schema próprio, fronteira de consumo
```

O que está em `marts` é contrato com o mundo externo (a futura API); o que está
em `staging` é cozinha interna.

### Estrutura

```
enem-ml-data-ops/
├── load_env.ps1
├── docker-compose.yml          só Postgres (pgAdmin foi removido)
├── .dockerignore               mantem data/raw fora do contexto de build
├── airflow/
│   └── Dockerfile              imagem oficial + venv separado do projeto
├── dags/
│   └── enem_pipeline.py        23 tasks, pool banco_pesado
├── ingestion/
│   ├── config.py               colunas de cada base, separador, encoding
│   ├── load_raw.py             ingestão via COPY, idempotente, em blocos
│   ├── build_seeds.py          gera os seeds a partir dos artefatos do INEP
│   └── build_matriz.py         gera o seed da Matriz a partir do PDF oficial
├── quality/
│   └── expectations_raw.py     Great Expectations na fronteira (camada raw)
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml            usa env_var, versionado
│   ├── packages.yml            dbt_utils
│   ├── macros/
│   │   ├── util.sql            num, inteiro, grande, booleano
│   │   ├── explode_respostas.sql        CH, CN, MT
│   │   ├── explode_respostas_lc.sql     LC (caso especial)
│   │   ├── agrega_por_item.sql
│   │   └── generate_schema_name.sql     marts sem prefixo staging_
│   ├── seeds/
│   │   ├── dominios.csv        500 pares código→rótulo, 59 variáveis
│   │   ├── co_prova.csv        74 versões de prova classificadas
│   │   └── matriz_referencia.csv  120 habilidades → competência + descrição
│   ├── models/
│   │   ├── staging/
│   │   │   ├── _sources.yml
│   │   │   ├── _staging.yml
│   │   │   ├── stg_itens.sql
│   │   │   ├── stg_participantes.sql
│   │   │   └── stg_resultados.sql
│   │   ├── intermediate/
│   │   │   ├── _intermediate.yml
│   │   │   ├── int_respostas_{mt,ch,cn,lc}.sql       views
│   │   │   ├── int_acerto_item_{mt,ch,cn,lc}.sql     tables
│   │   │   ├── int_acerto_item_escola.sql
│   │   │   └── int_acerto_item_nacional.sql
│   │   └── marts/
│   │       ├── _marts.yml
│   │       ├── dim_escola.sql
│   │       ├── mart_escola_area.sql
│   │       ├── mart_diagnostico_habilidade.sql
│   │       └── mart_diagnostico_competencia.sql
│   └── tests/
│       ├── stg_itens_grao_unico.sql
│       ├── taxa_acerto_plausivel.sql
│       ├── item_sem_parametro.sql
│       ├── percentil_publicavel.sql
│       ├── taxa_condiz_com_status.sql
│       ├── habilidades_completas.sql
│       ├── marts_mesma_populacao.sql
│       ├── nota_zero_nao_entra_na_media.sql
│       └── competencia_cobre_habilidades.sql
└── data/raw/                   CSVs do INEP, fora do Git
```

### Materialização

- `staging` → view, **exceto `stg_resultados`** que é **table** (senão
  reconverte 4,8 milhões de linhas de texto a cada consulta).
- `intermediate` → `int_respostas_*` são **view** (o grão fino nunca toca o
  disco); `int_acerto_item_*` são **table**.
- `marts` → **table**, com `+schema: marts` e o `pre_hook` no nível da pasta (no
  `dbt_project.yml`), para que todo mart novo já nasça com paralelismo desligado.
- Os `int_acerto_item_{area}` usam
  `pre_hook="set max_parallel_workers_per_gather = 0"`. Isso **não é opcional**:
  cada worker paralelo recebe sua própria fatia de memória, e é isso que derruba
  o servidor.
- O macro `generate_schema_name` faz o `+schema` valer como está. Sem ele o dbt
  concatena e o schema viraria `staging_marts`.
- `vars: n_minimo_diagnostico: 20` no `dbt_project.yml` — o N mínimo mora num
  lugar só e aparece no diff. Vira seed se um dia ganhar estrutura (N por rede,
  por exemplo).

### Ordem de construção

```powershell
cd dbt
dbt deps
dbt seed
dbt run --select stg_itens
dbt run --select stg_participantes
dbt run --select stg_resultados

dbt run --select int_respostas_mt
dbt run --select int_respostas_ch
dbt run --select int_respostas_cn
dbt run --select int_respostas_lc

dbt run --select int_acerto_item_mt
dbt run --select int_acerto_item_ch
dbt run --select int_acerto_item_cn
dbt run --select int_acerto_item_lc

dbt run --select int_acerto_item_escola
dbt run --select int_acerto_item_nacional

dbt run --select dim_escola
dbt run --select mart_escola_area
dbt run --select mart_diagnostico_habilidade    # depende do mart_escola_area
dbt run --select mart_diagnostico_competencia   # depende do mart_escola_area

dbt test
```

Antes dos marts, o seed da Matriz precisa existir:

```powershell
# uma vez, da raiz (o PDF vai para data/raw/, fora do Git)
curl -o data/raw/matriz_referencia.pdf `
  https://download.inep.gov.br/download/enem/matriz_referencia.pdf
python -m ingestion.build_matriz --pdf data/raw/matriz_referencia.pdf
cd dbt; dbt seed --select matriz_referencia
```

E a guarda de fronteira, uma vez depois da ingestão (não a cada `dbt run` — ela
varre a `raw` inteira):

```powershell
python -m quality.expectations_raw
```

Os marts são baratos (segundos a ~1 min). `dbt build --select marts` também
serve e resolve a ordem de dependência sozinho.

---

## Armadilhas dos dados — cada uma custou horas

### As bases de participante e resultado NÃO são relacionáveis

O dicionário é explícito: `NU_SEQUENCIAL` (chave de RESULTADOS) é distinta de
`NU_INSCRICAO` (chave de PARTICIPANTES) e **não pode ser usada para relacionar
as duas bases**. É desidentificação deliberada.

As duas têm exatamente 4.810.772 linhas, o que tenta a ligá-las pela ordem.
**Não fazer isso** — a ordem não é garantida e reconstruir o vínculo contorna
uma proteção intencional. Qualquer análise cruzando perfil socioeconômico com
desempenho individual está fora do escopo desta edição.

### `CO_POSICAO` não é a posição na prova

É um identificador sequencial global do item — começa em centenas, não em 1. A
posição real (1 a 45, ou 1 a 50 em LC) é reconstruída em `stg_itens` com
`row_number() over (partition by CO_PROVA order by CO_POSICAO)`.

Usar o `CO_POSICAO` cru quebra silenciosamente a junção com as respostas.

### Junção item ↔ resposta é SEMPRE por `(co_prova, posicao)`

As quatro cores regulares contêm os mesmos itens **em ordens diferentes**. A
posição 7 é um item na prova Azul e outro na Verde. Juntar só por `posicao`
produz resultado plausível e completamente falso.

### LC: gabarito do participante tem 50 posições, resposta tem 45

Layout da string `gabarito_lc`: inglês em 1–5, espanhol em 6–10, comuns em
11–50. A resposta do aluno tem 45 posições (5 da língua dele + 40 comuns).
Indexar uma pela outra desalinha 40 dos 45 itens.

**Solução:** em LC, o gabarito vem de `stg_itens.gabarito` (catálogo), não da
string. A junção já garante que é o item certo, e as duas fontes usam a mesma
codificação (verificado: 4410/4410 iguais em MT).

No catálogo, as posições 1–10 de LC são os itens de língua estrangeira,
**intercalados** entre inglês e espanhol (não 1–5 / 6–10). A junção filtra por
`(i.cod_lingua is null or i.cod_lingua = p.cod_lingua)` e um `row_number`
particionado por aluno renumera de 1 a 45.

### Linha que não existe é omissão silenciosa — LC habilidade 8

A `int_acerto_item_escola` só tem linha para item **respondido**. A habilidade 8
de LC é coberta só por **itens de espanhol** — nenhum comum, nenhum de inglês.
Numa escola sem aluno de espanhol, ninguém respondeu nada dessa habilidade, e a
linha simplesmente não existe: são **1.824 das 29.260 escolas com presença em
LC (6,2%)**.

Um mart que parte das linhas da escola faz a habilidade **sumir** do relatório
dessas escolas. É o mesmo defeito da MT hab 21 por outro caminho — lá a edição
não tinha item válido, aqui a escola não teve quem respondesse.

**Solução:** o `mart_diagnostico_habilidade` monta um **grid completo** escola ×
área × habilidade e distingue os dois casos: `nao_avaliada` (a edição não tem o
que medir) e `nao_administrada` (a escola não teve quem respondesse). O teste
`habilidades_completas` trava a regressão — nenhum teste por linha vê uma linha
que não existe.

As habilidades **5, 6 e 7 de LC** sofrem uma versão mais branda: o lastro varia
com o mix de línguas da escola (1 a 3 itens, contra 2–3 no nacional). Por isso o
mart carrega `n_itens_validos` e `n_itens_validos_nacional` lado a lado.

### Idempotência da ingestão — o `DROP` precisa de `CASCADE`

O `load_raw.py` faz `DROP TABLE IF EXISTS raw.<base>` para ser idempotente.
A partir da Etapa 2 isso **quebra**: `stg_itens` e `stg_participantes` são
**views** sobre as tabelas raw, e o Postgres recusa o drop —
`cannot drop table ... because other objects depend on it`.

O erro ficou escondido por cinco etapas porque, manualmente, a ingestão sempre
rodou **antes** de existir qualquer modelo. Só apareceu na primeira execução
orquestrada, que é a primeira vez que o pipeline roda a *segunda* vez.

Solução: `DROP TABLE IF EXISTS raw.<base> CASCADE`. É seguro porque tudo acima
da raw é derivado e o próprio DAG reconstrói em seguida — derrubar a view e
recriá-la em minutos é correto; manter uma view apontando para uma tabela
recriada do zero é que seria perigoso.

Note que `stg_resultados` **não** dá esse problema: é materializado como
*table*, e tabela não cria dependência com a origem.

Lição além do bug: **"é idempotente" só vale depois de rodar duas vezes.** O
retry automático não salvaria — a falha é determinística, não transitória.

### Nota 0 é sentinela, não desempenho

`NU_NOTA_*` vem **0** para quem esteve presente e entregou a prova
**inteiramente em branco** — verificado: 100% dos zerados têm o vetor de
respostas só com pontos. A TRI estima proficiência a partir do *padrão* de
respostas; sem resposta não há padrão, e o INEP grava 0 porque a coluna precisa
de um número.

O sinal que denuncia: existem milhares de notas **exatamente** 0 e **nenhuma**
entre 0 e 250 — o piso real da escala é 308–320. Distribuição contínua não dá
salto assim.

Um `avg(nota)` ingênuo distorce a média da escola em **até 147,5 pontos**
(218 escolas afetadas em MT, 197 delas publicáveis). O tipo não denuncia: um
`numeric` aceita zero sem reclamar. Solução: `avg(nullif(nota, 0))` e a
contagem exposta em `n_prova_em_branco`.

Provas em branco por área: **CH 2.489 · LC 663 · MT 221 · CN 163** (na população
do diagnóstico).

### Dois defeitos que o `limpa()` deveria pegar e não pegava

Apareceram ao mostrar a descrição completa da competência na tela — enquanto
ela vinha truncada, os dois ficavam escondidos no fim da frase.

**O asterisco órfão (LC C2).** A descrição terminava em `grupos sociais*.` e o
asterisco aparece **uma única vez nas 24 páginas** do PDF, sem nota de rodapé
nenhuma — marcador sem referente. O `limpa()` já tinha a regra
(`rstrip("*")`), mas ela só pegava o asterisco em **última** posição, e aqui
vinha a pontuação depois. Não foi decisão editorial nova: foi consertar onde a
intenção já estava escrita.

**A palavra composta partida (CN C6 e C7).** O PDF quebra a linha em
`científico-` e continua `tecnológicas.` na seguinte; juntar com espaço dava
**`científico- tecnológicas`**, e assim chegou à tela. Colar é seguro *neste*
documento: as 6 linhas terminadas em hífen foram conferidas uma a uma e todas
são compostos (`histórico-geográficos`, `científico-tecnológicas` ×3,
`lógico-semânticas`). **Não há hifenização de sílaba aqui** — se houvesse, a
regra teria de decidir se o hífen fica ou sai, e não daria para automatizar.

Lição de método: a correção foi para o **gerador do seed**, não para a tela. Eu
tinha começado remendando na exibição, e estava errado — quando a regra já
existe na origem, o remendo a jusante esconde o bug em vez de resolvê-lo. O
seed continua derivado do artefato; o que mudou foi a limpeza ficar completa.

### Extração de PDF quebra palavras

Extratores que **inferem** o espaço comparando a distância entre glifos com uma
largura de referência quebram palavras em PDF justificado: `signif icados`,
`natur ais`, `argumenta tivas`, `situações -problema`. Calibrar o limiar não
resolve — o sinal é ambíguo por natureza.

Usar extrator que trabalhe com o **posicionamento real** de cada caractere
(`pdfplumber`). A diferença não aparece em teste nenhum — aparece quando alguém
lê "signif icados" no relatório.

### O que vem DEPOIS da última linha também entra — o ANEXO na CH H30

O `build_matriz.py` fecha uma habilidade quando encontra a próxima (`H\d+ –`) ou
uma competência. A **CH H30 é a última do PDF**, e logo depois vem o ANEXO com
os objetos de conhecimento das quatro áreas. Nenhuma linha dele casa com os
padrões, então todas viraram continuação da H30: **21.710 caracteres** numa
descrição que tem 93.

O estrago não ficou no seed. A descrição viaja **replicada por escola** nos
marts: `mart_diagnostico_habilidade` estava com **1.671 MB** e caiu para 1.326
depois do conserto; a geografia, de 249 para 177. **417 MB de disco** numa
máquina que vive perto do limite — e ninguém tinha olhado, porque a contagem de
linhas estava certíssima.

Solução: cortar o texto na linha `ANEXO` (o único marcador de fim que o PDF
tem) e — o que importa mais — **validar o teto**: descrição acima de 600
caracteres derruba o script. As guardas existentes perguntavam se a descrição
era *curta demais* ou vazia; nunca ocorreu que o perigo fosse o excesso.

Lição geral: **todo parser de documento precisa saber onde o documento acaba.**
Sem marcador de fim, o último registro absorve o rodapé, o anexo, a bibliografia
— e passa em qualquer teste de contagem.

### `NU_INSCRICAO` estoura o `integer`

12 dígitos; o `integer` do Postgres vai até 2.147.483.647. Usar o macro
`grande()` (bigint). Os scripts oficiais do INEP sinalizam isso com
`integer64='character'`.

Nota: o erro **não aparece no `dbt run`** (view só guarda a definição), só quando
alguém consulta ou o `dbt test` roda.

### `substring` não aceita `bigint`

`row_number()` devolve `bigint` e
`substring(texto from bigint for integer)` não existe no Postgres. Sempre
`::int` na posição.

### Duas divergências entre os artefatos oficiais do INEP

O `build_seeds.py` reconcilia automaticamente e reporta:

- `TP_STATUS_REDACAO` — o script R lista 7 níveis para 8 rótulos; falta o
  código 9 ("Parte desconectada"). Resolvido pelo dicionário.
- `TP_COR_RACA` — o dicionário lista 6 categorias, o script R tem 7 (inclui o
  código 6, "Não dispõe da informação"). Mantida a versão mais completa.

Regra do script: quando o dicionário traz *mais* códigos, ele prevalece; quando
traz *menos*, mantém-se o script R e sinaliza (leitura incompleta de planilha
costuma ser falha de parsing, não divergência real).

### Encoding e separador

CSV separado por `;` e em `latin-1` (não UTF-8).

---

## Fatos dos dados (ENEM 2025)

### Volumes

- `raw.resultados_2025` — 4.810.772 linhas, 41 colunas
- `raw.participantes_2025` — 4.810.772 linhas, 35 colunas
- `raw.itens_prova_2025` — 6.105 linhas, 14 colunas

### Cobertura

- 36,1% dos resultados têm `CO_ESCOLA` (1.739.028). É a escola de conclusão do
  ensino médio, vinculada ao Censo Escolar — só quem está concluindo agora tem.
- **17.874 escolas** com 20+ participantes presentes em MT.
- 97,4% dos presentes em MT fizeram prova regular.

### Provas

132 versões (33 por área), 565 itens distintos no total. Dentro das regulares o
conjunto é **idêntico** — as cores são a mesma prova reordenada:

| área | códigos regulares | cores | itens |
|---|---|---|---|
| CH | 1447–1450 | Azul, Amarela, Branca, Verde | 45 |
| CN | 1483–1486 | Azul, Amarela, Verde, Cinza | 45 |
| LC | 1459–1462 | Azul, Amarela, Verde, Branca | 50 |
| MT | 1471–1474 | Azul, Amarela, Verde, Cinza | 45 |

**A quarta cor não é a mesma em todas as áreas** — CH e LC usam Branca, CN e MT
usam Cinza. São dias diferentes de prova.

### A cor é do CADERNO, e o caderno é do DIA

Consequência da linha acima, que só apareceu ao desenhar a tela: o ENEM aplica
**LC + CH no 1º dia** e **CN + MT no 2º**, e cada dia tem **um** caderno. Logo a
cor vale para as **duas áreas do dia** — verificado no dado, cada cor emparelha
exatamente LC↔CH e CN↔MT:

| dia | áreas | cores |
|---|---|---|
| 1º | LC + CH | Azul · Amarela · **Branca** · Verde |
| 2º | CN + MT | Azul · Amarela · **Cinza** · Verde |

O formulário do site pedia **quatro** cores, uma por área — convite a uma
combinação que não existe (Branca em Matemática). Agora pede **duas**, uma por
dia, e as respostas continuam por área porque é assim que a Vista Pedagógica as
apresenta. Menos campo, menos erro possível, e espelha como a pessoa viveu a
prova.

Tipos de aplicação no seed `co_prova`: `regular` (16), `acessibilidade` (20),
`reaplicacao` (14), `bam` (24). A regra de classificação é durável: é regular
quando o rótulo é só o nome da cor, sem qualificador.

Distribuição de participantes em MT: regular 3.176.917, BAM 62.206,
acessibilidade 20.548, reaplicação 665.

### Língua estrangeira

`cod_lingua = 0` → Inglês, `1` → Espanhol (rótulo oficial).

### Itens problemáticos

**Cinco** itens ficaram **não avaliáveis** (taxa nula no agregado, preservados
no grão para aparecerem como "não avaliados"). Todos os cinco **sem parâmetro de
TRI** — nenhum entrou na escoragem oficial. No fonte do INEP eles vêm com
`IN_ITEM_ABAN` marcado, então `item_abandonado` é o superconjunto e
`item_anulado` (gabarito `X`) é o subconjunto dos anulados — por isso os anulados
aparecem com as **duas** flags verdadeiras.

| co_item | área | hab | gabarito | anulado | motivo |
|---|---|---|---|---|---|
| 141557 | CN | 1  | X | sim | Previamente exposto |
| 141774 | CN | 9  | X | sim | Previamente exposto |
| 31350  | MT | 21 | X | sim | Previamente exposto |
| 96748  | CN | 25 | B | não | Problema de convergência |
| 97593  | MT | 22 | A | não | Problema de convergência |

Os três **anulados** saíram por "Previamente exposto" (item vazado/reaproveitado),
gabarito `X`, sem resposta correta. Os dois de **gabarito válido** saíram por
"Problema de convergência" — a calibração da TRI não convergiu, então não têm
parâmetro e não foram escorados. Mesmo tratamento: não avaliáveis.

**Impacto na cobertura por habilidade:**

- **MT hab 21 — ZERO itens válidos** (o anulado 31350 era o único). Não pode ser
  diagnosticada em 2025. O relatório precisa dizer isso, não omitir.
- **CN hab 9 · CN hab 25 · MT hab 22 — 1 item válido cada** (perderam um item
  para anulado/abandonado). Ficam frágeis: um item não é a medida de uma
  habilidade, é a medida daquele item. Merecem ressalva no relatório.

Nota histórica: até a Etapa 3, o `96748` (abandonado, **não** anulado) escapava
do `where acertou is not null` e entrava no diagnóstico com taxa calculada, como
se fosse item normal — um item que o INEP havia tirado da escoragem. Foi a
preservação de anulados/abandonados que expôs isso; o `96748` sequer estava
documentado antes.

### Itens por habilidade — o fato que mais pesa no produto

30 habilidades por área, 120 no total. Média de itens **válidos** por
habilidade: CH 1,50 · CN 1,40 · LC 1,67 · MT 1,43.

Distribuição: **1 habilidade com zero** itens válidos (MT 21), **62 com um
único item**, 57 com dois ou mais. Ou seja, **mais da metade das habilidades é
medida por um item só**.

Consequência: *precisão* não é problema (uma escola com 100 alunos tem 100
respostas por item), mas *validade de conteúdo* é. Um item não representa a
habilidade inteira — mede também o enunciado, o distrator, o tema. Duas saídas
combináveis: reportar o número de itens que embasa cada medida (feito — a coluna
`n_itens_validos` e o `status` no mart) e agregar no nível de **competência de
área** (pendente do seed da Matriz).

**Resolvido na Etapa 5:** os microdados trazem só o *número* da habilidade; a
descrição e a competência vêm da Matriz de Referência
(`download.inep.gov.br/download/enem/matriz_referencia.pdf`), derivada pelo
`build_matriz.py`.

Competências por área: **LC 9 · MT 7 · CN 8 · CH 6** (30 no total, 120
habilidades). Agregar no grão da competência dá **4 a 11 itens válidos por
medida** (mínimo por área: CH 6, CN 4, LC 4, MT 4) contra 0–2 por habilidade —
é o que resolve o problema de validade de conteúdo.

Confirmação cruzada: a Competência 2 de LC ("língua estrangeira moderna")
agrupa exatamente H5–H8, que é o conjunto que a Etapa 4 identificou
empiricamente como dependente de língua.

---

## Validação — a verificação que importa

A correlação entre `param_dificuldade` (parâmetro **b** da TRI, calibrado pelo
INEP) e `taxa_acerto_nacional` (calculada do zero a partir dos vetores de
resposta) **tem que ser fortemente negativa**. São dois caminhos independentes
concordando sobre quais itens são difíceis.

```sql
select area,
       round(corr(param_dificuldade, taxa_acerto_nacional)::numeric, 3) as correlacao,
       round(avg(taxa_acerto_nacional), 1) as taxa_media,
       count(*) as itens
from staging.int_acerto_item_nacional
group by 1 order by 1;
```

Valores obtidos e validados:

| área | correlação | taxa média |
|---|---|---|
| CH | −0,808 | 35,8% |
| CN | −0,799 | 32,6% |
| LC | −0,910 | 45,1% |
| MT | −0,854 | 31,9% |

LC vir mais alta é esperado — historicamente é a área de maior acerto no ENEM.

**Se a correlação vier fraca ou positiva, a junção está quebrada.** Foi assim
que o bug de LC foi pego: −0,027 e taxa de 22,6% (colada no acaso de 20%).
Nenhum outro teste teria pego.

### Sobre o limiar de taxa de acerto

Taxa abaixo de 20% **não** indica erro. O parâmetro de acerto casual (`c`)
desses itens fica entre 0,063 e 0,125, então o piso da curva é 6-12%, não 20% —
o aluno não chuta ao acaso, escolhe convictamente o distrator. Itens muito
difíceis chegam legitimamente a 8-15%. O piso do teste é **5%**.

### Verificações dos marts (Etapa 4)

```sql
-- os dois casos-limite estao declarados, nao omitidos
select area, habilidade, status, count(*) as escolas
from marts.mart_diagnostico_habilidade
where (area = 'MT' and habilidade = 21) or (area = 'LC' and habilidade = 8)
group by 1,2,3 order by 1,2,3;

-- publicaveis por area
select area, count(*) filter (where publicavel) as publicaveis
from marts.mart_escola_area group by 1 order by 1;
```

Valores obtidos: MT 21 → 29.193 escolas `nao_avaliada`. LC 8 → 1.824
`nao_administrada` + 27.436 `ok`.

O `\dn` deve listar `marts`, nunca `staging_marts`.

### Verificações da Etapa 5

```sql
-- o sentinela saiu da media: esperado ZERO linhas
select area, count(*) from marts.mart_escola_area where media_nota < 300 group by 1;

-- lastro por competencia: esperado minimo >= 4 nas quatro areas
select area, min(n_itens_validos_nacional), round(avg(n_itens_validos_nacional),1)
from marts.mart_diagnostico_competencia group by 1 order by 1;
```

Publicáveis **após** a correção do sentinela: **CH 18.098 · LC 18.108 ·
CN 17.600 · MT 17.600**. Eram 18.115/18.115/17.601/17.601 antes — 26 escolas
perderam publicação por terem 20+ presentes mas menos de 20 notas estimáveis.
CH perdeu 17, coerente com ser a área com muito mais prova em branco.

Lastro por competência: CH mín 6 (média 7,5) · CN mín 4 (5,3) · LC mín 4 (5,6) ·
MT mín 4 (6,1).

### Baseline do Great Expectations

`python -m quality.expectations_raw` → **3 suites, 22 expectations, 100%**
(itens 9 · resultados 9 · notas 4). Leva ~3 min: varre a `raw` inteira, então
rodar **uma vez** depois da ingestão, nunca a cada `dbt run`.

Duas leituras da saída que evitam susto:

- `missing_count` alto em `TX_RESPOSTAS_*` (1,55 mi em CN/MT, 1,35 mi em CH/LC)
  é **esperado** — são os ausentes, que não têm vetor. Expectation de *valor*
  avalia só os não nulos. Já `TP_PRESENCA_*` vem com `missing_count: 0`.
- O `element_count` do query asset das notas já é o total **filtrado** pelo
  `row_condition` (sem os zeros): MT 3.259.443 · CH 3.448.468 · LC 3.455.194 ·
  CN 3.259.561. Somando os zeros de volta reconstrói os presentes — CH e LC
  fecham em 3.457.555, o mesmo dia de prova.

---

## Decisões metodológicas

- **Só provas regulares** entram no diagnóstico. Acessibilidade fica **fora**
  (decisão fechada) — deixa ~20 mil participantes com deficiência fora do
  diagnóstico da própria escola, custo assumido. Reaplicação e BAM têm itens
  próprios e não são comparáveis na mesma métrica.
- **Só participantes presentes** (`cod_presenca = 1`).
- **Só quem tem `CO_ESCOLA`** — participante sem escola não pode ser atribuído a
  escola nenhuma. A consequência deixou de ser dívida e virou **decisão**: a
  referência é *entre concluintes com escola identificada*, e esse é o peer group
  correto para um diagnóstico de escola. Comparar a turma que se forma agora
  contra a população inteira do ENEM (treineiros, quem terminou o médio há dez
  anos) não seria mais rigoroso, seria menos. Limitação a registrar no README: a
  referência representa concluintes vinculados ao Censo, não "o Brasil inteiro".
- **Item anulado sai do cálculo**, sem crédito e sem penalidade. Não é uma
  escolha entre duas opções: em TRI a nota não é contagem de acertos, é
  estimativa de traço latente. Item sem gabarito não carrega informação sobre
  proficiência. Como as notas oficiais foram calculadas assim, excluir mantém o
  diagnóstico na mesma contabilidade da nota que o participante recebeu.
- **Ausência estrutural não é fracasso.** Um aluno que fez inglês não respondeu
  os itens de espanhol — isso é item não administrado, nunca erro. A junção por
  `cod_lingua` resolve na origem.
- **N mínimo para publicar diagnóstico: 20** (`var n_minimo_diagnostico`), e
  exige 20 **presentes** e 20 **com nota**. Escola com poucos alunos gera
  resultado instável e potencialmente identificável. Escolas abaixo do limiar
  **continuam nas tabelas** com `publicavel = false`, sem percentil — excluí-las
  apagaria a informação de que existem; publicá-las exporia o que o N não
  sustenta. O flag viaja nos **dois** marts: quem consome só o de habilidades
  não pode publicar escola pequena sem saber.
- **Percentil pela nota oficial**, não pela taxa de acerto. É a escala pública
  que as escolas conhecem, estimada por TRI (pondera dificuldade, desconta
  acerto casual) e auditável. A taxa de acerto fica com o que só ela faz: abrir
  o desempenho por habilidade. Cada medida no seu posto.
- **Uma régua por área, não por rede.** O percentil compara todas as escolas
  publicáveis da área — Federal e Municipal juntas. Recortar por rede/UF embute
  um juízo sobre o que é comparável e faria "percentil 80" significar coisas
  diferentes em tabelas diferentes. Os atributos de recorte estão na
  `dim_escola`; a API pode *filtrar* o ranking, não recalculá-lo.
- **Taxa ponderada, não média das taxas.** Soma acertos ÷ soma respostas, na
  escola e na referência, simetricamente — agregadas pela mesma regra, são
  comparáveis por construção. Exceção honesta: LC 5–8, onde o conjunto de itens
  varia com o mix de línguas (por isso os dois lastros lado a lado).
- **Nota zero sai da média e é contada à parte.** Não é desempenho, é ausência
  de evidência (ver "Nota 0 é sentinela"). Mesmo princípio do item anulado e da
  habilidade não avaliada: **preservar a linha, anular a métrica, expor a
  contagem**. O contra-argumento — o aluno que entregou em branco faz parte da
  realidade da escola — é legítimo, e por isso a saída não é apagar, é separar e
  mostrar: uma métrica que mistura "foi mal" com "não fez" não mede nem uma coisa
  nem outra.
- **Habilidade e competência convivem.** Habilidade é *acionável* (diz o que
  trabalhar) mas frágil (1–2 itens); competência é *confiável* (4–11 itens) mas
  larga demais para virar plano de aula. Publicar os dois, com
  `n_itens_validos` em ambos, deixa quem lê escolher o peso de cada afirmação.
- **Staging faz três coisas e só três:** renomeia, converte tipo, mantém
  um-para-um com a fonte. Sem junções, sem filtros de regra de negócio, sem
  agregação. Filtro de prova regular e de presença é decisão de análise e vive
  na camada intermediate.

---

## Convenções de código

- Modelos dbt em SQL, sem `CREATE TABLE` manual — o dbt materializa.
- Lógica repetida entre áreas vira **macro**, nunca copiar e colar.
- Listas de áreas com laço Jinja (`{% set areas = ['mt','ch','cn','lc'] %}`), para
  que acrescentar uma área seja uma linha.
- Colunas explícitas em `union all`, nunca `select *` entre modelos de origens
  diferentes.
- Decisões de escopo viram **seed versionado**, não `WHERE` com números mágicos.
  Escalar solto (o N mínimo) vira `var` no `dbt_project.yml` — seed de uma célula
  é cerimônia; vira seed quando ganhar estrutura.
- **Derivar de artefato oficial, nunca transcrever.** Todo seed sai de script
  (`build_seeds.py`, `build_matriz.py`), e o script **falha alto** em vez de
  gravar resultado parcial. Transcrição manual em volume é onde o erro silencioso
  mora: um seed pela metade vira join, vira relatório, e ninguém percebe porque
  não há com o que comparar.
- **Teste de fronteira ≠ teste de transformação.** O `dbt test` pergunta "meu SQL
  fez o que eu quis?"; o Great Expectations pergunta "o dado que chegou é o que
  eu esperava?". Falha no primeiro = meu código está errado; no segundo = o
  mundo mudou. Pressuposto sobre a fonte vira expectation na `raw`, não teste no
  dbt.
- **Linha ausente é omissão silenciosa.** Onde o grão é "entidade × dimensão",
  montar o **grid completo** e declarar o vazio com um status, em vez de deixar a
  linha faltar. Nenhum teste por linha vê uma linha que não existe — por isso
  também um teste de *completude* (`habilidades_completas`).
- Nomes canônicos em português nas camadas acima de raw (`renda_familiar`, não
  `Q007`), para que a troca de edição não propague mudança de nome.
- Prefixo `qtd_` para variáveis de quantidade e `tem_` para binárias no
  questionário socioeconômico.
- **Nunca apagar um teste para o pipeline ficar verde.** Falha de teste é
  descoberta: investigar, entender, e então ajustar o teste documentando o
  porquê.

---

## Não commitar

`.env`, `.venv/`, `data/raw/`, `dbt/target/`, `dbt/logs/`, `logs/`, `docs/`,
`dbt/dbt_packages/`, `dbt/.user.yml`.

`docs/` são os Volumes (narrativa do projeto, HTML) — publicados por outro
caminho, fora do versionamento.

Os seeds em `dbt/seeds/` **devem** ser commitados, mesmo sendo gerados pelo
`build_seeds.py` — é o que permite clonar e rodar `dbt seed` sem baixar 2,6 GB
de microdados, e é o que faz a decisão de escopo aparecer no diff.

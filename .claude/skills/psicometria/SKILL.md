---
name: psicometria
description: Verifica afirmações conceituais sobre TRI (Teoria de Resposta ao Item) antes que elas cheguem à tela ou à documentação. Use ao escrever ou revisar qualquer texto que explique como a nota do ENEM funciona, o que move a pontuação, o que a informação de Fisher mede, como a escala é definida ou o que transfere entre edições — inclusive em webapp/metodo.html, webapp/index.html, CLAUDE.md e PLANO.md.
---

# Psicometria — a quarta lente

Este projeto tem três lentes que conferem **números e código**: `dbt test`
(o SQL fez o que eu quis?), Great Expectations (o dado que chegou é o
esperado?) e `ci/testa_webapp.js` (a conta do navegador está certa?).

Nenhuma confere **teoria**. Foi por aí que passaram os dois erros conceituais
de 27/07/2026, que sobreviveram a três rodadas de verificação porque os
verificadores liam código, não psicometria.

Esta skill é a quarta lente. Ela existe para um tipo de defeito só: **a frase
plausível escrita de memória.**

## O procedimento

Toda afirmação conceitual sobre TRI que for para texto visível precisa de uma
destas três coisas, nesta ordem de preferência:

1. **Página de referência** — apontar obra e página (ver `referencias/INDICE.md`).
2. **Conta reproduzível** — se não está no livro, calcular. Use
   `scripts/verifica.py`, que já carrega os parâmetros reais dos 180 itens.
3. **Ressalva explícita no texto** — se não dá para nenhuma das duas, a frase
   diz que é observação empírica desta edição, não propriedade da teoria.

Não existe quarta opção. Frase que soa certa e não tem nenhuma das três **não
entra**.

## Regra de conduta ao medir

O primeiro número que aparece costuma vir de um caso patológico. Antes de
publicar qualquer valor:

- **Pergunte se o cenário existe.** Ao medir "mesmo total de acertos dá notas
  diferentes", o caso extremo (acertar só as mais difíceis) dá 566 pontos de
  diferença — e não existe: ninguém responde assim. Simulando padrões
  plausíveis, a resposta honesta é **33 pontos** (p05–p95). O número errado era
  17× maior e teria ido para a tela.
- **Cheque se bateu num clamp.** θ = −3,5 ou +4,5 quase sempre é o limitador,
  não a medida.
- **Separe "no papel" de "na prova de 2025".** Propriedade do modelo transfere;
  medida desta edição não.

## Invariantes — o que é derivável

Referências: **B** = Baker (2001), *The Basics of IRT*;
**A** = Andrade, Tavares & Valle (2000). Ambas em `referencias/`.

### O que move o θ

A contribuição de cada resposta no passo de estimação (**B, eq. 5-1, p. 85**):

```
θ(s+1) = θ(s) + Σ aᵢ·(uᵢ − Pᵢ) / Σ aᵢ²·Pᵢ·Qᵢ
```

Sob 3PL o peso `aᵢ` vira `1,7·aᵢ·(Pᵢ−cᵢ)/(Pᵢ(1−cᵢ))`. Consequências:

- **Errar questão que estava abaixo do seu nível é o que mais derruba.**
  O termo do erro é `−peso·P`, máximo quando P é alto.
- **Acertar questão muito acima do seu nível quase não sobe.** Quando
  `(P−c) → 0` o peso zera: o modelo trata o acerto como possível chute.
- **Sem acerto casual (`c = 0`), a dificuldade é irrelevante** — trocar erro
  por acerto move o mesmo tanto em qualquer questão (medido: +0,1389 em todas).
  Com `c` do ENEM, a fácil move **3,5×** mais que a difícil.

### O que a informação de Fisher mede

**Informação = 1/variância** (**B, eq. 6-1, p. 104**). Ela mede **precisão de
estimativa**, e `SE(θ̂) = 1/√I(θ)` (**B, eq. 5-2, p. 88**).

- Informação **não** é "pontos disponíveis". Já mordeu aqui: LC C2 (língua
  estrangeira, 3–5 itens) tinha a maior informação da área e quase nada a
  entregar. Por isso a tela ordena por **ganho de um passo**, não por informação.
- A informação do 2PL é o **teto** da do 3PL (**B, p. 113**): *"getting the item
  correct by guessing should not enhance the precision"*.
- Informação é **local em θ**. "Este item é mais informativo" sem dizer em qual
  nível não significa nada.

### A escala

- `nota = 100·θ + 500` é **definição**, não aproximação (INEP, *Procedimentos
  de Análise*; **A, cap. 6**). Nunca escrever que "a fórmula erra" ou "tem
  desvio".
- A escala precisa de âncora — ponto médio e unidade (**B, cap. 7, "The Metric
  Problem", p. 134**). No ENEM a âncora é o grupo de 2009.
- O `theta_efetivo` da calibração empírica é **outra quantidade**: o θ cuja TCC
  reproduz o total médio de acertos observado. Não é correção da escala.

### O que transfere entre edições

- Equalização por itens comuns põe edições na mesma métrica (**A, cap. 4 e
  7.3; B, p. 150**). Por isso a **nota** atravessa anos.
- **Acertos não atravessam**: cada ano tem itens próprios, e E(acertos|θ) muda
  com eles.
- Parâmetros de item são **invariantes de grupo** — propriedade do item, não de
  quem respondeu (**B, p. 51**). Mas **B, p. 62** avisa: isso não quer dizer que
  as estimativas numéricas sejam idênticas entre amostras.

## Soa certo e está errado

Lista de frases tentadoras. Todas já foram escritas aqui ou quase.

| frase | veredito |
|---|---|
| "Acertar uma difícil sobe mais do que acertar uma fácil" | **invertida** sob 3PL; **vazia** sob Rasch (não há diferença) |
| "A informação é máxima quando a dificuldade da questão bate com o nível da pessoa" | verdade só em 1PL/2PL. Sob 3PL o pico fica **acima** de b — medido em **180/180** itens de 2025 (mediana +0,062, máx +0,210) |
| "O `c` é a chance de chute: 1/5 = 0,20" | **não.** Medido nos 180 itens: mediana **0,171**, varia de 0,007 a 0,399, e **68%** ficam abaixo de 0,20. `c` é a assíntota inferior estimada, não 1/alternativas |
| "A fórmula 500 + 100·θ é uma aproximação" | é **definição** |
| "Mesmo número de acertos dá a mesma nota" | não — o padrão importa. Espalhamento realista medido: **33 pontos** (p05–p95, MT, 25 acertos) |
| "Quem gabarita tem θ máximo" | MLE dá **+∞** e falha (**B, p. 89**); o número vem do priori (EAP) |
| "Mais itens dão mais precisão" | só **onde** a informação deles está; precisão é local em θ |
| "A informação de Fisher diz onde estudar rende mais ponto" | mede precisão, não ponto disponível |
| "Item difícil discrimina melhor" | dificuldade (`b`) e discriminação (`a`) são parâmetros independentes |

## Verificar algo que não está na lista

```bash
python .claude/skills/psicometria/scripts/verifica.py --help
```

O script carrega `webapp/dados/motor.json` (parâmetros reais das 16 provas
regulares) e sabe calcular P, informação, θ por máxima verossimilhança e o
efeito de trocar uma resposta. Se a afirmação é sobre o ENEM 2025, ela é
mensurável — meça antes de escrever.

# Referências de TRI

PDFs e materiais de referência sobre Teoria de Resposta ao Item.
**Esta pasta está no `.gitignore`** — material protegido por direito autoral não
vai para o repositório público. Só o [`INDICE.md`](INDICE.md) é versionado, e
ele contém apenas metadados e localização de trechos, nunca o texto integral.

## O que já está aqui

| obra | origem | situação |
|---|---|---|
| **Andrade, Tavares & Valle (2000)**, _TRI: conceitos e aplicações_ (164 p.) | [UFPR](https://docs.ufpr.br/~aanjos/CE095/LivroTRI_DALTON.pdf) — ABE/SINAPE 2000 | obtida |
| **Baker (2001)**, _The Basics of Item Response Theory_, 2ª ed. (180 p.) | [UNICAMP](https://www.ime.unicamp.br/~cnaber/Baker_Book.pdf) — ERIC Clearinghouse, **distribuição gratuita autorizada** | obtida |
| Material de aula de **Dalton F. Andrade** (UFSC) — escala de habilidade, introdução à TRI | [inf.ufsc.br/~dalton.andrade/TRI](http://www.inf.ufsc.br/~dalton.andrade/TRI/) | obtido (`dalton-ufsc/`) |
| _ENEM — Procedimentos de Análise_ (INEP, 30 p.) | dentro do ZIP dos microdados 2025 | em `data/raw/` |

As duas obras baixadas cobrem, juntas, **todo** o aparato que o projeto usa:
modelo 3PL, informação de Fisher, curva característica do teste, estimação
bayesiana e equalização por itens comuns.

## Ainda a obter (nenhuma tem versão livre legítima)

Todas exigem compra ou biblioteca. **Não baixar de Scribd, pdfcoffee, z-lib ou
espelhos afins** — são cópias não autorizadas.

| obra | para quê |
|---|---|
| **Baker & Kim**, _IRT: Parameter Estimation Techniques_, 2ª ed. (CRC/Routledge) | estimação em profundidade; endurecer o nível 3 |
| **Hambleton, Swaminathan & Rogers**, _Fundamentals of IRT_ (Sage, 1991) | há exemplar em empréstimo no [Internet Archive](https://archive.org/details/fundamentalsofit0002hamb) |
| **Embretson & Reise**, _IRT for Psychologists_ | o limite do que se pode afirmar sobre **um indivíduo** |
| **Kolen & Brennan**, _Test Equating, Scaling and Linking_, 3ª ed. ([Springer](https://link.springer.com/book/10.1007/978-1-4939-0317-7)) | equalização entre edições |

Nenhuma é bloqueante: o Baker cobre equalização (cap. 7) e o Andrade cobre
estimação bayesiana (cap. 3.6) e equalização (cap. 4) num nível já suficiente
para o que está na tela.

## Como isto entra no trabalho — a quarta lente

A regra da casa vale aqui também: **derivar de artefato, nunca transcrever de
memória.** Afirmação conceitual sobre TRI que for para a tela ou para a
documentação deve poder ser apontada a uma página de uma destas obras — do
mesmo jeito que os seeds saem do artefato oficial do INEP e a Matriz sai do PDF,
nunca de digitação.

As três lentes que já existiam — dbt test (o SQL fez o que eu quis?), Great
Expectations (o dado que chegou é o esperado?) e `ci/testa_webapp.js` (a conta
do navegador está certa?) — conferem **números e código**. Nenhuma confere
**teoria**, e foi exatamente por aí que passaram os dois erros abaixo.

**Lente 4 — teoria:** antes de publicar afirmação conceitual, apontar a página.
O registro fica no [`INDICE.md`](INDICE.md), seção "Afirmações verificadas".

### Os dois erros que motivaram isto

1. **27/07/2026** — a página "Como funciona" afirmava que *"acertar uma questão
   difícil sobe mais do que acertar uma fácil"*. Medido nos itens de MT 2025, no
   nível 1,15: acertar fácil empurra +0,55 e difícil +0,40 — o oposto. E o
   efeito dominante nem era esse: errar uma fácil custa −2,06 contra −0,09 de
   errar uma difícil.
2. **Mesma data** — atribuía a altura dos degraus à "região mais disputada".
   A causa real é a concentração de questões: 31 das 43 de MT entre 600 e 799.

Ambas eram frases plausíveis, escritas de memória, que sobreviveram a três
rodadas de verificação.

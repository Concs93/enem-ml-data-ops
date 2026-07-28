# Índice das referências de TRI

Versionado de propósito: contém só **metadados e onde encontrar cada assunto**,
nunca o texto das obras. Os arquivos em si ficam fora do Git
(ver [LEIA-ME.md](LEIA-ME.md)).

---

## 1. Andrade, Tavares & Valle (2000) — *Teoria da Resposta ao Item: conceitos e aplicações*

**Arquivo:** `Andrade-Tavares-Valle-2000-TRI.pdf` (164 páginas) ·
**Editora:** Associação Brasileira de Estatística (ABE), SINAPE 2000 ·
**Distribuição pública:** <https://docs.ufpr.br/~aanjos/CE095/LivroTRI_DALTON.pdf> (UFPR)

**Por que esta é a referência principal:** é a obra que o **próprio INEP cita**
no documento *"ENEM — Procedimentos de Análise"* ao descrever a equalização.
Alinhamento máximo entre o que o site afirma e o que o exame faz.

Autores: **Dalton Francisco de Andrade** (hoje UFSC; à época UFC),
**Heliton Ribeiro Tavares** (UFPA), **Raquel da Cunha Valle** (Fundação Carlos
Chagas).

### Estrutura

| cap. | assunto | p. |
|---|---|---|
| 1 | Introdução | 3 |
| 2 | Modelos matemáticos (CCI, informação, modelos de 1–3 parâmetros) | 7 |
| 3 | Estimação numa única população (itens, habilidades, MV marginal, **bayesiana**) | 27 |
| 4 | **Equalização** (tipos, problemas de estimação, a posteriori) | 79 |
| 5 | Estimação com duas ou mais populações | 93 |
| 6 | **A escala de habilidade** — construção, interpretação e aplicação | 109 |
| 7 | Recursos computacionais — **BILOG e BILOG-MG**, e a equalização neles | 123 |
| 8 | Considerações gerais | 135 |

### Onde conferir cada afirmação do projeto

| assunto | páginas |
|---|---|
| modelo de 3 parâmetros / curva característica do item | 11, 20–23 |
| parâmetro **a** (discriminação) e seu peso | 19–24, 27–29, 33–34 |
| parâmetro **c** (acerto casual) | 14, 20–21, 27, 44–45 |
| estimação bayesiana / esperança a posteriori (EAP) | 35, 41, 85–87 |
| quadratura (os "40 pontos" que o INEP usa) | 69–76 |
| **equalização por itens comuns** | 89–104, 130 |
| itens âncora | 111, 120–122, 129 |
| construção e **interpretação de escalas** | 109–122 |
| BILOG-MG e a equalização nele | 128–132 |

### Ligações diretas com este projeto

- **Cap. 4 e 7.3** sustentam o banco multiedição (2020–2025): é a teoria por
  trás de somar itens de anos diferentes na mesma métrica.
- **Cap. 3.6 (bayesiana)** é o método do nível 3 — a re-estimação por EAP que
  já foi validada em laboratório (r = 0,9907 contra a nota oficial).
- **Cap. 6** é a régua para a página "Como funciona": o que se pode e o que não
  se pode afirmar ao interpretar uma escala.
- **Cap. 2** é a régua para as afirmações sobre o que move a nota — assunto dos
  dois erros conceituais registrados no LEIA-ME.

---

## 2. Baker (2001) — *The Basics of Item Response Theory*, 2ª ed.

**Arquivo:** `Baker-2001-Basics-of-IRT.pdf` (180 páginas) ·
**Editora:** ERIC Clearinghouse on Assessment and Evaluation, ISBN 1-886047-03-0 ·
**Distribuição gratuita autorizada** pela própria editora ·
**Espelho acadêmico:** <https://www.ime.unicamp.br/~cnaber/Baker_Book.pdf> (UNICAMP)

**Para que serve aqui:** é o texto que *deriva* o que o Andrade apresenta.
Onde o produto precisa explicar um mecanismo (e não só citá-lo), a conta está
neste livro, com exemplo numérico fechado.

| cap. | assunto | p. |
|---|---|---|
| 1–2 | curva característica do item; modelos de 1, 2 e 3 parâmetros | 5, 21 |
| 3 | estimação dos parâmetros do item; **invariância de grupo** | 47, 51 |
| 4 | **curva característica do teste** | 65 |
| 5 | **estimação da habilidade de um examinando** (eq. 5-1) | 85 |
| 6 | **função de informação** (item, teste, e como interpretá-la) | 106 |
| 7 | calibração, **o problema da métrica**, e **equalização** | 133, 134, 150 |
| 8 | montar prova a partir de banco pré-calibrado | 156 |

Ligações diretas: **cap. 4** é a curva que a calibração empírica inverte;
**cap. 5** é o motor do nível 3; **cap. 6** é o que ordena as prioridades;
**cap. 7** é o banco multiedição.

---

## 3. Material de aula de Dalton F. Andrade (UFSC)

Pasta `dalton-ufsc/`, de <http://www.inf.ufsc.br/~dalton.andrade/TRI/>:

| arquivo | conteúdo |
|---|---|
| `Escala-de-Habilidade.ppt` | construção e ancoragem da escala |
| `Exemplos-escala-de-habilidades.doc` | exemplos de interpretação por nível |
| `TRI-Introducao-2005.ppt` | introdução didática |
| `TRI-IASI-Rosario-2006.ppt` | versão ampliada (IASI 2006) |

Os dois primeiros são a régua para a página "Como funciona": tratam de como se
**descreve** um nível da escala em linguagem de conteúdo — que é exatamente o
que o mapa do aluno faz ao dizer o que estudar.

---

## 4. Afirmações verificadas (lente 4 — teoria)

Registro do que já foi conferido contra o texto, para não ser re-litigado.

### O peso de acertar uma questão fácil vs. uma difícil

**Afirmação na tela:** *"errar uma questão que estava abaixo do seu degrau é o
que mais puxa para baixo; acertar uma bem acima empurra pouco — o modelo
considera que pode ter sido chute."*

**Fonte:** Baker, eq. 5-1 (p. 85), o passo de Newton-Raphson

```
θ(s+1) = θ(s) + Σ aᵢ·(uᵢ − Pᵢ) / Σ aᵢ²·Pᵢ·Qᵢ
```

O numerador é a contribuição de cada resposta. Sob 3PL o peso `aᵢ` vira
`1,7·aᵢ·(Pᵢ−cᵢ)/(Pᵢ(1−cᵢ))`, e é aí que está tudo:

| modelo | efeito de trocar um erro por acerto |
|---|---|
| 2PL / Rasch (`c = 0`) | **idêntico para toda questão** (+0,1389 na simulação): a dificuldade é irrelevante, só a discriminação `a` importa |
| 3PL (o do ENEM) | fácil move **3,5×** mais que difícil (+0,122 vs +0,035) |

**Conclusão:** a assimetria inteira é causada pelo parâmetro de acerto casual.
Quando `(P−c) → 0` — questão muito acima do nível da pessoa — o acerto é
descontado como chute e quase não move o θ. Confere com a medição feita nos
itens reais de MT 2025 (+0,55 fácil vs +0,40 difícil; e errar fácil −2,06
contra −0,09 de errar difícil).

Corolário que vale registrar: a frase *"acertar uma difícil sobe mais"* não é
só imprecisa — sob Rasch ela é **vazia** (não há diferença) e sob 3PL é
**invertida**.

---

## 5. A obter (nenhuma com versão livre legítima)

| obra | para quê |
|---|---|
| **Baker & Kim**, *IRT: Parameter Estimation Techniques*, 2ª ed. | estimação em profundidade |
| **Hambleton, Swaminathan & Rogers**, *Fundamentals of IRT* | [empréstimo no Internet Archive](https://archive.org/details/fundamentalsofit0002hamb) |
| **Embretson & Reise**, *IRT for Psychologists* | o limite do que se afirma sobre um indivíduo |
| **Kolen & Brennan**, *Test Equating, Scaling and Linking*, 3ª ed. | equalização entre edições |
| Produção de **Adriano Ferreti Borgatto** (UFSC) | escalas e aplicações; artigos abertos na SciELO e no repositório da UFSC |

---

## 6. Fonte primária do ENEM (não é livro, mas manda mais)

`data/raw/enem_procedimentos_de_analise.pdf` — *"ENEM — Procedimentos de
Análise"*, publicado pelo INEP dentro do ZIP dos microdados de 2025 (30 p.).
Descreve calibração, DIF, estimação por EAP, equalização e a escala (500,100).
**Em conflito entre livro e este documento, vale este** — ele descreve o que o
exame de fato faz.

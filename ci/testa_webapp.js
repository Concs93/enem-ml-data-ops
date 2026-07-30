/*
 * Testes de regressao do webapp -- a unica camada do projeto que nao tinha
 * verificacao automatizada, e (nao por coincidencia) a unica onde a auditoria
 * adversarial achou erro de conta de verdade (2026-07-27).
 *
 * Carrega o CODIGO REAL de webapp/index.html num sandbox com DOM falso --
 * nada de replica que deriva em silencio. Requer webapp/dados/motor.json
 * gerado (python -m export.export_site).
 *
 * Cada caso daqui e um bug que JA EXISTIU:
 *  1. curva nota<->acertos com trecho plano -> "+40 pontos" fantasma no piso
 *  2. clamp de theta em 3,00 contra grade que vai a 5,00 -> MT 905 com +0
 *  3. extrapolacao sem teto -> "+654 pontos" para aluno de nota 340
 *  4. gabarito de outra edicao aceito em nota media -> diagnostico falso
 *
 * Uso:  node ci/testa_webapp.js
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const RAIZ = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(RAIZ, "webapp", "index.html"), "utf8");
const motor = JSON.parse(fs.readFileSync(path.join(RAIZ, "webapp", "dados", "motor.json"), "utf8"));

// ---- DOM falso: o minimo que o script toca no boot -------------------------
function elemento() {
  return {
    value: "", textContent: "", innerHTML: "", className: "", open: false,
    style: {}, dataset: {},
    classList: { add() {}, remove() {}, toggle() {} },
    addEventListener() {}, setAttribute() {}, scrollIntoView() {},
  };
}
const els = {};
const documento = {
  getElementById: id => (els[id] = els[id] || elemento()),
  querySelectorAll: () => [],
  addEventListener() {},
};

const sandbox = {
  document: documento,
  fetch: () => Promise.resolve({ json: () => Promise.resolve(motor) }),
  matchMedia: () => ({ matches: false }),
  console, Math, JSON, Number, String, Object, Array, Promise, Set, Map,
  isFinite, parseFloat, parseInt,
};
vm.createContext(sandbox);

const script = html.split("<script>")[1].split("</script>")[0];
// let/const do topo do script nao viram propriedades do contexto do vm; o
// epilogo exporta o que os testes precisam (getters, porque M e TH_MAX so
// sao atribuidos quando o fetch falso resolve)
const epilogo = `
;globalThis.X = {
  get M(){ return M }, get TH_MAX(){ return TH_MAX },
  get TH_MIN(){ return TH_MIN }, get PASSO_GRADE(){ return PASSO_GRADE }, k,
  faixaDisponivel, curvaAcertos, notaPorAcertos, motorArea,
  corrigeCaderno, padraoSuspeito, cartaoArea, cartaoEstudo,
  erroPadrao, itensDaArea, get NOS_QUAD(){ return NOS_QUAD }, resumoDesc,
  limitesNota, reparte, V, cortesDesempenho,
};`;
vm.runInContext(script + epilogo, sandbox);
const X = sandbox.X;

// ---- execucao dos testes ---------------------------------------------------
const falhas = [];
function caso(nome, fn) {
  try { fn(); console.log(`  ok  ${nome}`); }
  catch (e) { falhas.push(nome); console.log(`  XX  ${nome}: ${e.message}`); }
}
function espera(cond, msg) { if (!cond) throw new Error(msg); }

function areaDe(sig, nota, lin) {
  const faixa = X.faixaDisponivel(sig, lin, nota);
  const cal = X.M.calibracao[X.k(sig, sig === "LC" ? lin : null, faixa)];
  const theta = cal[0].toFixed(2);
  return { sig, nota, faixa, theta,
           perfil: X.M.perfil[X.k(sig, sig === "LC" ? lin : null, theta)] || [] };
}
function totalDaAreaDe(a) {
  const mot = X.motorArea(a);
  let dT = 0;
  for (const h of a.perfil) if (h[4] > 0) dT += mot.tetoHab(h[0], h[4], h[1]);
  return mot.ganho(dT).pts;
}
function passoDaArea(a) {
  const mot = X.motorArea(a);
  let dE = 0;
  for (const h of a.perfil) if (h[4] > 0) dE += mot.agoraHab(h[0], h[4], h[1]);
  return { mot, pts: mot.ganho(dE).pts };
}

(async () => {
  // o boot do script resolve o fetch em microtarefas
  await new Promise(r => setTimeout(r, 0));
  espera(X.M, "motor.json nao carregou no sandbox");

  console.log("\n== grade derivada dos dados ==");
  caso("TH_MAX vem da grade (>= 5), nao de constante", () =>
    espera(X.TH_MAX >= 5, `TH_MAX = ${X.TH_MAX}`));

  console.log("\n== curva nota<->acertos ==");
  for (const [sig, lin] of [["MT", null], ["CH", null], ["CN", null], ["LC", 0], ["LC", 1]]) {
    caso(`curva ${sig}${lin !== null ? "/" + lin : ""} estritamente crescente apos dedup`, () => {
      const c = X.curvaAcertos(sig, lin);
      espera(c.length > 10, `curva curta demais (${c.length})`);
      for (let i = 1; i < c.length; i++)
        espera(c[i].E > c[i - 1].E, `E nao cresce em ${c[i - 1].nota}->${c[i].nota}`);
    });
  }
  caso("extrapolacao limitada ao teto FISICO da escala (maior nota real)", () => {
    const c = X.curvaAcertos("MT", null);
    espera(c.teto && Math.abs(c.teto - X.M.maxNota["MT|_"]) < 1e-9,
      `curva sem teto fisico (teto=${c.teto})`);
    const r = X.notaPorAcertos(c, c[c.length - 1].E + 50);
    espera(r.alem, "deveria marcar alem");
    espera(r.nota <= c.teto + 1e-9, `nota extrapolada ${r.nota} > teto ${c.teto}`);
    espera(r.nota >= c[c.length - 1].nota, "extrapolacao abaixo da propria curva");
  });
  caso("CH: o teto fisico (856,4) fica ACIMA do fim da curva calibravel (~775)", () => {
    // a calibracao corta faixas com n<100, mas a escala vai alem -- o site
    // nao pode dizer menos que a maior nota real (um usuario conferiu)
    const c = X.curvaAcertos("CH", null);
    espera(c.teto > c[c.length - 1].nota + 20,
      `teto ${c.teto} vs fim da curva ${c[c.length - 1].nota}`);
  });

  console.log("\n== piso da calibracao (regiao de prova em branco) ==");
  caso("MT 340: area marcada como piso", () =>
    espera(passoDaArea(areaDe("MT", 340, null)).mot.piso === true, "piso nao marcado"));
  caso("MT 340: ganho de milesimo NAO vira pontos fantasma", () => {
    const { mot } = passoDaArea(areaDe("MT", 340, null));
    espera(mot.ganho(0.002).pts <= 1, `dA=0,002 rendeu +${mot.ganho(0.002).pts}`);
  });
  caso("MT 340: um acerto vale o gradiente real (5 a 40 pts), nao 0 nem 200", () => {
    const { mot } = passoDaArea(areaDe("MT", 340, null));
    const p = mot.ganho(1).pts;
    espera(p >= 5 && p <= 40, `1 acerto rendeu +${p}`);
  });

  console.log("\n== topo da escala (o clamp que zerava MT 900+) ==");
  caso("MT 905: passo de estudo rende > 0 pontos", () => {
    const { pts } = passoDaArea(areaDe("MT", 905, null));
    espera(pts > 0, `ptsAgora = ${pts}`);
  });
  caso("MT 613: passo da area inteira na faixa sa (20 a 150 pts)", () => {
    // meio desvio GLOBAL de theta vale ~68-90 pontos pela reta de
    // equalizacao (135 x 0,5); o teste guarda contra 0 e contra absurdo,
    // nao contra o valor legitimo
    const { pts } = passoDaArea(areaDe("MT", 613, null));
    espera(pts >= 20 && pts <= 150, `ptsAgora = ${pts}`);
  });

  console.log("\n== guarda de padrao (gabarito de outra edicao/cor) ==");
  const cpMT = Object.keys(X.M.provas)
    .find(c => X.M.provas[c].area === "MT" && X.M.provas[c].cor === "Azul");
  const thetaMT520 = X.M.calibracao["MT|_|520"][0];
  caso("vetor aleatorio plano com nota 520 e recusado", () => {
    const txt = Array.from({ length: 45 }, (_, i) => "ABCDE"[i % 5]).join("");
    const corr = X.corrigeCaderno("MT", cpMT, null, txt, thetaMT520);
    espera(X.padraoSuspeito(corr, 520) === true, "vetor plano passou");
  });
  caso("vetor coerente com nota 520 passa", () => {
    const its = [...X.M.provas[cpMT].itens].sort((x, y) => x[0] - y[0]);
    const txt = its.map(it => {
      const gab = it[2], pa = it[4], pb = it[5], pc = it[6];
      if (pa == null) return "A";
      const P = pc + (1 - pc) / (1 + Math.exp(-1.7 * pa * (thetaMT520 - pb)));
      return P >= 0.5 ? gab : (gab === "A" ? "B" : "A");   // deterministico
    }).join("");
    const corr = X.corrigeCaderno("MT", cpMT, null, txt, thetaMT520);
    espera(X.padraoSuspeito(corr, 520) === false, "vetor coerente recusado");
  });

  console.log("\n== as somas fecham na tela (o que o leitor confere) ==");
  // dentro de cada bloco de competencia, os "ate +N" das habilidades tem de
  // somar o "ate +N" do cabecalho -- foi exatamente a conferencia que o dono
  // do produto fez a mao e nao fechava no desenho anterior
  function confereSomas(html, rotulo) {
    const blocos = html.split('<details class="compbloco"').slice(1);
    let conferidos = 0;
    for (const b of blocos) {
      const cab = b.match(/class="cval">até \+(\d+) ponto/);
      if (!cab) continue;                       // bloco fechado/dominado
      const total = Number(cab[1]);
      const corpo = b.split("</summary>")[1] || "";
      const partes = [...corpo.matchAll(/<b>até \+(\d+) ponto/g)].map(m => Number(m[1]));
      if (!partes.length) continue;
      const soma = partes.reduce((s, v) => s + v, 0);
      // depois do conserto (piso de +1 descontado da maior fatia), a soma
      // fecha exata salvo o caso raro em que a maior fatia nao absorve
      espera(Math.abs(soma - total) <= 1,
        `${rotulo}: habilidades somam +${soma}, cabecalho diz +${total}`);
      conferidos++;
    }
    espera(conferidos >= 3, `${rotulo}: so ${conferidos} blocos conferiveis`);
  }
  caso("diagnostico MT 613: fatias das habilidades somam o teto da competencia", () =>
    confereSomas(X.cartaoArea(areaDe("MT", 613, null)), "diagnostico MT 613"));

  // e um andar acima: as competencias somam o "Fechando tudo", que nunca
  // passa da maior nota real da area -- o achado do usuario que somou tudo
  function confereTotal(a, rotulo, maxArea) {
    // a linha "Fechando tudo" saiu da tela (o comparativo ja mostra o mesmo
    // numero). A invariante continua: as competencias tem de somar o teto da
    // area -- so que agora o total vem do MOTOR, nao de um texto na tela
    const html = X.cartaoArea(a), nota = a.nota;
    espera(!/Fechando tudo/.test(html), `${rotulo}: "Fechando tudo" voltou ao cartao`);
    const total = totalDaAreaDe(a);
    const comps = [...html.matchAll(/class="cval">até \+(\d+) ponto/g)].map(x => Number(x[1]));
    espera(comps.length >= 3, `${rotulo}: poucas competencias (${comps.length})`);
    const soma = comps.reduce((s, v) => s + v, 0);
    espera(Math.abs(soma - total) <= 1,
      `${rotulo}: competencias somam +${soma}, total diz +${total}`);
    espera(nota + total <= maxArea + 1,
      `${rotulo}: ${nota}+${total} passa do maximo real ${maxArea}`);
  }
  caso("CH 565: competencias somam o total, e nada passa de 856,4", () =>
    confereTotal(areaDe("CH", 565, null), "diagnostico CH 565", X.M.maxNota["CH|_"]));
  caso("MT 613: competencias somam o total, e nada passa de 980,3", () =>
    confereTotal(areaDe("MT", 613, null), "diagnostico MT 613", X.M.maxNota["MT|_"]));

  // o cartao da PROXIMA usa outra moeda: QUESTOES (peso tipico), nunca pontos
  // -- pontos ali mirariam uma prova que nao existe, com escala de 2025 e
  // transferencia de ordem fraca (rho +0,27). Decisao do dono do produto
  function confereEstudo(html, rotulo) {
    espera(!/Fechando tudo/.test(html), `${rotulo}: "Fechando tudo" nao pertence a este cartao`);
    espera(!/até \+\d+ ponto/.test(html), `${rotulo}: pontos nao pertencem a este cartao`);
    const comps = [...html.matchAll(/class="cval">~([\d,]+) questões/g)]
      .map(m => Number(m[1].replace(",", ".")));
    espera(comps.length >= 5, `${rotulo}: poucas competencias (${comps.length})`);
    const soma = comps.reduce((s, v) => s + v, 0);
    espera(Math.abs(soma - 45) <= 0.5,
      `${rotulo}: pesos somam ${soma.toFixed(1)}, esperado ~45`);
  }
  caso("estudo MT 613: moeda e QUESTAO, e os pesos somam as 45 da prova", () =>
    confereEstudo(X.cartaoEstudo(areaDe("MT", 613, null)), "estudo MT 613"));
  caso("estudo CH 565: moeda e QUESTAO, e os pesos somam as 45 da prova", () =>
    confereEstudo(X.cartaoEstudo(areaDe("CH", 565, null)), "estudo CH 565"));

  // ---------------------------------------------------------------------
  // A FOLGA DA MEDIDA. A prova nao mede todos os niveis com a mesma precisao,
  // e o conselho passou a ser integrado sobre a faixa plausivel da nota em vez
  // de calculado num ponto. O que estes casos travam e a consequencia visivel:
  // a mesma pessoa nao pode ver uma competencia em "comece por aqui" e, um
  // erro-padrao adiante, a mesma competencia em "mais distante"
  console.log("\n== a folga da medida (SE) e a estabilidade do conselho ==");

  const N_ITENS = { MT: 43, CH: 45, CN: 42 };
  for (const sig in N_ITENS) {
    caso(`itensDaArea ${sig}: ${N_ITENS[sig]} itens validos, com os 3 parametros`, () => {
      const it = X.itensDaArea(sig, null);
      espera(it.length === N_ITENS[sig], `${sig}: ${it.length} itens, esperado ${N_ITENS[sig]}`);
      espera(it.every(o => o.pa > 0 && o.pc >= 0 && o.pc < 1),
        `${sig}: item com parametro invalido`);
    });
  }
  // em LC o conjunto muda com a lingua: 5 da lingua + 40 comuns
  for (const lin of [0, 1]) {
    caso(`itensDaArea LC/${lin}: 45 itens (5 da lingua + 40 comuns)`, () => {
      const it = X.itensDaArea("LC", lin);
      espera(it.length === 45, `LC/${lin}: ${it.length} itens, esperado 45`);
    });
  }

  caso("SE cai do piso ao miolo e sobe de novo no topo (a prova mede melhor no meio)", () => {
    for (const sig of ["MT", "CH", "CN"]) {
      const baixo = X.erroPadrao(sig, null, -1.0);   // ~nota 400
      const meio  = X.erroPadrao(sig, null,  1.5);   // ~nota 650
      espera(baixo > meio, `${sig}: SE embaixo (${baixo.toFixed(3)}) <= no meio (${meio.toFixed(3)})`);
      espera(meio > 0.05 && baixo < 2.0,
        `${sig}: SE fora de faixa plausivel (${meio.toFixed(3)} / ${baixo.toFixed(3)})`);
    }
  });

  // grupos da tela, a partir do motor real: >=55% e >=22% do maior passo
  function gruposEm(sig, nota, lin, desloca) {
    const base = areaDe(sig, nota, lin);
    const se = X.erroPadrao(sig, lin, Number(base.theta));
    const th = Math.max(X.TH_MIN, Math.min(X.TH_MAX, Number(base.theta) + desloca * se));
    // encaixa na grade, igual ao motor -- sem isso a chave nao existe e o caso
    // e descartado em silencio (foi assim que a primeira versao deste teste
    // avaliou 47 competencias achando que avaliava 140)
    const t = (Math.round(th / X.PASSO_GRADE) * X.PASSO_GRADE).toFixed(2);
    const a = { sig, nota, faixa: base.faixa, theta: t,
                perfil: X.M.perfil[X.k(sig, sig === "LC" ? lin : null, t)] || [] };
    if (!a.perfil.length) return null;
    const mot = X.motorArea(a);
    const por = {};
    for (const h of a.perfil) {
      if (!(h[4] > 0)) continue;
      const c = (X.M.matriz[X.k(sig, h[0])] || {}).comp;
      if (c) por[c] = (por[c] || 0) + mot.agoraHab(h[0], h[4], h[1]);
    }
    const top = Math.max(...Object.values(por)) || 1e-9;
    const g = {};
    for (const c in por) g[c] = por[c] >= 0.55 * top ? 1 : por[c] >= 0.22 * top ? 2 : 3;
    return g;
  }
  // conta quantas competencias pulam DOIS grupos ("comece aqui" <-> "mais
  // distante") dentro de um erro-padrao. Medido antes da correcao: 0,3% no
  // miolo e 11,7% abaixo de 500; depois, 0,0% e 5,6%
  function pulos(casos) {
    let pula = 0, total = 0;
    for (const [sig, nota, lin] of casos) {
      const g0 = gruposEm(sig, nota, lin, 0);
      const gm = gruposEm(sig, nota, lin, -1);
      const gp = gruposEm(sig, nota, lin, +1);
      if (!g0 || !gm || !gp) continue;
      for (const c in g0) {
        if (gm[c] == null || gp[c] == null) continue;
        total++;
        if (Math.max(g0[c], gm[c], gp[c]) - Math.min(g0[c], gm[c], gp[c]) >= 2) pula++;
      }
    }
    return { pula, total };
  }

  // ESTE e o caso que trava a mudanca. Os de estabilidade abaixo NAO travam:
  // a estabilidade e alta com e sem a integracao, entao eles passam verdes com
  // o bug de volta (verificado removendo o encaixe na grade: 32/32 verde).
  // O que so vale com a integracao ativa e a DIFERENCA contra o calculo
  // pontual, e ela tem de ser grande onde o SE e grande
  // ESTE e o caso que trava a mudanca, e ele precisou de duas tentativas.
  //
  // A 1a versao so exigia que o resultado DIFERISSE do calculo pontual. Nao
  // servia: o modo de falha real nao e "a integracao some", e "a integracao
  // perde nos em silencio". Sem o encaixe na grade, `toFixed(2)` arredonda
  // para 0,01 contra uma grade de 0,05, entao ~1 em cada 5 nos sobrevive por
  // coincidencia -- o resultado muda, so que com pesos errados. Verificado:
  // com o bug de volta, a suite inteira (32 casos) ficava VERDE.
  //
  // A versao que trava refaz a quadratura por fora e exige IGUALDADE. Se
  // qualquer no for descartado, os numeros divergem.
  caso("a integracao usa os 7 nos: bate com a quadratura refeita por fora", () => {
    const snap = v => (Math.round(Math.max(X.TH_MIN, Math.min(X.TH_MAX, v))
                       / X.PASSO_GRADE) * X.PASSO_GRADE).toFixed(2);
    for (const [sig, lin, nota] of
         [["MT", null, 400], ["CH", null, 400], ["CN", null, 430],
          ["MT", null, 620], ["LC", 0, 450]]) {
      const a = areaDe(sig, nota, lin);
      const th = Number(a.theta);
      const se = X.erroPadrao(sig, lin, th);
      const thUp = Math.min(th + 0.5, X.TH_MAX);
      const recua = thUp === th;
      const g = v => X.M.perfil[X.k(sig, sig === "LC" ? lin : null, snap(v))];

      // a mesma media que o motor deve estar fazendo, refeita aqui
      const eR = {}, eU = {};
      let tot = 0, usados = 0;
      for (const [z, w] of X.NOS_QUAD) {
        const c = Math.max(X.TH_MIN, Math.min(X.TH_MAX, th + z * se));
        const lo = recua ? Math.max(X.TH_MIN, c - 0.5) : c;
        const hi = recua ? c : Math.min(X.TH_MAX, c + 0.5);
        const pl = g(lo), ph = g(hi);
        espera(pl && ph, `${sig} ${nota}: no z=${z} caiu fora da grade — `
          + "toda a serie tem de existir apos o encaixe");
        for (const h of pl) eR[h[0]] = (eR[h[0]] || 0) + w * h[1];
        for (const h of ph) eU[h[0]] = (eU[h[0]] || 0) + w * h[1];
        tot += w; usados++;
      }
      espera(usados === X.NOS_QUAD.length,
        `${sig} ${nota}: so ${usados} de ${X.NOS_QUAD.length} nos usados`);
      for (const h in eR) { eR[h] /= tot; eU[h] /= tot; }

      let esperado = 0;
      for (const h of a.perfil)
        if (h[4] > 0 && eR[h[0]] != null && eU[h[0]] != null)
          esperado += h[4] * Math.max(eU[h[0]] - eR[h[0]], 0) / 100;

      const mot = X.motorArea(a);
      let obtido = 0;
      for (const h of a.perfil) if (h[4] > 0) obtido += mot.agoraHab(h[0], h[4], h[1]);

      espera(esperado > 0, `${sig} ${nota}: quadratura de referencia deu zero`);
      espera(Math.abs(obtido - esperado) <= 1e-9 * Math.max(1, esperado),
        `${sig} ${nota}: motor deu ${obtido.toFixed(6)}, quadratura completa `
        + `da ${esperado.toFixed(6)} — algum no esta sendo descartado`);
    }
  });

  caso("miolo da escala (520-700): NENHUMA competencia pula de 'comece aqui' a 'mais distante'", () => {
    const casos = [];
    for (const sig of ["MT", "CH", "CN"]) for (const n of [520, 560, 600, 640, 680])
      casos.push([sig, n, null]);
    for (const n of [520, 560, 600, 640, 680]) casos.push(["LC", n, 0]);
    const { pula, total } = pulos(casos);
    espera(total >= 100, `poucos casos avaliados (${total})`);
    espera(pula === 0, `${pula} de ${total} competencias pulam 2 grupos no miolo`);
  });

  caso("faixa baixa (400-500): instabilidade contida (era 11,7% sem a integracao)", () => {
    const casos = [];
    for (const sig of ["MT", "CH", "CN"]) for (const n of [400, 430, 460, 500])
      casos.push([sig, n, null]);
    for (const n of [400, 430, 460, 500]) casos.push(["LC", n, 0]);
    const { pula, total } = pulos(casos);
    espera(total >= 80, `poucos casos avaliados (${total})`);
    espera(pula / total <= 0.08,
      `${pula} de ${total} (${(100 * pula / total).toFixed(1)}%) pulam 2 grupos; teto do teste 8%`);
  });

  // a ressalva da folga aparece SO onde a medida e larga -- no miolo ela seria
  // ruido, e no piso ja existe um aviso mais forte que a substitui
  // CN 400 tem SE ~49 pontos; CH 450 (~23) NAO dispara, e esta certo -- e uma
  // precisao proxima da do miolo. O limiar e meio passo, nao "nota baixa"
      // o corte por resolucao da fonte: acerto_esperado vem com round(...,1), entao
  // residuo abaixo de meia casa e ruido -- sem o corte ele virava "+1 ponto"
  // colado a "acerto tipico ~100%", tirando o ponto de quem de fato rende
  caso("habilidade que a faixa da como 100% nao vira 'ate +1 ponto'", () => {
    let achou = 0;
    for (const [sig, nota] of [["MT", 880], ["CH", 760], ["CN", 800], ["MT", 920]]) {
      const a = areaDe(sig, nota, null);
      if (!a.perfil.length) continue;
      const mot = X.motorArea(a);
      for (const h of a.perfil) {
        if (!(h[4] > 0) || h[1] < 99.95) continue;
        achou++;
        espera(mot.tetoHab(h[0], h[4], h[1]) === 0,
          `${sig} ${nota} H${h[0]}: esperado ${h[1]}% e teto ${mot.tetoHab(h[0], h[4], h[1])}`);
      }
    }
    espera(achou >= 3, `so ${achou} habilidades em 100% encontradas para testar`);
  });

  // O cabecalho fechado leva so o inicio da descricao oficial da Matriz (que
  // tem 21 a 33 palavras). Dois defeitos ja aconteceram aqui: um caractere de
  // controle 0x08 dentro da regex, que a fazia nunca casar e passava
  // despercebido porque o terminal renderiza backspace apagando o vizinho; e
  // `[\s]*` no lugar de `[\s]+`, que cortava no meio da palavra
  // ("construcoes humanas" -> "construcoes human"). Nenhum dos dois aparece
  // sem comparar o resumo com o texto integral.
  caso("resumo da competencia: prefixo do texto oficial e em palavra inteira", () => {
    const vistos = new Set();
    let n = 0;
    for (const ch in X.M.matriz) {
      const d = X.M.matriz[ch].compdesc;
      if (!d || vistos.has(d)) continue;
      vistos.add(d); n++;
      const r = X.resumoDesc(d);
      const corpo = r.endsWith("…") ? r.slice(0, -1) : r;
      espera(d.startsWith(corpo), `resumo nao e prefixo do original: ${corpo.slice(0, 50)}`);
      if (r.endsWith("…") && corpo.length < d.length) {
        const prox = d[corpo.length];
        espera(!/[\wÀ-ÿ-]/.test(prox),
          `corte no meio da palavra: "...${corpo.slice(-25)}" seguido de "${d.slice(corpo.length, corpo.length + 12)}"`);
      }
      espera(corpo.split(/\s+/).length <= 16, `resumo longo demais (${corpo.split(/\s+/).length} palavras)`);
    }
    espera(n >= 30, `so ${n} descricoes de competencia encontradas`);
  });
  // nenhum caractere de controle no fonte: foi assim que o 0x08 entrou
  caso("o fonte do site nao tem caractere de controle invisivel", () => {
    const bruto = require("fs").readFileSync(path.join(RAIZ, "webapp", "index.html"), "utf8");
    const achados = [...bruto].filter(c => c.charCodeAt(0) < 32 && !"\n\r\t".includes(c));
    espera(achados.length === 0,
      `${achados.length} caractere(s) de controle: ${[...new Set(achados.map(c => "0x" + c.charCodeAt(0).toString(16)))].join(", ")}`);
  });

  // As questoes concretas do cartao de estudo: recomendar conteudo sem dizer
  // onde pratica-lo deixa o trabalho todo para a pessoa
  caso("toda habilidade que pontua no cartao de estudo tem questao citada", () => {
    let semEndereco = [];
    for (const chave in X.M.estudo) {
      const [area, lingua, theta] = chave.split("|");
      if (Math.abs(Number(theta) - 1.0) > 1e-9) continue;   // um nivel basta
      for (const linha of X.M.estudo[chave]) {
        const [hab, esp, ganho, pri, ipp] = linha;
        if (!(ipp > 0)) continue;
        const qs = X.M.questoes[X.k(area, lingua === "_" ? null : Number(lingua), hab)];
        if (!qs || !qs.length) semEndereco.push(`${area}/${lingua} H${hab}`);
      }
    }
    espera(semEndereco.length === 0,
      `${semEndereco.length} habilidades sem questao: ${semEndereco.slice(0, 5).join(", ")}`);
  });
  caso("as questoes citadas existem no caderno: edicao 2020-2025 e posicao valida", () => {
    let n = 0;
    for (const chave in X.M.questoes) {
      const [area] = chave.split("|");
      const limite = area === "LC" ? 50 : 45;
      for (const [ed, pos] of X.M.questoes[chave]) {
        n++;
        espera(ed >= 2020 && ed <= 2025, `${chave}: edicao ${ed} fora de 2020-2025`);
        espera(pos >= 1 && pos <= limite,
          `${chave}: posicao ${pos} fora de 1-${limite} (${area})`);
      }
    }
    espera(n > 1000, `so ${n} questoes no banco de enderecos`);
  });
  caso("em LC as questoes de lingua vem marcadas ING/ESP", () => {
    // as 5 questoes da secao de lingua sao diferentes entre ingles e espanhol;
    // sem marca, "Q4 ENEM 2025" em LC nao diz qual caderno abrir
    for (const [lin, marca] of [[0, "ING"], [1, "ESP"]]) {
      const qs = X.M.questoes[X.k("LC", lin, 8)] || [];   // H8: so itens de lingua
      espera(qs.length >= 5, `LC/${lin} H8: so ${qs.length} questoes`);
      espera(qs.every(q => q[2] === lin),
        `LC/${lin} H8: questao sem a marca de lingua correta`);
      // o motor le a lingua do DOM, nao do objeto da area -- sem isto o
      // sandbox renderiza sempre ingles e o teste passa por engano
      documento.getElementById("lingua").value = String(lin);
      const h = X.cartaoEstudo(areaDe("LC", 600, lin));
      espera(h.includes(marca), `cartao de LC/${lin} nao mostra ${marca}`);
    }
    // as comuns NAO levam marca -- marcar tudo faria a distincao perder sentido
    documento.getElementById("lingua").value = "0";
    const comuns = (X.M.questoes[X.k("LC", 0, 16)] || []).filter(q => q[2] != null);
    espera(comuns.length === 0, `H16 (comum) tem ${comuns.length} questoes marcadas`);
  });
  caso("a tela declara a cor do caderno (numero sem cor e endereco errado)", () => {
    // as quatro cores sao a mesma prova reordenada: Q7 do azul e outra questao
    // no amarelo. Citar o numero sem a cor erra em tres de quatro cadernos
    const h = X.cartaoEstudo(areaDe("MT", 613, null));
    espera(/caderno azul/i.test(h), "cartao de estudo nao diz a cor do caderno");
  });

  // O card da area anuncia "1o conteudo: ate +X" e o cartao abre com essa
  // mesma competencia -- os dois numeros TEM de ser identicos. Ja divergiram:
  // a reparticao estava escrita duas vezes e o comparativo pulava o desconto
  // do arredondamento, anunciando +68 para o que o cartao mostrava como +66
  caso("o numero do card da area e o mesmo da 1a competencia do cartao", () => {
    const VET = "CBBCAEAABDBECDDDBAADECBDDACBAECDEBDDA.EBCEBAC";
    const casos = [
      ["MT", 613, null, null], ["CH", 565, null, null], ["CN", 500, null, null],
      ["LC", 600, 0, null], ["MT", 613, null, VET], ["MT", 770, null, VET],
    ];
    for (const [sig, nota, lin, vet] of casos) {
      if (vet) {
        const cp = Object.keys(X.M.provas).find(c => X.M.provas[c].area === sig);
        X.V[sig] = { cp, txt: vet, erro: null };
      }
      const a = areaDe(sig, nota, lin);
      if (!a.perfil.length) { X.V[sig] = {}; continue; }

      // o caminho do COMPARATIVO
      const mot = X.motorArea(a);
      let dT = 0; const porComp = {};
      for (const h of a.perfil) {
        if (!(h[4] > 0)) continue;
        const t = mot.tetoHab(h[0], h[4], h[1]); dT += t;
        const c = (X.M.matriz[X.k(sig, h[0])] || {}).comp;
        if (c) porComp[c] = (porComp[c] || 0) + t;
      }
      const ptsTeto = mot.ganho(dT).pts;
      const fatias = X.reparte(Object.keys(porComp).map(c => porComp[c]), ptsTeto);
      const doCard = fatias.length ? Math.max(...fatias) : 0;

      // o caminho do CARTAO
      const html = X.cartaoArea(a);
      const vals = [...html.matchAll(/class="cval">até \+(\d+) ponto/g)].map(m => Number(m[1]));
      X.V[sig] = {};
      if (!vals.length) continue;
      const doCartao = Math.max(...vals);
      espera(doCard === doCartao,
        `${sig} ${nota}${vet ? " (com vetor)" : ""}: card diz +${doCard}, cartao mostra +${doCartao}`);
    }
  });

  // NOTA MAXIMA DA EDICAO: nao ha ponto acima, entao a tela nao pode oferecer
  // nenhum. Oferecia: o piso de 1 da reparticao rodava mesmo com o total
  // zerado e inventava "+1 ponto" em CADA competencia -- sete pontos do nada,
  // para quem ja tirou a maior nota que a edicao produziu
  caso("na nota maxima a tela nao oferece ponto nenhum", () => {
    for (const [sig, lin] of [["MT", null], ["CH", null], ["CN", null], ["LC", 0]]) {
      const max = X.M.maxNota[X.k(sig, sig === "LC" ? lin : null)];
      const a = areaDe(sig, Math.floor(max), lin);
      if (!a.perfil.length) continue;
      const h = X.cartaoArea(a);
      const vals = [...h.matchAll(/até \+(\d+) ponto/g)].map(m => Number(m[1]));
      espera(vals.length === 0,
        `${sig} ${max}: oferece ${vals.length} valores (${vals.slice(0, 4).join(", ")})`);
      espera(!/\+0 ponto/.test(h), `${sig} ${max}: escreve "+0 pontos"`);
      // e tem de dizer o que fazer, senao a pessoa fica sem resposta
      espera(/já está no alto|lapidar|manter em dia/.test(h),
        `${sig} ${max}: sem orientacao para quem esta no topo`);
    }
  });
  caso("nota do miolo continua oferecendo pontos (a guarda nao pode zerar tudo)", () => {
    const h = X.cartaoArea(areaDe("MT", 613, null));
    const vals = [...h.matchAll(/até \+(\d+) ponto/g)].map(m => Number(m[1]));
    espera(vals.length >= 5, `MT 613: so ${vals.length} valores`);
    espera(vals.every(v => v >= 1), `MT 613: valor zero na lista (${vals.join(", ")})`);
  });
  caso("plural: nunca 'até +1 pontos'", () => {
    for (const [sig, nota] of [["MT", 613], ["MT", 940], ["CH", 800], ["CN", 830]]) {
      const a = areaDe(sig, nota, null);
      if (!a.perfil.length) continue;
      espera(!/\+1 pontos/.test(X.cartaoArea(a)), `${sig} ${nota}: "+1 pontos"`);
    }
  });

  // Os tres exemplos usam os cortes de 27% e 73% da distribuicao real de
  // notas (regra classica de Kelley para grupo superior/inferior). Os cortes
  // saem do n por faixa que a calibracao ja traz -- se a conta quebrar, os
  // tres botoes viram o mesmo exemplo e ninguem percebe
  caso("cortes de desempenho: p27 < p73, dentro dos limites reais da area", () => {
    for (const [sig, lin] of [["MT", null], ["CH", null], ["CN", null], ["LC", 0], ["LC", 1]]) {
      const c = X.cortesDesempenho(sig, lin);
      espera(c, `${sig}: sem cortes`);
      espera(c.min < c.p27 && c.p27 < c.p73 && c.p73 < c.max,
        `${sig}: cortes fora de ordem (${c.min} / ${c.p27} / ${c.p73} / ${c.max})`);
      // Mesma escala do formulario, com folga de UMA faixa: os cortes usam o
      // meio da faixa de 10 pontos (faixa+5) e os limites usam o extremo real,
      // entao exigir igualdade compararia duas coisas diferentes
      const l = X.limitesNota(sig, lin);
      espera(c.min >= l.min - 10 && c.max <= l.max + 10,
        `${sig}: cortes (${c.min}-${c.max}) fora da escala do formulario (${l.min}-${l.max})`);
      // e os tres grupos precisam ter tamanho parecido com o desenho (27/46/27)
      espera(c.p73 - c.p27 > 20, `${sig}: faixa do meio estreita demais`);
      // os cortes tem de vir dos ACERTOS (regra de Kelley e sobre escore
      // bruto), nao da nota -- e o escore bruto cabe na prova
      const nq = sig === "LC" ? 50 : 45;
      espera(c.acP27 >= 1 && c.acP27 < c.acP73 && c.acP73 < nq,
        `${sig}: cortes de acertos fora de ordem ou fora da prova (${c.acP27}/${c.acP73} de ${nq})`);
    }
  });

  // A lista tem de DESCER pelo numero exibido. Antes a posicao vinha do passo
  // e o numero era o teto: em 60% dos cartoes aparecia um "+37" acima de um
  // "+82" (pior caso, MT 500: 76 · 72 · 66 · 37 · 82 · 73 · 50). Ordem que
  // contradiz o numero ao lado e lida como erro, nao como sutileza
  caso("a lista de competencias desce pelo numero exibido, sem inversao", () => {
    let cartoes = 0, ruins = 0, pior = "";
    for (const [sig, lin] of [["MT", null], ["CH", null], ["CN", null], ["LC", 0]]) {
      for (let nota = 400; nota <= 880; nota += 40) {
        const a = areaDe(sig, nota, lin);
        if (!a.perfil.length) continue;
        const h = X.cartaoArea(a);
        const vals = [...h.matchAll(/class="cval">até \+(\d+) ponto/g)].map(m => Number(m[1]));
        if (vals.length < 3) continue;
        cartoes++;
        for (let i = 1; i < vals.length; i++) {
          if (vals[i] > vals[i - 1]) { ruins++; pior = `${sig} ${nota}: ${vals.join(" · ")}`; break; }
        }
      }
    }
    espera(cartoes >= 30, `poucos cartoes avaliados (${cartoes})`);
    espera(ruins === 0, `${ruins} de ${cartoes} cartoes com inversao — ex.: ${pior}`);
  });
  caso("o selo 'comece por aqui' marca parte da lista, nao tudo nem nada", () => {
    // o que a medicao sustenta e um GRUPO de boas apostas (~metade), nao um
    // vencedor unico. Selo em tudo nao informa; em nada, perde o sinal
    let comSelo = 0, total = 0;
    for (const [sig, nota] of [["MT", 500], ["MT", 613], ["CH", 565], ["CN", 600], ["LC", 600]]) {
      const a = areaDe(sig, nota, sig === "LC" ? 0 : null);
      if (!a.perfil.length) continue;
      const h = X.cartaoArea(a);
      const n = (h.match(/class="cval">até \+/g) || []).length;
      const sel = (h.match(/badge rende/g) || []).length;
      if (n < 3) continue;
      total += n; comSelo += sel;
      espera(sel >= 1 && sel < n,
        `${sig} ${nota}: ${sel} selos em ${n} competencias`);
    }
    espera(total > 0, "nenhum cartao avaliado");
    espera(comSelo / total <= 0.7, `selo em ${(100 * comSelo / total).toFixed(0)}% — perde o sinal`);
  });

  // Nota fora da faixa real da edicao: antes, faixaDisponivel() encostava na
  // faixa mais proxima e o mapa saia calculado para outra pessoa, em silencio
  caso("limites de nota saem dos dados: 1a faixa calibrada e maior nota real", () => {
    for (const [sig, lin] of [["MT", null], ["CH", null], ["CN", null], ["LC", 0], ["LC", 1]]) {
      const l = X.limitesNota(sig, lin);
      espera(l, `${sig}: sem limites`);
      // o maximo e a maior nota realmente tirada, que viaja no motor.json
      const chave = X.k(sig, sig === "LC" ? lin : null);
      espera(Math.abs(l.max - X.M.maxNota[chave]) <= 0.05,
        `${sig}: max ${l.max} != maxNota ${X.M.maxNota[chave]}`);
      // o minimo sai de minNota quando ele existe (o piso REAL da edicao);
      // sem ele, cai na primeira faixa calibrada -- que e mais alta, entao o
      // fallback recusa gente que existe. So vale enquanto o motor.json nao
      // for reexportado
      if (X.M.minNota && X.M.minNota[chave] != null) {
        espera(Math.abs(l.min - X.M.minNota[chave]) <= 0.05,
          `${sig}: min ${l.min} != minNota ${X.M.minNota[chave]}`);
        espera(l.min > 0, `${sig}: piso ${l.min} -- o zero e sentinela e nao pode entrar`);
      } else {
        let menor = Infinity;
        for (const ch in X.M.calibracao) {
          const [a, ll, f] = ch.split("|");
          if (a === sig && ll === (sig === "LC" ? String(lin) : "_")) menor = Math.min(menor, Number(f));
        }
        espera(l.min === menor, `${sig}: sem minNota, min ${l.min} != primeira faixa ${menor}`);
      }
      espera(l.min >= 250 && l.min <= 400, `${sig}: minimo implausivel (${l.min})`);
      espera(l.max >= 700 && l.max <= 1000, `${sig}: maximo implausivel (${l.max})`);
    }
  });
  caso("a faixa aceita cobre toda a calibracao da area (nao corta nota real)", () => {
    // recusar acima do fim da curva rejeitaria nota verdadeira: a curva acaba
    // onde a amostra fica rala, e a diferenca chega a 114 pontos em LC/espanhol
    for (const [sig, lin] of [["MT", null], ["CH", null], ["CN", null], ["LC", 0], ["LC", 1]]) {
      const l = X.limitesNota(sig, lin);
      let maior = -Infinity;
      for (const ch in X.M.calibracao) {
        const [a, ll, f] = ch.split("|");
        if (a === sig && ll === (sig === "LC" ? String(lin) : "_")) maior = Math.max(maior, Number(f) + 5);
      }
      espera(l.max >= maior, `${sig}: teto ${l.max} corta a ultima faixa calibrada (${maior})`);
    }
  });

  // dois bugs ANTERIORES a integracao, achados pela revisao adversarial de
  // 28/07 e corrigidos junto
  caso("piso: nao existe trofeu de 'ja esta no alto' no fundo da escala", () => {
    for (const [sig, nota] of [["MT", 340], ["CH", 330], ["CN", 350]]) {
      const h = X.cartaoArea(areaDe(sig, nota, null));
      espera(!/já está no alto/.test(h),
        `${sig} ${nota}: trofeu de topo numa nota de piso — diz o oposto da realidade`);
      espera(/não separa níveis/.test(h), `${sig} ${nota}: sumiu o aviso de piso`);
    }
  });
  caso("topo da grade (MT 960): o teto mede no nivel da pessoa, nao meio passo abaixo", () => {
    // ali 'recua' inverte quem carrega o nivel: e o espUp, nao o espRef.
    // Confundir os dois inflava o teto ~4x (a faixa acerta 43 de 43 validas)
    const h = X.cartaoArea(areaDe("MT", 960, null));
    const m = h.match(/Fechando tudo: até \+(\d+) ponto/);
    if (m) espera(Number(m[1]) <= 10,
      `MT 960 oferece +${m[1]} pontos a quem ja acerta tudo o que vale ponto`);
    espera(/já está no alto/.test(h), "MT 960 sem o cartao de topo");
  });

  
  console.log(falhas.length
    ? `\n${falhas.length} FALHA(S): ${falhas.join(" | ")}`
    : "\ntodos os casos passaram");
  process.exit(falhas.length ? 1 : 0);
})();

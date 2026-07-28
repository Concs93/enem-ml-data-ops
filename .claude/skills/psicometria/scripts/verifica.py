"""Calculadora de TRI sobre os itens reais do ENEM 2025.

Existe para uma coisa: transformar afirmacao conceitual em conta, antes que ela
va para a tela. Carrega webapp/dados/motor.json (parametros das 16 provas
regulares) e responde as perguntas que mais aparecem.

    python .claude/skills/psicometria/scripts/verifica.py --help
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics as st
from pathlib import Path

D = 1.7  # constante de escalonamento; a mesma usada em todo o projeto
RAIZ = Path(__file__).resolve().parents[4]
MOTOR = RAIZ / "webapp" / "dados" / "motor.json"

# theta fora desta janela e artefato do limitador, nao medida
TH_MIN, TH_MAX = -3.5, 4.5


def carrega(area: str | None = None, prova: str | None = None):
    """Devolve [(a, b, c, habilidade, posicao, area, cod_prova), ...]."""
    if not MOTOR.exists():
        raise SystemExit(
            f"nao achei {MOTOR}\n"
            "rode antes:  python export/export_site.py"
        )
    motor = json.loads(MOTOR.read_text(encoding="utf-8"))
    itens = []
    for cod, pv in motor["provas"].items():
        if prova and cod != prova:
            continue
        if area and pv["area"] != area.upper():
            continue
        for pos, _x, _gab, hab, a, b, c, _y in pv["itens"]:
            if a is None:  # item sem calibracao (anulado / sem convergencia)
                continue
            itens.append((a, b, c, hab, pos, pv["area"], cod))
    if not itens:
        raise SystemExit("nenhum item bateu com o filtro")
    return itens


def P(t, a, b, c):
    """Probabilidade de acerto no 3PL."""
    return c + (1 - c) / (1 + math.exp(-D * a * (t - b)))


def I(t, a, b, c):
    """Informacao de Fisher do item."""
    p = P(t, a, b, c)
    return D * D * a * a * ((p - c) / (1 - c)) ** 2 * (1 - p) / p


def theta_mle(par, u, t0=0.0):
    """Baker eq. 5-1, com o peso do 3PL. Devolve (theta, bateu_no_limite)."""
    t = t0
    for _ in range(300):
        num = den = 0.0
        for (a, b, c), ui in zip(par, u):
            p = min(max(P(t, a, b, c), 1e-9), 1 - 1e-9)
            w = D * a * (p - c) / (p * (1 - c))
            num += w * (ui - p)
            den += w * w * p * (1 - p)
        if den < 1e-12:
            break
        passo = num / den
        t += max(-0.5, min(0.5, passo))
        if abs(passo) < 1e-10:
            break
    preso = t <= TH_MIN + 1e-6 or t >= TH_MAX - 1e-6
    return max(TH_MIN, min(TH_MAX, t)), preso


def nota(t):
    return 500 + 100 * t


# ---------------------------------------------------------------- comandos


def cmd_item(args):
    """Curva e informacao de um item, ou o resumo dos parametros da area."""
    itens = carrega(args.area, args.prova)
    print(f"{len(itens)} itens validos\n")
    for nome, idx in (("a (discriminacao)", 0), ("b (dificuldade)", 1), ("c (acerto casual)", 2)):
        v = sorted(x[idx] for x in itens)
        q = st.quantiles(v, n=4)
        print(
            f"  {nome:<20} min {v[0]:.3f}  p25 {q[0]:.3f}  "
            f"mediana {st.median(v):.3f}  p75 {q[2]:.3f}  max {v[-1]:.3f}"
        )
    print("\n  P(acerto) e informacao por nivel, item mediano em dificuldade:")
    mediano = sorted(itens, key=lambda x: x[1])[len(itens) // 2]
    a, b, c = mediano[:3]
    print(f"  (a={a:.3f}  b={b:.3f}  c={c:.3f})")
    print(f"  {'theta':>7} {'nota':>6} {'P':>7} {'info':>7}")
    for t in (-1, 0, 0.5, 1, 1.5, 2, 3):
        print(f"  {t:>7.1f} {nota(t):>6.0f} {P(t,a,b,c):>7.3f} {I(t,a,b,c):>7.3f}")


def cmd_pico(args):
    """Onde fica o pico de informacao: em b, ou acima?"""
    itens = carrega(args.area, args.prova)
    desvios = []
    for a, b, c, *_ in itens:
        grid = [b - 1 + 0.002 * i for i in range(1001)]
        pico = max(grid, key=lambda t: I(t, a, b, c))
        desvios.append(pico - b)
    acima = sum(1 for d in desvios if d > 0.001)
    print(f"{len(desvios)} itens testados")
    print(
        f"  desvio (pico - b):  min {min(desvios):+.3f}  "
        f"mediana {st.median(desvios):+.3f}  max {max(desvios):+.3f}"
    )
    print(f"  com pico ACIMA de b: {acima}/{len(desvios)}")
    print(
        "\n  Sob 1PL/2PL o pico fica exatamente em b. Sob 3PL, o termo (P-c)\n"
        "  desloca o pico para cima: a informacao morre onde o acerto vira chute."
    )


def cmd_troca(args):
    """Quanto muda o theta ao trocar um erro por acerto, por dificuldade."""
    itens = carrega(args.area, args.prova)
    par = [(a, b, c) for a, b, c, *_ in itens]
    th = args.theta
    u = [1 if P(th, *it) >= 0.5 else 0 for it in par]
    base, _ = theta_mle(par, u)
    linhas = []
    for j, it in enumerate(par):
        if u[j] == 1:
            continue
        v = u[:]
        v[j] = 1
        t2, preso = theta_mle(par, v)
        if not preso:
            linhas.append((P(th, *it), t2 - base))
    if not linhas:
        raise SystemExit("nenhum item errado nesse nivel; tente --theta menor")
    linhas.sort(key=lambda x: -x[0])
    n = max(1, len(linhas) // 4)
    faceis = [d for _p, d in linhas[:n]]
    dificeis = [d for _p, d in linhas[-n:]]
    print(f"nivel theta {th:+.2f} (nota ~{nota(th):.0f}), {len(linhas)} questoes erradas\n")
    print(f"  {'P(acerto)':>10} {'ganho em theta':>16} {'~pontos':>9}")
    for p, d in linhas[:3]:
        print(f"  {p:>10.3f} {d:>16.4f} {100*d:>9.1f}")
    print("  ...")
    for p, d in linhas[-3:]:
        print(f"  {p:>10.3f} {d:>16.4f} {100*d:>9.1f}")
    mf, md = sum(faceis) / len(faceis), sum(dificeis) / len(dificeis)
    print(f"\n  quartil mais FACIL   media {mf:+.4f}  (~{100*mf:.1f} pontos)")
    print(f"  quartil mais DIFICIL media {md:+.4f}  (~{100*md:.1f} pontos)")
    if md > 1e-6:
        print(f"  razao facil/dificil: {mf/md:.2f}x")
    print(
        "\n  A assimetria inteira vem do parametro c. Com c=0 a razao seria 1,00x\n"
        "  (Baker eq. 5-1, p. 85)."
    )


def cmd_padrao(args):
    """Mesmo total de acertos -> quanta nota de diferenca, realisticamente?"""
    itens = carrega(args.area, args.prova or "1471")
    par = [(a, b, c) for a, b, c, *_ in itens]
    random.seed(args.semente)
    alvo = args.acertos
    notas, tent = [], 0
    while len(notas) < args.amostras and tent < 400_000:
        tent += 1
        th = random.uniform(args.theta - 0.5, args.theta + 0.5)
        u = [1 if random.random() < P(th, *it) else 0 for it in par]
        if sum(u) != alvo:
            continue
        t, preso = theta_mle(par, u)
        if not preso:
            notas.append(nota(t))
    if len(notas) < 30:
        raise SystemExit(
            f"so {len(notas)} amostras com {alvo} acertos; "
            "ajuste --acertos para perto do esperado nesse --theta"
        )
    notas.sort()
    p05, p95 = notas[int(0.05 * len(notas))], notas[int(0.95 * len(notas))]
    print(f"{len(par)} itens validos, pessoas simuladas com exatamente {alvo} acertos")
    print(f"  amostras: {len(notas)}")
    print(
        f"  nota  min {notas[0]:.0f}  p05 {p05:.0f}  mediana {st.median(notas):.0f}  "
        f"p95 {p95:.0f}  max {notas[-1]:.0f}"
    )
    print(f"  amplitude p05-p95: {p95-p05:.0f} pontos   desvio-padrao: {st.pstdev(notas):.1f}")
    print(
        "\n  Use a amplitude p05-p95, nao min-max: o extremo e padrao patologico\n"
        "  (acertar so as dificeis) e nao acontece."
    )


def cmd_se(args):
    """Erro-padrao de theta: o que a prova consegue afirmar sobre uma pessoa."""
    itens = carrega(args.area, args.prova)
    par = [(a, b, c) for a, b, c, *_ in itens]
    print(f"{len(par)} itens validos")
    print(f"  {'theta':>7} {'nota':>6} {'info total':>11} {'SE(theta)':>10} {'+-pontos':>9}")
    for t in (-1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3):
        tot = sum(I(t, *it) for it in par)
        se = 1 / math.sqrt(tot) if tot > 0 else float("inf")
        print(f"  {t:>7.1f} {nota(t):>6.0f} {tot:>11.3f} {se:>10.3f} {100*se:>9.1f}")
    print(
        "\n  SE = 1/sqrt(informacao) (Baker eq. 5-2, p. 88). Afirmacao sobre uma\n"
        "  pessoa que caiba dentro de +-1 SE nao esta sustentada pela prova."
    )


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--area", help="MT, CH, CN ou LC")
    ap.add_argument("--prova", help="codigo (ex.: 1471 = MT Azul)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("item", help="resumo dos parametros e uma curva de exemplo")
    s.set_defaults(func=cmd_item)

    s = sub.add_parser("pico", help="o pico de informacao fica em b? (nao, sob 3PL)")
    s.set_defaults(func=cmd_pico)

    s = sub.add_parser("troca", help="ganho ao trocar erro por acerto, por dificuldade")
    s.add_argument("--theta", type=float, default=1.0)
    s.set_defaults(func=cmd_troca)

    s = sub.add_parser("padrao", help="mesmo total de acertos, quanta nota de diferenca")
    s.add_argument("--acertos", type=int, default=25)
    s.add_argument("--theta", type=float, default=1.0)
    s.add_argument("--amostras", type=int, default=1500)
    s.add_argument("--semente", type=int, default=7)
    s.set_defaults(func=cmd_padrao)

    s = sub.add_parser("se", help="erro-padrao de theta por nivel")
    s.set_defaults(func=cmd_se)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

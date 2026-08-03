"""Gera os prints do site para divulgacao (LinkedIn, README, apresentacao).

Fotografa o site EM PRODUCAO, nao o local: o que vai para o post tem de ser o
que a pessoa encontra ao clicar no link. Se o deploy estiver atrasado, o print
sai da versao antiga -- e isso e informacao, nao defeito.

    python divulgacao/gera_prints.py

Os PNG ficam fora do Git (ver .gitignore): sao derivados, e este script os
reproduz. O que vale versionar e a receita.

Qual usar no post: o 1_comparativo. E o unico que continua legivel reduzido no
feed e o unico que mostra o produto DECIDINDO -- quatro areas, notas
diferentes, e o selo em cima de uma delas. Os outros sao altos e densos, e
viram borrao no celular.
"""

import os
import sys

from playwright.sync_api import sync_playwright

B = "https://concs93.github.io/enem-ml-data-ops"
SAIDA = "divulgacao"

# Notas de exemplo escolhidas de proposito: a MAIOR nota (MT 600) nao e a area
# onde o passo rende mais (CH, com 540). A tese do produto aparece sozinha no
# print, sem precisar de legenda
NOTAS = {"n-lc": "580", "n-ch": "540", "n-cn": "505", "n-mt": "600"}


def main() -> None:
    os.makedirs(SAIDA, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()

        pg = b.new_page(viewport={"width": 1200, "height": 1200},
                        device_scale_factor=2)
        pg.goto(f"{B}/?p=1", wait_until="networkidle")
        pg.wait_for_timeout(1500)
        for campo, v in NOTAS.items():
            pg.fill(f"#{campo}", v)
        pg.click("text=Ver meu mapa de estudo")
        pg.wait_for_timeout(2500)

        pg.locator("h2:has-text('Se você só tiver tempo')").locator("xpath=..") \
          .screenshot(path=os.path.join(SAIDA, "1_comparativo.png"))
        pg.locator("h2:has-text('Como foi a prova')").locator("xpath=..") \
          .screenshot(path=os.path.join(SAIDA, "2_competencias.png"))

        g = b.new_page(viewport={"width": 1200, "height": 1000},
                       device_scale_factor=2)
        g.goto(f"{B}/estados.html?p=1", wait_until="networkidle")
        g.wait_for_timeout(1500)
        g.click("#mapa path[data-cod='31']")          # Minas Gerais
        g.wait_for_timeout(2500)
        g.locator(".painel").screenshot(path=os.path.join(SAIDA, "3_estados.png"))

        t = b.new_page(viewport={"width": 1200, "height": 760},
                       device_scale_factor=2)
        t.goto(f"{B}/?p=2", wait_until="networkidle")
        t.wait_for_timeout(1500)
        t.screenshot(path=os.path.join(SAIDA, "4_home.png"))

        b.close()

    for f in sorted(os.listdir(SAIDA)):
        if f.endswith(".png"):
            kb = os.path.getsize(os.path.join(SAIDA, f)) / 1024
            print(f"  {f:24} {kb:6.0f} KB")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Infográfico do BYD Song Plus para a Missão Global Miami (pedido dele em
16/11/2026): o preço no Brasil contra o preço na China, a picape americana
como comparação e o que aconteceria com o preço aqui se o yuan fosse ao
câmbio de equilíbrio (paridade do poder de compra) do gráfico anterior.

Preços são de tabela e entram à mão (data abaixo); o câmbio vem do Banco
Central (PTAX, SGS 1) e do Fed (H.10, DEXCHUS). Escreve um HTML de 1920x1080;
a imagem sai com o Chrome headless:

    python3 scripts/infografico_byd.py
    (renderizar assets/missao/byd-yuan.html em 1920x1080 para assets/missao/byd-yuan.jpg)

Hipótese do cenário: o preço no Brasil acompanha o custo em dólar do carro
chinês (impostos ad valorem, margens e real constantes). É o teto do repasse.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import cenario_fomc as cf                                     # noqa: E402

DATA_PRECOS = "16/11/2026"
BYD_BR = 249990          # BYD Song Plus DM-i 2027, tabela BYD Brasil (versão única)
BYD_CN = 175800          # 宋PLUS DM-i 智驾版, versão mais cara (faixa oficial de ¥ 135.800 a ¥ 175.800)
FORD_BR = 296090         # Chevrolet Equinox Activ, preço público sugerido em out/2026 (feito no México)
FORD_US = 35600          # Equinox ACTIV AWD 2026, MSRP sem o frete (Cars.com)
# câmbio de equilíbrio do yuan (gráfico china-yuan-ppc, out/26), por data-base
EQUILIBRIO = [("dez/2019", 5.60), ("dez/2020", 5.28), ("dez/2014", 5.07)]

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def br(v, casas=0):
    s = "{:,.{c}f}".format(v, c=casas)
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def calcula():
    ptax = json.loads(cf.baixar("https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados/ultimos/1?formato=json"))[0]
    brl = float(ptax["valor"])
    cny_d = cf.fred("DEXCHUS", mensal=False)
    dia = max(cny_d)
    cny = cny_d[dia]
    brl_cny = brl / cny
    cen = [(base, eq, cny / eq - 1, BYD_BR * cny / eq) for base, eq in EQUILIBRIO]
    return dict(ptax=ptax, brl=brl, dia=dia, cny=cny, brl_cny=brl_cny, byd_cn_r=BYD_CN * brl_cny,
                ford_us_r=FORD_US * brl, cen=cen)


# ---- a lâmina dos carros, com os preços aparecendo a cada clique (pedido dele em 16/11/2026)

CARROS = [("byd", "carro-byd.png", "BYD Song Plus DM-i", "SUV híbrido plug-in, importado da China"),
          ("equinox", "carro-equinox.png", "Chevrolet Equinox Activ", "SUV a gasolina, americano, feito no México")]
BASE_Y = 790


def imagem_carros():
    """A foto dos dois carros (assets/missao/foto-07.jpg), a partir dos recortes oficiais
    que ele mandou (fundo transparente, sombra clara já trocada por sombra escura)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
    W, H = 1920, 1080
    pasta = os.path.join(RAIZ, "assets", "missao")
    fundo = ImageOps.fit(Image.open(os.path.join(pasta, "fundo-grafico.jpg")).convert("RGB"), (W, H)).convert("RGBA")
    fb = ImageFont.truetype("/usr/share/fonts/truetype/lato/Lato-Bold.ttf", 50)
    fr = ImageFont.truetype("/usr/share/fonts/truetype/lato/Lato-Regular.ttf", 30)
    centros = {}
    for k, (cid, arq, nome, sub) in enumerate(CARROS):
        cx = 480 + k * 960
        car = Image.open(os.path.join(pasta, arq)).convert("RGBA")
        esc = min(840 / car.width, 520 / car.height)
        car = car.resize((int(car.width * esc), int(car.height * esc)), Image.LANCZOS)
        luz = Image.new("L", (W, H), 0)
        ImageDraw.Draw(luz).ellipse((cx - 470, BASE_Y - car.height - 60, cx + 470, BASE_Y + 40), fill=110)
        luz = luz.filter(ImageFilter.GaussianBlur(90))
        fundo = Image.composite(Image.new("RGBA", (W, H), (170, 195, 230, 255)), fundo, luz)
        fundo.alpha_composite(car, (cx - car.width // 2, BASE_Y - car.height))
        d = ImageDraw.Draw(fundo)
        for txt, f, cor, y in ((nome, fb, "white", BASE_Y + 60), (sub, fr, "#c9d6e8", BASE_Y + 128)):
            w = d.textlength(txt, font=f)
            d.text((cx - w / 2, y), txt, font=f, fill=cor)
        centros[cid] = (cx, BASE_Y - car.height // 2)
    fundo.convert("RGB").save(os.path.join(pasta, "foto-07.jpg"), "JPEG", quality=88, optimize=True, progressive=True)
    return centros


def figura_carros():
    """A figura da lâmina: a foto e, por cima, uma caixa por carro; cada passo (→, espaço ou
    Enter na apresentação) acende uma linha, e a foto atrás fica desfocada."""
    v = calcula()
    centros = imagem_carros()
    linha = lambda cx, rot, val, sub=None, cen=False: dict(caixa=cx, rot=rot, val=val, sub=sub, cenario=cen)
    # primeiro o preço de origem (China, depois EUA), depois os dois no Brasil (pedido dele em 16/11/2026)
    passos = [[linha("byd", "Preço na China, no câmbio de hoje", "R$ " + br(v["byd_cn_r"]),
                     "¥ %s a R$ %s por yuan" % (br(BYD_CN), br(v["brl_cny"], 2)))],
              [linha("equinox", "Preço nos EUA, no câmbio de hoje", "R$ " + br(v["ford_us_r"]),
                     "US$ %s a R$ %s por dólar" % (br(FORD_US), br(v["brl"], 2)))],
              [linha("byd", "Preço no Brasil", "R$ " + br(BYD_BR)),
               linha("equinox", "Preço no Brasil", "R$ " + br(FORD_BR))]]
    for base, eq, val, p in v["cen"]:
        passos.append([linha("byd", "No Brasil, com o yuan a ¥ %s por US$" % br(eq, 2), "R$ %s mil" % br(p / 1000),
                             "yuan %s%% mais forte (equilíbrio desde %s)" % (br(100 * val), base), True)])
    return dict(id="foto-07", tipo="figura", foto=True, imagem="assets/missao/foto-07.jpg",
                titulo="BYD Song Plus DM-i e Chevrolet Equinox Activ",
                caixas={cid: dict(x=centros[cid][0], nome=nome) for cid, _, nome, _ in CARROS}, passos=passos)


def main():
    v = calcula()
    ptax, brl, dia, cny, brl_cny = v["ptax"], v["brl"], v["dia"], v["cny"], v["brl_cny"]
    byd_cn_r, ford_us_r, cen = v["byd_cn_r"], v["ford_us_r"], v["cen"]
    print("PTAX %s: R$ %.4f; yuan %s: ¥ %.4f; R$ %.4f por yuan" % (ptax["data"], brl, dia, cny, brl_cny))
    print("BYD: China R$ %.0f, Brasil %.2fx; Equinox: EUA R$ %.0f, Brasil %.2fx"
          % (byd_cn_r, BYD_BR / byd_cn_r, ford_us_r, FORD_BR / ford_us_r))
    for base, eq, val, p in cen:
        print("  yuan a ¥ %.2f (%s): +%.0f%% -> R$ %.0f" % (eq, base, 100 * val, p))

    maxp = max(p for *_, p in cen)

    def barra(rot, sub, valor, cor, destaque=False):
        w = 1060 * valor / maxp
        return ('<div class="b"><div class="b-rot"><b>%s</b><span>%s</span></div>'
                '<div class="b-trilho"><div class="b-barra" style="width:%.0fpx;background:%s"></div>'
                '<div class="b-val%s">R$ %s mil</div></div></div>'
                % (rot, sub, w, cor, " forte" if destaque else "", br(valor / 1000, 0)))
    barras = barra("Hoje", "¥ %s por US$" % br(cny, 2), BYD_BR, "#4F81BD", True)
    for base, eq, val, p in cen:
        barras += barra("¥ %s por US$" % br(eq, 2), "equilíbrio desde %s; yuan +%s%%" % (base, br(100 * val, 0)),
                        p, "#C0504D")

    html = """<!doctype html><html><head><meta charset="utf-8"><style>
* { box-sizing: border-box; margin: 0; }
body { width: 1920px; height: 1080px; overflow: hidden; color: #fff;
  font-family: Calibri, Carlito, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  background: #061630 url("fundo-grafico.jpg") center / cover no-repeat; position: relative; }
h1 { position: absolute; left: 60px; top: 46px; font-size: 54px; font-weight: 700; }
.sub { position: absolute; left: 62px; top: 118px; font-size: 27px; font-style: italic; color: #c9d6e8; }
.cartoes { position: absolute; left: 60px; right: 60px; top: 190px; display: flex; gap: 40px; }
.c { flex: 1; background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.14); border-radius: 18px; padding: 26px 34px; }
.c h2 { font-size: 32px; font-weight: 700; }
.c .tipo { font-size: 22px; color: #c9d6e8; margin-top: 4px; }
.c .linhas { display: flex; gap: 30px; margin-top: 22px; }
.c .l { flex: 1; }
.c .l .onde { font-size: 22px; color: #c9d6e8; text-transform: uppercase; letter-spacing: .04em; }
.c .l .preco { font-size: 46px; font-weight: 700; margin-top: 2px; }
.c .l .conv { font-size: 22px; color: #c9d6e8; }
.c .mult { margin-top: 18px; font-size: 28px; }
.c .mult b { font-size: 40px; color: #8EB4E3; }
.c .imp { margin-top: 6px; font-size: 23px; color: #c9d6e8; }
.cen { position: absolute; left: 60px; right: 60px; top: 585px; }
.cen h3 { font-size: 34px; font-weight: 700; margin-bottom: 18px; }
.b { display: flex; align-items: center; height: 80px; }
.b-rot { width: 380px; display: flex; flex-direction: column; }
.b-rot b { font-size: 30px; }
.b-rot span { font-size: 21px; color: #c9d6e8; }
.b-trilho { display: flex; align-items: center; gap: 18px; }
.b-barra { height: 52px; border-radius: 4px; }
.b-val { font-size: 34px; font-weight: 700; }
.nota { position: absolute; left: 62px; right: 60px; bottom: 26px; font-size: 19px; color: #aebdd3; line-height: 1.35; }
</style></head><body>
<h1>BYD Song Plus: o preço no Brasil e com o yuan no equilíbrio</h1>
<p class="sub">Preços de tabela em %(data)s; câmbio de R$ %(brl)s por US$ e ¥ %(cny)s por US$, ou R$ %(brlcny)s por yuan</p>
<div class="cartoes">
  <div class="c"><h2>BYD Song Plus DM-i</h2><p class="tipo">SUV híbrido plug-in, importado da China</p>
    <div class="linhas">
      <div class="l"><p class="onde">China</p><p class="preco">¥ %(byd_cn)s</p><p class="conv">= R$ %(byd_cn_r)s</p></div>
      <div class="l"><p class="onde">Brasil</p><p class="preco">R$ %(byd_br)s</p></div>
    </div>
    <p class="mult">No Brasil, <b>%(byd_mult)sx</b> o preço na China</p>
    <p class="imp">Imposto de importação: 35%%</p></div>
  <div class="c"><h2>Chevrolet Equinox Activ</h2><p class="tipo">SUV americano a gasolina, feito no México</p>
    <div class="linhas">
      <div class="l"><p class="onde">EUA</p><p class="preco">US$ %(ford_us)s</p><p class="conv">= R$ %(ford_us_r)s</p></div>
      <div class="l"><p class="onde">Brasil</p><p class="preco">R$ %(ford_br)s</p></div>
    </div>
    <p class="mult">No Brasil, <b>%(ford_mult)sx</b> o preço nos EUA</p>
    <p class="imp">Imposto de importação: 0%% (acordo automotivo Brasil-México)</p></div>
</div>
<div class="cen"><h3>O Song Plus no Brasil se o yuan fosse ao câmbio de equilíbrio (PPC)</h3>%(barras)s</div>
<p class="nota">Cenário: o preço no Brasil acompanha o custo em dólar do carro chinês, com o real, os impostos e as margens
constantes; é o teto do repasse. China: versão mais cara do 宋PLUS DM-i (faixa oficial de ¥ 135.800 a ¥ 175.800).
EUA: Equinox ACTIV AWD, sem o frete. Fontes: BYD, Chevrolet, Banco Central, Federal Reserve e FtM.</p>
</body></html>""" % dict(
        data=DATA_PRECOS, brl=br(brl, 2), cny=br(cny, 2), brlcny=br(brl_cny, 2),
        byd_cn=br(BYD_CN), byd_cn_r=br(byd_cn_r), byd_br=br(BYD_BR), byd_mult=br(BYD_BR / byd_cn_r, 2),
        ford_us=br(FORD_US), ford_us_r=br(ford_us_r), ford_br=br(FORD_BR), ford_mult=br(FORD_BR / ford_us_r, 2),
        barras=barras)
    saida = os.path.join(RAIZ, "assets", "missao", "byd-yuan.html")
    with open(saida, "w", encoding="utf-8") as f:
        f.write(html)
    print("gravado", saida)


if __name__ == "__main__":
    main()

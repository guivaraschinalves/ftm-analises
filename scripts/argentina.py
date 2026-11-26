#!/usr/bin/env python3
"""
Argentina: risco país, dólar blue, dólar oficial e brecha cambial (diários).
Gera dados/argentina.json. Só biblioteca padrão. Rodado à mão. Página
própria: argentina.html (fora do índice).

Pedido dele em 26/11/2026.

DE ONDE VEM CADA COISA (Ámbito, mercados.ambito.com, histórico geral)

  - riesgopais/historico-general: risco país (EMBI do JP Morgan) em pontos
    básicos, desde dez/1998. Datas "dd-mm-aaaa".
  - dolar/informal/historico-general: dólar blue, compra e venda, desde
    jan/2002. Datas "dd/mm/aaaa".
  - dolar/oficial/historico-general: dólar oficial do Ámbito (varejo, média
    dos bancos; não é o atacado da Com. A 3500), desde abr/2002.
  - Usa-se a venda nas duas cotações.

ARMADILHA DO ÁMBITO: a lista vem do mais novo para o mais velho e às vezes
repete a data (cotação carimbada com o dia da publicação, não do fechamento;
ex.: em 24/11/2026 aparecem 1.700 e 1.675, e o 1.675 é o fechamento de
23/11). Fica a primeira ocorrência de cada data, que é a última publicada e
bate com o "valor_cierre_ant" do próprio Ámbito. O dia que some fica buraco.

BRECHA = blue (venda) ÷ oficial (venda) − 1, em %, e blue − oficial em pesos,
só nos dias com as duas cotações.

CONFERÊNCIAS QUE ABORTAM (segunda fonte: api.argentinadatos.com)
  - Risco país: mesmo dia nas duas fontes, diferença ≤ 1% em pelo menos 99%
    dos dias em comum, e o último ponto igual.
  - Blue e oficial: média mensal das duas fontes, nos mesmos dias, a partir
    de 2014, com diferença ≤ 0,5 peso + TOL_MES[nome]. O ArgentinaDatos
    guarda uma foto por dia corrido (às vezes com um dia de atraso) e
    arredonda para peso inteiro por anos (daí o meio peso), por isso a
    conferência é pela média do mês, não dia a dia. O oficial tem tolerância
    maior porque o do Ámbito é a média dos bancos e o do ArgentinaDatos é o
    Banco Nación (em 2024 ficam a uns 3%).
  - O último fechamento do Ámbito tem de aparecer no ArgentinaDatos em até
    2 dias corridos (≤ 0,5%).
  - Brecha recalculada a partir da série gravada (arredondada) contra a de
    precisão cheia: ≤ 0,05 p.p.
"""
import datetime
import json
import os
import statistics
import sys
import time
import urllib.request

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SAIDA = os.path.join(RAIZ, "dados", "argentina.json")
AMBITO = "https://mercados.ambito.com//%s/historico-general/01-01-1990/%s"
ARGDATOS = "https://api.argentinadatos.com/v1/%s"
UA = {"User-Agent": "Mozilla/5.0 (ftm-analises)"}
TOL_MES = {"blue": 0.03, "oficial": 0.04}   # na média mensal, além de 0,5 peso de arredondamento
INICIO_CONF = "2014-01"

BRANCO, AZUL = "#FFFFFF", "#4F81BD"


def baixar(url, tentativas=4):
    for k in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if k == tentativas - 1:
                raise RuntimeError("falhou %s: %s" % (url, e))
            time.sleep(3 * (k + 1))


def num_ar(txt):
    """'1.067,00' -> 1067.0"""
    return float(txt.replace(".", "").replace(",", "."))


def ambito(caminho, sep):
    hoje = datetime.date.today().strftime("%d-%m-%Y")
    linhas = baixar(AMBITO % (caminho, hoje))
    if not linhas or linhas[0][0] != "Fecha":
        raise RuntimeError("Ámbito %s: cabeçalho inesperado %r" % (caminho, linhas[:1]))
    col = linhas[0].index("Venta") if "Venta" in linhas[0] else linhas[0].index("Puntos")
    out, repetidas = {}, 0
    for r in linhas[1:]:
        d = datetime.datetime.strptime(r[0], "%d" + sep + "%m" + sep + "%Y").date()
        if d in out:
            repetidas += 1
            continue
        out[d] = num_ar(r[col])
    if len(out) < 4000:
        raise RuntimeError("Ámbito %s: só %d dias" % (caminho, len(out)))
    print("Ámbito %-15s %d dias (%d datas repetidas descartadas), %s a %s"
          % (caminho, len(out), repetidas, min(out), max(out)))
    return out


def argdatos(caminho, campo):
    return {datetime.date.fromisoformat(r["fecha"]): float(r[campo]) for r in baixar(ARGDATOS % caminho)}


def conferir_risco(a, b):
    comuns = [d for d in a if d in b]
    ruins = [(d, a[d], b[d]) for d in comuns if abs(b[d] / a[d] - 1) > 0.01]
    print("risco país: %d dias em comum, %d com diferença > 1%%" % (len(comuns), len(ruins)))
    if len(comuns) < 5000 or len(ruins) > 0.01 * len(comuns):
        raise RuntimeError("risco país não bate com o ArgentinaDatos: %r" % ruins[:10])
    ult = max(a)
    if ult in b and b[ult] != a[ult]:
        raise RuntimeError("risco país: último ponto %s difere (%s × %s)" % (ult, a[ult], b[ult]))


def conferir_cambio(nome, a, b):
    m = {}
    for d, v in a.items():
        if d in b and d.strftime("%Y-%m") >= INICIO_CONF:
            m.setdefault(d.strftime("%Y-%m"), []).append((v, b[d]))
    ruins = []
    for k, pares in m.items():
        xa = statistics.mean(x for x, _ in pares)
        xb = statistics.mean(y for _, y in pares)
        ruins.append(((abs(xb - xa) - 0.5) / xa, k))
    ruins.sort(reverse=True)
    print("%s: %d meses conferidos desde %s, maior diferença além do arredondamento %.2f%% (%s)"
          % (nome, len(m), INICIO_CONF, ruins[0][0] * 100, ruins[0][1]))
    if len(m) < 100 or ruins[0][0] > TOL_MES[nome]:
        raise RuntimeError("%s: média mensal não bate: %r" % (nome, ruins[:5]))
    ult = max(a)
    ok = [d for d in b if 0 <= (d - ult).days <= 2 and abs(b[d] / a[ult] - 1) <= 0.005]
    if not ok:
        raise RuntimeError("%s: último fechamento %s (%s) não aparece no ArgentinaDatos" % (nome, ult, a[ult]))


def serie(nome, s, casas, **extra):
    return dict(nome=nome, dados=[[d.isoformat(), round(s[d], casas)] for d in sorted(s)], **extra)


def main():
    risco = ambito("riesgopais", "-")
    blue = ambito("dolar/informal", "/")
    oficial = ambito("dolar/oficial", "/")

    conferir_risco(risco, argdatos("finanzas/indices/riesgo-pais", "valor"))
    conferir_cambio("blue", blue, argdatos("cotizaciones/dolares/blue", "venta"))
    conferir_cambio("oficial", oficial, argdatos("cotizaciones/dolares/oficial", "venta"))

    dias = sorted(d for d in blue if d in oficial)
    brecha = {d: (blue[d] / oficial[d] - 1) * 100 for d in dias}
    dif = {d: blue[d] - oficial[d] for d in dias}
    for d in dias:
        b2 = (round(blue[d], 2) / round(oficial[d], 2) - 1) * 100
        if abs(b2 - brecha[d]) > 0.05:
            raise RuntimeError("brecha de %s não fecha: %s × %s" % (d, b2, brecha[d]))

    u = max(risco)
    print("último risco país: %s = %.0f pontos" % (u, risco[u]))
    u = dias[-1]
    print("último câmbio: %s, blue %.2f, oficial %.2f, brecha %.2f%% (%.2f pesos)"
          % (u, blue[u], oficial[u], brecha[u], dif[u]))
    pico = max(dias, key=lambda d: brecha[d])
    print("maior brecha: %s = %.1f%%" % (pico, brecha[pico]))

    g_risco = dict(
        id="argentina-risco-pais", titulo="Risco país da Argentina, desde 1998",
        subtitulo="Spread do EMBI da Argentina sobre os títulos do Tesouro americano, em pontos básicos; diário",
        unidade="int", diario=True, buracoMax=8, fonte="Ámbito (JP Morgan)",
        series=[serie("Risco país", risco, 0, cor=BRANCO, largura=3, rotulo=True)],
    )
    g_cambio = dict(
        id="argentina-dolar-blue-oficial", titulo="Dólar blue e dólar oficial na Argentina, desde 2002",
        subtitulo="Pesos por dólar, cotação de venda; diário",
        unidade="n2", diario=True, buracoMax=8, fonte="Ámbito",
        series=[serie("Dólar blue", blue, 2, cor=BRANCO, largura=3, rotulo=True),
                serie("Dólar oficial", oficial, 2, cor=AZUL, largura=2.5, rotulo=True)],
    )
    g_brecha = dict(
        id="argentina-brecha-cambial", titulo="Brecha cambial na Argentina: dólar blue menos dólar oficial, desde 2002",
        subtitulo="Diferença entre o dólar blue e o oficial, cotação de venda; diário",
        diario=True, buracoMax=8, fonte="Ámbito e FtM", unidade="pct1",
        variantes=[
            dict(rot="em %", unidade="pct1",
                 series=[serie("Brecha (%)", brecha, 2, cor=BRANCO, largura=3, rotulo=True)]),
            dict(rot="em pesos", unidade="n2",
                 series=[serie("Brecha (pesos)", dif, 2, cor=BRANCO, largura=3, rotulo=True)]),
        ],
    )

    ref = max(max(risco), dias[-1])
    doc = dict(assunto="Argentina", grupo="Análises Variadas", fonte="Ámbito e FtM",
               referencia=ref.strftime("%Y-%m"), atualizado=datetime.date.today().isoformat(), formato="artigo",
               secoes=[dict(titulo="Risco país", texto="", fontes=[], figuras=[], graficos=[g_risco]),
                       dict(titulo="Câmbio", texto="", fontes=[], figuras=[], graficos=[g_cambio, g_brecha])])
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado", SAIDA)


if __name__ == "__main__":
    sys.exit(main())

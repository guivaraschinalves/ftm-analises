#!/usr/bin/env python3
"""
Argentina: risco país, dólar blue, dólar oficial e brecha cambial (diários),
reservas internacionais (bruta, ativos e passivos, líquida) e inflação.
Gera dados/argentina.json. Só biblioteca padrão. Rodado à mão. Página
própria: argentina.html (fora do índice).

Pedido dele em 26/11/2026. Todo gráfico tem dois recortes: a série inteira
(com a marca da posse) e só desde a posse de Milei (10/12/2023; nas séries
mensais, desde dez/2023).

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

RESERVAS
  - Bruta, diária: BCRA, API de Estadísticas v4.0, variável 1 ("Reservas
    internacionales"), US$ milhões, desde 1996. Cifras provisórias.
  - Ativos e passivos, mensal (fim de mês): a planilha de Reservas
    Internacionais e Liquidez em Moeda Estrangeira que o BCRA entrega ao FMI
    (padrão SDDS), lida da API SDMX do FMI (IMF.STA/IRFCL, ARG, setor S1X =
    autoridade monetária). Ativo: IRFCL65 (ativos de reserva oficiais).
    Passivos: a seção II, drenos predeterminados de curto prazo (vencem em
    até 12 meses), em três partes:
      depósitos, empréstimos e títulos em moeda estrangeira = IRFCL78 (ou,
        quando falta, IRFCL79 + IRFCL80 saídas + IRFCL80 entradas); aqui
        entram os depósitos dos bancos no BCRA (encaixes), repos, BIS;
      swaps e futuros, posição vendida = IRFCL1T (o swap com a China a
        partir de dez/2022);
      outros drenos = IRFCL85 (até nov/2022 o BCRA lançava aqui o swap com
        a China).
  - Reserva líquida = ativos de reserva + drenos (que vêm negativos), só do
    BCRA. Os vencimentos do Tesouro (setor S1311) ficam de fora.

INFLAÇÃO
  - INDEC, IPC nacional base dez/2016 = 100 (serie_ipc_divisiones.csv,
    código 0, região Nacional). Mensal e em 12 meses recalculadas do índice.
    A série nacional começa em dez/2016; a série longa do BCRA (desde 1943)
    emenda índices de outra cobertura, os números de 2007 a 2015 e um
    substituto no apagão estatístico de 2015/16, e por isso não entra.

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
  - Reserva bruta do FMI (IRFCL65) contra o último dia do mês do BCRA desde
    2002: ≤ 0,5%, salvo ago a nov/2009 (a alocação de DEG de 2009 entra
    antes no FMI; ≤ 6%) e jan/2002 e dez/2003 (≤ 2,5%).
  - As três partes dos drenos somam o total da seção II (IRFCLDT2): ≤ US$ 2
    milhões em todo mês.
  - IPC: variação mensal e em 12 meses refeitas do índice contra as
    publicadas pelo INDEC (≤ 0,051 p.p., o INDEC publica com uma casa) e
    contra as variáveis 27 e 28 da API do BCRA a partir de jun/2017 (≤ 0,051
    p.p.; antes disso o BCRA usa o IPC GBA).
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
BCRA = "https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/%d?desde=%s&hasta=%s&limit=3000&offset=%d"
FMI = ("https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IRFCL/+/ARG.*.S1X.M"
       "?attributes=dsd&measures=all")
INDEC = "https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_divisiones.csv"
POSSE = datetime.date(2023, 12, 10)
# de jan a mai/2017 o BCRA (variáveis 27 e 28) traz o IPC GBA: o nacional só
# saiu depois, retroativo a jan/2017
INICIO_BCRA_IPC = "2017-06"
POSSE_MES = "2023-12"
# meses em que a reserva bruta do FMI pode se afastar da do BCRA (ver acima)
TOL_BRUTA = {"2009-08": 0.06, "2009-09": 0.06, "2009-10": 0.06, "2009-11": 0.06,
             "2002-01": 0.025, "2003-12": 0.025}
TOL_MES = {"blue": 0.03, "oficial": 0.04}   # na média mensal, além de 0,5 peso de arredondamento
INICIO_CONF = "2014-01"

BRANCO, AZUL, VERMELHO, VERDE, AZUL_ESC = "#FFFFFF", "#4F81BD", "#C0504D", "#9BBB59", "#1F497D"


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
    chave = lambda d: d if isinstance(d, str) else d.isoformat()
    return dict(nome=nome, dados=[[chave(d), round(s[d], casas)] for d in sorted(s)], **extra)


def recortes(series, mensal, rot_extra="", unidade=None):
    """Série inteira (com a marca da posse) e só desde a posse de Milei."""
    desde = POSSE_MES if mensal else POSSE.isoformat()
    suf = (", " + rot_extra) if rot_extra else ""
    a = dict(rot="Série inteira" + suf, series=series, eventos=[dict(em=desde, rot="Posse de Milei")])
    b = dict(rot="Desde a posse de Milei" + suf, eventos=[],
             series=[dict(x, dados=[p for p in x["dados"] if p[0] >= desde]) for x in series])
    if unidade:
        a["unidade"] = b["unidade"] = unidade
    return [a, b]


def bcra(var, desde="1996-01-01"):
    hoje = datetime.date.today().isoformat()
    out, off = {}, 0
    while True:
        d = baixar(BCRA % (var, desde, hoje, off))
        det = d["results"][0]["detalle"]
        for x in det:
            out[datetime.date.fromisoformat(x["fecha"])] = float(x["valor"])
        if len(det) < 3000:
            break
        off += 3000
    if not out:
        raise RuntimeError("BCRA %d: vazio" % var)
    print("BCRA %-4d %d pontos, %s a %s" % (var, len(out), min(out), max(out)))
    return out


def irfcl():
    """{indicador: {"aaaa-mm": US$ milhões}} da planilha de liquidez (S1X)."""
    d = baixar(FMI)
    st = d["data"]["structures"][0]
    dims = st["dimensions"]["series"]
    pos = [x["id"] for x in dims].index("INDICATOR")
    per = [o["value"] for o in st["dimensions"]["observation"][0]["values"]]
    tab = {}
    for k, s in d["data"]["dataSets"][0]["series"].items():
        ind = dims[pos]["values"][int(k.split(":")[pos])]["id"]
        for i, o in s["observations"].items():
            if o[0] not in (None, "NaN"):
                tab.setdefault(ind, {})[per[int(i)].replace("-M", "-")] = float(o[0]) / 1e6
    print("FMI IRFCL: %d indicadores, ativos de reserva de %s a %s"
          % (len(tab), min(tab["IRFCLDT1_IRFCL65_USD"]), max(tab["IRFCLDT1_IRFCL65_USD"])))
    return tab


def reservas_mensais(tab, bruta_dia):
    ativo = tab["IRFCLDT1_IRFCL65_USD"]
    total = tab["IRFCLDT2_USD"]
    swaps = tab.get("IRFCLDT2_IRFCL1T_SHP_USD", {})
    outros = tab.get("IRFCLDT2_IRFCL85_USD", {})
    dep = {}
    for m in total:
        if m in tab.get("IRFCLDT2_IRFCL78_USD", {}):
            dep[m] = tab["IRFCLDT2_IRFCL78_USD"][m]
        else:
            dep[m] = sum(tab.get(k, {}).get(m, 0.0) for k in
                         ("IRFCLDT2_IRFCL79_FO_USD", "IRFCLDT2_IRFCL80_FO_USD", "IRFCLDT2_IRFCL80_IN_USD"))
    meses = sorted(m for m in total if m in ativo)
    for m in meses:
        soma = dep[m] + swaps.get(m, 0.0) + outros.get(m, 0.0)
        if abs(soma - total[m]) > 2:
            raise RuntimeError("drenos de %s não somam o total: %.0f × %.0f" % (m, soma, total[m]))
    # conferência: ativo do FMI × último dia do mês do BCRA
    fim = {}
    for d, v in bruta_dia.items():
        k = d.strftime("%Y-%m")
        if k not in fim or d > fim[k][0]:
            fim[k] = (d, v)
    pior = (0, None)
    for m, v in ativo.items():
        if m < "2002-01" or m not in fim:
            continue
        dif = abs(fim[m][1] / v - 1)
        if dif > TOL_BRUTA.get(m, 0.005):
            raise RuntimeError("reserva bruta de %s: FMI %.0f × BCRA %.0f" % (m, v, fim[m][1]))
        if m not in TOL_BRUTA:
            pior = max(pior, (dif, m))
    print("reserva bruta FMI × BCRA: maior diferença fora das exceções %.3f%% (%s)" % (pior[0] * 100, pior[1]))
    liq = {m: ativo[m] + total[m] for m in meses}
    return meses, ativo, dep, swaps, outros, liq


def ipc():
    with urllib.request.urlopen(urllib.request.Request(INDEC, headers=UA), timeout=120) as r:
        linhas = r.read().decode("latin-1").splitlines()
    cab = linhas[0].split(";")
    ic = {c: cab.index(c) for c in ("Codigo", "Periodo", "Indice_IPC", "v_m_IPC", "v_i_a_IPC", "Region")}
    ind, vm_pub, via_pub = {}, {}, {}
    for l in linhas[1:]:
        c = l.split(";")
        if len(c) < len(cab) or c[ic["Codigo"]] != "0" or c[ic["Region"]] != "Nacional":
            continue
        m = c[ic["Periodo"]][:4] + "-" + c[ic["Periodo"]][4:6]
        ind[m] = num_ar(c[ic["Indice_IPC"]]) if "," in c[ic["Indice_IPC"]] else float(c[ic["Indice_IPC"]])
        for col, dest in (("v_m_IPC", vm_pub), ("v_i_a_IPC", via_pub)):
            if c[ic[col]] not in ("NA", ""):
                dest[m] = float(c[ic[col]].replace(",", "."))
    meses = sorted(ind)
    if meses[0] != "2016-12" or len(meses) < 100:
        raise RuntimeError("IPC INDEC: série inesperada %s a %s" % (meses[0], meses[-1]))
    def menos(m, k):
        t = int(m[:4]) * 12 + int(m[5:]) - 1 - k
        return "%04d-%02d" % (t // 12, t % 12 + 1)
    vm = {m: (ind[m] / ind[menos(m, 1)] - 1) * 100 for m in meses if menos(m, 1) in ind}
    via = {m: (ind[m] / ind[menos(m, 12)] - 1) * 100 for m in meses if menos(m, 12) in ind}
    for nome, calc, pub in (("mensal", vm, vm_pub), ("12 meses", via, via_pub)):
        if set(calc) != set(pub):
            raise RuntimeError("IPC %s: meses diferentes do publicado" % nome)
        pior = max(abs(calc[m] - pub[m]) for m in calc)
        print("IPC %s refeito × INDEC: maior diferença %.3f p.p." % (nome, pior))
        if pior > 0.051:
            raise RuntimeError("IPC %s não bate com o INDEC" % nome)
    for var, nome, calc in ((27, "mensal", vm), (28, "12 meses", via)):
        b = {d.strftime("%Y-%m"): v for d, v in bcra(var, "2016-01-01").items()}
        comuns = [m for m in calc if m in b and m >= INICIO_BCRA_IPC]
        pior = max(abs(calc[m] - b[m]) for m in comuns)
        print("IPC %s × BCRA (var. %d): %d meses, maior diferença %.3f p.p." % (nome, var, len(comuns), pior))
        if len(comuns) < len([m for m in calc if m >= INICIO_BCRA_IPC]) - 1 or pior > 0.051:
            raise RuntimeError("IPC %s não bate com o BCRA" % nome)
    return vm, via


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

    bruta = bcra(1)
    meses, ativo, dep, swaps, outros, liq = reservas_mensais(irfcl(), bruta)
    vm, via = ipc()
    u = max(bruta)
    print("última reserva bruta (BCRA): %s = US$ %.0f milhões" % (u, bruta[u]))
    m = meses[-1]
    print("último mês da planilha: %s, bruta %.0f, depósitos etc. %.0f, swaps %.0f, outros %.0f, líquida %.0f"
          % (m, ativo[m], dep[m], swaps.get(m, 0), outros.get(m, 0), liq[m]))
    print("líquida em %s (posse): %.0f" % ("2023-12", liq["2023-12"]))
    m = max(vm)
    print("IPC %s: mensal %.2f%%, 12 meses %.2f%%" % (m, vm[m], via[m]))

    g_risco = dict(
        id="argentina-risco-pais", titulo="Risco país da Argentina",
        subtitulo="Spread do EMBI da Argentina sobre os títulos do Tesouro americano, em pontos básicos; diário",
        unidade="int", diario=True, buracoMax=8, fonte="Ámbito (JP Morgan)",
        variantes=recortes([serie("Risco país", risco, 0, cor=BRANCO, largura=3, rotulo=True)], False),
    )
    g_cambio = dict(
        id="argentina-dolar-blue-oficial", titulo="Dólar blue e dólar oficial na Argentina",
        subtitulo="Pesos por dólar, cotação de venda; diário",
        unidade="n2", diario=True, buracoMax=8, fonte="Ámbito",
        variantes=recortes([serie("Dólar blue", blue, 2, cor=BRANCO, largura=3, rotulo=True),
                            serie("Dólar oficial", oficial, 2, cor=AZUL, largura=2.5, rotulo=True)], False),
    )
    g_brecha = dict(
        id="argentina-brecha-cambial", titulo="Brecha cambial na Argentina: dólar blue menos dólar oficial",
        subtitulo="Diferença entre o dólar blue e o oficial, cotação de venda; diário",
        diario=True, buracoMax=8, fonte="Ámbito e FtM", unidade="pct1",
        variantes=recortes([serie("Brecha (%)", brecha, 2, cor=BRANCO, largura=3, rotulo=True)], False, "em %", "pct1")
        + recortes([serie("Brecha (pesos)", dif, 2, cor=BRANCO, largura=3, rotulo=True)], False, "em pesos", "n2"),
    )
    bi = lambda d: {k: v / 1000 for k, v in d.items()}
    g_bruta = dict(
        id="argentina-reservas-brutas", titulo="Reservas internacionais brutas do BCRA",
        subtitulo="US$ bilhões; diário; cifras provisórias", unidade="usd-bi", diario=True, buracoMax=8,
        fonte="BCRA (Principales variables)",
        variantes=recortes([serie("Reservas brutas", bi(bruta), 3, cor=BRANCO, largura=3, rotulo=True)], False),
    )
    g_comp = dict(
        id="argentina-reservas-ativos-passivos", titulo="Reservas do BCRA: ativos e passivos de curto prazo",
        subtitulo="US$ bilhões, fim de mês; passivos: saídas de moeda estrangeira já contratadas que vencem em até 12 meses",
        unidade="usd-bi", fonte="BCRA (Reservas Internacionais e Liquidez em Moeda Estrangeira, via FMI) e FtM",
        variantes=recortes([
            serie("Reservas brutas", {m: ativo[m] / 1000 for m in meses}, 3, cor=AZUL, tipo="barra"),
            serie("Depósitos, empréstimos e títulos", {m: dep[m] / 1000 for m in meses}, 3, cor=VERMELHO, tipo="barra"),
            serie("Swaps de moeda", {m: swaps[m] / 1000 for m in meses if m in swaps}, 3, cor=VERDE, tipo="barra"),
            serie("Outros (até nov/22, inclui o swap com a China)", {m: outros[m] / 1000 for m in meses if m in outros},
                  3, cor=AZUL_ESC, tipo="barra"),
            serie("Reservas líquidas", {m: liq[m] / 1000 for m in meses}, 3, cor=BRANCO, largura=3, rotulo=True),
        ], True),
    )
    g_liq = dict(
        id="argentina-reservas-liquidas", titulo="Reservas internacionais líquidas do BCRA",
        subtitulo="Reservas brutas menos os passivos de curto prazo do BCRA em moeda estrangeira; US$ bilhões, fim de mês",
        unidade="usd-bi", fonte="BCRA (Reservas Internacionais e Liquidez em Moeda Estrangeira, via FMI) e FtM",
        variantes=recortes([serie("Reservas líquidas", {m: liq[m] / 1000 for m in meses}, 3,
                                  cor=BRANCO, largura=3, rotulo=True)], True),
    )
    g_ipc_m = dict(
        id="argentina-inflacao-mensal", titulo="Inflação mensal na Argentina",
        subtitulo="IPC nacional, variação % em relação ao mês anterior", unidade="pct1",
        fonte="INDEC (IPC) e FtM",
        variantes=recortes([serie("Inflação mensal", vm, 1, cor=AZUL, tipo="barra", rotulo=True)], True),
    )
    g_ipc_a = dict(
        id="argentina-inflacao-12m", titulo="Inflação em 12 meses na Argentina",
        subtitulo="IPC nacional, variação % acumulada em 12 meses", unidade="pct1",
        fonte="INDEC (IPC) e FtM",
        variantes=recortes([serie("Inflação em 12 meses", via, 1, cor=BRANCO, largura=3, rotulo=True)], True),
    )

    ref = max(max(risco), dias[-1], max(bruta))
    doc = dict(assunto="Argentina", grupo="Análises Variadas", fonte="Ámbito, BCRA, FMI, INDEC e FtM",
               referencia=ref.strftime("%Y-%m"), atualizado=datetime.date.today().isoformat(), formato="artigo",
               secoes=[dict(titulo="Risco país", texto="", fontes=[], figuras=[], graficos=[g_risco]),
                       dict(titulo="Câmbio", texto="", fontes=[], figuras=[], graficos=[g_cambio, g_brecha]),
                       dict(titulo="Reservas internacionais", texto="", fontes=[], figuras=[],
                            graficos=[g_bruta, g_comp, g_liq]),
                       dict(titulo="Inflação", texto="", fontes=[], figuras=[], graficos=[g_ipc_m, g_ipc_a])])
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado", SAIDA)


if __name__ == "__main__":
    sys.exit(main())

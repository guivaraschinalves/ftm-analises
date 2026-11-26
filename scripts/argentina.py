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
    dos bancos; não é o atacado da Com. A 3500), desde abr/2002. Fica o
    Ámbito por decisão dele (26/11/2026), mesmo com dias que destoam do BCRA
    (ex.: 23/04/2025, 1.333,24 no Ámbito contra 1.174,51 do BCRA, que dá
    brecha de −9,2% nesse dia).
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
        entram os depósitos dos bancos no BCRA (encaixes) e empréstimos;
      swaps e futuros, posição vendida = IRFCL1T (o swap com a China a
        partir de dez/2022);
      outros drenos = IRFCL85 (inclui os repos, IRFCL48T; até nov/2022 o
        BCRA lançava aqui também o swap com a China).
  - Reserva líquida = ativos de reserva + drenos (que vêm negativos), só do
    BCRA. Os vencimentos do Tesouro (setor S1311) ficam de fora.

INFLAÇÃO
  - INDEC, IPC nacional base dez/2016 = 100 (serie_ipc_divisiones.csv,
    código 0, região Nacional). Mensal e em 12 meses recalculadas do índice.
    A série nacional começa em dez/2016; a série longa do BCRA (desde 1943)
    emenda índices de outra cobertura, os números de 2007 a 2015 e um
    substituto no apagão estatístico de 2015/16, e por isso não entra.

BASE MONETÁRIA E M2 (mensal, fim de mês, desde jan/1990)
  - BCRA, API v4.0, séries históricas mensais em milhares de pesos:
    1606 base monetária = 1608 moeda em poder do público + 1609 moeda nos
    bancos + 1610 contas correntes dos bancos no BCRA (reservas bancárias);
    1611/1612 M1 total/em moeda local; 1617/1618 M2 total/em moeda local.
    M1 em moeda estrangeira = 1611 − 1612; poupança (cajas de ahorro) em
    moeda local = 1618 − 1612; em moeda estrangeira = (1617 − 1618) − (1611 −
    1612). Os depósitos em dólar já vêm convertidos em pesos pelo BCRA.
  - Em dólares: dividido pelo câmbio de referência do BCRA (Com. A 3500,
    variável 5, último dia útil do mês) a partir de mar/2002, quando a série
    começa; antes, pelo câmbio oficial de fim de mês do FMI (IMF.STA/ER,
    XDC_USD, EOP_RT), que cobre 1990 a fev/2002.
  - Variação em 12 meses a partir de jan/1992: em 1990 e 1991, saindo da
    hiperinflação, passa de 1.000% e achata o resto da série.

ATIVOS DO BCRA (mensal, fim de mês, desde jan/1990)
  - Balanço do BCRA, planilha balbcrhis.xls do próprio BCRA (Cuadro I-2,
    aba "B.C.R.A."), lida pelo rótulo do código de cada coluna (bcra2...):
    ativos externos líquidos (activos externos netos, total), crédito ao
    setor oficial (sector oficial, total) e créditos a entidades financeiras
    em moeda nacional; a soma é o total das fontes da base monetária.
  - Valores convertidos a milhares de pesos atuais com as colunas
    "Unidades monetarias originales representadas" e "Equivalencia" (nota
    da aba Observaciones). O câmbio de valuação da própria
    planilha não serve antes de 2002 (vem na unidade antiga): em dólares usa
    o mesmo câmbio da base e do M2, e a coluna "1 u$s =" fica como
    conferência a partir de abr/2002.

BRASIL, PARA COMPARAR (variação em 12 meses no mesmo gráfico da Argentina)
  - BCB, SGS: 1788 base monetária restrita (saldo de fim de período) =
    1786 papel-moeda emitido + 1787 reservas bancárias; 27810 M2 (conceito
    atual, saldo de fim de período) = 27791 M1 + 1835 depósitos de poupança +
    27809 títulos privados em poder do público.
  - A base vem em unidade monetária corrente: a variação em 12 meses só
    começa em jul/1995, um ano depois do real. O M2 no conceito atual começa
    em dez/2001, então a variação começa em dez/2002.

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
  - Oficial do Ámbito × BCRA (variável 4) dia a dia desde jun/2010: mediana
    ≤ 0,1% e no máximo 1% dos dias acima de 1% (os poucos dias fora ficam
    impressos no log; a série usada continua a do Ámbito).
  - Brecha recalculada a partir da série gravada (arredondada) contra a de
    precisão cheia: ≤ 0,05 p.p.
  - Reserva bruta do FMI (IRFCL65) contra o último dia do mês do BCRA desde
    2002: ≤ 0,5%, salvo ago a nov/2009 (a alocação de DEG de 2009 entra
    antes no FMI; ≤ 6%) e jan/2002 e dez/2003 (≤ 2,5%).
  - As três partes dos drenos somam o total da seção II (IRFCLDT2): ≤ US$ 2
    milhões em todo mês.
  - Base monetária = soma dos três componentes; M1 e M2 totais = moeda local
    + estrangeira (cc e cajas de ahorro, 1613 a 1616, 1619 a 1622): ≤ 1 mil
    pesos em todo mês desde 1990.
  - Base monetária do BCRA contra a do FMI (MFS_CBS, S121_L_MB_CBS, desde
    2017): ≤ 0,01%.
  - Câmbio do FMI contra o de referência do BCRA (variável 5, último dia
    útil do mês) desde abr/2002: ≤ TOL_CAMBIO (3%; o FMI usa outra cotação
    oficial e chega a 2,3% de distância; a mediana fica perto de zero).
  - Balanço do BCRA: ativos externos + setor oficial + crédito a bancos =
    total das fontes, e essa soma − absorção = base monetária (≤ 1 mil pesos;
    exceções da própria planilha em TOTAL_ERRADO e ABSORCAO_ERRADA, e o total
    usado é sempre a soma das três contas); essa base contra a série 1606 da API do BCRA (≤ 0,01%); câmbio
    de valuação contra o câmbio usado na base e no M2, desde abr/2002 (≤ 3,5%, TOL_VALUACAO; mar/2002, o primeiro mês do câmbio de referência, fica de fora).
  - Brasil: base = papel-moeda emitido + reservas bancárias e M2 = M1 +
    poupança + títulos privados (≤ R$ 2 mil em todo mês); base do BCB contra
    a do FMI (MFS_MA, NDMBM_MAI): ≤ 0,01%.
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
FMI_ER = ("https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/ER/+/ARG.XDC_USD.EOP_RT.M"
          "?attributes=dsd&measures=all")
FMI_CBS = ("https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/MFS_CBS/+/ARG.S121_L_MB_CBS.*.M"
           "?attributes=dsd&measures=all")
SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.%d/dados?formato=json&dataInicial=01/01/1990&dataFinal=%s"
FMI_MA_BR = ("https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/MFS_MA/+/BRA.NDMBM_MAI.*.M"
             "?attributes=dsd&measures=all")
INICIO_YOY_BR_BASE = "1995-07"
INICIO_YOY_BR_M2 = "2002-12"
BALBCR = "https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/balbcrhis.xls"
# meses em que a própria planilha não fecha (conferido à mão em 26/11/2026):
# em 2014 a célula do total diverge da soma das três contas, mas a soma menos
# a absorção dá a base exata (o total publicado é que está errado); em
# nov/2009 a absorção difere em 4,1 bi de pesos. Trocar se o BCRA corrigir.
TOTAL_ERRADO = {"2014-01", "2014-02", "2014-09", "2014-10", "2014-11", "2014-12"}
ABSORCAO_ERRADA = {"2009-11"}
MESES_ES = {"Ene.": 1, "Feb.": 2, "Mar.": 3, "Abr.": 4, "May.": 5, "Jun.": 6, "Jul.": 7, "Ago.": 8,
            "Sep.": 9, "Set.": 9, "Oct.": 10, "Nov.": 11, "Dic.": 12}
INICIO_MON = "1990-01"
INICIO_YOY = "1992-01"
TOL_CAMBIO = 0.03
# valuação do balanço × câmbio de fim de mês: até 3,1% em 2002 e 2003, logo
# depois da desvalorização (a data de valuação nem sempre é o último dia útil)
TOL_VALUACAO = 0.035
INDEC = "https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_divisiones.csv"
POSSE = datetime.date(2023, 12, 10)
INICIO_OFICIAL_BCRA = datetime.date(2010, 6, 1)
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
AZUL_CLARO = "#8EB4E3"


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
    # o dia de hoje é cotação intradia, não fechamento
    out.pop(datetime.date.today(), None)
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


def conferir_oficial_bcra(amb):
    v4 = bcra(4, INICIO_OFICIAL_BCRA.isoformat())
    hoje = datetime.date.today()
    v4 = {d: x for d, x in v4.items() if d < hoje}
    com = [d for d in amb if d in v4]
    difs = sorted(((abs(amb[d] / v4[d] - 1), d) for d in com), reverse=True)
    med = statistics.median(x for x, _ in difs)
    fora = [(str(d), amb[d], v4[d]) for x, d in difs if x > 0.01]
    print("oficial Ámbito × BCRA (var. 4): %d dias, mediana %.3f%%, %d dias acima de 1%%; maiores: %r"
          % (len(com), med * 100, len(fora), fora[:3]))
    if len(com) < 3000 or med > 0.001 or len(fora) > 0.01 * len(com):
        raise RuntimeError("oficial do Ámbito não bate com o BCRA")


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


def sdmx_mensal(url):
    """Série única mensal do FMI: {"aaaa-mm": valor}."""
    d = baixar(url)
    st = d["data"]["structures"][0]
    per = [o["value"] for o in st["dimensions"]["observation"][0]["values"]]
    series = list(d["data"]["dataSets"][0]["series"].values())
    if len(series) != 1:
        raise RuntimeError("FMI: esperava 1 série, vieram %d (%s)" % (len(series), url))
    return {per[int(i)].replace("-M", "-"): float(o[0]) for i, o in series[0]["observations"].items()
            if o[0] not in (None, "NaN")}


def mais(m, k):
    t = int(m[:4]) * 12 + int(m[5:]) - 1 + k
    return "%04d-%02d" % (t // 12, t % 12 + 1)


def monetario():
    v = {}
    for n in list(range(1606, 1634)):
        if n in (1607, 1623, 1624) or n >= 1625:
            continue
        v[n] = {d.strftime("%Y-%m"): x for d, x in bcra(n, "1940-01-01").items()}
    meses = [m for m in sorted(v[1606]) if m >= INICIO_MON]
    for m in meses:
        g = lambda n: v[n].get(m, 0.0)
        for nome, a, b in (("base", g(1606), g(1608) + g(1609) + g(1610)),
                           ("M1 local", g(1612), g(1608) + g(1613) + g(1614)),
                           ("M1 estrangeira", g(1611) - g(1612), g(1615) + g(1616)),
                           ("M2 local", g(1618), g(1612) + g(1619) + g(1620)),
                           ("M2 estrangeira", g(1617) - g(1618), g(1615) + g(1616) + g(1621) + g(1622))):
            if abs(a - b) > 1:
                raise RuntimeError("%s de %s não fecha: %.0f × %.0f" % (nome, m, a, b))
    print("identidades da base, M1 e M2: %d meses, de %s a %s" % (len(meses), meses[0], meses[-1]))
    cbs = sdmx_mensal(FMI_CBS)
    pior = max(abs(cbs[m] / 1000 / v[1606][m] - 1) for m in cbs if m in v[1606])
    print("base monetária BCRA × FMI (MFS): %d meses, maior diferença %.4f%%"
          % (len([m for m in cbs if m in v[1606]]), pior * 100))
    if pior > 0.0001:
        raise RuntimeError("base monetária não bate com o FMI")
    cambio = sdmx_mensal(FMI_ER)
    ref = {}
    for d, x in bcra(5, "2002-03-01").items():
        k = d.strftime("%Y-%m")
        if k not in ref or d > ref[k][0]:
            ref[k] = (d, x)
    difs = sorted(((abs(ref[m][1] / cambio[m] - 1), m) for m in cambio if m in ref and m >= "2002-04"), reverse=True)
    print("câmbio FMI × BCRA (var. 5): %d meses, maior diferença %.3f%% (%s)" % (len(difs), difs[0][0] * 100, difs[0][1]))
    if difs[0][0] > TOL_CAMBIO:
        raise RuntimeError("câmbio do FMI não bate com o BCRA: %r" % difs[:5])
    print("câmbio FMI × BCRA: mediana %.3f%%" % (statistics.median(x for x, _ in difs) * 100))
    cambio = {m: x for m, x in cambio.items() if m < "2002-03"}
    cambio.update({m: x for m, (_, x) in ref.items()})
    falta = [m for m in meses if m not in cambio]
    if falta:
        print("meses sem câmbio do FMI (ficam buraco em dólares):", falta)
    return v, meses, cambio


def balanco_bcra(base_api, cambio):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from xls import abas
    with urllib.request.urlopen(urllib.request.Request(BALBCR, headers=UA), timeout=120) as r:
        c = abas(r.read())["B.C.R.A."]
    cols = sorted({k for _, k in c})
    linhas = sorted({r for r, _ in c})
    # cada coluna tem um código (bcra2, bcra6...) numa linha do cabeçalho
    cod = {}
    for k in cols:
        for r in linhas[:40]:
            v = c.get((r, k))
            if isinstance(v, str) and v.strip().startswith("bcra"):
                cod[v.strip()] = k
    precisa = {"externos": "bcra2", "oficial": "bcra6", "bancos": "bcra17", "absorcao": "bcra19",
               "base": "bcra29", "cambio": "bcra34"}
    falta = [v for v in precisa.values() if v not in cod]
    if falta:
        raise RuntimeError("balbcrhis: códigos não achados %r" % falta)
    # a coluna do total das fontes não tem código: é a de rótulo "Total" logo antes de "Fuentes de absorción"
    k_total = cod["bcra19"] - 1
    # externos: o código bcra2 é "Oro y divisas"; o total de ativos externos é a coluna anterior
    k_ext = cod["bcra2"] - 1
    k_uni, k_eq = 4, 5
    # o leitor devolve RK inteiro como int: vale como número também
    num = lambda v: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    out = {n: {} for n in ("externos", "oficial", "bancos", "total", "absorcao", "base", "cambio")}
    for r in linhas:
        ano, mes = c.get((r, 0)), c.get((r, 1))
        # o rótulo do mês às vezes traz marca ("Ene. *", "Ene. ")
        mes = mes.split()[0] if isinstance(mes, str) and mes.split() else mes
        if num(ano) is None or mes not in MESES_ES:
            continue
        m = "%04d-%02d" % (int(ano), MESES_ES[mes])
        if m < INICIO_MON or num(c.get((r, k_total))) is None:
            continue
        fator = c[(r, k_uni)] * c[(r, k_eq)] / 1000      # -> milhares de pesos atuais
        for n, k in (("externos", k_ext), ("oficial", cod["bcra6"]), ("bancos", cod["bcra17"]),
                     ("total", k_total), ("absorcao", cod["bcra19"]), ("base", cod["bcra29"])):
            v = num(c.get((r, k)))
            out[n][m] = (v or 0.0) * fator
        if num(c.get((r, cod["bcra34"]))):
            out["cambio"][m] = c[(r, cod["bcra34"])]
    meses = sorted(out["total"])
    todos = [mais(meses[0], k) for k in range(len(meses) + 24) if mais(meses[0], k) <= meses[-1]]
    if [m for m in todos if m not in out["total"]]:
        raise RuntimeError("balbcrhis: meses faltando %r" % [m for m in todos if m not in out["total"]])
    for m in meses:
        soma = out["externos"][m] + out["oficial"][m] + out["bancos"][m]
        ok_total = abs(soma - out["total"][m]) <= 1 or m in TOTAL_ERRADO
        ok_base = abs(soma - out["absorcao"][m] - out["base"][m]) <= 1 or m in ABSORCAO_ERRADA
        if not (ok_total and ok_base):
            raise RuntimeError("balanço do BCRA de %s não fecha: soma %.0f, total %.0f, base %.0f"
                               % (m, soma, out["total"][m], out["base"][m]))
        out["total"][m] = soma            # o total é a soma das três contas
    # dez/2007: a base do balanço fica 0,30% acima da série 1606 (revisão); os demais meses batem exatamente
    pior = max((abs(out["base"][m] / base_api[m] - 1), m) for m in meses if m in base_api and m != "2007-12")
    if abs(out["base"]["2007-12"] / base_api["2007-12"] - 1) > 0.005:
        raise RuntimeError("base de dez/2007 do balanço passou de 0,5% da API")
    print("balanço do BCRA: %d meses (%s a %s); base contra a API, maior diferença %.4f%% (%s)"
          % (len(meses), meses[0], meses[-1], pior[0] * 100, pior[1]))
    if pior[0] > 0.0001:
        raise RuntimeError("base do balanço não bate com a API do BCRA")
    # a coluna de valuação só vale como conferência a partir de mar/2002 (antes vem na unidade antiga)
    difc = max((abs(out["cambio"][m] / cambio[m] - 1), m) for m in out["cambio"] if m in cambio and m >= "2002-04")
    print("câmbio de valuação × câmbio da base: maior diferença %.3f%% (%s)" % (difc[0] * 100, difc[1]))
    if difc[0] > TOL_VALUACAO:
        raise RuntimeError("câmbio de valuação do balanço não bate")
    return meses, out


def sgs(cod):
    hoje = datetime.date.today().strftime("%d/%m/%Y")
    d = baixar(SGS % (cod, hoje))
    out = {}
    for x in d:
        if x["valor"] not in (None, ""):
            dd, mm, aa = x["data"].split("/")
            out["%s-%s" % (aa, mm)] = float(x["valor"])
    if not out:
        raise RuntimeError("SGS %d vazio" % cod)
    print("BCB SGS %-5d %d meses, %s a %s" % (cod, len(out), min(out), max(out)))
    return out


def brasil():
    base, pme, resb = sgs(1788), sgs(1786), sgs(1787)
    m2, m1, poup, tit = sgs(27810), sgs(27791), sgs(1835), sgs(27809)
    for m in base:
        if m >= "1995-01" and abs(base[m] - pme.get(m, 0) - resb.get(m, 0)) > 2:
            raise RuntimeError("base do Brasil de %s não fecha: %.0f" % (m, base[m] - pme.get(m, 0) - resb.get(m, 0)))
    comuns_m2 = [m for m in m2 if m in m1 and m in poup and m in tit]
    if len(comuns_m2) < len(m2) - 1:      # o M1 do conceito atual começa um mês depois (jan/2002)
        raise RuntimeError("M2 do Brasil: faltam componentes em %d meses" % (len(m2) - len(comuns_m2)))
    for m in comuns_m2:
        if abs(m2[m] - m1[m] - poup[m] - tit[m]) > 2:
            raise RuntimeError("M2 do Brasil de %s não fecha: %.0f" % (m, m2[m] - m1[m] - poup[m] - tit[m]))
    fmi = sdmx_mensal(FMI_MA_BR)
    comuns = [m for m in fmi if m in base and m >= "1995-01"]
    pior = max(abs(fmi[m] / 1000 / base[m] - 1) for m in comuns)
    print("base do Brasil BCB × FMI: %d meses, maior diferença %.4f%%" % (len(comuns), pior * 100))
    if len(comuns) < 300 or pior > 0.0001:
        raise RuntimeError("base do Brasil não bate com o FMI")
    yoy_ = lambda s_, ini: {m: (s_[m] / s_[mais(m, -12)] - 1) * 100 for m in s_
                            if m >= ini and mais(m, -12) in s_}
    return yoy_(base, INICIO_YOY_BR_BASE), yoy_(m2, INICIO_YOY_BR_M2)


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
    conferir_oficial_bcra(oficial)

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
    mon, meses_mon, cambio = monetario()
    br_base, br_m2 = brasil()
    meses_bal, bal = balanco_bcra({m: mon[1606][m] for m in meses_mon}, cambio)
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
        id="argentina-brecha-cambial", titulo="Brecha cambial na Argentina: dólar blue sobre o dólar oficial",
        subtitulo="Quanto o dólar blue supera o oficial, em % ou em pesos; cotação de venda; diário",
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

    def quatro(series_fn, unidade_pesos="n2"):
        return (recortes(series_fn("pesos"), True, "em pesos", unidade_pesos)
                + recortes(series_fn("usd"), True, "em dólares", "usd-bi"))

    def conv(serie_mil, moeda):
        """milhares de pesos -> trilhões de pesos ou bilhões de dólares"""
        if moeda == "pesos":
            return {m: x / 1e9 for m, x in serie_mil.items()}
        return {m: x / cambio[m] / 1e6 for m, x in serie_mil.items() if m in cambio}

    sel = lambda n: {m: mon[n][m] for m in meses_mon}
    bm, pub, bancos, resb = sel(1606), sel(1608), sel(1609), sel(1610)
    m1l, m1t, m2l, m2t = sel(1612), sel(1611), sel(1618), sel(1617)
    m1e = {m: m1t[m] - m1l[m] for m in meses_mon}
    poup = {m: m2t[m] - m1t[m] for m in meses_mon}
    poupl = {m: m2l[m] - m1l[m] for m in meses_mon}
    poupe = {m: (m2t[m] - m2l[m]) - m1e[m] for m in meses_mon}
    m2e = {m: m2t[m] - m2l[m] for m in meses_mon}
    g_bm = dict(
        id="argentina-base-monetaria", titulo="Base monetária na Argentina e seus componentes",
        subtitulo="Fim de mês; trilhões de pesos ou US$ bilhões pelo câmbio oficial de fim de mês",
        unidade="n2", fonte="BCRA, FMI (câmbio) e FtM",
        variantes=quatro(lambda moeda: [
            serie("Moeda em poder do público", conv(pub, moeda), 4, cor=VERDE, tipo="barra"),
            serie("Moeda nos bancos", conv(bancos, moeda), 4, cor=VERMELHO, tipo="barra"),
            serie("Reservas bancárias no BCRA", conv(resb, moeda), 4, cor=AZUL_CLARO, tipo="barra"),
            serie("Base monetária", conv(bm, moeda), 4, cor=BRANCO, largura=3, rotulo=True)]),
    )
    yoy = lambda s_: {m: (s_[m] / s_[mais(m, -12)] - 1) * 100 for m in s_ if m >= INICIO_YOY and mais(m, -12) in s_}
    g_bm_a = dict(
        id="argentina-base-monetaria-12m", titulo="Base monetária: variação em 12 meses, Argentina e Brasil",
        subtitulo="Variação % do saldo de fim de mês em moeda local sobre o mesmo mês do ano anterior",
        unidade="pct1", fonte="BCRA, BCB e FtM",
        variantes=recortes([serie("Argentina", yoy(bm), 2, cor=BRANCO, largura=3, rotulo=True),
                            serie("Brasil", br_base, 2, cor=VERDE, largura=2.5, rotulo=True)], True),
    )
    g_m2 = dict(
        id="argentina-m2-m1-poupanca", titulo="Agregado monetário M2 na Argentina: M1 e depósitos de poupança",
        subtitulo="M2 = M1 + depósitos de poupança (cajas de ahorro), em pesos e em moeda estrangeira; fim de mês; trilhões de pesos ou US$ bilhões",
        unidade="n2", fonte="BCRA, FMI (câmbio) e FtM",
        variantes=quatro(lambda moeda: [
            serie("M1", conv(m1t, moeda), 4, cor=VERMELHO, tipo="barra"),
            serie("Depósitos de poupança", conv(poup, moeda), 4, cor=VERDE, tipo="barra"),
            serie("M2", conv(m2t, moeda), 4, cor=BRANCO, largura=3, rotulo=True)]),
    )
    g_m2_moeda = dict(
        id="argentina-m2-por-moeda", titulo="Agregado monetário M2 na Argentina: moeda nacional e estrangeira",
        subtitulo="Depósitos em dólar convertidos pelo câmbio oficial; fim de mês; trilhões de pesos ou US$ bilhões",
        unidade="n2", fonte="BCRA, FMI (câmbio) e FtM",
        variantes=quatro(lambda moeda: [
            serie("M2 em moeda nacional", conv(m2l, moeda), 4, cor=AZUL, tipo="barra"),
            serie("M2 em moeda estrangeira", conv(m2e, moeda), 4, cor=VERDE, tipo="barra"),
            serie("M2 total", conv(m2t, moeda), 4, cor=BRANCO, largura=3, rotulo=True)]),
    )
    g_m2_4 = dict(
        id="argentina-m2-componentes", titulo="Agregado monetário M2 na Argentina: componentes por moeda",
        subtitulo="M1 e depósitos de poupança, em moeda nacional e estrangeira; fim de mês; trilhões de pesos ou US$ bilhões",
        unidade="n2", fonte="BCRA, FMI (câmbio) e FtM",
        variantes=quatro(lambda moeda: [
            serie("M1 em moeda nacional", conv(m1l, moeda), 4, cor=AZUL, tipo="barra"),
            serie("M1 em moeda estrangeira", conv(m1e, moeda), 4, cor=VERMELHO, tipo="barra"),
            serie("Poupança em moeda nacional", conv(poupl, moeda), 4, cor=AZUL_ESC, tipo="barra"),
            serie("Poupança em moeda estrangeira", conv(poupe, moeda), 4, cor=VERDE, tipo="barra"),
            serie("M2 total", conv(m2t, moeda), 4, cor=BRANCO, largura=3, rotulo=True)]),
    )
    g_m2_a = dict(
        id="argentina-m2-12m", titulo="Agregado monetário M2: variação em 12 meses, Argentina e Brasil",
        subtitulo="Variação % do saldo de fim de mês em moeda local sobre o mesmo mês do ano anterior",
        unidade="pct1", fonte="BCRA, BCB e FtM",
        variantes=recortes([serie("Argentina: M2 total", yoy(m2t), 2, cor=BRANCO, largura=3, rotulo=True),
                            serie("Argentina: M2 em moeda nacional", yoy(m2l), 2, cor=AZUL, largura=2.5, rotulo=True),
                            serie("Brasil: M2", br_m2, 2, cor=VERDE, largura=2.5, rotulo=True)], True),
    )
    g_m2_pct = dict(
        id="argentina-m2-pct-estrangeira", titulo="Parcela do M2 em moeda estrangeira na Argentina",
        subtitulo="% do M2 total; fim de mês", unidade="pct1", fonte="BCRA e FtM",
        variantes=recortes([serie("M2 em moeda estrangeira", {m: m2e[m] / m2t[m] * 100 for m in meses_mon}, 2,
                                  cor=AZUL, tipo="barra", rotulo=True)], True),
    )
    conv_bal = conv          # mesmo câmbio da base e do M2
    g_ativos = dict(
        id="argentina-ativos-bcra", titulo="Ativos do BCRA: fontes da base monetária",
        subtitulo="Fim de mês; trilhões de pesos ou US$ bilhões pelo câmbio oficial de fim de mês",
        unidade="n2", fonte="BCRA (balanço, Cuadro I-2), FMI (câmbio) e FtM",
        variantes=quatro(lambda moeda: [
            serie("Ativos externos líquidos", conv_bal(bal["externos"], moeda), 4, cor=AZUL, tipo="barra"),
            serie("Crédito ao setor oficial", conv_bal(bal["oficial"], moeda), 4, cor=VERMELHO, tipo="barra"),
            serie("Créditos a entidades financeiras em moeda nacional", conv_bal(bal["bancos"], moeda), 4,
                  cor=VERDE, tipo="barra"),
            serie("Ativos do BCRA", conv_bal(bal["total"], moeda), 4, cor=BRANCO, largura=3, rotulo=True)]),
    )
    g_ativos_a = dict(
        id="argentina-ativos-bcra-12m", titulo="Ativos do BCRA: variação em 12 meses",
        subtitulo="Variação % do total das fontes da base monetária em pesos sobre o mesmo mês do ano anterior",
        unidade="pct1", fonte="BCRA (balanço, Cuadro I-2) e FtM",
        variantes=recortes([serie("Ativos do BCRA", yoy(bal["total"]), 2, cor=VERDE, largura=3, rotulo=True)], True),
    )
    mb_ = meses_bal[-1]
    print("ativos do BCRA %s: %.2f tri de pesos (US$ %.1f bi), externos %.2f, oficial %.2f, bancos %.2f; 12m %.1f%%"
          % (mb_, bal["total"][mb_] / 1e9, bal["total"][mb_] / cambio[mb_] / 1e6, bal["externos"][mb_] / 1e9,
             bal["oficial"][mb_] / 1e9, bal["bancos"][mb_] / 1e9, yoy(bal["total"])[mb_]))

    m = meses_mon[-1]
    print("monetário %s: base %.2f tri, M2 %.2f tri (US$ %.1f bi), %% em moeda estrangeira %.1f%%, "
          "base 12m %.1f%%, M2 12m %.1f%%" % (m, bm[m] / 1e9, m2t[m] / 1e9, m2t[m] / cambio[m] / 1e6,
                                               m2e[m] / m2t[m] * 100, yoy(bm)[m], yoy(m2t)[m]))
    mb = max(br_base)
    print("Brasil %s: base 12m %.1f%%, M2 12m %.1f%%" % (mb, br_base[mb], br_m2[max(br_m2)]))

    ref = max(max(risco), dias[-1], max(bruta))
    doc = dict(assunto="Argentina", grupo="Análises Variadas", fonte="Ámbito, BCRA, BCB, FMI, INDEC e FtM",
               referencia=ref.strftime("%Y-%m"), atualizado=datetime.date.today().isoformat(), formato="artigo",
               secoes=[dict(titulo="Risco país", texto="", fontes=[], figuras=[], graficos=[g_risco]),
                       dict(titulo="Câmbio", texto="", fontes=[], figuras=[], graficos=[g_cambio, g_brecha]),
                       dict(titulo="Reservas internacionais", texto="", fontes=[], figuras=[],
                            graficos=[g_bruta, g_comp, g_liq]),
                       dict(titulo="Inflação", texto="", fontes=[], figuras=[], graficos=[g_ipc_m, g_ipc_a]),
                       dict(titulo="Ativos do BCRA", texto="", fontes=[], figuras=[], graficos=[g_ativos, g_ativos_a]),
                       dict(titulo="Base monetária", texto="", fontes=[], figuras=[], graficos=[g_bm, g_bm_a]),
                       dict(titulo="M2", texto="", fontes=[], figuras=[],
                            graficos=[g_m2, g_m2_moeda, g_m2_4, g_m2_a, g_m2_pct])])
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado", SAIDA)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Parte "China e desequilíbrios globais" da Missão Global Miami (chamada pelo
missao_miami.py). Só biblioteca padrão.

DE ONDE VEM CADA COISA

  - Balanço de pagamentos dos EUA: BEA (International Transactions, tabela
    1.2) pelo FRED, séries IEA*, trimestrais desde 1999, em US$ milhões. Antes
    de 1999 (só no gráfico em % do PIB) o FMI (Balance of Payments, BPM6) pelo
    DBnomics, desde 1973: é o mesmo dado do BEA na apresentação do FMI.
  - Sinais: como nos slides do BP, a conta financeira e as reservas entram com
    o sinal do financiamento (entrada de capital positiva; compra de reservas
    negativa), de modo que conta corrente + capital + financeira + reservas +
    erros e omissões = 0.
  - China: SAFE (State Administration of Foreign Exchange), série do BP em
    US$ (BPM6), trimestral desde 1998, em US$ 100 milhões; já vem com esse
    sinal. PIB em dólares: FMI (WEO). Reservas sem ouro: FMI (IFS) pelo FRED.
  - Comércio dos EUA por país: Census pelo FRED (EXP*/IMP*, mensal, US$
    milhões, sem ajuste); total com o mundo: EXP0004/IMP0004 (desde 1989).
  - DXY: calculado com as cotações do Fed (H.10, pelo FRED) e os pesos fixos
    do índice da ICE, desde 1999 (o euro).
  - Tarifa efetiva: impostos de importação (NIPA, B235RC1) sobre a importação
    de bens (A253RC1), trimestral, valores anualizados.
"""
import json
import re

import cenario_fomc as cf

AZUL, VERMELHO, VERDE = "#4F81BD", "#C0504D", "#9BBB59"
AZUL_ESCURO, AZUL_CLARO, VINHO, AMARELO = "#1F497D", "#8EB4E3", "#632523", "#FFFF00"
CINZA, CINZA_ESCURO = "#8a8a86", "#5c5c59"
BRANCO = cf.BRANCO
UA = {"User-Agent": "Mozilla/5.0 (ftm-analises)"}

FONTE_BEA = "BEA (International Transactions) via FRED e FtM"
SAFE_PAGINA = "https://www.safe.gov.cn/en/2019/0329/1496.html"
DBNOMICS = "https://api.db.nomics.world/v22/series/IMF/BOP/Q.US.%s?observations=1&format=json"


# ---------- utilidades ----------

def fim_tri(m):
    """"AAAA-MM" do primeiro mês do trimestre (FRED) -> último mês."""
    return "%s-%02d" % (m[:4], int(m[5:7]) + 2)


def bea(sid):
    """Série trimestral do FRED com a chave no último mês do trimestre."""
    return {fim_tri(k): v for k, v in cf.fred(sid).items()}


def soma4(d):
    ks = sorted(d)
    return {ks[i]: sum(d[k] for k in ks[i - 3:i + 1]) for i in range(3, len(ks))
            if cf_meses(ks[i - 3], ks[i]) == 9}


def cf_meses(a, b):
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def escala(d, f):
    return {k: v * f for k, v in d.items()}


def barras(nome, cor, dados, casas=1, **extra):
    return cf.serie(nome, cor, dados, casas, tipo="barra", **extra)


def linha(nome, cor, dados, casas=1, **extra):
    extra.setdefault("largura", 5)
    extra.setdefault("rotulo", True)
    return cf.serie(nome, cor, dados, casas, **extra)


def rot_tri(k):
    return "%dº tri/%s" % (int(k[5:7]) // 3, k[:4])


# ---------- fontes ----------

def imf_us(codigo):
    d = json.loads(cf.baixar(DBNOMICS % codigo))["series"]["docs"][0]
    out = {}
    for p, v in zip(d["period"], d["value"]):
        if v not in (None, "NA"):
            out["%s-%02d" % (p[:4], 3 * int(p[-1]))] = float(v)
    return out


def safe_bop():
    """{rótulo: {"AAAA-MM": US$ bi}} do BP trimestral da China (SAFE)."""
    from missao_miami import xlsx_celulas
    pagina = cf.baixar(SAFE_PAGINA, headers=UA).decode("utf-8", "replace")
    link = re.findall(r'href="(/en/file/[^"]+\.xlsx)"', pagina)
    if not link:
        raise RuntimeError("SAFE: link da planilha do BP não encontrado")
    cel = xlsx_celulas(cf.baixar("https://www.safe.gov.cn" + link[0], headers=UA), "quarterly(USD)")
    unidade = " ".join(str(v) for (r, k), v in cel.items() if r <= 4 and k == 1)
    if "100 million" not in unidade:
        raise RuntimeError("SAFE: unidade inesperada (%r)" % unidade)
    cab = {}
    for (r, k), v in cel.items():
        m = re.match(r"(\d{4})Q([1-4])$", str(v).strip())
        if m and k > 1:
            cab[k] = "%s-%02d" % (m.group(1), 3 * int(m.group(2)))
    linhas = {}
    for (r, k), v in cel.items():
        if k == 1 and v:
            linhas.setdefault(re.sub(r"\s+", " ", v).strip(), r)
    quero = {"cc": "1. Current account", "bens": "1.A.a Goods", "servicos": "1.A.b Services",
             "renda1": "1.B Primary income", "renda2": "1.C Secondary income", "capital": "2.1 Capital account",
             "financeira": "2.2.1 Financial account excluding reserve assets", "reservas": "2.2.2 Reserve assets",
             "erros": "3.Net errors and omissions"}
    out = {}
    for chave, rot in quero.items():
        if rot not in linhas:
            raise RuntimeError("SAFE: linha %r não encontrada" % rot)
        r = linhas[rot]
        out[chave] = {q: float(cel[(r, k)]) / 10 for k, q in cab.items() if cel.get((r, k)) not in (None, "")}
    # identidade: CC + capital + financeira + reservas + erros = 0
    pior = max(abs(sum(out[c][q] for c in ("cc", "capital", "financeira", "reservas", "erros")))
               for q in out["cc"])
    if pior > 0.5:
        raise RuntimeError("SAFE: o BP não fecha (sobra de US$ %.1f bi)" % pior)
    return out


# ---------- EUA: conta corrente e dólar ----------

def graficos_eua_externo(pib):
    cc = {k: 100 * v / pib[k] for k, v in bea("NETFI").items() if k in pib}
    u = max(cc)
    print("  CC/PIB dos EUA (NIPA) %s: %.1f%%" % (u, cc[u]))
    g_cc = dict(id="eua-cc-pib", titulo="Conta corrente dos EUA em % do PIB",
                subtitulo="Saldo em conta corrente das contas nacionais, em %% do PIB, trimestral, desde 1947; "
                          "%s: %s%%" % (rot_tri(u), cf.br(cc[u], 1)),
                unidade="%", buracoMax=3, fonte="BEA via FRED (NETFI e GDP) e FtM",
                series=[linha("Conta corrente / PIB", AZUL, cc, 2)])
    broad = cf.fred("TWEXBPA")
    eme = cf.fred("RTWEXEMEGS")
    g_dol = dict(id="eua-cc-dolar", titulo="Conta corrente dos EUA e dólar real",
                 subtitulo="Conta corrente em % do PIB (esq.); índices do dólar real do Fed (dir.): amplo, só "
                           "bens (mar/1973 = 100, encerrado em 2019), e contra emergentes (jan/2006 = 100)",
                 unidade="%", unidade2="ind", buracoMax=3, fonte="BEA e Federal Reserve via FRED e FtM",
                 series=[linha("Conta corrente / PIB", AZUL, cc, 2),
                         linha("Dólar real amplo, só bens (dir.)", VERDE, broad, 1, largura=3, dir=True,
                               unidade="ind", rotulo=False),         # acabou em 2019: sem número na ponta
                         linha("Dólar real contra emergentes (dir.)", VERMELHO, eme, 1, largura=3, dir=True,
                               unidade="ind")])
    man, tot = cf.fred("MANEMP"), cf.fred("PAYEMS")
    ind = {k: 100 * v / tot[k] for k, v in man.items() if k in tot}
    u = max(ind)
    g_ind = dict(id="eua-emprego-industria", titulo="Peso da indústria no emprego dos EUA",
                 subtitulo="Empregados na indústria de transformação, em %% do emprego formal não agrícola "
                           "(payroll), desde 1939; %s: %s%%" % (cf.rot_mes(u), cf.br(ind[u], 1)),
                 unidade="%", fonte="BLS via FRED (MANEMP e PAYEMS) e FtM",
                 series=[linha("Indústria / emprego total", AZUL, ind, 2)])
    return g_cc, g_dol, g_ind


# ---------- EUA: balanço de pagamentos ----------

def bp_eua():
    """Trimestral, US$ milhões, com o sinal dos slides; BEA desde 1999, FMI antes."""
    bea_ = dict(cc=bea("IEABC"), capital=bea("IEABCP"), nlf=bea("IEANLF"), reservas=bea("IEAAR"),
                erros=bea("IEASD"))
    out = dict(cc=bea_["cc"], capital=bea_["capital"],
               financeira={k: -(v - bea_["reservas"][k]) for k, v in bea_["nlf"].items()},
               reservas={k: -v for k, v in bea_["reservas"].items()}, erros=bea_["erros"])
    fmi = dict(cc=imf_us("BCA_BP6_USD"), capital=imf_us("BK_BP6_USD"), nlf=imf_us("BF_BP6_USD"),
               reservas=imf_us("BFRA_BP6_USD"), erros=imf_us("BOPFR_BP6_USD"))
    antes = dict(cc=fmi["cc"], capital=fmi["capital"],
                 financeira={k: -(v - fmi["reservas"][k]) for k, v in fmi["nlf"].items() if k in fmi["reservas"]},
                 reservas={k: -v for k, v in fmi["reservas"].items()}, erros=fmi["erros"])
    # o FMI repete o BEA: confere a sobreposição antes de emendar
    comum = [k for k in antes["cc"] if k in out["cc"]]
    dif = max(abs(antes["cc"][k] - out["cc"][k]) for k in comum)
    print("  BP dos EUA: FMI x BEA na conta corrente, maior diferença %.0f mi em %d trimestres" % (dif, len(comum)))
    for c in out:
        for k, v in antes[c].items():
            if k < "1999-01":
                out[c][k] = v
    return out


def graficos_bp_eua(pib):
    bp = bp_eua()
    q = {c: soma4(d) for c, d in bp.items()}
    pib4 = {k: v for k, v in soma4(pib).items()}          # soma de 4 trimestres de taxa anualizada = 4 x o ano
    pct = {c: {k: 100 * v / (pib4[k] * 1000 / 4) for k, v in d.items() if k in pib4} for c, d in q.items()}
    u = max(pct["cc"])
    print("  BP dos EUA em 4 tri %s: CC %.1f%%, financeira %.1f%%, erros %.1f%% do PIB"
          % (u, pct["cc"][u], pct["financeira"][u], pct["erros"][u]))
    nomes = [("cc", "Conta corrente", AZUL), ("capital", "Conta capital", AMARELO),
             ("financeira", "Conta financeira", VERDE), ("reservas", "Reservas internacionais", CINZA),
             ("erros", "Erros e omissões", VERMELHO)]
    g_pct = dict(id="eua-bp-pib", titulo="Balanço de pagamentos dos EUA em % do PIB",
                 subtitulo="Acumulado em 4 trimestres, em %% do PIB, desde 1973; conta financeira sem as "
                           "reservas, positiva quando entra capital; %s: conta corrente %s%%, financeira %s%%"
                           % (rot_tri(u), cf.br(pct["cc"][u], 1), cf.br(pct["financeira"][u], 1)),
                 unidade="%", barra=3, buracoMax=3,
                 fonte="BEA (desde 1999) e FMI (Balance of Payments, antes) via FRED e DBnomics; FtM",
                 series=[barras(n, c, pct[k], 2, rotulo=k in ("cc", "financeira", "erros")) for k, n, c in nomes])
    bi = {c: {k: v / 1000 for k, v in d.items() if k >= "1999-12"} for c, d in q.items()}
    g_bi = dict(id="eua-bp", titulo="Balanço de pagamentos dos EUA",
                subtitulo="US$ bilhões, acumulado em 4 trimestres, desde 1999; %s: conta corrente US$ %s bi, "
                          "financeira US$ %s bi" % (rot_tri(u), cf.br(bi["cc"][u], 0), cf.br(bi["financeira"][u], 0)),
                unidade="usd-bi", barra=3, buracoMax=3, fonte=FONTE_BEA,
                series=[barras(n, c, bi[k], 1, rotulo=k in ("cc", "financeira", "erros")) for k, n, c in nomes])
    # conta corrente por componente
    comp = [("Balança comercial (bens)", AZUL, "IEABCG"), ("Serviços", VERMELHO, "IEABCS"),
            ("Renda primária", VERDE, "IEABCPI"), ("Renda secundária", AZUL_ESCURO, "IEABCSI")]
    cc4 = {n: {k: v / 1000 for k, v in soma4(bea(s)).items()} for n, _, s in comp}
    tot = {k: v / 1000 for k, v in soma4(bea("IEABC")).items()}
    u = max(tot)
    g_cc = dict(id="eua-cc-componentes", titulo="Conta corrente dos EUA por componente",
                subtitulo="US$ bilhões, acumulado em 4 trimestres, desde 1999; %s: saldo de US$ %s bi"
                          % (rot_tri(u), cf.br(tot[u], 0)),
                unidade="usd-bi", barra=3, buracoMax=3, fonte=FONTE_BEA,
                series=[barras(n, c, cc4[n], 1) for n, c, _ in comp]
                + [linha("Saldo em conta corrente", BRANCO, tot, 1)])
    # conta financeira por componente (sem reservas), sinal de entrada de capital
    a = {s: bea(s) for s in ("IEAADI", "IEAIDI", "IEAAPI", "IEAIPI", "IEAAOI", "IEAIOI", "IEAFD", "IEANLF", "IEAAR")}
    outros = {k: a["IEAIOI"][k] - a["IEAAOI"][k] - a["IEAFD"].get(k, 0) for k in a["IEAIOI"]}
    fa = [("IED no exterior", AZUL, {k: -v for k, v in a["IEAADI"].items()}),
          ("IED no país", VERMELHO, a["IEAIDI"]),
          ("Carteira no exterior", VERDE, {k: -v for k, v in a["IEAAPI"].items()}),
          ("Carteira no país", AZUL_ESCURO, a["IEAIPI"]),
          ("Outros investimentos e derivativos", AZUL_CLARO, outros)]
    saldo = {k: -(v - a["IEAAR"][k]) for k, v in a["IEANLF"].items()}
    soma = {k: sum(d[k] for _, _, d in fa) for k in saldo if all(k in d for _, _, d in fa)}
    pior = max(abs(soma[k] - saldo[k]) for k in soma)
    if pior > 5:          # arredondamento do BEA (US$ milhões)
        raise RuntimeError("conta financeira dos EUA: componentes não fecham o saldo (%.0f mi)" % pior)
    fa4 = [(n, c, {k: v / 1000 for k, v in soma4(d).items()}) for n, c, d in fa]
    s4 = {k: v / 1000 for k, v in soma4(saldo).items()}
    u = max(s4)
    print("  conta financeira dos EUA em 4 tri %s: US$ %.0f bi" % (u, s4[u]))
    g_fa = dict(id="eua-conta-financeira", titulo="Conta financeira dos EUA por componente",
                subtitulo="US$ bilhões, acumulado em 4 trimestres, desde 1999, sem as reservas; positivo = entrada "
                          "de capital (estrangeiro comprando ativo nos EUA), negativo = saída; %s: saldo de US$ %s bi"
                          % (rot_tri(u), cf.br(s4[u], 0)),
                unidade="usd-bi", barra=3, buracoMax=3, fonte=FONTE_BEA,
                series=[barras(n, c, d, 1) for n, c, d in fa4] + [linha("Saldo da conta financeira", BRANCO, s4, 1)])
    return g_pct, g_cc, g_bi, g_fa


PAISES = [("Brasil", "3510", AMARELO), ("Canadá", "CA", AZUL_ESCURO), ("China", "CH", VERMELHO),
          ("França", "FR", CINZA), ("Alemanha", "GE", VERDE), ("Itália", "4759", AZUL_CLARO),
          ("Japão", "JP", BRANCO), ("México", "MX", AZUL), ("Suíça", "4419", VINHO),
          ("Reino Unido", "UK", CINZA_ESCURO)]


def grafico_comercio_paises():
    def saldo(cod):
        x, m = cf.fred("EXP" + cod), cf.fred("IMP" + cod)
        return {k: x[k] - v for k, v in m.items() if k in x}
    total = saldo("0004")
    ult = max(total)
    anos = sorted({k[:4] for k in total if k >= "1989-01"})
    meses_ult = sum(1 for k in total if k[:4] == ult[:4])

    def anual(d):
        return {a: sum(v for k, v in d.items() if k[:4] == a) for a in anos}
    tot = anual(total)
    parcial = meses_ult < 12
    # o eixo leva só o ano (rótulo longo encolhe a fonte de todos); a caixa do mouse diz até que mês
    longas = [a if a != ult[:4] or not parcial else "%s (jan a %s)" % (a, cf.MESES[int(ult[5:7]) - 1].lower())
              for a in anos]
    series = []
    for nome, cod, cor in PAISES:
        sh = anual(saldo(cod))
        series.append(dict(nome=nome, cor=cor, tipo="barra",
                           dados=[[str(i), round(100 * sh[a] / tot[a], 1)] for i, a in enumerate(anos)]))
    ch = series[2]["dados"][-1][1]
    print("  comércio dos EUA %s: China %.1f%% do déficit; México %.1f%%" % (longas[-1], ch, series[7]["dados"][-1][1]))
    return dict(id="eua-comercio-paises", titulo="Déficit comercial dos EUA por país",
                subtitulo="Saldo da balança de bens com cada país, em % do saldo total do ano (déficit com o país "
                          "sobre o déficit total; negativo = superávit dos EUA com o país), desde 1989"
                          + ("; %s" % longas[-1] if parcial else ""),
                unidade="%", categorias=anos, categoriasLongas=longas, barra=1, fonte="Census via FRED e FtM", series=series)


# ---------- China ----------

def graficos_china():
    bp = safe_bop()
    q = {c: soma4(d) for c, d in bp.items()}
    u = max(q["cc"])
    cny = cf.fred("DEXCHUS")
    print("  BP da China em 4 tri %s: CC US$ %.0f bi, financeira US$ %.0f bi, reservas US$ %.0f bi"
          % (u, q["cc"][u], q["financeira"][u], q["reservas"][u]))
    nomes = [("cc", "Conta corrente", AZUL), ("capital", "Conta capital", AMARELO),
             ("financeira", "Conta financeira", VERDE), ("reservas", "Reservas internacionais", CINZA),
             ("erros", "Erros e omissões", VERMELHO)]
    g_bp = dict(id="china-bp", titulo="Balanço de pagamentos da China",
                subtitulo="US$ bilhões, acumulado em 4 trimestres (esq.), desde 1998; conta financeira sem as "
                          "reservas, negativa quando sai capital; reservas negativas = compra pelo banco central; "
                          "yuans por dólar (dir.); %s: conta corrente US$ %s bi" % (rot_tri(u), cf.br(q["cc"][u], 0)),
                unidade="usd-bi", unidade2="cny", barra=3, buracoMax=3,
                fonte="SAFE (China), Federal Reserve via FRED (DEXCHUS) e FtM",
                series=[barras(n, c, q[k], 1, rotulo=k in ("cc", "financeira", "reservas"))
                        for k, n, c in nomes]
                + [linha("Yuans por dólar (dir.)", BRANCO, {k: v for k, v in cny.items() if k >= "1998-12"}, 2,
                         dir=True, unidade="cny")])
    # saldo anual do BP (= variação das reservas com o sinal trocado) e em % do PIB
    anos = sorted({k[:4] for k in bp["reservas"] if sum(1 for j in bp["reservas"] if j[:4] == k[:4]) == 4})
    saldo = {a: -sum(v for k, v in bp["reservas"].items() if k[:4] == a) for a in anos}
    pib = json.loads(cf.baixar("https://www.imf.org/external/datamapper/api/v1/NGDPD/CHN"))["values"]["NGDPD"]["CHN"]
    pct = {a: 100 * v / pib[a] for a, v in saldo.items() if pib.get(a)}
    ua = anos[-1]
    print("  saldo do BP da China em %s: US$ %.0f bi (%.1f%% do PIB)" % (ua, saldo[ua], pct.get(ua, float("nan"))))
    idx = {a: str(i) for i, a in enumerate(anos)}
    lim_bi = 300 * -(-max(abs(v) for v in saldo.values()) // 300)       # passo de 100 ou mais, 6 intervalos
    lim_pct = 3 * -(-max(abs(v) for v in pct.values()) // 3)
    g_saldo = dict(id="china-bp-saldo", titulo="Saldo do balanço de pagamentos da China",
                   subtitulo="US$ bilhões por ano (esq.) e em %% do PIB (dir.); saldo = conta corrente + capital + "
                             "financeira + erros, que é o que o banco central compra (ou vende) de reservas; %s: "
                             "US$ %s bi, %s%% do PIB" % (ua, cf.br(saldo[ua], 0), cf.br(pct[ua], 1)),
                   unidade="usd-bi", unidade2="%", categorias=anos, barra=0.7,
                   # zero na mesma linha dos dois eixos: limites simétricos, 6 intervalos
                   eixo=dict(min=-lim_bi, max=lim_bi), eixo2=dict(min=-lim_pct, max=lim_pct),
                   fonte="SAFE (China), FMI (World Economic Outlook, PIB em dólares) e FtM",
                   series=[dict(nome="Superávit", cor=AZUL, tipo="barra",
                                dados=[[idx[a], round(v, 1)] for a, v in saldo.items() if v >= 0]),
                           dict(nome="Déficit", cor=VERMELHO, tipo="barra",
                                dados=[[idx[a], round(v, 1)] for a, v in saldo.items() if v < 0]),
                           dict(nome="Saldo / PIB (dir.)", cor=BRANCO, largura=5, rotulo=True, dir=True,
                                unidade="%", dados=[[idx[a], round(v, 1)] for a, v in sorted(pct.items())])])
    comp = [("bens", "Balança comercial (bens)", AZUL), ("servicos", "Serviços", VERMELHO),
            ("renda1", "Renda primária", VERDE), ("renda2", "Renda secundária", AZUL_ESCURO)]
    g_cc = dict(id="china-cc", titulo="Conta corrente da China por componente",
                subtitulo="US$ bilhões, acumulado em 4 trimestres, desde 1998; %s: saldo de US$ %s bi, bens US$ %s bi"
                          % (rot_tri(u), cf.br(q["cc"][u], 0), cf.br(q["bens"][u], 0)),
                unidade="usd-bi", barra=3, buracoMax=3, fonte="SAFE (China) e FtM",
                series=[barras(n, c, q[k], 1) for k, n, c in comp]
                + [linha("Saldo em conta corrente", BRANCO, q["cc"], 1)])
    res = {k: v / 1000 for k, v in cf.fred("TRESEGCNM052N").items()}
    ur = max(res)
    g_res = dict(id="china-reservas", titulo="Reservas internacionais da China",
                 subtitulo="Sem o ouro, em US$ bilhões, fim de mês, desde 1977; pico de US$ %s bi em %s; %s: US$ %s bi"
                           % (cf.br(max(res.values()), 0), cf.rot_mes(max(res, key=res.get)), cf.rot_mes(ur), cf.br(res[ur], 0)),
                 unidade="usd-bi", fonte="FMI (International Financial Statistics) via FRED (TRESEGCNM052N)",
                 series=[linha("Reservas sem ouro", AZUL, res, 0)])
    return g_res, g_bp, g_saldo, g_cc


# ---------- dólar e tarifas ----------

DXY_PESOS = [("DEXUSEU", -0.576), ("DEXJPUS", 0.136), ("DEXUSUK", -0.119), ("DEXCAUS", 0.091),
             ("DEXSDUS", 0.042), ("DEXSZUS", 0.036)]


def grafico_dxy():
    s = {sid: cf.fred(sid, mensal=False) for sid, _ in DXY_PESOS}
    dias = sorted(set.intersection(*[set(d) for d in s.values()]))
    dxy = {}
    for d in dias:
        v = 50.14348112
        for sid, p in DXY_PESOS:
            v *= s[sid][d] ** p
        dxy[d] = v
    u = max(dxy)
    print("  DXY %s: %.1f" % (u, dxy[u]))
    return dict(id="dxy", titulo="Índice do dólar (DXY)",
                subtitulo="Dólar contra euro, iene, libra, dólar canadense, coroa sueca e franco suíço, com os pesos "
                          "do índice da ICE, desde 1999; %s: %s" % (cf.rotulo_dia(u), cf.br(dxy[u], 1)),
                unidade="ind", diario=True, buracoMax=6, eixo=dict(zero=False),
                fonte="Federal Reserve (H.10) via FRED; cálculo FtM com os pesos da ICE",
                series=[linha("DXY", AZUL, dxy, 2, largura=3)])


def grafico_tarifa():
    imp, bens = bea("B235RC1Q027SBEA"), bea("A253RC1Q027SBEA")
    t = {k: 100 * v / bens[k] for k, v in imp.items() if k in bens}
    u = max(t)
    print("  tarifa efetiva dos EUA %s: %.1f%%" % (u, t[u]))
    return dict(id="eua-tarifa-efetiva", titulo="Tarifa efetiva dos EUA",
                subtitulo="Impostos de importação arrecadados, em %% da importação de bens, trimestral, desde 1947; "
                          "%s: %s%%" % (rot_tri(u), cf.br(t[u], 1)),
                unidade="%", buracoMax=3, fonte="BEA (contas nacionais) via FRED e FtM",
                series=[linha("Tarifa efetiva", AZUL, t, 2)])


CHINA = [("Déficit externo dos EUA", "eua-cc-pib"), ("", "eua-bp-pib"), ("", "eua-cc-dolar"),
         ("", "eua-emprego-industria"),
         ("China: reservas e balanço de pagamentos", "china-reservas"), ("", "china-bp"), ("", "china-bp-saldo"),
         ("", "china-cc"),
         ("Balanço de pagamentos dos EUA", "eua-cc-componentes"), ("", "eua-bp"), ("", "eua-conta-financeira"),
         ("", "eua-comercio-paises"),
         ("Dólar e tarifas", "dxy"), ("", "eua-tarifa-efetiva"),
         ("Ouro nas reservas", "reservas-ouro-tesouros")]      # copiado do ftm-dados (reservas.json)
PARTE_CHINA = "China e desequilíbrios globais"


def graficos():
    pib = bea("GDP")
    out = list(graficos_eua_externo(pib)) + list(graficos_bp_eua(pib)) + list(graficos_china())
    out += [grafico_comercio_paises(), grafico_dxy(), grafico_tarifa()]
    return out

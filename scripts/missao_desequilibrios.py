#!/usr/bin/env python3
"""
Gráficos novos da parte "China e desequilíbrios globais" da Missão Global
Miami (pedido dele em 16/11/2026), chamados pelo missao_china.py. Só
biblioteca padrão.

DE ONDE VEM CADA COISA

  - PIB dos EUA no PIB mundial: em dólares correntes, Banco Mundial
    (NY.GDP.MKTP.CD, desde 1960); pela paridade do poder de compra, FMI (PPPSH).
  - Emprego na indústria por segmento: BLS (CES, com ajuste sazonal) via FRED.
  - Indústria em % do PIB: BEA (GDP by industry, tabela TVA110, anual desde
    1997; o arquivo histórico de 1947 a 1997 saiu do ar).
  - Desequilíbrios globais: saldo em conta corrente de cada país (BCA, US$ bi)
    sobre o PIB mundial (NGDPD), do WEO, com as projeções do FMI. Zona do euro
    = agregado EURO do FMI. "Outros" = soma dos demais países, então o total
    das barras é a discrepância estatística. A linha é a soma dos saldos em
    valor absoluto, a medida de desequilíbrio global do FMI.
  - Reservas da China em % do PIB: reservas sem ouro no fim do ano (FMI, IFS,
    pelo FRED) sobre o PIB em dólares (WEO).
  - Câmbio de equilíbrio do yuan: yuans por dólar do Fed (H.10, EXCHUS)
    corrigido pela inflação relativa, China (FMI, CPI) contra EUA (CPI-U sem
    ajuste, com out/25 pela média geométrica de set e nov/25), a partir de
    uma data-base em que se supõe o câmbio em equilíbrio.
  - VIX (Cboe) e incerteza de política econômica (Baker, Bloom e Davis), via
    FRED, médias mensais.
  - Tarifas: Monthly Treasury Statement, tabela 4 (Fiscal Data), linha
    Customs Duties: arrecadação bruta, devoluções e líquida, mensal, desde
    mar/2015.
"""
import datetime
import json

import cenario_fomc as cf

AZUL, VERMELHO, VERDE = "#4F81BD", "#C0504D", "#9BBB59"
AZUL_ESCURO, AZUL_CLARO, VINHO, AMARELO = "#1F497D", "#8EB4E3", "#632523", "#FFFF00"
CINZA = "#8a8a86"
BRANCO = cf.BRANCO
JSON_H = {"User-Agent": "ftm-analises", "Accept": "application/json"}
WEO = "https://www.imf.org/external/datamapper/api/v1/"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def linha(nome, cor, dados, casas=1, **extra):
    extra.setdefault("largura", 5)
    extra.setdefault("rotulo", True)
    return cf.serie(nome, cor, dados, casas, **extra)


def barras(nome, cor, dados, casas=1, **extra):
    return cf.serie(nome, cor, dados, casas, tipo="barra", **extra)


_WEO = {}


def weo(ind):
    """{código: {"AAAA": valor}} do datamapper do FMI (países e agregados)."""
    if ind not in _WEO:
        _WEO[ind] = json.loads(cf.baixar(WEO + ind))["values"][ind]
    return _WEO[ind]


def anual(d):
    return {"%s-12" % a: v for a, v in d.items() if v is not None}


def ano_weo():
    """Ano corrente: no WEO é estimativa; dali em diante, projeção."""
    return str(datetime.date.today().year)


# ---------- EUA no mundo e indústria ----------

BM_PIB = ("https://api.worldbank.org/v2/country/WLD;USA/indicator/NY.GDP.MKTP.CD"
          "?format=json&per_page=500&date=1960:2100")


def grafico_pib_eua_mundo():
    """Em dólares: Banco Mundial desde 1960 (o mesmo do gráfico do FRED que ele
    mandou); pela PPC: FMI desde 1980."""
    r = json.loads(cf.baixar(BM_PIB, headers={"User-Agent": "ftm-analises"}))
    bm = {}
    for x in r[1]:
        if x["value"] is not None:
            bm.setdefault(x["countryiso3code"], {})[x["date"]] = x["value"]
    nominal = {a: 100 * v / bm["WLD"][a] for a, v in bm["USA"].items() if a in bm["WLD"]}
    ate = ano_weo()
    ppc = {a: v for a, v in weo("PPPSH")["USA"].items() if a <= ate}
    un = max(nominal)
    print("  PIB dos EUA / mundo: %s %.1f%% em dólares (1960 %.1f%%); %s %.1f%% em PPC"
          % (un, nominal[un], nominal["1960"], ate, ppc[ate]))
    return dict(id="pib-eua-mundo", titulo="PIB dos EUA em % do PIB mundial", unidade="%", buracoMax=13,
                subtitulo="Anual", variantes=[
                    dict(rot="Em dólares correntes, desde 1960", fonte="Banco Mundial e FtM",
                         series=[linha("EUA / mundo", AZUL, anual(nominal), 1)]),
                    dict(rot="Pela paridade do poder de compra, desde 1980",
                         fonte="FMI (World Economic Outlook; %s = estimativa) e FtM" % ate,
                         series=[linha("EUA / mundo", AZUL, anual(ppc), 1)])])


EMPREGO = [("eua-emprego-metal-primario", "CES3133100001", "metais primários",
            "siderurgia, alumínio e outros metais básicos"),
           ("eua-emprego-metal-fabricado", "CES3133200001", "produtos de metal",
            "estruturas, ferramentas, peças e embalagens de metal"),
           ("eua-emprego-eletronicos", "CES3133400001", "computadores e eletrônicos",
            "computadores, semicondutores, equipamentos de comunicação e instrumentos")]


def graficos_emprego_industria():
    out = []
    for gid, sid, nome, detalhe in EMPREGO:
        d = cf.fred(sid)
        u = max(d)
        pico = max(d, key=d.get)
        out.append(dict(id=gid, titulo="Emprego na indústria dos EUA: %s" % nome,
                        subtitulo="Empregados em milhares, com ajuste sazonal, desde 1990; %s: %s mil"
                                  % (cf.rot_mes(u), cf.br(d[u], 0)),
                        unidade="mil", fonte="BLS (CES) via FRED (%s)" % sid,
                        # eixo sem o zero: a queda aparece melhor (pedido dele em 16/11/2026)
                        **({"eixo": dict(zero=False)} if gid != "eua-emprego-metal-fabricado" else {}),
                        series=[linha("Empregados", AZUL, d, 1)]))
        print("  emprego em %s: %s %.0f mil (pico %s, %.0f mil)" % (nome, u, d[u], pico, d[pico]))
    return out


BEA_VA = "https://apps.bea.gov/industry/Release/XLS/GDPxInd/ValueAdded.xlsx"


def grafico_va_industria():
    from missao_miami import xlsx_celulas
    cel = xlsx_celulas(cf.baixar(BEA_VA, headers={"User-Agent": "Mozilla/5.0 (ftm-analises)"}), "TVA110-A")
    cab = next(r for (r, k), v in cel.items() if str(v).strip() == "Line")
    anos = {k: str(v).strip() for (r, k), v in cel.items() if r == cab and str(v).strip().isdigit()}
    linha_m = [r for (r, k), v in cel.items() if k == 2 and str(v).strip() == "Manufacturing"]
    if len(linha_m) != 1 or not anos:
        raise RuntimeError("BEA TVA110: linha da indústria de transformação não encontrada")
    r = linha_m[0]
    va = {anos[k]: float(cel[(r, k)]) for k in anos if cel.get((r, k)) not in (None, "")}
    u, a0 = max(va), min(va)
    print("  indústria / PIB dos EUA: %s %.1f%%, %s %.1f%%" % (a0, va[a0], u, va[u]))
    return dict(id="eua-va-industria", titulo="Indústria de transformação em % do PIB dos EUA",
                subtitulo="Valor adicionado da indústria de transformação, anual, de %s a %s; %s: %s%%"
                          % (a0, u, u, cf.br(va[u], 1)),
                unidade="%", buracoMax=13, eixo=dict(zero=False), fonte="BEA (GDP by Industry, tabela TVA110)",
                series=[linha("Indústria / PIB", AZUL, anual(va), 1)])


# ---------- desequilíbrios globais (FMI) ----------

PETROLEO = ["SAU", "ARE", "KWT", "QAT", "OMN", "BHR", "IRQ", "IRN", "NOR", "RUS", "KAZ", "AZE", "NGA", "AGO",
            "DZA", "LBY", "VEN", "BRN", "TTO"]
EURO = ["AUT", "BEL", "HRV", "CYP", "EST", "FIN", "FRA", "DEU", "GRC", "IRL", "ITA", "LVA", "LTU", "LUX", "MLT",
        "NLD", "PRT", "SVK", "SVN", "ESP", "BGR"]
GRUPOS = [("EUA", ["USA"], AZUL), ("China", ["CHN"], VERMELHO), ("Zona do euro", None, AMARELO),
          ("Japão", ["JPN"], AZUL_CLARO), ("Exportadores de petróleo", PETROLEO, VERDE), ("Outros", "resto", CINZA)]


def grafico_fmi_desequilibrios():
    bca, mundo = weo("BCA"), weo("NGDPD")["WEOWORLD"]
    paises = set(json.loads(cf.baixar(WEO + "countries"))["countries"])
    paises &= set(bca)
    ate = ano_weo()
    anos = [str(a) for a in range(1990, 2032) if str(a) in mundo]

    def soma(cods, a):
        return sum(bca[c].get(a) or 0 for c in cods if c in bca)
    usados = {"USA", "CHN", "JPN"} | set(PETROLEO) | set(EURO)
    resto = sorted(paises - usados)
    series, por = [], {}
    for nome, cods, cor in GRUPOS:
        if cods is None:
            v = {a: bca["EURO"].get(a) for a in anos}
        elif cods == "resto":
            v = {a: soma(resto, a) for a in anos}
        else:
            v = {a: soma(cods, a) for a in anos}
        pct = {a: 100 * x / mundo[a] for a, x in v.items() if x is not None}
        por[nome] = pct
        series.append(barras(nome, cor, anual({a: x for a, x in pct.items() if a <= ate}), 2))
        series.append(barras(nome + " (projeção)", cor, anual({a: x for a, x in pct.items() if a > ate}), 2,
                             legenda=False, opacidade=0.45))
    total = {a: 100 * sum(abs(bca[c].get(a) or 0) for c in paises) / mundo[a] for a in anos}
    series.append(linha("Soma dos saldos em valor absoluto", BRANCO, anual(total), 2, largura=4))
    pico = max((a for a in anos if a <= ate), key=total.get)
    print("  desequilíbrio global: %s %.1f%% do PIB mundial (pico %s %.1f%%); 2031 %.1f%%"
          % (ate, total[ate], pico, total[pico], total.get(anos[-1], float("nan"))))
    return dict(id="fmi-desequilibrios", titulo="Desequilíbrios globais: saldo em conta corrente por região",
                subtitulo="Em %% do PIB mundial, anual, de 1990 a %s; tom mais claro = projeção do FMI a partir de %d"
                          % (anos[-1], int(ate) + 1),
                unidade="%", barra=10, buracoMax=13, fonte="FMI (World Economic Outlook) e FtM", series=series)


# o gráfico do próprio FMI, no lugar do refeito acima (pedido dele em 16/11/2026);
# grafico_fmi_desequilibrios() fica para quando ele quiser a versão com dado
FIGURA_FMI = dict(id="fmi-desequilibrios", tipo="figura", imagem="assets/missao/fmi-desequilibrios.jpg",
                  titulo="Desequilíbrios globais voltam a crescer depois de anos de queda",
                  subtitulo="Saldo em conta corrente por país e região, em % do PIB mundial; a linha é a soma dos "
                            "saldos em valor absoluto",
                  fonte="FMI (IMF Blog, 6/4/2026)",
                  link="https://www.imf.org/en/blogs/articles/2026/04/06/global-imbalances-old-questions-new-answers",
                  rotuloLink="Ver o post")


# ---------- China ----------

def grafico_china_reservas_pib():
    res = cf.fred("TRESEGCNM052N")
    pib = weo("NGDPD")["CHN"]
    # fim de cada ano e, no ano corrente, o último mês, sobre o PIB estimado do ano
    u = max(res)
    meses = [m for m in res if m[5:] == "12"] + ([u] if u[5:] != "12" else [])
    dados = {m: 100 * res[m] / 1000 / pib[m[:4]] for m in meses if pib.get(m[:4])}
    pct = {m[:4]: v for m, v in dados.items()}
    pico = max(pct, key=pct.get)
    print("  reservas da China / PIB: pico %s %.1f%%; %s %.1f%%" % (pico, pct[pico], u, pct[u[:4]]))
    return dict(id="china-reservas-pib", titulo="Reservas internacionais da China em % do PIB",
                subtitulo="Reservas sem o ouro no fim do ano sobre o PIB em dólares do ano; pico de %s%% em %s; "
                          "%s: %s%%" % (cf.br(pct[pico], 1), pico, cf.rot_mes(u), cf.br(pct[u[:4]], 1)),
                unidade="%", buracoMax=13, fonte="FMI (International Financial Statistics, via FRED, e World Economic Outlook) e FtM",
                series=[linha("Reservas / PIB", AZUL, dados, 1)])


IMF_CPI_CHN = "https://api.imf.org/external/sdmx/2.1/data/IMF.STA,CPI/CHN.CPI._T.IX.M?startPeriod=1990-01"


def cpi_china():
    r = json.loads(cf.baixar(IMF_CPI_CHN, headers=JSON_H))
    tempo = [v["id"].replace("-M", "-") for v in r["structure"]["dimensions"]["observation"][0]["values"]]
    obs = list(r["dataSets"][0]["series"].values())[0]["observations"]
    return {tempo[int(k)]: float(v[0]) for k, v in obs.items() if v[0] not in (None, "")}


def graficos_yuan_equilibrio():
    cny, cn = cf.fred("EXCHUS"), cpi_china()
    us = dict(cf.fred("CPIAUCNS"))
    if us.get("2025-10") is None:
        us["2025-10"] = (us["2025-09"] * us["2025-11"]) ** 0.5
    out = []
    for base in ("2014-12", "2019-12", "2020-12"):
        meses = [m for m in sorted(cny) if m >= base and m in cn and m in us]
        eq = {m: cny[base] * (cn[m] / cn[base]) / (us[m] / us[base]) for m in meses}
        mk = {m: cny[m] for m in meses}
        u = meses[-1]
        print("  yuan de equilíbrio desde %s: %s mercado %.2f, PPC %.2f" % (base, u, mk[u], eq[u]))
        out.append(dict(id="china-yuan-ppc-%s" % base[:4],
                        titulo="A taxa de câmbio de equilíbrio do yuan: a partir de dez/%s" % base[:4],
                        subtitulo="Yuans por dólar, de mercado e pela paridade do poder de compra; "
                                  "%s: ¥ %s de mercado e ¥ %s pela PPC"
                                  % (cf.rot_mes(u), cf.br(mk[u], 2), cf.br(eq[u], 2)),
                        unidade="cny", eixo=dict(zero=False),
                        fonte="Federal Reserve (H.10) via FRED, FMI (CPI da China) e BLS (CPI-U) via FRED",
                        series=[linha("Câmbio de mercado", VERDE, mk, 4),
                                linha("Câmbio pela PPC", AZUL, eq, 4, largura=6)]))
    return out


# ---------- incerteza e tarifas ----------

def grafico_vix_incerteza():
    vix = {}
    for d, v in cf.fred("VIXCLS", mensal=False).items():
        vix.setdefault(d[:7], []).append(v)
    vix = {m: sum(x) / len(x) for m, x in vix.items()}
    epu = cf.fred("USEPUINDXM")
    u = min(max(vix), max(epu))

    def var(ini):
        return [linha("VIX (esq.)", VERMELHO, cf.desde(vix, ini), 1, largura=4),
                linha("Incerteza de política econômica (dir.)", AZUL, cf.desde(epu, ini), 0, largura=4, dir=True,
                      unidade="pts")]
    print("  VIX %s: %.1f; incerteza: %.0f" % (u, vix[u], epu[u]))
    return dict(id="vix-incerteza", titulo="Volatilidade implícita (VIX) e incerteza de política econômica nos EUA",
                subtitulo="Médias mensais; VIX em pontos (esq.); índice de incerteza de Baker, Bloom e Davis "
                          "(dir., média de 1985 a 2009 = 100)",
                unidade="pts", unidade2="pts",
                eventos=[dict(em="2025-04", rot="Liberation Day"), dict(em="2026-03", rot="Início da guerra")],
                fonte="Cboe e Baker, Bloom e Davis (policyuncertainty.com), via FRED",
                variantes=[dict(rot="Desde 1990", series=var("1990-01")),
                           dict(rot="Desde 2024", series=var("2024-01"))])


MTS4 = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_4"
        "?filter=classification_desc:eq:Customs%20Duties&sort=record_date&page[size]=1000"
        "&fields=record_date,current_month_gross_rcpt_amt,current_month_refund_amt,current_month_net_rcpt_amt")


def tarifas_mts():
    dados = json.loads(cf.baixar(MTS4, headers=JSON_H))["data"]
    out = {"bruta": {}, "devolucao": {}, "liquida": {}}
    for r in dados:
        m = r["record_date"][:7]
        out["bruta"][m] = float(r["current_month_gross_rcpt_amt"]) / 1e9
        out["devolucao"][m] = float(r["current_month_refund_amt"]) / 1e9
        out["liquida"][m] = float(r["current_month_net_rcpt_amt"]) / 1e9
    return out


def graficos_tarifas():
    t = tarifas_mts()
    bruta, dev = t["bruta"], t["devolucao"]
    u = max(bruta)
    b12 = cf.soma12(bruta)
    g_rec = dict(id="tarifas-receita", titulo="Receitas tarifárias dos EUA",
                 subtitulo="Impostos de importação arrecadados (bruto, antes das devoluções), US$ bilhões; "
                           "%s: US$ %s bi no mês e US$ %s bi em 12 meses"
                           % (cf.rot_mes(u), cf.br(bruta[u], 1), cf.br(b12[u], 0)),
                 unidade="usd-bi", fonte="Tesouro dos EUA (Monthly Treasury Statement, tabela 4) e FtM", variantes=[
                     dict(rot="Por mês", barra=1, series=[barras("Arrecadação no mês", AZUL, bruta, 1, rotulo=True)]),
                     dict(rot="Em 12 meses", series=[linha("Arrecadação em 12 meses", AZUL, b12, 1)])])
    # por mês do ano: 2026 e 2025 em destaque, os anos anteriores (cheios) em cinza
    anos = sorted({m[:4] for m in bruta})
    series = []
    for a in anos:
        meses = {str(i): bruta["%s-%02d" % (a, i + 1)] for i in range(12) if "%s-%02d" % (a, i + 1) in bruta}
        if a in (anos[-1], anos[-2]):
            continue
        if len(meses) < 12:
            continue
        primeiro = not series
        series.append(dict(nome="%s a %s" % (anos[1], anos[-3]) if primeiro else a, cor=CINZA, largura=2,
                           rotulo=False, dados=[[k, round(v, 1)] for k, v in meses.items()],
                           **({} if primeiro else {"legenda": False})))
    for a, cor in ((anos[-2], AZUL), (anos[-1], VERMELHO)):
        meses = {str(i): bruta["%s-%02d" % (a, i + 1)] for i in range(12) if "%s-%02d" % (a, i + 1) in bruta}
        series.append(dict(nome=a, cor=cor, largura=5, rotulo=True,
                           dados=[[k, round(v, 1)] for k, v in meses.items()]))
    ac = {a: sum(v for m, v in bruta.items() if m[:4] == a and m[5:] <= u[5:]) for a in (anos[-2], anos[-1])}
    g_anos = dict(id="tarifas-receita-anos", titulo="Receitas tarifárias dos EUA por mês: %s, %s e anos anteriores"
                  % (anos[-1], anos[-2]),
                  subtitulo="Impostos de importação arrecadados (customs duties, bruto), US$ bilhões por mês; "
                            "de jan a %s: US$ %s bi em %s e US$ %s bi em %s"
                            % (MESES[int(u[5:]) - 1], cf.br(ac[anos[-1]], 0), anos[-1], cf.br(ac[anos[-2]], 0),
                               anos[-2]),
                  unidade="usd-bi", categorias=MESES,
                  fonte="Tesouro dos EUA (Monthly Treasury Statement, tabela 4) e FtM", series=series)
    ini_dev = min(m for m, v in dev.items() if m >= "2026-01" and v > 10)
    acum = sum(v for m, v in dev.items() if m >= ini_dev)
    print("  tarifas %s: bruta US$ %.1f bi, 12 meses US$ %.0f bi; devoluções desde %s: US$ %.0f bi"
          % (u, bruta[u], b12[u], ini_dev, acum))
    g_dev = dict(id="tarifas-devolucoes", titulo="Devoluções de tarifas nos EUA",
                 subtitulo="Impostos de importação devolvidos, US$ bilhões por mês, desde 2024; de %s a %s: US$ %s bi"
                           % (cf.rot_mes(ini_dev), cf.rot_mes(u), cf.br(acum, 0)),
                 unidade="usd-bi", barra=1, fonte="Tesouro dos EUA (Monthly Treasury Statement, tabela 4) e FtM",
                 series=[barras("Devoluções no mês", VERMELHO, cf.desde(dev, "2024-01"), 1, rotulo=True)])
    return [g_rec, g_anos, g_dev]


# ---------- fotos ----------

FOTOS = [(1, "Foto 1"), (2, "Foto 2"), (3, "Foto 3"),
         (4, "G7 Economists Memo on Global Imbalances (28/3/2026)"),
         (5, "Desequilíbrios globais: G7, Bank of England e FMI"),
         (6, "Desequilíbrios globais: G7, Bank of England, FMI, Caixin e South China Morning Post"),
         (7, "BYD Dolphin Mini"), (8, "Reciprocal Tariffs"),
         (9, "Devolução de US$ 166 bilhões em tarifas (Fox Business, 20/4/2026)"), (10, "Foto 10")]


def fotos():
    return [dict(id="foto-%02d" % n, tipo="figura", foto=True, titulo=t,
                 imagem="assets/missao/foto-%02d.jpg" % n) for n, t in FOTOS]


def graficos():
    out = fotos() + [grafico_pib_eua_mundo()] + graficos_emprego_industria() + [grafico_va_industria()]
    out += [FIGURA_FMI, grafico_china_reservas_pib()] + graficos_yuan_equilibrio()
    out += [grafico_vix_incerteza()] + graficos_tarifas()
    return out

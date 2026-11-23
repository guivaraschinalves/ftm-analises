#!/usr/bin/env python3
"""
Migração na Europa: fluxos, estoque de nascidos no exterior, origens e idade,
para a UE-27, Alemanha, França, Itália e Espanha. Gera dados/migracao-europa.json.
Só biblioteca padrão. Rodado à mão. O texto vem de textos/migracao-europa.md.

Pedido dele em 18/11/2026, a partir do md "ftm-analises-migracao-europa-graficos"
(OpenBot). Os números saem da API do Eurostat, não do md; batem com ele.

DE ONDE VEM CADA COISA (API de disseminação do Eurostat, JSON-stat)

  - demo_pjan: população em 1º de janeiro (série histórica e 2024 para as taxas de fluxo).
  - migr_imm8 e migr_emi2: imigração e emigração anuais, totais (idade
    completa). Incluem o retorno de nativos e, na UE-27, a mudança entre países
    da UE.
  - migr_imm5prv e migr_emi3nxt: imigração por país de residência anterior e
    emigração por país de destino seguinte (2020–2024, critério uniforme
    pós-Brexit NEU27_2020_FOR para fluxos apenas com países fora da UE-27).
  - migr_pop3ctb: população em 1º/jan/2025 por país de nascimento (total,
    nativos, nascidos no exterior, na UE e fora dela), sexo e faixa de 5 anos.
  - migr_imm3ctb: imigração de 2024 por país de nascimento e faixa de 5 anos
    (para a idade, a "alcançada no ano", REACH: a única que a França publica).
    A França não abre os países de fora da UE; a UE-27 não abre país nenhum.
    A idade dos novos imigrantes da UE-27 não sai pronta: é a soma dos países
    que publicam a abertura por idade.
  - Idade média: ponto médio de cada faixa (2,5; 7,5; ...; 82,5) e 88,5 para
    85+, como no md.
  - demo_gind: crescimento natural (NATGROW, NATGROWRT), população média (AVG)
    e saldo migratório com ajustes (CNMIGRAT) no Eurostat (2020–2024).
  - Our World in Data (UN DESA, International Migrant Stock 2024 e UN WPP
    2024; Penn World Table 2025 e Huberman & Minns 2005): migrant-stock-share,
    migrant-stock-total, population-growth-rate-with-and-without-migration e
    annual-working-hours-per-worker.
  - Banco Mundial (NE.GDI.FTOT.ZS via CSV em ZIP): FBCF / PIB (1970–2025),
    conferida em 2024 contra Eurostat (nama_10_gdp, P51G, PC_GDP).
  - Henley & Partners / New World Wealth (2025): migração líquida de milionários.
  - HMRC (GOV.UK NONDOMTABLES.ods): contribuintes non-dom no Reino Unido (2008–2025).
"""
import csv
import datetime
import io
import json
import math
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SAIDA = os.path.join(RAIZ, "dados", "migracao-europa.json")
API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
OWID = "https://ourworldindata.org/grapher/"
WB_GFCF = "https://api.worldbank.org/v2/en/indicator/NE.GDI.FTOT.ZS?downloadformat=csv"
WB_GDP_PPP = "https://api.worldbank.org/v2/en/indicator/NY.GDP.MKTP.PP.CD?downloadformat=csv"
WB_GDPCAP_PPP = "https://api.worldbank.org/v2/en/indicator/NY.GDP.PCAP.PP.CD?downloadformat=csv"
WB_GDPCAP_USD = "https://api.worldbank.org/v2/en/indicator/NY.GDP.PCAP.CD?downloadformat=csv"
WB_GDP_USD = "https://api.worldbank.org/v2/en/indicator/NY.GDP.MKTP.CD?downloadformat=csv"
WB_POP = "https://api.worldbank.org/v2/en/indicator/SP.POP.TOTL?downloadformat=csv"
UE15 = ["AUT", "BEL", "DNK", "FIN", "FRA", "DEU", "GRC", "IRL", "ITA", "LUX", "NLD", "PRT", "ESP", "SWE", "GBR"]
UE27_ISO3 = ["AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC",
             "HUN", "IRL", "ITA", "LVA", "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK",
             "SVN", "ESP", "SWE"]
NORDICOS = ["SWE", "DNK", "NOR", "FIN"]
CONT_OCID = ["DEU", "FRA", "ITA", "NLD", "BEL", "AUT"]
HENLEY_2025 = "https://www.henleyglobal.com/newsroom/press-releases/henley-private-wealth-migration-report-2025"
HMRC_ODS = "https://assets.publishing.service.gov.uk/media/6a5a3d5b5ca06bf11ccb43fe/NONDOMTABLES.ods"
OCDE_PDB = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PDB@DF_PDB,2.0/"
OCDE_MIG_EMP = "https://sdmx.oecd.org/public/rest/data/OECD.ELS.IMD,DSD_MIG@DF_MIG_NUP_SEX,1.0/"
STATBANK_DK = "https://api.statbank.dk/v1/data"
PWT_11 = "https://dataverse.nl/api/access/datafile/554105"
QOG_STD = "https://www.qogdata.pol.gu.se/data/qog_std_cs_jan24.csv"
UA = {"User-Agent": "ftm-analises"}
UA_OCDE = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
           "Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}

# Tabela 1 de Olivier Blanchard, "The Economic Future of Europe" (JEP, 2004), EUA = 100.
# Valores históricos publicados (fixos, 19/11/2026).
BLANCHARD_2004 = {
    "EU15": {"1970": (69, 65, 101), "2000": (70, 91, 77)},
    "FRA": {"1970": (73, 73, 99), "2000": (71, 105, 67)},
}

AZUL, VERMELHO, VERDE = "#4F81BD", "#C0504D", "#9BBB59"
AZUL_CLARO, LARANJA, AMARELO, BRANCO = "#8EB4E3", "#F79646", "#FFFF00", "#FFFFFF"

TERR = [("EU27_2020", "UE-27"), ("DE", "Alemanha"), ("FR", "França"), ("IT", "Itália"), ("ES", "Espanha")]
UE = ["BE", "BG", "CZ", "DK", "DE", "EE", "IE", "EL", "ES", "FR", "HR", "IT", "CY", "LV", "LT", "LU", "HU", "MT",
      "NL", "AT", "PL", "PT", "RO", "SI", "SK", "FI", "SE"]
FAIXAS = ["Y_LT5", "Y5-9", "Y10-14", "Y15-19", "Y20-24", "Y25-29", "Y30-34", "Y35-39", "Y40-44", "Y45-49",
          "Y50-54", "Y55-59", "Y60-64", "Y65-69", "Y70-74", "Y75-79", "Y80-84", "Y_GE85"]
ROT_FAIXAS = ["0–4", "5–9", "10–14", "15–19", "20–24", "25–29", "30–34", "35–39", "40–44", "45–49",
              "50–54", "55–59", "60–64", "65–69", "70–74", "75–79", "80–84", "85+"]
MEIOS = [2.5 + 5 * i for i in range(17)] + [88.5]
AGREGADOS = {"TOTAL", "FOR", "NAT", "EU27_2020_FOR", "NEU27_2020_FOR", "UNK", "STLS", "EU28_FOR", "NEU28_FOR",
             "EU27_2007_FOR", "NEU27_2007_FOR", "EU25_FOR", "NEU25_FOR", "EU15_FOR", "NEU15_FOR", "EFTA_FOR",
             "EU27_2020_NAT", "EFTA", "CC5_13_FOR", "NEU27_2020_NAT"}
# nomes em português dos países que podem aparecer no topo
NOMES = {"UA": "Ucrânia", "SY": "Síria", "TR": "Turquia", "RO": "Romênia", "IN": "Índia", "BD": "Bangladesh",
         "AL": "Albânia", "MA": "Marrocos", "PK": "Paquistão", "EG": "Egito", "CO": "Colômbia", "VE": "Venezuela",
         "PE": "Peru", "AR": "Argentina", "IT": "Itália", "DE": "Alemanha", "BE": "Bélgica", "ES": "Espanha",
         "PT": "Portugal", "PL": "Polônia", "BG": "Bulgária", "AF": "Afeganistão", "CN": "China", "BR": "Brasil",
         "TN": "Tunísia", "DZ": "Argélia", "NG": "Nigéria", "GE": "Geórgia", "RU": "Rússia", "US": "EUA",
         "UK": "Reino Unido", "FR": "França", "NL": "Países Baixos", "AT": "Áustria", "HR": "Croácia",
         "HU": "Hungria", "GR": "Grécia", "EL": "Grécia", "IQ": "Iraque", "IR": "Irã", "PH": "Filipinas",
         "LK": "Sri Lanka", "SN": "Senegal", "HN": "Honduras", "CU": "Cuba", "UY": "Uruguai", "CL": "Chile",
         "EC": "Equador", "BO": "Bolívia", "DO": "República Dominicana", "NP": "Nepal", "MD": "Moldávia",
         "RS": "Sérvia", "XK": "Kosovo", "MK": "Macedônia do Norte", "BA": "Bósnia", "KO": "Kosovo",
         "IE": "Irlanda", "CZ": "Tchéquia", "SK": "Eslováquia", "LT": "Lituânia", "LV": "Letônia",
         "SE": "Suécia", "DK": "Dinamarca", "FI": "Finlândia", "LU": "Luxemburgo", "NO": "Noruega",
         "CH": "Suíça", "SI": "Eslovênia", "CY": "Chipre", "MT": "Malta", "EE": "Estônia"}


def baixar(url, headers=None, tentativas=4, timeout=120):
    """Baixa uma URL usando apenas biblioteca padrão, com retentativas."""
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:                               # noqa: BLE001
            ultimo = e
            time.sleep(2 * (i + 1))
    raise RuntimeError("não deu para baixar %s: %s" % (url, ultimo))


def eurostat(codigo, chaves, **filtros):
    """{tupla com os códigos das dimensões em `chaves`, nessa ordem: valor}, mais os rótulos."""
    pares = []
    for k, v in filtros.items():
        for x in (v if isinstance(v, list) else [v]):
            pares.append("%s=%s" % (k, x))
    r = json.loads(baixar(API + codigo + "?format=JSON&lang=EN&" + "&".join(pares), headers=UA))
    ids, tam = r["id"], r["size"]
    cats = [sorted(r["dimension"][d]["category"]["index"].items(), key=lambda kv: kv[1]) for d in ids]
    varia = [ids.index(c) for c in chaves]
    out = {}
    for pos, v in r["value"].items():
        pos, coord = int(pos), []
        for i in reversed(range(len(ids))):
            coord.append(pos % tam[i])
            pos //= tam[i]
        coord.reverse()
        chave = tuple(cats[i][coord[i]][0] for i in varia)
        out[chave if len(chave) > 1 else chave[0]] = v
    rotulos = {d: r["dimension"][d]["category"].get("label", {}) for d in ids}
    return out, rotulos


def br(v, casas=1):
    s = "{:,.{c}f}".format(v, c=casas)
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def conferir(condicao, msg):
    if not condicao:
        raise RuntimeError("conferência falhou: " + msg)


def owid_cols(slug, colunas):
    """Baixa CSV do Our World in Data e retorna {(entity, year): {col: float}}."""
    url = OWID + slug + ".csv?v=1&csvType=full&useColumnShortNames=true"
    txt = baixar(url, headers=UA).decode("utf-8")
    out = {}
    for row in csv.DictReader(io.StringIO(txt)):
        vals = {}
        for c in colunas:
            v = row.get(c, "").strip()
            if v:
                vals[c] = float(v)
        if vals:
            out[(row["entity"], row["year"])] = vals
    return out


def owid(slug, coluna):
    """Baixa CSV do Our World in Data e retorna {(entity, year): float}."""
    return {k: v[coluna] for k, v in owid_cols(slug, [coluna]).items() if coluna in v}


def carregar_horas():
    """Retorna {entity: [(year_str, float), ...]} de 1950 a 2023."""
    raw = owid("annual-working-hours-per-worker", "working_hours_omm")
    out = {}
    for (ent, y), v in raw.items():
        if int(y) >= 1950:
            out.setdefault(ent, []).append((y, v))
    for ent in out:
        out[ent].sort(key=lambda kv: int(kv[0]))
    return out


def _carregar_wb_zip(url, prefixo, codigos, ano_ini, ano_fim):
    """Baixa CSV em ZIP do Banco Mundial e retorna {iso3: {year_str: float}}."""
    zbytes = baixar(url, headers=UA)
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        fn = [n for n in z.namelist() if n.startswith(prefixo) and n.endswith(".csv")][0]
        txt = z.read(fn).decode("utf-8-sig")
    linhas = txt.splitlines()
    idx_hdr = next(i for i, l in enumerate(linhas[:10]) if "Country Code" in l)
    reader = csv.DictReader(io.StringIO("\n".join(linhas[idx_hdr:])))
    anos = [str(y) for y in range(ano_ini, ano_fim + 1)]
    alvo = set(codigos)
    out = {}
    for row in reader:
        cc = row["Country Code"]
        if cc in alvo:
            out[cc] = {y: float(row[y]) for y in anos if row.get(y, "").strip()}
    return out


def carregar_wb_fbcf():
    """Retorna {iso3: [(year_str, float), ...]} de 1970 a 2025."""
    cods = ["EUU", "DEU", "FRA", "ITA", "ESP", "GBR", "USA", "CAN", "JPN", "KOR"]
    bruto = _carregar_wb_zip(WB_GFCF, "API_NE.GDI.FTOT.ZS", cods, 1970, 2025)
    return {cc: sorted(bruto[cc].items(), key=lambda kv: int(kv[0])) for cc in cods if cc in bruto}


def carregar_wb_pib_ppp():
    """Retorna participação no PIB mundial em PPP (1990-2025) e PIB per capita relativo aos EUA."""
    anos_ppp = [str(y) for y in range(1990, 2026)]
    anos_usd = [str(y) for y in range(1960, 2026)]
    cods_world = sorted(set(["WLD", "EUU", "USA", "CHN"] + UE15 + UE27_ISO3 + NORDICOS))
    pib_ppp = _carregar_wb_zip(WB_GDP_PPP, "API_NY.GDP.MKTP.PP.CD", cods_world, 1990, 2025)

    part = {"UE15": [], "UE27": [], "USA": [], "CHN": [], "GBR": [], "NORD": [],
            "SWE": [], "DNK": [], "NOR": [], "FIN": []}
    for y in anos_ppp:
        wld = pib_ppp["WLD"][y]
        s15 = sum(pib_ppp[c][y] for c in UE15) / wld * 100.0
        euu = pib_ppp["EUU"][y] / wld * 100.0
        s27 = sum(pib_ppp[c][y] for c in UE27_ISO3) / wld * 100.0
        conferir(abs(euu - s27) < 0.05, "WB EUU diverge da soma dos 27 em %s: %.3f vs %.3f" % (y, euu, s27))
        part["UE15"].append((y, s15))
        part["UE27"].append((y, euu))
        part["USA"].append((y, pib_ppp["USA"][y] / wld * 100.0))
        part["CHN"].append((y, pib_ppp["CHN"][y] / wld * 100.0))
        part["GBR"].append((y, pib_ppp["GBR"][y] / wld * 100.0))
        part["NORD"].append((y, sum(pib_ppp[c][y] for c in NORDICOS) / wld * 100.0))
        for c in NORDICOS:
            part[c].append((y, pib_ppp[c][y] / wld * 100.0))

    conferir(20.0 < part["UE15"][0][1] < 23.0 and 12.0 < part["UE15"][-1][1] < 15.0,
             "UE-15 PPP/PIB mundial fora do esperado: 1990=%.2f 2025=%.2f" % (part["UE15"][0][1], part["UE15"][-1][1]))
    conferir(13.0 < part["USA"][-1][1] < 16.0, "EUA PPP/PIB mundial 2025 inesperado: %.2f" % part["USA"][-1][1])
    conferir(0.9 < part["NORD"][-1][1] < 1.6 and part["NORD"][0][1] > part["NORD"][-1][1],
             "Nórdicos PPP/PIB mundial fora do esperado: 1990=%.2f 2025=%.2f" % (part["NORD"][0][1], part["NORD"][-1][1]))

    paises_pc = sorted(set(["USA", "GBR", "FRA", "ITA", "KOR", "CHN"] + NORDICOS))
    paises_agg = sorted(set(CONT_OCID))
    pc_ppp_raw = _carregar_wb_zip(WB_GDPCAP_PPP, "API_NY.GDP.PCAP.PP.CD", paises_pc, 1990, 2025)
    pc_usd_raw = _carregar_wb_zip(WB_GDPCAP_USD, "API_NY.GDP.PCAP.CD", paises_pc, 1960, 2025)
    pib_usd = _carregar_wb_zip(WB_GDP_USD, "API_NY.GDP.MKTP.CD", paises_agg, 1960, 2025)
    pop_raw = _carregar_wb_zip(WB_POP, "API_SP.POP.TOTL", paises_agg, 1960, 2025)

    rel_ppp = {c: [(y, pc_ppp_raw[c][y] / pc_ppp_raw["USA"][y] * 100.0) for y in anos_ppp]
               for c in paises_pc if c != "USA"}
    rel_usd = {c: [(y, pc_usd_raw[c][y] / pc_usd_raw["USA"][y] * 100.0) for y in anos_usd]
               for c in paises_pc if c != "USA"}
    rel_ppp["CONT"] = [
        (y, (sum(pib_ppp[c][y] for c in CONT_OCID) / sum(pop_raw[c][y] for c in CONT_OCID))
         / pc_ppp_raw["USA"][y] * 100.0)
        for y in anos_ppp
    ]
    rel_usd["CONT"] = [
        (y, (sum(pib_usd[c][y] for c in CONT_OCID) / sum(pop_raw[c][y] for c in CONT_OCID))
         / pc_usd_raw["USA"][y] * 100.0)
        for y in anos_usd
    ]

    for c in ("GBR", "FRA", "ITA", "KOR", "CHN", "SWE", "DNK", "NOR", "FIN", "CONT"):
        conferir(len(rel_ppp[c]) == len(anos_ppp) and len(rel_usd[c]) == len(anos_usd),
                 "série incompleta de PIB per capita para %s" % c)
    conferir(rel_ppp["KOR"][0][1] < 40.0 and rel_ppp["KOR"][-1][1] > 65.0,
             "Coreia do Sul PPP/EUA inesperado: 1990=%.1f 2025=%.1f" % (rel_ppp["KOR"][0][1], rel_ppp["KOR"][-1][1]))
    conferir(rel_ppp["NOR"][-1][1] > 100.0 and 70.0 < rel_ppp["CONT"][-1][1] < 85.0,
             "Escandinavos/Europa Continental PPP/EUA inesperado: NOR=%.1f CONT=%.1f"
             % (rel_ppp["NOR"][-1][1], rel_ppp["CONT"][-1][1]))
    return part, rel_ppp, rel_usd


def carregar_satisfacao():
    """Retorna notas Cantril (Gallup/WHR 2011-2025) e % felizes (WVS até 2022), conferidos com Eurostat ilc_pw01."""
    cantril = owid("happiness-cantril-ladder", "cantril_ladder_score")
    happy = owid("share-of-people-who-say-they-are-happy", "happy")
    eu_pw25, _ = eurostat("ilc_pw01", ["geo"], sex="T", age="Y_GE16", isced11="TOTAL", life_sat="LIFE", time="2025")
    conferir(7.0 <= eu_pw25["EU27_2020"] <= 7.5, "Eurostat ilc_pw01 UE-27 2025 inesperado: %.2f" % eu_pw25["EU27_2020"])

    paises_c = [
        ("Finland", "Finlândia", AZUL),
        ("Denmark", "Dinamarca", AZUL),
        ("Sweden", "Suécia", AZUL),
        ("Norway", "Noruega", AZUL),
        ("Netherlands", "Países Baixos", AZUL),
        ("Switzerland", "Suíça", AZUL),
        ("Germany", "Alemanha", AZUL),
        ("United States", "Estados Unidos", VERMELHO),
        ("United Kingdom", "Reino Unido", AZUL),
        ("France", "França", AZUL),
        ("Italy", "Itália", AZUL),
        ("Spain", "Espanha", AZUL),
        ("Argentina", "Argentina", AMARELO),
        ("World", "Média mundial", BRANCO),
    ]
    anos_c = [str(y) for y in range(2011, 2026) if y != 2013]
    series_c = {
        en: [(y, cantril[(en, y)]) for y in anos_c]
        for en, _, _ in paises_c
    }
    rank_c25 = sorted(
        [(pt, cantril[(en, "2025")], cor) for en, pt, cor in paises_c],
        key=lambda x: -x[1],
    )
    conferir(cantril[("Finland", "2025")] > cantril[("Germany", "2025")] > cantril[("World", "2025")],
             "ranking Cantril 2025 fora do esperado")

    paises_h = [
        ("Norway", "Noruega", AZUL),
        ("Sweden", "Suécia", AZUL),
        ("United Kingdom", "Reino Unido", AZUL),
        ("France", "França", AZUL),
        ("Netherlands", "Países Baixos", AZUL),
        ("Denmark", "Dinamarca", AZUL),
        ("Finland", "Finlândia", AZUL),
        ("Spain", "Espanha", AZUL),
        ("United States", "Estados Unidos", VERMELHO),
        ("Germany", "Alemanha", AZUL),
        ("Argentina", "Argentina", AMARELO),
        ("Italy", "Itália", AZUL),
    ]
    rank_h22 = sorted(
        [(pt, happy[(en, "2022")], cor) for en, pt, cor in paises_h],
        key=lambda x: -x[1],
    )
    conferir(all(v > 80.0 for _, v, _ in rank_h22), "WVS 2022 abaixo de 80%% inesperado")
    return rank_c25, rank_h22, series_c, eu_pw25["EU27_2020"]


def carregar_henley_2025():
    """Baixa o press release oficial da Henley 2025 e verifica os valores por regex."""
    html = baixar(HENLEY_2025, headers=UA).decode("utf-8", errors="ignore")
    txt = re.sub(r"<(script|style).*?</\1>", " ", html, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    esperados = {
        "Reino Unido": (r"–16,500", -16500),
        "França": (r"France, Spain, and Germany are expected to see net HNWI losses in 2025 — with projected net outflows of –800, –500, and –400", -800),
        "Espanha": (r"–800, –500, and –400", -500),
        "Alemanha": (r"–800, –500, and –400", -400),
        "Noruega": (r"Norway \(–150\)", -150),
        "Irlanda": (r"Ireland \(–100\)", -100),
        "Suécia": (r"Sweden \(–50\)", -50),
        "Itália": (r"Italy , Portugal , and Greece are also forecast to see record inflows of \+3,600, \+1,400 and \+1,200", 3600),
        "Suíça": (r"Switzerland , set to attract a net gain of \+3,000", 3000),
        "Portugal": (r"\+3,600, \+1,400 and \+1,200", 1400),
        "Grécia": (r"\+3,600, \+1,400 and \+1,200", 1200),
        "Malta": (r"Malta \(\+500\)", 500),
        "Mônaco": (r"Monaco \(\+200\)", 200),
        "Montenegro": (r"Montenegro \(\+150\)", 150),
        "Letônia": (r"Latvia .*?\+100 HNWIs", 100),
        "Emirados Árabes Unidos": (r"UAE retains its crown.*?\+9,800", 9800),
        "Estados Unidos": (r"\+7,500 new wealthy migrants", 7500),
        "Arábia Saudita": (r"Saudi Arabia .*?\+2,400", 2400),
        "Singapura": (r"Singapore \( \+1,600 \)", 1600),
        "Austrália": (r"Australia \(\+1,000\)", 1000),
        "Canadá": (r"Canada \(\+1,000\)", 1000),
        "Japão": (r"Japan \(\+600\)", 600),
        "China": (r"–7,800 net outflow from China", -7800),
    }
    valores = {}
    for pais, (padrao, val) in esperados.items():
        conferir(re.search(padrao, txt) is not None, "Henley 2025 não confirmou %s (%s)" % (pais, padrao))
        valores[pais] = val
    return valores


def carregar_hmrc_nondom():
    """Lê Table_2, Table_3 e Table_13 de NONDOMTABLES.ods (HMRC / GOV.UK)."""
    ods = baixar(HMRC_ODS, headers=UA)
    ns = {
        "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
        "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    }
    with zipfile.ZipFile(io.BytesIO(ods)) as z:
        root = ET.fromstring(z.read("content.xml"))
    tabelas = {}
    for tbl in root.findall(".//table:table", ns):
        nome = tbl.get("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}name")
        if nome not in ("Table_2", "Table_3", "Table_13"):
            continue
        linhas = []
        for r in tbl.findall("table:table-row", ns):
            vals = []
            for c in r.findall("table:table-cell", ns):
                rep = int(c.get("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}number-columns-repeated") or 1)
                t = "".join(p.text or "" for p in c.findall(".//text:p", ns)).strip()
                vals.extend([t] * min(rep, 15))
            limpos = [x for x in vals if x]
            if limpos:
                linhas.append(limpos)
        tabelas[nome] = linhas

    def extrair_serie(linhas):
        hdr_idx = next(i for i, r in enumerate(linhas) if r[0] == "Tax Year Ending")
        col_n = linhas[hdr_idx].index("Number of individuals")
        return {
            r[0]: int(r[col_n].replace(",", ""))
            for r in linhas[hdr_idx + 1:]
            if len(r) > col_n and re.fullmatch(r"\d{4}", r[0])
        }

    todos = extrair_serie(tabelas["Table_2"])
    resid = extrair_serie(tabelas["Table_3"])
    chegadas = {}
    hdr13 = next(i for i, r in enumerate(tabelas["Table_13"]) if r[0] == "Year of stay")
    for r in tabelas["Table_13"][hdr13 + 1:]:
        if len(r) >= 3 and r[0] == "1" and re.fullmatch(r"\d{4}", r[1]):
            chegadas[r[1]] = int(r[2].replace(",", ""))
    return todos, resid, chegadas


def carregar_ocde_blanchard():
    """Puxa GDP (PPP corrente), POP e HRSTO de 2000 a 2025 na OCDE (EUA = 100)."""
    eu15 = ["AUT", "BEL", "DNK", "FIN", "FRA", "DEU", "GRC", "IRL", "ITA", "LUX", "NLD", "PRT", "ESP", "SWE", "GBR"]
    areas = "+".join(["USA", "EU27_2020"] + eu15)
    url = (OCDE_PDB + areas
           + ".A.GDP+POP+HRSTO._T..V+_Z.N._Z.?startPeriod=2000&endPeriod=2025")
    txt = baixar(url, headers=UA_OCDE).decode("utf-8")
    raw = {}
    for row in csv.DictReader(io.StringIO(txt)):
        m = row["MEASURE"]
        if m == "GDP" and not (row["UNIT_MEASURE"] == "USD_PPP" and row["PRICE_BASE"] == "V"
                               and row["CONVERSION_TYPE"] == "PPP"):
            continue
        if m == "POP" and row["UNIT_MEASURE"] != "PS":
            continue
        if m == "HRSTO" and row["UNIT_MEASURE"] != "H":
            continue
        if row.get("OBS_VALUE", "").strip():
            raw[(row["REF_AREA"], row["TIME_PERIOD"], m)] = float(row["OBS_VALUE"])

    out = {"EU15": {}, "FRA": {}, "EU27": {}}
    for y in range(2000, 2026):
        yr = str(y)
        us_g = raw[("USA", yr, "GDP")]
        us_p = raw[("USA", yr, "POP")]
        us_h = raw[("USA", yr, "HRSTO")]
        for chave, paises in [("EU15", eu15), ("FRA", ["FRA"]), ("EU27", ["EU27_2020"])]:
            g = sum(raw[(c, yr, "GDP")] for c in paises)
            p = sum(raw[(c, yr, "POP")] for c in paises)
            h = sum(raw[(c, yr, "HRSTO")] for c in paises)
            gp = 100.0 * (g / p) / (us_g / us_p)
            gh = 100.0 * (g / h) / (us_g / us_h)
            hp = 100.0 * (h / p) / (us_h / us_p)
            conferir(abs((gp / 100.0) - (gh / 100.0) * (hp / 100.0)) < 1e-6,
                     "identidade PIB/pessoa != PIB/hora * Horas/pessoa em %s %s" % (chave, yr))
            out[chave][yr] = (gp, gh, hp)
    return out


def _pwt_fallback_json():
    """Reaproveita PWT 11.0 (1970-2023) já gravada em dados/migracao-europa.json se dataverse.nl estiver fora."""
    with open(SAIDA, "r", encoding="utf-8") as f:
        doc = json.load(f)
    g = next(x for s in doc["secoes"] for x in s["graficos"] if x["id"] == "migracao-produtividade-blanchard")
    vmap = {v["rot"]: {sr["nome"]: {d[0][:4]: float(d[1]) for d in sr["dados"]} for sr in v["series"]} for v in g["variantes"]}
    out = {"EU15": {}, "FRA": {}}
    for y in range(1970, 2024):
        yr = str(y)
        for ch, nome in (("EU15", "EU-15"), ("FRA", "França")):
            out[ch][yr] = (
                vmap["PIB por pessoa (1970 a 2023, PWT)"][nome][yr],
                vmap["PIB por hora (1970 a 2023, PWT)"][nome][yr],
                vmap["Horas por pessoa (1970 a 2023, PWT)"][nome][yr],
            )
    return out


def carregar_pwt11_blanchard():
    """Puxa PWT 11.0 (cgdpo, pop, emp, avh) de 1970 a 2023 para EUA, EU-15 e França (EUA = 100)."""
    eu15 = ["AUT", "BEL", "DNK", "FIN", "FRA", "DEU", "GRC", "IRL", "ITA", "LUX", "NLD", "PRT", "ESP", "SWE", "GBR"]
    alvos = set(eu15) | {"USA"}
    try:
        xlsx = baixar(PWT_11, headers={"User-Agent": "Mozilla/5.0"}, tentativas=2, timeout=20)
    except RuntimeError as e:
        if os.path.exists(SAIDA):
            print("  AVISO PWT 11.0 (%s): usando séries PWT já gravadas em %s" % (e, SAIDA))
            return _pwt_fallback_json()
        raise
    ns_m = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    ns_r = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

    def _col_idx(ref):
        v = 0
        for ch in ref:
            if ch.isalpha():
                v = v * 26 + (ord(ch) - 64)
        return v - 1

    raw = {}
    with zipfile.ZipFile(io.BytesIO(xlsx)) as z:
        ss = [
            "".join(t.text or "" for t in si.iter(ns_m + "t"))
            for si in ET.fromstring(z.read("xl/sharedStrings.xml"))
        ]
        wb_root = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rmap = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        target = next(
            "xl/" + rmap[sh.attrib[ns_r + "id"]].lstrip("/")
            for sh in wb_root.iter(ns_m + "sheet")
            if sh.attrib["name"] == "Data"
        )
        hdr = {}
        with z.open(target) as f:
            for _, elem in ET.iterparse(f, events=("end",)):
                if elem.tag == ns_m + "row":
                    rv = {}
                    for c in elem:
                        v_el = c.find(ns_m + "v")
                        if v_el is not None and v_el.text is not None:
                            rv[_col_idx(c.attrib["r"])] = ss[int(v_el.text)] if c.attrib.get("t") == "s" else v_el.text
                    if elem.attrib.get("r") == "1":
                        hdr = {v: k for k, v in rv.items()}
                    else:
                        cc = rv.get(hdr["countrycode"])
                        yr_s = rv.get(hdr["year"])
                        if cc in alvos and yr_s and yr_s.isdigit() and 1970 <= int(yr_s) <= 2023:
                            raw[(cc, yr_s)] = {
                                k: float(rv[hdr[k]])
                                for k in ("cgdpo", "pop", "emp", "avh")
                                if k in hdr and hdr[k] in rv
                            }
                    elem.clear()

    out = {"EU15": {}, "FRA": {}}
    for y in range(1970, 2024):
        yr = str(y)
        for c in alvos:
            conferir(all(k in raw.get((c, yr), {}) for k in ("cgdpo", "pop", "emp", "avh")),
                     "PWT 11.0 incompleto para %s em %s" % (c, yr))
        us = raw[("USA", yr)]
        us_h = us["emp"] * us["avh"]
        for chave, paises in [("EU15", eu15), ("FRA", ["FRA"])]:
            g = sum(raw[(c, yr)]["cgdpo"] for c in paises)
            p = sum(raw[(c, yr)]["pop"] for c in paises)
            h = sum(raw[(c, yr)]["emp"] * raw[(c, yr)]["avh"] for c in paises)
            gp = 100.0 * (g / p) / (us["cgdpo"] / us["pop"])
            gh = 100.0 * (g / h) / (us["cgdpo"] / us_h)
            hp = 100.0 * (h / p) / (us_h / us["pop"])
            conferir(abs((gp / 100.0) - (gh / 100.0) * (hp / 100.0)) < 1e-6,
                     "identidade PWT falhou em %s %s" % (chave, yr))
            out[chave][yr] = (gp, gh, hp)
    return out


def carregar_ocde_emprego_mig():
    """Taxa de emprego (15 a 64 anos) de nativos vs nascidos no exterior na OCDE (2025)."""
    paises = [
        ("IRL", "Irlanda"), ("PRT", "Portugal"), ("USA", "EUA"), ("ITA", "Itália"),
        ("GBR", "Reino Unido"), ("AUS", "Austrália"), ("CAN", "Canadá"), ("ESP", "Espanha"),
        ("DNK", "Dinamarca"), ("BEL", "Bélgica"), ("FRA", "França"), ("SWE", "Suécia"),
        ("DEU", "Alemanha"), ("FIN", "Finlândia"), ("NLD", "Países Baixos"),
    ]
    areas = "+".join(c for c, _ in paises)
    url = OCDE_MIG_EMP + areas + "._Z.A.EMP_WAP._T.NB+FB._Z.PT_WAP_SUB?startPeriod=2025&endPeriod=2025"
    txt = baixar(url, headers=UA_OCDE).decode("utf-8")
    vals = {}
    for row in csv.DictReader(io.StringIO(txt)):
        if row.get("OBS_VALUE", "").strip():
            vals[(row["REF_AREA"], row["BIRTH_PLACE"])] = float(row["OBS_VALUE"])
    out = []
    for c, nome in paises:
        conferir((c, "NB") in vals and (c, "FB") in vals, "OCDE emprego 2025 ausente para %s" % c)
        nb, fb = vals[(c, "NB")], vals[(c, "FB")]
        conferir(30.0 < nb < 95.0 and 30.0 < fb < 95.0, "OCDE emprego suspeito para %s" % c)
        out.append((c, nome, nb, fb, fb - nb))
    out.sort(key=lambda item: -item[4])
    return out


def carregar_dinamarca_van66():
    """Autorizações de residência anuais por motivo na Dinamarca (StatBank VAN66, 1997 a 2025)."""
    payload = json.dumps({
        "table": "VAN66",
        "format": "CSV",
        "lang": "en",
        "variables": [{"code": "OPHOLD", "values": ["*"]}, {"code": "Tid", "values": ["*"]}],
    }).encode("utf-8")
    req = urllib.request.Request(STATBANK_DK, data=payload,
                                 headers={"Content-Type": "application/json", "User-Agent": "ftm-analises"})
    ultimo = None
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = r.read().decode("utf-8-sig")
            break
        except Exception as e:
            ultimo = e
            time.sleep(2 * (i + 1))
    else:
        raise RuntimeError("não deu para baixar VAN66: %s" % ultimo)

    out = {}
    for row in csv.DictReader(io.StringIO(txt), delimiter=";"):
        yr = row["TID"].strip()
        oph = row["OPHOLD"].strip()
        v = int(row["INDHOLD"]) if row["INDHOLD"].strip().isdigit() else 0
        d = out.setdefault(yr, {"asilo": 0, "familia": 0, "trabalho": 0, "eu": 0, "ucrania": 0, "total": 0})
        d["total"] += v
        if "Asylum" in oph:
            d["asilo"] += v
        elif "Family reunification" in oph:
            d["familia"] += v
        elif oph == "Work" or oph.startswith("Work"):
            d["trabalho"] += v
        elif "EU/EEA" in oph:
            d["eu"] += v
        elif "Ukraine" in oph:
            d["ucrania"] += v
    anos = sorted(out.keys(), key=int)
    conferir(anos[0] == "1997" and int(anos[-1]) >= 2025, "VAN66 período inesperado: %s..%s" % (anos[0], anos[-1]))
    conferir(len(anos) == int(anos[-1]) - int(anos[0]) + 1, "buraco em VAN66")
    conferir(out["2001"]["asilo"] + out["2001"]["familia"] > out["2004"]["asilo"] + out["2004"]["familia"] * 2,
             "queda pós-Starthjælp não confirmada em VAN66")
    return out


def carregar_diversidade_tributos():
    """Diversidade étnica (Alesina/QoG), nascidos no exterior (ONU 2024) e carga tributária/PIB na OCDE."""
    oecd = {
        "AUS": "Austrália", "AUT": "Áustria", "BEL": "Bélgica", "CAN": "Canadá", "CHL": "Chile",
        "COL": "Colômbia", "CRI": "Costa Rica", "CZE": "Tchéquia", "DNK": "Dinamarca", "EST": "Estônia",
        "FIN": "Finlândia", "FRA": "França", "DEU": "Alemanha", "GRC": "Grécia", "HUN": "Hungria",
        "ISL": "Islândia", "IRL": "Irlanda", "ISR": "Israel", "ITA": "Itália", "JPN": "Japão",
        "KOR": "Coreia do Sul", "LVA": "Letônia", "LTU": "Lituânia", "LUX": "Luxemburgo", "MEX": "México",
        "NLD": "Países Baixos", "NZL": "Nova Zelândia", "NOR": "Noruega", "POL": "Polônia", "PRT": "Portugal",
        "SVK": "Eslováquia", "SVN": "Eslovênia", "ESP": "Espanha", "SWE": "Suécia", "CHE": "Suíça",
        "TUR": "Turquia", "GBR": "Reino Unido", "USA": "EUA",
    }
    qog_txt = baixar(QOG_STD, headers={"User-Agent": "Mozilla/5.0"}).decode("utf-8", errors="ignore")
    eth = {
        r["ccodealp"]: float(r["al_ethnic2000"])
        for r in csv.DictReader(io.StringIO(qog_txt))
        if r.get("ccodealp") in oecd and r.get("al_ethnic2000", "").strip()
    }
    tax_txt = baixar(OWID + "total-tax-revenues-gdp.csv?v=1&csvType=full&useColumnShortNames=true", headers=UA).decode("utf-8")
    tax = {}
    for r in csv.DictReader(io.StringIO(tax_txt)):
        c, v, y = r.get("code", ""), r.get("tax_inc_sc", "").strip(), r.get("year", "").strip()
        if c in oecd and v and y.isdigit():
            yi = int(y)
            if yi >= 2020 and (c not in tax or yi > tax[c][0]):
                tax[c] = (yi, float(v))

    mig_txt = baixar(OWID + "migrant-stock-share.csv?v=1&csvType=full&useColumnShortNames=true", headers=UA).decode("utf-8")
    mig = {}
    for r in csv.DictReader(io.StringIO(mig_txt)):
        c, v, y = r.get("code", ""), r.get("immigrant_share_of_dest_population_all", "").strip(), r.get("year", "").strip()
        if c in oecd and v and y == "2024":
            mig[c] = float(v)

    conferir(len(eth) == 38 and len(tax) == 38 and len(mig) == 38,
             "OCDE incompleta em diversidade/tributos: eth=%d tax=%d mig=%d" % (len(eth), len(tax), len(mig)))
    return [(c, oecd[c], eth[c], mig[c], tax[c][1], tax[c][0]) for c in sorted(oecd)]


ANOS_EXTRA = ["2020", "2021", "2022", "2023", "2024"]
TERR_PIR = [("IT", "Itália"), ("FR", "França"), ("ES", "Espanha"), ("DE", "Alemanha"), ("EU27_2020", "UE-27")]
TERR_OWID = [("IT", "Italy", "Itália"), ("FR", "France", "França"),
             ("ES", "Spain", "Espanha"), ("DE", "Germany", "Alemanha")]
ROT_PIR = ROT_FAIXAS[:15] + ["75+"]


def main():
    geos = [g for g, _ in TERR]
    pop_t, _ = eurostat("demo_pjan", ["geo", "time"], geo=geos, age="TOTAL", sex="T")
    imi_t, _ = eurostat("migr_imm8", ["geo", "time"], geo=geos, age="TOTAL", sex="T", agedef="COMPLET")
    emi_t, _ = eurostat("migr_emi2", ["geo", "time"], geo=geos, age="TOTAL", sex="T", agedef="COMPLET")
    # fluxos por residência anterior / destino seguinte (2020–2024: corte uniforme pós-Brexit fora da UE-27)
    partes = ["TOTAL", "EU27_2020_FOR", "NEU27_2020_FOR", "UNK"]
    imm_prv, _ = eurostat("migr_imm5prv", ["geo", "partner", "time"], geo=geos, time=ANOS_EXTRA,
                          age="TOTAL", sex="T", agedef="COMPLET", partner=partes)
    emi_nxt, _ = eurostat("migr_emi3nxt", ["geo", "partner", "time"], geo=geos, time=ANOS_EXTRA,
                          age="TOTAL", sex="T", agedef="COMPLET", partner=partes)
    # indicadores demográficos (população média e saldo natural, 2020–2024)
    gind, _ = eurostat("demo_gind", ["geo", "indic_de", "time"], geo=geos, time=ANOS_EXTRA,
                       indic_de=["AVG", "NATGROW", "NATGROWRT"])
    # estoque em 1º/jan/2025 por bloco de nascimento, sexo e idade (inclui o total e nativos)
    est, _ = eurostat("migr_pop3ctb", ["geo", "c_birth", "sex", "age"], geo=geos, time="2025",
                      sex=["T", "M", "F"], age=["TOTAL"] + FAIXAS,
                      c_birth=["TOTAL", "FOR", "NAT", "EU27_2020_FOR", "NEU27_2020_FOR"])
    # fluxo de 2024 por país de nascimento (todos) no total de idades; e por idade para os nascidos fora
    flu, rot = eurostat("migr_imm3ctb", ["geo", "c_birth"], geo=geos, time="2024", sex="T", age="TOTAL", agedef="COMPLET")
    # idade "alcançada no ano" (REACH): é a que a França publica, e a do md
    flu_idade, _ = eurostat("migr_imm3ctb", ["geo", "age"], geo=geos + [g for g in UE if g not in geos], time="2024",
                            sex="T", agedef="REACH", c_birth="FOR", age=FAIXAS)
    nomes_pais = rot.get("c_birth", {})

    anos_por_geo = {}
    for g in geos:
        ys = sorted({t for gg, t in pop_t if gg == g}
                    & {t for gg, t in imi_t if gg == g}
                    & {t for gg, t in emi_t if gg == g}, key=int)
        conferir(len(ys) >= 10 and ys[-1] == "2024", "%s série histórica insuficiente ou sem 2024" % g)
        conferir(len(ys) == int(ys[-1]) - int(ys[0]) + 1, "%s buraco inesperado na série histórica" % g)
        for y in ys:
            conferir(pop_t.get((g, y), 0) > 0 and imi_t.get((g, y), 0) > 0 and emi_t.get((g, y), 0) > 0,
                     "%s sem população ou fluxos em %s" % (g, y))
        conferir(abs(imi_t[(g, "2024")] - flu[(g, "TOTAL")]) <= 1,
                 "%s migr_imm8 2024 (%s) != migr_imm3ctb TOTAL (%s)" % (g, imi_t[(g, "2024")], flu[(g, "TOTAL")]))
        for y in ANOS_EXTRA:
            conferir(imm_prv.get((g, "TOTAL", y)) == imi_t[(g, y)],
                     "%s migr_imm5prv TOTAL %s != migr_imm8" % (g, y))
            conferir(emi_nxt.get((g, "TOTAL", y)) == emi_t[(g, y)],
                     "%s migr_emi3nxt TOTAL %s != migr_emi2" % (g, y))
            conferir(imm_prv.get((g, "NEU27_2020_FOR", y), 0) > 0 and emi_nxt.get((g, "NEU27_2020_FOR", y), 0) > 0,
                     "%s sem fluxo extra-UE em %s" % (g, y))
            soma_im = sum(imm_prv.get((g, p, y), 0) for p in ("EU27_2020_FOR", "NEU27_2020_FOR", "UNK"))
            soma_em = sum(emi_nxt.get((g, p, y), 0) for p in ("EU27_2020_FOR", "NEU27_2020_FOR", "UNK"))
            if g == "EU27_2020":
                conferir(soma_im <= imm_prv[(g, "TOTAL", y)] and soma_em <= emi_nxt[(g, "TOTAL", y)],
                         "%s parcelas extra/intra passam do TOTAL em %s" % (g, y))
            else:
                conferir(soma_im == imm_prv[(g, "TOTAL", y)] and soma_em == emi_nxt[(g, "TOTAL", y)],
                         "%s EU + fora UE + UNK != TOTAL em %s" % (g, y))
            conferir(abs(1000.0 * gind[(g, "NATGROW", y)] / gind[(g, "AVG", y)] - gind[(g, "NATGROWRT", y)]) <= 0.15,
                     "%s NATGROW/AVG diverge de NATGROWRT em %s" % (g, y))
        anos_por_geo[g] = ys
        conferir(est[(g, "EU27_2020_FOR", "T", "TOTAL")] + est[(g, "NEU27_2020_FOR", "T", "TOTAL")]
                 == est[(g, "FOR", "T", "TOTAL")], "%s estoque UE + fora UE != FOR" % g)
        for cb in ("TOTAL", "FOR", "NAT"):
            conferir(est[(g, cb, "M", "TOTAL")] + est[(g, cb, "F", "TOTAL")] == est[(g, cb, "T", "TOTAL")],
                     "%s %s M + F != T" % (g, cb))
            for sx in ("T", "M", "F"):
                conferir(sum(est[(g, cb, sx, f)] for f in FAIXAS) == est[(g, cb, sx, "TOTAL")],
                         "%s %s %s soma das faixas etárias != TOTAL" % (g, cb, sx))
        conferir(flu.get((g, "EU27_2020_FOR"), 0) + flu.get((g, "NEU27_2020_FOR"), 0) == flu[(g, "FOR")],
                 "%s fluxo UE + fora UE != FOR" % g)

    # 1. fluxos em % da população e em milhares de pessoas (2024 e série histórica; total e fora da UE-27)
    cats = [n for _, n in TERR]
    im = {g: 100 * imi_t[(g, "2024")] / pop_t[(g, "2024")] for g in geos}
    em = {g: 100 * emi_t[(g, "2024")] / pop_t[(g, "2024")] for g in geos}
    im_ext = {g: 100 * imm_prv[(g, "NEU27_2020_FOR", "2024")] / pop_t[(g, "2024")] for g in geos}
    em_ext = {g: 100 * emi_nxt[(g, "NEU27_2020_FOR", "2024")] / pop_t[(g, "2024")] for g in geos}
    im_q = {g: imi_t[(g, "2024")] / 1000.0 for g in geos}
    em_q = {g: emi_t[(g, "2024")] / 1000.0 for g in geos}
    im_ext_q = {g: imm_prv[(g, "NEU27_2020_FOR", "2024")] / 1000.0 for g in geos}
    em_ext_q = {g: emi_nxt[(g, "NEU27_2020_FOR", "2024")] / 1000.0 for g in geos}
    for g, n in TERR:
        ys = anos_por_geo[g]
        print("  %s (%s–%s): imigração %.2f%% (%.0f mil; fora UE %.2f%%, %.0f mil), "
              "emigração %.2f%% (%.0f mil; fora UE %.2f%%, %.0f mil), "
              "saldo %+.2f p.p. (fora UE %+.2f p.p.)"
              % (n, ys[0], ys[-1], im[g], im_q[g], im_ext[g], im_ext_q[g],
                 em[g], em_q[g], em_ext[g], em_ext_q[g], im[g] - em[g], im_ext[g] - em_ext[g]))
    g_fluxos = dict(id="migracao-fluxos", titulo="Imigração e emigração, 2024",
                    subtitulo="Entradas e saídas no ano (em % da população em 1º/jan/2024 ou milhares de pessoas); "
                              "saldo = imigração menos emigração",
                    unidade="%", categorias=cats, agrupadas=True, barra=0.8,
                    fonte="Eurostat (migr_imm8, migr_emi2 e demo_pjan) e FtM",
                    variantes=[
                        dict(rot="Total (% pop.)", unidade="%",
                             fonte="Eurostat (migr_imm8, migr_emi2 e demo_pjan) e FtM",
                             series=[dict(nome="Imigração", cor=AZUL, tipo="barra", valores=True,
                                          dados=[[str(i), round(im[g], 2)] for i, g in enumerate(geos)]),
                                     dict(nome="Emigração", cor=VERMELHO, tipo="barra", valores=True,
                                          dados=[[str(i), round(em[g], 2)] for i, g in enumerate(geos)]),
                                     dict(nome="Saldo", cor=VERDE, tipo="barra", valores=True,
                                          dados=[[str(i), round(im[g] - em[g], 2)] for i, g in enumerate(geos)])]),
                        dict(rot="Fora da UE-27 (% pop.)", unidade="%",
                             fonte="Eurostat (migr_imm5prv, migr_emi3nxt e demo_pjan) e FtM",
                             series=[dict(nome="Imigração", cor=AZUL, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_ext[g], 2)] for i, g in enumerate(geos)]),
                                     dict(nome="Emigração", cor=VERMELHO, tipo="barra", valores=True,
                                          dados=[[str(i), round(em_ext[g], 2)] for i, g in enumerate(geos)]),
                                     dict(nome="Saldo", cor=VERDE, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_ext[g] - em_ext[g], 2)] for i, g in enumerate(geos)])]),
                        dict(rot="Total (mil)", unidade="mil",
                             fonte="Eurostat (migr_imm8 e migr_emi2) e FtM",
                             series=[dict(nome="Imigração", cor=AZUL, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_q[g], 1)] for i, g in enumerate(geos)]),
                                     dict(nome="Emigração", cor=VERMELHO, tipo="barra", valores=True,
                                          dados=[[str(i), round(em_q[g], 1)] for i, g in enumerate(geos)]),
                                     dict(nome="Saldo", cor=VERDE, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_q[g] - em_q[g], 1)] for i, g in enumerate(geos)])]),
                        dict(rot="Fora da UE-27 (mil)", unidade="mil",
                             fonte="Eurostat (migr_imm5prv e migr_emi3nxt) e FtM",
                             series=[dict(nome="Imigração", cor=AZUL, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_ext_q[g], 1)] for i, g in enumerate(geos)]),
                                     dict(nome="Emigração", cor=VERMELHO, tipo="barra", valores=True,
                                          dados=[[str(i), round(em_ext_q[g], 1)] for i, g in enumerate(geos)]),
                                     dict(nome="Saldo", cor=VERDE, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_ext_q[g] - em_ext_q[g], 1)] for i, g in enumerate(geos)])]),
                    ])

    var_fluxos_tempo = []
    var_fluxos_tempo_qtd = []
    var_fluxos_fora = []
    var_fluxos_fora_qtd = []
    for g, n in TERR:
        ys = anos_por_geo[g]
        im_s = {y: 100 * imi_t[(g, y)] / pop_t[(g, y)] for y in ys}
        em_s = {y: 100 * emi_t[(g, y)] / pop_t[(g, y)] for y in ys}
        im_sq = {y: imi_t[(g, y)] / 1000.0 for y in ys}
        em_sq = {y: emi_t[(g, y)] / 1000.0 for y in ys}
        conferir(abs(im_s["2024"] - im[g]) < 1e-9 and abs(em_s["2024"] - em[g]) < 1e-9,
                 "%s 2024 histórico diverge do resumo" % g)
        var_fluxos_tempo.append(dict(rot=n, series=[
            dict(nome="Imigração", cor=AZUL, largura=4.5, rotulo=True,
                 dados=[["%s-01" % y, round(im_s[y], 2)] for y in ys]),
            dict(nome="Emigração", cor=VERMELHO, largura=4.5, rotulo=True,
                 dados=[["%s-01" % y, round(em_s[y], 2)] for y in ys]),
            dict(nome="Saldo", cor=VERDE, largura=5.5, rotulo=True,
                 dados=[["%s-01" % y, round(im_s[y] - em_s[y], 2)] for y in ys])]))
        var_fluxos_tempo_qtd.append(dict(rot=n, series=[
            dict(nome="Imigração", cor=AZUL, largura=4.5, rotulo=True,
                 dados=[["%s-01" % y, round(im_sq[y], 1)] for y in ys]),
            dict(nome="Emigração", cor=VERMELHO, largura=4.5, rotulo=True,
                 dados=[["%s-01" % y, round(em_sq[y], 1)] for y in ys]),
            dict(nome="Saldo", cor=VERDE, largura=5.5, rotulo=True,
                 dados=[["%s-01" % y, round(im_sq[y] - em_sq[y], 1)] for y in ys])]))

        im_es = {y: 100 * imm_prv[(g, "NEU27_2020_FOR", y)] / pop_t[(g, y)] for y in ANOS_EXTRA}
        em_es = {y: 100 * emi_nxt[(g, "NEU27_2020_FOR", y)] / pop_t[(g, y)] for y in ANOS_EXTRA}
        im_esq = {y: imm_prv[(g, "NEU27_2020_FOR", y)] / 1000.0 for y in ANOS_EXTRA}
        em_esq = {y: emi_nxt[(g, "NEU27_2020_FOR", y)] / 1000.0 for y in ANOS_EXTRA}
        conferir(abs(im_es["2024"] - im_ext[g]) < 1e-9 and abs(em_es["2024"] - em_ext[g]) < 1e-9,
                 "%s 2024 extra-UE histórico diverge do resumo" % g)
        var_fluxos_fora.append(dict(rot=n, series=[
            dict(nome="Imigração de fora da UE-27", cor=AZUL, largura=4.5, rotulo=True,
                 dados=[[str(i), round(im_es[y], 2)] for i, y in enumerate(ANOS_EXTRA)]),
            dict(nome="Emigração para fora da UE-27", cor=VERMELHO, largura=4.5, rotulo=True,
                 dados=[[str(i), round(em_es[y], 2)] for i, y in enumerate(ANOS_EXTRA)]),
            dict(nome="Saldo", cor=VERDE, largura=5.5, rotulo=True,
                 dados=[[str(i), round(im_es[y] - em_es[y], 2)] for i, y in enumerate(ANOS_EXTRA)])]))
        var_fluxos_fora_qtd.append(dict(rot=n, series=[
            dict(nome="Imigração de fora da UE-27", cor=AZUL, largura=4.5, rotulo=True,
                 dados=[[str(i), round(im_esq[y], 1)] for i, y in enumerate(ANOS_EXTRA)]),
            dict(nome="Emigração para fora da UE-27", cor=VERMELHO, largura=4.5, rotulo=True,
                 dados=[[str(i), round(em_esq[y], 1)] for i, y in enumerate(ANOS_EXTRA)]),
            dict(nome="Saldo", cor=VERDE, largura=5.5, rotulo=True,
                 dados=[[str(i), round(im_esq[y] - em_esq[y], 1)] for i, y in enumerate(ANOS_EXTRA)])]))
    g_fluxos_tempo = dict(id="migracao-fluxos-tempo",
                          titulo="Imigração e emigração em % da população ao longo do tempo",
                          subtitulo="Entradas e saídas anuais (inclui intra-UE), sobre a população em 1º de janeiro; "
                                    "saldo = imigração menos emigração, em pontos percentuais",
                          unidade="%", buracoMax=12,
                          fonte="Eurostat (migr_imm8, migr_emi2 e demo_pjan) e FtM",
                          variantes=var_fluxos_tempo)
    g_fluxos_tempo_qtd = dict(id="migracao-fluxos-tempo-qtd",
                              titulo="Imigração e emigração em milhares de pessoas ao longo do tempo",
                              subtitulo="Entradas e saídas anuais (inclui intra-UE); saldo = imigração menos emigração",
                              unidade="mil", buracoMax=12,
                              fonte="Eurostat (migr_imm8 e migr_emi2) e FtM",
                              variantes=var_fluxos_tempo_qtd)
    g_fluxos_fora = dict(id="migracao-fluxos-fora-ue-tempo",
                         titulo="Imigração e emigração de fora da UE-27 em % da população, 2020–2024",
                         subtitulo="Entradas vindas de fora da UE-27 e saídas para fora da UE-27 no ano, sobre a "
                                   "população em 1º de janeiro; saldo = entradas menos saídas, em pontos percentuais",
                         unidade="%", categorias=ANOS_EXTRA,
                         fonte="Eurostat (migr_imm5prv, migr_emi3nxt e demo_pjan) e FtM",
                         variantes=var_fluxos_fora)
    g_fluxos_fora_qtd = dict(id="migracao-fluxos-fora-ue-tempo-qtd",
                             titulo="Imigração e emigração de fora da UE-27 em milhares de pessoas, 2020–2024",
                             subtitulo="Entradas vindas de fora da UE-27 e saídas para fora da UE-27 no ano; "
                                       "saldo = entradas menos saídas",
                             unidade="mil", categorias=ANOS_EXTRA,
                             fonte="Eurostat (migr_imm5prv e migr_emi3nxt) e FtM",
                             variantes=var_fluxos_fora_qtd)

    # 2. estoque de nascidos no exterior (em % da população e em milhares de pessoas, 2025)
    pct = {b: {g: 100 * est[(g, b, "T", "TOTAL")] / est[(g, "TOTAL", "T", "TOTAL")] for g in geos}
           for b in ("FOR", "EU27_2020_FOR", "NEU27_2020_FOR")}
    est_q = {b: {g: est[(g, b, "T", "TOTAL")] / 1000.0 for g in geos}
             for b in ("FOR", "EU27_2020_FOR", "NEU27_2020_FOR")}
    tot = "; ".join("%s %s%% (%s mi)" % (n, br(pct["FOR"][g]), br(est_q["FOR"][g] / 1000.0)) for g, n in TERR)
    g_estoque = dict(id="migracao-estoque", titulo="Nascidos no exterior, 1º de janeiro de 2025",
                     subtitulo="Residentes nascidos em outro país, por bloco de nascimento; total: %s" % tot,
                     unidade="%", categorias=cats, barra=0.6,
                     fonte="Eurostat (migr_pop3ctb) e FtM",
                     variantes=[
                         dict(rot="% da população", unidade="%",
                              series=[dict(nome="Nascidos em outro país da UE", cor=AZUL_CLARO, tipo="barra",
                                           dados=[[str(i), round(pct["EU27_2020_FOR"][g], 2)] for i, g in enumerate(geos)]),
                                      dict(nome="Nascidos fora da UE", cor=AZUL, tipo="barra",
                                           dados=[[str(i), round(pct["NEU27_2020_FOR"][g], 2)] for i, g in enumerate(geos)])]),
                         dict(rot="Milhares de pessoas", unidade="mil",
                              series=[dict(nome="Nascidos em outro país da UE", cor=AZUL_CLARO, tipo="barra",
                                           dados=[[str(i), round(est_q["EU27_2020_FOR"][g], 1)] for i, g in enumerate(geos)]),
                                      dict(nome="Nascidos fora da UE", cor=AZUL, tipo="barra",
                                           dados=[[str(i), round(est_q["NEU27_2020_FOR"][g], 1)] for i, g in enumerate(geos)])]),
                     ])

    # 2b. Europa x América do Norte, 1990–2024 (UN DESA 2024 via Our World in Data)
    anos_owid = ["1990", "1995", "2000", "2005", "2010", "2015", "2020", "2024"]
    owid_pct = owid("migrant-stock-share", "immigrant_share_of_dest_population_all")
    owid_tot = owid("migrant-stock-total", "immigrants_all")
    for ent in ("Europe", "North America", "European Union (27)"):
        for y in anos_owid:
            conferir((ent, y) in owid_pct and (ent, y) in owid_tot, "OWID sem dado para %s em %s" % (ent, y))
            conferir(0.0 < owid_pct[(ent, y)] < 50.0 and owid_tot[(ent, y)] > 0,
                     "OWID valor inválido para %s em %s" % (ent, y))
    for y in anos_owid:
        conferir(owid_tot[("Europe", y)] > owid_tot[("European Union (27)", y)],
                 "OWID Europe <= EU27 em %s" % y)
    conferir(abs(owid_tot[("Europe", "2024")] / (owid_pct[("Europe", "2024")] / 100.0) - 744.6e6) < 20e6,
             "OWID população implícita da Europa em 2024 fora da faixa esperada")
    print("  OWID 2024: Europa %.2f%% (%.0f mil); América do Norte %.2f%% (%.0f mil)"
          % (owid_pct[("Europe", "2024")], owid_tot[("Europe", "2024")] / 1000.0,
             owid_pct[("North America", "2024")], owid_tot[("North America", "2024")] / 1000.0))
    g_europa_an = dict(id="migracao-europa-america-norte",
                       titulo="População nascida no exterior: Europa e América do Norte, 1990–2024",
                       subtitulo="Imigrantes residentes nascidos em outro país (definição continental do Our World "
                                 "in Data: América do Norte inclui América Central e Caribe)",
                       unidade="%", categorias=anos_owid,
                       fonte="UN DESA (International Migrant Stock 2024, via Our World in Data)",
                       variantes=[
                           dict(rot="% da população", unidade="%",
                                series=[dict(nome="Europa", cor=AZUL, largura=5, rotulo=True,
                                             dados=[[str(i), round(owid_pct[("Europe", y)], 2)]
                                                    for i, y in enumerate(anos_owid)]),
                                        dict(nome="América do Norte", cor=VERMELHO, largura=5, rotulo=True,
                                             dados=[[str(i), round(owid_pct[("North America", y)], 2)]
                                                    for i, y in enumerate(anos_owid)])]),
                           dict(rot="Milhares de pessoas", unidade="mil",
                                series=[dict(nome="Europa", cor=AZUL, largura=5, rotulo=True,
                                             dados=[[str(i), round(owid_tot[("Europe", y)] / 1000.0, 1)]
                                                    for i, y in enumerate(anos_owid)]),
                                        dict(nome="América do Norte", cor=VERMELHO, largura=5, rotulo=True,
                                             dados=[[str(i), round(owid_tot[("North America", y)] / 1000.0, 1)]
                                                    for i, y in enumerate(anos_owid)])]),
                       ])

    # 3. de onde vêm os novos imigrantes nascidos no exterior (2024: % e milhares)
    variantes, variantes_qtd, fora, fora_qtd = [], [], {}, {}
    for g, n in TERR:
        total = flu[(g, "FOR")]
        n_fora = flu.get((g, "NEU27_2020_FOR"), 0)
        fora[n] = 100 * n_fora / total
        fora_qtd[n] = n_fora / 1000.0
        if g == "EU27_2020":    # a UE-27 não abre país nenhum: só UE contra fora da UE
            variantes.append(dict(rot=n + " (só UE x fora da UE)", itens=[
                ["Nascidos fora da UE", round(fora[n], 1), AZUL],
                ["Nascidos em outro país da UE", round(100 - fora[n], 1), AZUL_CLARO]]))
            variantes_qtd.append(dict(rot=n + " (só UE x fora da UE)", itens=[
                ["Nascidos fora da UE", round(n_fora / 1000.0, 1), AZUL],
                ["Nascidos em outro país da UE", round((total - n_fora) / 1000.0, 1), AZUL_CLARO]]))
            continue
        # só países (código de duas letras); os agregados regionais têm código maior
        paises = {c: v for (gg, c), v in flu.items()
                  if gg == g and len(c) == 2 and c not in AGREGADOS and c != g and v}
        if g == "FR":       # a França não abre os países de fora da UE
            paises = {c: v for c, v in paises.items() if c in UE}
        top = sorted(paises.items(), key=lambda kv: -kv[1])[:5]
        itens = [[NOMES.get(c, nomes_pais.get(c, c)), round(100 * v / total, 1), AZUL if c not in UE else AZUL_CLARO]
                 for c, v in top]
        itens_qtd = [[NOMES.get(c, nomes_pais.get(c, c)), round(v / 1000.0, 1), AZUL if c not in UE else AZUL_CLARO]
                     for c, v in top]
        rot_v = n + (" (só países da UE)" if g == "FR" else "")
        variantes.append(dict(rot=rot_v, itens=itens))
        variantes_qtd.append(dict(rot=rot_v, itens=itens_qtd))
        print("  %s: %s" % (n, ", ".join("%s %.1f%%" % (a, b) for a, b, _ in itens)))
    g_origens = dict(id="migracao-origens", tipo="ranking", unidade="%",
                     titulo="Os cinco principais países de nascimento dos novos imigrantes, 2024",
                     subtitulo="%% dos imigrantes nascidos no exterior que chegaram no ano; azul claro = país da UE; "
                               "nascidos fora da UE: %s" % "; ".join("%s %s%%" % (n, br(v)) for n, v in fora.items()),
                     fonte="Eurostat (migr_imm3ctb) e FtM", itens=variantes[0]["itens"], variantes=variantes)
    g_origens_qtd = dict(id="migracao-origens-qtd", tipo="ranking", unidade="mil",
                         titulo="Os cinco principais países de nascimento dos novos imigrantes, 2024 (em milhares)",
                         subtitulo="Milhares de imigrantes nascidos no exterior que chegaram no ano; azul claro = país "
                                   "da UE; nascidos fora da UE: %s"
                                   % "; ".join("%s %s mil" % (n, br(v, 0)) for n, v in fora_qtd.items()),
                         fonte="Eurostat (migr_imm3ctb) e FtM", itens=variantes_qtd[0]["itens"],
                         variantes=variantes_qtd)

    # 4. idade: residentes e estoque de 2025, novos imigrantes de 2024 (distribuição % e milhares)
    def dist(contagem):
        s = sum(contagem)
        return [100 * x / s for x in contagem]

    def media(d):
        return sum(m * p for m, p in zip(MEIOS, d)) / 100
    var_idade, var_idade_qtd, medias = [], [], {}
    for g, n in TERR:
        resid_n = [est[(g, "TOTAL", "T", f)] for f in FAIXAS]
        estoq_n = [est[(g, "FOR", "T", f)] for f in FAIXAS]
        resid = dist(resid_n)
        estoq = dist(estoq_n)
        if all((g, f) in flu_idade for f in FAIXAS):
            novos_n, base = [flu_idade[(g, f)] for f in FAIXAS], None
        else:              # a UE-27 não publica: soma dos países que publicam todas as faixas
            com = [p for p in UE if all((p, f) in flu_idade for f in FAIXAS)]
            conferir(len(com) >= 20, "UE-27 com poucos países publicando idade: %d" % len(com))
            novos_n = [sum(flu_idade[(p, f)] for p in com) for f in FAIXAS]
            base = com
        novos = dist(novos_n)
        for nome_dist, d in (("resid", resid), ("estoq", estoq), ("novos", novos)):
            conferir(abs(sum(d) - 100.0) < 1e-6, "%s %s não soma 100%% (%.6f)" % (g, nome_dist, sum(d)))
        medias[g] = (media(resid), media(estoq), media(novos))
        print("  %s: idade média residentes %.1f, estoque %.1f, novos %.1f%s"
              % (n, medias[g][0], medias[g][1], medias[g][2], "" if base is None else
                 " (novos: %d países)" % len(base)))
        var_idade.append(dict(rot=n, series=[
            dict(nome="População residente, 2025", cor=AZUL_CLARO, tipo="barra",
                 dados=[[str(i), round(v, 2)] for i, v in enumerate(resid)]),
            dict(nome="Nascidos no exterior, estoque de 2025", cor=LARANJA, largura=6, traco="pontilhado",
                 dados=[[str(i), round(v, 2)] for i, v in enumerate(estoq)]),
            dict(nome="Novos imigrantes nascidos no exterior, 2024", cor=BRANCO, largura=5,
                 dados=[[str(i), round(v, 2)] for i, v in enumerate(novos)])]))
        var_idade_qtd.append(dict(rot=n, series=[
            dict(nome="População residente, 2025", cor=AZUL_CLARO, tipo="barra",
                 dados=[[str(i), round(v / 1000.0, 1)] for i, v in enumerate(resid_n)]),
            dict(nome="Nascidos no exterior, estoque de 2025", cor=LARANJA, largura=6, traco="pontilhado",
                 dados=[[str(i), round(v / 1000.0, 1)] for i, v in enumerate(estoq_n)]),
            dict(nome="Novos imigrantes nascidos no exterior, 2024", cor=BRANCO, largura=5,
                 dados=[[str(i), round(v / 1000.0, 1)] for i, v in enumerate(novos_n)])]))
    g_idade = dict(id="migracao-idade", titulo="Distribuição por idade: residentes, imigrantes e novos imigrantes",
                   subtitulo="% de cada grupo em cada faixa de 5 anos; a UE-27 dos novos imigrantes soma os países "
                             "que publicam a idade",
                   unidade="%", categorias=ROT_FAIXAS, barra=0.8, eixo=dict(min=0, max=20),
                   fonte="Eurostat (migr_pop3ctb e migr_imm3ctb) e FtM", variantes=var_idade)
    g_idade_qtd = dict(id="migracao-idade-qtd",
                       titulo="População por idade: residentes, imigrantes e novos imigrantes (em milhares)",
                       subtitulo="Milhares de pessoas em cada faixa de 5 anos; a UE-27 dos novos imigrantes soma os "
                                 "países que publicam a idade",
                       unidade="mil", categorias=ROT_FAIXAS, barra=0.8,
                       fonte="Eurostat (migr_pop3ctb e migr_imm3ctb) e FtM", variantes=var_idade_qtd)
    g_media = dict(id="migracao-idade-media", titulo="Idade média: residentes, imigrantes e novos imigrantes",
                   subtitulo="Anos, pelo ponto médio das faixas de 5 anos; residentes e estoque em 1º/jan/2025, "
                             "novos imigrantes em 2024",
                   unidade="anos", categorias=cats, agrupadas=True, barra=0.8,
                   fonte="Eurostat (migr_pop3ctb e migr_imm3ctb) e FtM",
                   series=[dict(nome="População residente", cor=AZUL_CLARO, tipo="barra", valores=True,
                                dados=[[str(i), round(medias[g][0], 1)] for i, g in enumerate(geos)]),
                           dict(nome="Nascidos no exterior (estoque)", cor=LARANJA, tipo="barra", valores=True,
                                dados=[[str(i), round(medias[g][1], 1)] for i, g in enumerate(geos)]),
                           dict(nome="Novos imigrantes", cor=BRANCO, tipo="barra", valores=True,
                                dados=[[str(i), round(medias[g][2], 1)] for i, g in enumerate(geos)])])

    # 4b. pirâmides etárias (nascidos no exterior x nativos, 1º/jan/2025, % e milhares)
    def faixas16(g, cb, sx):
        return [est[(g, cb, sx, f)] for f in FAIXAS[:15]] + [sum(est[(g, cb, sx, f)] for f in FAIXAS[15:])]

    var_pir, var_pir_qtd = [], []
    for g, n in TERR_PIR:
        for_m, for_f = faixas16(g, "FOR", "M"), faixas16(g, "FOR", "F")
        nat_m, nat_f = faixas16(g, "NAT", "M"), faixas16(g, "NAT", "F")
        for_tot = est[(g, "FOR", "T", "TOTAL")]
        nat_tot = est[(g, "NAT", "T", "TOTAL")]
        conferir(sum(for_m) + sum(for_f) == for_tot, "%s pirâmide FOR != TOTAL" % g)
        conferir(sum(nat_m) + sum(nat_f) == nat_tot, "%s pirâmide NAT != TOTAL" % g)
        pct_hm = round(100.0 * est[(g, "FOR", "M", "TOTAL")] / for_tot)
        pct_ml = 100 - pct_hm
        var_pir.append(dict(
            rot=n,
            esqRot="Homens (%d%%)" % pct_hm, dirRot="Mulheres (%d%%)" % pct_ml,
            linhaRot="Residentes nativos", esqCor=AZUL, dirCor=VERMELHO, linhaCor=BRANCO,
            series=[
                dict(nome="Homens (nascidos no exterior)", cor=AZUL,
                     dados=[[str(i), round(100.0 * v / for_tot, 2)] for i, v in enumerate(for_m)]),
                dict(nome="Mulheres (nascidos no exterior)", cor=VERMELHO,
                     dados=[[str(i), round(100.0 * v / for_tot, 2)] for i, v in enumerate(for_f)]),
                dict(nome="Homens (nativos)", cor=BRANCO,
                     dados=[[str(i), round(100.0 * v / nat_tot, 2)] for i, v in enumerate(nat_m)]),
                dict(nome="Mulheres (nativos)", cor=BRANCO,
                     dados=[[str(i), round(100.0 * v / nat_tot, 2)] for i, v in enumerate(nat_f)]),
            ],
        ))
        var_pir_qtd.append(dict(
            rot=n,
            esqRot="Homens (%s mil)" % br(est[(g, "FOR", "M", "TOTAL")] / 1000.0, 0),
            dirRot="Mulheres (%s mil)" % br(est[(g, "FOR", "F", "TOTAL")] / 1000.0, 0),
            esqCor=AZUL, dirCor=VERMELHO,
            series=[
                dict(nome="Homens (nascidos no exterior)", cor=AZUL,
                     dados=[[str(i), round(v / 1000.0, 1)] for i, v in enumerate(for_m)]),
                dict(nome="Mulheres (nascidos no exterior)", cor=VERMELHO,
                     dados=[[str(i), round(v / 1000.0, 1)] for i, v in enumerate(for_f)]),
            ],
        ))
    g_piramide = dict(
        id="migracao-piramide", tipo="piramide", unidade="%", categorias=ROT_PIR,
        titulo="Pirâmide etária dos imigrantes e nativos, 1º de janeiro de 2025",
        subtitulo="% da população de cada grupo por sexo e faixa etária; barras = nascidos no exterior; linha = nativos",
        fonte="Eurostat (migr_pop3ctb) e FtM", variantes=var_pir,
    )
    g_piramide_qtd = dict(
        id="migracao-piramide-qtd", tipo="piramide", unidade="mil", categorias=ROT_PIR,
        titulo="Pirâmide etária dos imigrantes em milhares de pessoas, 1º de janeiro de 2025",
        subtitulo="Milhares de residentes nascidos no exterior por sexo e faixa etária",
        fonte="Eurostat (migr_pop3ctb) e FtM", variantes=var_pir_qtd,
    )

    # 5. crescimento populacional com e sem migração (histórico 1950–2023 e extra-UE 2020–2024)
    c_com = "growth_rate__sex_all__age_all__variant_estimates"
    c_sem = "natural_change_rate__sex_all__age_all__variant_estimates"
    owid_cresc = owid_cols("population-growth-rate-with-and-without-migration", [c_com, c_sem])
    anos_wpp = [str(y) for y in range(1950, 2024)]
    var_cresc_hist = []
    for _, ent, n in TERR_OWID:
        for y in anos_wpp:
            d = owid_cresc.get((ent, y), {})
            conferir(c_com in d and c_sem in d, "OWID WPP sem dado para %s em %s" % (ent, y))
            conferir(-5.0 < d[c_com] < 5.0 and -5.0 < d[c_sem] < 5.0,
                     "OWID WPP valor fora da faixa em %s %s" % (ent, y))
        var_cresc_hist.append(dict(rot=n, series=[
            dict(nome="Com migração", cor=AZUL, largura=4.5, rotulo=True,
                 dados=[["%s-01" % y, round(owid_cresc[(ent, y)][c_com], 2)] for y in anos_wpp]),
            dict(nome="Sem migração", cor=VERMELHO, largura=4.5, rotulo=True,
                 dados=[["%s-01" % y, round(owid_cresc[(ent, y)][c_sem], 2)] for y in anos_wpp]),
        ]))
    g_cresc_hist = dict(
        id="migracao-crescimento-historico",
        titulo="Crescimento da população com e sem migração, 1950–2023",
        subtitulo="Variação anual da população total (%) contra crescimento natural (nascimentos menos óbitos)",
        unidade="%", buracoMax=12,
        fonte="ONU (World Population Prospects 2024, via Our World in Data)",
        variantes=var_cresc_hist,
    )

    var_cresc_ext, var_cresc_ext_q = [], []
    for g, n in TERR:
        s_com, s_sem_neu, s_sem = [], [], []
        q_com, q_sem_neu, q_sem = [], [], []
        for i, y in enumerate(ANOS_EXTRA):
            avg = gind[(g, "AVG", y)]
            nat = gind[(g, "NATGROW", y)]
            net_tot = imm_prv[(g, "TOTAL", y)] - emi_nxt[(g, "TOTAL", y)]
            net_eu = imm_prv[(g, "EU27_2020_FOR", y)] - emi_nxt[(g, "EU27_2020_FOR", y)]
            c1, c2, c3 = nat + net_tot, nat + net_eu, nat
            s_com.append([str(i), round(100.0 * c1 / avg, 2)])
            s_sem_neu.append([str(i), round(100.0 * c2 / avg, 2)])
            s_sem.append([str(i), round(100.0 * c3 / avg, 2)])
            q_com.append([str(i), round(c1 / 1000.0, 1)])
            q_sem_neu.append([str(i), round(c2 / 1000.0, 1)])
            q_sem.append([str(i), round(c3 / 1000.0, 1)])
        print("  %s crescimento 2024: com migração %+.2f%% (%+.0f mil), sem fora UE-27 %+.2f%% (%+.0f mil), "
              "sem migração %+.2f%% (%+.0f mil)"
              % (n, s_com[-1][1], q_com[-1][1], s_sem_neu[-1][1], q_sem_neu[-1][1], s_sem[-1][1], q_sem[-1][1]))
        var_cresc_ext.append(dict(rot=n, series=[
            dict(nome="Com migração", cor=AZUL, largura=4.5, rotulo=True, dados=s_com),
            dict(nome="Sem migração de fora da UE-27", cor=VERDE, largura=5.0, rotulo=True, dados=s_sem_neu),
            dict(nome="Sem migração (só crescimento natural)", cor=VERMELHO, largura=4.5, rotulo=True, dados=s_sem),
        ]))
        var_cresc_ext_q.append(dict(rot=n, series=[
            dict(nome="Com migração", cor=AZUL, largura=4.5, rotulo=True, dados=q_com),
            dict(nome="Sem migração de fora da UE-27", cor=VERDE, largura=5.0, rotulo=True, dados=q_sem_neu),
            dict(nome="Sem migração (só crescimento natural)", cor=VERMELHO, largura=4.5, rotulo=True, dados=q_sem),
        ]))
    g_cresc_extra = dict(
        id="migracao-crescimento-extra-ue",
        titulo="Crescimento da população com e sem migração de fora da UE-27, 2020–2024",
        subtitulo="Variação anual em % da população média: saldo natural mais saldo migratório registrado "
                  "(total, só intra-UE ou zero)",
        unidade="%", categorias=ANOS_EXTRA,
        fonte="Eurostat (demo_gind, migr_imm5prv e migr_emi3nxt) e FtM",
        variantes=var_cresc_ext,
    )
    g_cresc_extra_qtd = dict(
        id="migracao-crescimento-extra-ue-qtd",
        titulo="Variação da população com e sem migração de fora da UE-27, 2020–2024 (em milhares)",
        subtitulo="Milhares de pessoas no ano: saldo natural mais saldo migratório registrado "
                  "(total, só intra-UE ou zero)",
        unidade="mil", categorias=ANOS_EXTRA,
        fonte="Eurostat (demo_gind, migr_imm5prv e migr_emi3nxt) e FtM",
        variantes=var_cresc_ext_q,
    )

    # 6. Horas trabalhadas (Europa vs outros desenvolvidos, 1950–2023)
    horas = carregar_horas()
    paises_h = [
        ("South Korea", "Coreia do Sul", False),
        ("United States", "Estados Unidos", False),
        ("Canada", "Canadá", False),
        ("Italy", "Itália", True),
        ("Japan", "Japão", False),
        ("Spain", "Espanha", True),
        ("United Kingdom", "Reino Unido", True),
        ("France", "França", True),
        ("Germany", "Alemanha", True),
    ]
    for ent, _, _ in paises_h:
        pts = horas.get(ent, [])
        ini = "1953" if ent == "South Korea" else "1950"
        conferir(pts and pts[0][0] == ini and pts[-1][0] == "2023",
                 "horas %s intervalo inesperado (%s..%s)" % (ent, pts[0][0] if pts else None, pts[-1][0] if pts else None))
        conferir(len(pts) == int(pts[-1][0]) - int(pts[0][0]) + 1, "buraco em horas para %s" % ent)
        for _, v in pts:
            conferir(1000.0 < v < 3500.0, "valor suspeito em horas %s: %.1f" % (ent, v))
    h_2023 = {ent: horas[ent][-1][1] for ent, _, _ in paises_h}
    print("  Horas 2023:", ", ".join("%s %.0f h" % (pt, h_2023[ent]) for ent, pt, _ in paises_h))

    def s_horas(ent, nome, cor, largura=4.5):
        return dict(nome=nome, cor=cor, largura=largura, rotulo=True,
                    dados=[["%s-01" % y, round(v, 0)] for y, v in horas[ent]])

    rank_h = sorted(paises_h, key=lambda item: -h_2023[item[0]])
    itens_h = [[pt, round(h_2023[ent], 0), AZUL if eur else VERMELHO] for ent, pt, eur in rank_h]
    g_horas = dict(
        id="migracao-horas-trabalhadas",
        titulo="Horas trabalhadas por trabalhador ao ano: Europa vs outros desenvolvidos",
        subtitulo="Média anual por pessoa ocupada (1950–2023); no ranking, azul = europeus e vermelho = demais desenvolvidos",
        unidade="h0", buracoMax=12,
        fonte="Penn World Table (2025) e Huberman e Minns (2005) via Our World in Data",
        variantes=[
            dict(rot="Principais desenvolvidos (1950–2023)", eixo=dict(zero=False),
                 series=[
                     s_horas("United States", "Estados Unidos", BRANCO, 5.0),
                     s_horas("South Korea", "Coreia do Sul", AMARELO),
                     s_horas("Canada", "Canadá", AZUL_CLARO),
                     s_horas("Japan", "Japão", VERDE),
                     s_horas("United Kingdom", "Reino Unido", AZUL),
                     s_horas("France", "França", VERMELHO),
                 ]),
            dict(rot="Europeus x EUA (1950–2023)", eixo=dict(zero=False),
                 series=[
                     s_horas("United States", "Estados Unidos", BRANCO, 5.0),
                     s_horas("Italy", "Itália", AMARELO),
                     s_horas("Spain", "Espanha", VERDE),
                     s_horas("United Kingdom", "Reino Unido", AZUL_CLARO),
                     s_horas("France", "França", VERMELHO),
                     s_horas("Germany", "Alemanha", AZUL),
                 ]),
            dict(rot="Ranking 2023 (todos)", tipo="ranking", itens=itens_h),
        ],
    )

    # 7. FBCF / PIB (Europa vs outros desenvolvidos, 1970–2025)
    fbcf = carregar_wb_fbcf()
    eur_24, _ = eurostat("nama_10_gdp", ["geo"], geo=geos, na_item="P51G", unit="PC_GDP", time="2024")
    for wb_c, eu_c in [("EUU", "EU27_2020"), ("DEU", "DE"), ("FRA", "FR"), ("ITA", "IT"), ("ESP", "ES")]:
        wb_24 = dict(fbcf[wb_c])["2024"]
        conferir(abs(wb_24 - eur_24[eu_c]) <= 0.25,
                 "FBCF/PIB 2024 %s WB (%.2f) != Eurostat (%.2f)" % (wb_c, wb_24, eur_24[eu_c]))
    paises_f = [
        ("KOR", "Coreia do Sul", False),
        ("JPN", "Japão", False),
        ("CAN", "Canadá", False),
        ("FRA", "França", True),
        ("ITA", "Itália", True),
        ("USA", "Estados Unidos", False),
        ("EUU", "UE-27", True),
        ("ESP", "Espanha", True),
        ("DEU", "Alemanha", True),
        ("GBR", "Reino Unido", True),
    ]
    for cc, _, _ in paises_f:
        pts = fbcf[cc]
        conferir(pts[0][0] == "1970" and pts[-1][0] in ("2024", "2025"),
                 "FBCF %s período inesperado (%s..%s)" % (cc, pts[0][0], pts[-1][0]))
        conferir(len(pts) == int(pts[-1][0]) - int(pts[0][0]) + 1, "buraco em FBCF para %s" % cc)
    f_ult = {cc: (fbcf[cc][-1][0], fbcf[cc][-1][1]) for cc, _, _ in paises_f}
    print("  FBCF/PIB último ano:", ", ".join("%s (%s) %.1f%%" % (pt, f_ult[cc][0], f_ult[cc][1]) for cc, pt, _ in paises_f))

    def s_fbcf(cc, nome, cor, largura=4.5):
        return dict(nome=nome, cor=cor, largura=largura, rotulo=True,
                    dados=[["%s-01" % y, round(v, 2)] for y, v in fbcf[cc]])

    rank_f = sorted(paises_f, key=lambda item: -f_ult[item[0]][1])
    itens_f = [[pt + (" (2024)" if f_ult[cc][0] == "2024" else ""), round(f_ult[cc][1], 1), AZUL if eur else VERMELHO]
               for cc, pt, eur in rank_f]
    g_fbcf = dict(
        id="migracao-fbcf-pib",
        titulo="Formação Bruta de Capital Fixo (FBCF) em % do PIB: Europa vs outros desenvolvidos",
        subtitulo="Investimento fixo em % do PIB (1970–2025; EUA e Japão até 2024); no ranking, azul = europeus",
        unidade="%", buracoMax=12,
        fonte="Banco Mundial (WDI, NE.GDI.FTOT.ZS; conferido contra Eurostat nama_10_gdp)",
        variantes=[
            dict(rot="Principais desenvolvidos (1970–2025)", eixo=dict(zero=False),
                 series=[
                     s_fbcf("EUU", "UE-27", BRANCO, 5.0),
                     s_fbcf("KOR", "Coreia do Sul", AMARELO),
                     s_fbcf("JPN", "Japão", VERDE),
                     s_fbcf("CAN", "Canadá", AZUL_CLARO),
                     s_fbcf("USA", "Estados Unidos", VERMELHO),
                     s_fbcf("DEU", "Alemanha", AZUL),
                 ]),
            dict(rot="Europeus x EUA (1970–2025)", eixo=dict(zero=False),
                 series=[
                     s_fbcf("USA", "Estados Unidos", BRANCO, 5.0),
                     s_fbcf("FRA", "França", VERDE),
                     s_fbcf("ITA", "Itália", AMARELO),
                     s_fbcf("ESP", "Espanha", AZUL_CLARO),
                     s_fbcf("DEU", "Alemanha", AZUL),
                     s_fbcf("GBR", "Reino Unido", VERMELHO),
                 ]),
            dict(rot="Ranking último ano (2024–2025)", tipo="ranking", unidade="pct1", itens=itens_f),
        ],
    )

    part_ppp, rel_ppp, rel_usd = carregar_wb_pib_ppp()
    print("  PIB mundial PPP (2025): UE-15 %.2f%%, UE-27 %.2f%%, EUA %.2f%%, China %.2f%%, Nórdicos %.2f%% (SWE %.2f%%, NOR %.2f%%, DNK %.2f%%, FIN %.2f%%)"
          % (part_ppp["UE15"][-1][1], part_ppp["UE27"][-1][1], part_ppp["USA"][-1][1], part_ppp["CHN"][-1][1],
             part_ppp["NORD"][-1][1], part_ppp["SWE"][-1][1], part_ppp["NOR"][-1][1], part_ppp["DNK"][-1][1], part_ppp["FIN"][-1][1]))
    print("  PIB/hab EUA=100 (2025, PPC | US$): GBR %.1f|%.1f, FRA %.1f|%.1f, ITA %.1f|%.1f, KOR %.1f|%.1f, CHN %.1f|%.1f"
          % (rel_ppp["GBR"][-1][1], rel_usd["GBR"][-1][1],
             rel_ppp["FRA"][-1][1], rel_usd["FRA"][-1][1],
             rel_ppp["ITA"][-1][1], rel_usd["ITA"][-1][1],
             rel_ppp["KOR"][-1][1], rel_usd["KOR"][-1][1],
             rel_ppp["CHN"][-1][1], rel_usd["CHN"][-1][1]))
    print("  PIB/hab Nórdicos vs Continental (2025, PPC | US$): NOR %.1f|%.1f, DNK %.1f|%.1f, SWE %.1f|%.1f, FIN %.1f|%.1f, CONT %.1f|%.1f"
          % (rel_ppp["NOR"][-1][1], rel_usd["NOR"][-1][1],
             rel_ppp["DNK"][-1][1], rel_usd["DNK"][-1][1],
             rel_ppp["SWE"][-1][1], rel_usd["SWE"][-1][1],
             rel_ppp["FIN"][-1][1], rel_usd["FIN"][-1][1],
             rel_ppp["CONT"][-1][1], rel_usd["CONT"][-1][1]))

    def _s_wb(pts, nome, cor, largura=4.5, tracejada=False):
        s = dict(nome=nome, cor=cor, largura=largura, rotulo=True,
                 dados=[["%s-01" % y, round(v, 2)] for y, v in pts])
        if tracejada:
            s["tracejada"] = True
        return s

    def _s_eua100(pts_ref):
        return dict(nome="EUA (base 100)", cor=BRANCO, largura=2.5, tracejada=True, rotulo=True,
                    dados=[["%s-01" % y, 100.0] for y, _ in pts_ref])

    grupos_rel = {
        "principais": [
            ("GBR", "Reino Unido", VERMELHO, 4.5),
            ("FRA", "França", AZUL, 4.5),
            ("KOR", "Coreia do Sul", AMARELO, 4.0),
            ("ITA", "Itália", AZUL_CLARO, 4.5),
            ("CHN", "China", VERDE, 3.5),
        ],
        "nordicos": [
            ("NOR", "Noruega", AZUL_CLARO, 4.0),
            ("DNK", "Dinamarca", AMARELO, 4.0),
            ("SWE", "Suécia", AZUL, 4.5),
            ("CONT", "Europa Ocidental Continental", VERMELHO, 5.0),
            ("FIN", "Finlândia", VERDE, 3.5),
        ],
    }

    def _var_rel_eua(rot, mapa, grupo="principais", min_ano=None):
        def _flt(cc):
            return [(y, v) for y, v in mapa[cc] if min_ano is None or int(y) >= min_ano]
        specs = grupos_rel[grupo]
        ref = _flt(specs[0][0])
        return dict(
            rot=rot, eixo=dict(zero=False),
            series=[_s_eua100(ref)] + [_s_wb(_flt(cc), nome, cor, larg) for cc, nome, cor, larg in specs],
        )

    g_pib_mundial_ppp = dict(
        id="migracao-pib-mundial-ppp",
        titulo="Participação no PIB mundial em PPC (PPP): UE-15, UE-27, Nórdicos e EUA, 1990 a 2025",
        subtitulo="Fatia do PIB mundial em paridade de poder de compra corrente (%); Nórdicos = Suécia, Dinamarca, Noruega e Finlândia",
        unidade="pct1", buracoMax=15,
        fonte="Banco Mundial (WDI, NY.GDP.MKTP.PP.CD) e FtM",
        eventos=[dict(em="2008-01", rot="Crise 2008"), dict(em="2020-01", rot="Covid-19")],
        variantes=[
            dict(rot="UE-15, UE-27 e EUA (1990 a 2025)", eixo=dict(zero=False),
                 series=[
                     _s_wb(part_ppp["UE15"], "UE-15 (15 primeiros membros)", AZUL, 5.0),
                     _s_wb(part_ppp["USA"], "Estados Unidos", VERMELHO),
                     _s_wb(part_ppp["UE27"], "UE-27 (bloco atual)", BRANCO, 3.5),
                 ]),
            dict(rot="Com China, Reino Unido e Nórdicos (1990 a 2025)", eixo=dict(zero=False),
                 series=[
                     _s_wb(part_ppp["CHN"], "China", AMARELO),
                     _s_wb(part_ppp["USA"], "Estados Unidos", VERMELHO),
                     _s_wb(part_ppp["UE27"], "UE-27 (bloco atual)", BRANCO, 3.5),
                     _s_wb(part_ppp["UE15"], "UE-15 (15 primeiros membros)", AZUL, 5.0),
                     _s_wb(part_ppp["GBR"], "Reino Unido", VERDE, 3.5),
                     _s_wb(part_ppp["NORD"], "Nórdicos (4 países)", AZUL_CLARO, 3.5),
                 ]),
            dict(rot="Escandinavos / Nórdicos (1990 a 2025)", unidade="%", eixo=dict(zero=False),
                 series=[
                     _s_wb(part_ppp["NORD"], "Total Nórdicos (4 países)", BRANCO, 5.0),
                     _s_wb(part_ppp["SWE"], "Suécia", AZUL, 4.5),
                     _s_wb(part_ppp["NOR"], "Noruega", VERMELHO, 4.5),
                     _s_wb(part_ppp["DNK"], "Dinamarca", AMARELO, 4.0),
                     _s_wb(part_ppp["FIN"], "Finlândia", VERDE, 3.5),
                 ]),
        ],
    )

    g_pib_pc_eua = dict(
        id="migracao-pib-pc-relativo-eua",
        titulo="PIB per capita relativo aos EUA (EUA = 100): Europa, Nórdicos, Coreia do Sul e China",
        subtitulo="PPC (1990 a 2025) e US$ correntes (1960 a 2025); Europa Ocidental Continental = Alemanha, França, Itália, Países Baixos, Bélgica e Áustria",
        unidade="ind", buracoMax=15,
        fonte="Banco Mundial (WDI, NY.GDP.PCAP.PP.CD, NY.GDP.PCAP.CD e SP.POP.TOTL) e FtM",
        eventos=[dict(em="2008-01", rot="Crise 2008"), dict(em="2020-01", rot="Covid-19")],
        variantes=[
            _var_rel_eua("PPC: UK, França, Itália, Coreia e China (1990 a 2025)", rel_ppp, "principais"),
            _var_rel_eua("US$: UK, França, Itália, Coreia e China (1990 a 2025)", rel_usd, "principais", min_ano=1990),
            _var_rel_eua("US$: UK, França, Itália, Coreia e China (1960 a 2025)", rel_usd, "principais"),
            _var_rel_eua("PPC: Escandinavos vs Europa Continental (1990 a 2025)", rel_ppp, "nordicos"),
            _var_rel_eua("US$: Escandinavos vs Europa Continental (1990 a 2025)", rel_usd, "nordicos", min_ano=1990),
            _var_rel_eua("US$: Escandinavos vs Europa Continental (1960 a 2025)", rel_usd, "nordicos"),
        ],
    )

    rank_c25, rank_h22, series_c, eu_sat25 = carregar_satisfacao()
    print("  Satisfação 2025 (Cantril | Eurostat UE-27=%.1f): Finlândia %.2f, Dinamarca %.2f, Alemanha %.2f, EUA %.2f, França %.2f, Mundo %.2f | WVS 2022: %s %.1f%% .. %s %.1f%%"
          % (eu_sat25,
             series_c["Finland"][-1][1], series_c["Denmark"][-1][1], series_c["Germany"][-1][1],
             series_c["United States"][-1][1], series_c["France"][-1][1], series_c["World"][-1][1],
             rank_h22[0][0], rank_h22[0][1], rank_h22[-1][0], rank_h22[-1][1]))
    g_satisfacao = dict(
        id="migracao-satisfacao-europa-eua",
        titulo="Satisfação com a vida e felicidade: Europa e EUA vs média mundial",
        subtitulo="Nota Cantril (0 a 10, Gallup/WHR 2025) e parcela que se diz feliz (WVS 2022); azul = europeus, amarelo = Argentina",
        tipo="ranking", unidade="n2",
        fonte="World Happiness Report / Gallup (via OWID), World Values Survey / IVS (via OWID), Eurostat (ilc_pw01) e FtM",
        itens=[[pt, round(v, 2), cor] for pt, v, cor in rank_c25],
        variantes=[
            dict(rot="Nota de satisfação (Gallup/WHR 2025, 0 a 10)", tipo="ranking", unidade="n2",
                 itens=[[pt, round(v, 2), cor] for pt, v, cor in rank_c25]),
            dict(rot="Parcela que se diz feliz (WVS, onda 2022)", tipo="ranking", unidade="pct1",
                 itens=[[pt, round(v, 1), cor] for pt, v, cor in rank_h22]),
            dict(rot="Evolução da satisfação (Gallup/WHR, 2011 a 2025)", tipo="linha", unidade="n2", buracoMax=30,
                 eixo=dict(zero=False), eventos=[dict(em="2020-01", rot="Covid-19")],
                 series=[
                     dict(nome="Finlândia", cor=AZUL_CLARO, largura=4.0, rotulo=True,
                          dados=[["%s-01" % y, round(v, 2)] for y, v in series_c["Finland"]]),
                     dict(nome="Dinamarca", cor=AMARELO, largura=4.0, rotulo=True,
                          dados=[["%s-01" % y, round(v, 2)] for y, v in series_c["Denmark"]]),
                     dict(nome="Alemanha", cor=AZUL, largura=4.5, rotulo=True,
                          dados=[["%s-01" % y, round(v, 2)] for y, v in series_c["Germany"]]),
                     dict(nome="Estados Unidos", cor=VERMELHO, largura=4.5, rotulo=True,
                          dados=[["%s-01" % y, round(v, 2)] for y, v in series_c["United States"]]),
                     dict(nome="França", cor=VERDE, largura=3.5, rotulo=True,
                          dados=[["%s-01" % y, round(v, 2)] for y, v in series_c["France"]]),
                     dict(nome="Média mundial", cor=BRANCO, largura=3.5, tracejada=True, rotulo=True,
                          dados=[["%s-01" % y, round(v, 2)] for y, v in series_c["World"]]),
                 ]),
        ],
    )

    # 8. Saídas fiscais e saídas de milionários
    hen = carregar_henley_2025()
    eur_hen = [
        "Itália", "Suíça", "Portugal", "Grécia", "Malta", "Mônaco", "Montenegro", "Letônia",
        "Suécia", "Irlanda", "Noruega", "Alemanha", "Espanha", "França", "Reino Unido",
    ]
    glob_hen = [
        "Emirados Árabes Unidos", "Estados Unidos", "Itália", "Suíça", "Arábia Saudita",
        "Singapura", "Portugal", "Grécia", "Canadá", "Austrália", "Japão",
        "França", "China", "Reino Unido",
    ]
    itens_hen_eur = [[p, hen[p], AZUL if hen[p] >= 0 else VERMELHO] for p in eur_hen]
    itens_hen_glob = [[p, hen[p], AZUL if hen[p] >= 0 else VERMELHO] for p in glob_hen]
    print("  Henley 2025 Europa: Itália %+d, Suíça %+d, França %+d, Espanha %+d, Alemanha %+d, Reino Unido %+d"
          % (hen["Itália"], hen["Suíça"], hen["França"], hen["Espanha"], hen["Alemanha"], hen["Reino Unido"]))
    g_milionarios = dict(
        id="migracao-milionarios-2025",
        titulo="Migração líquida de milionários em 2025",
        subtitulo="Saldo líquido estimado de indivíduos com US$ 1 milhão+ investíveis (entradas menos saídas)",
        tipo="ranking", unidade="int", sinal=True,
        fonte="Henley & Partners e New World Wealth (Henley Private Wealth Migration Report 2025)",
        itens=itens_hen_eur,
        variantes=[
            dict(rot="Europa (2025)", itens=itens_hen_eur),
            dict(rot="Principais polos globais (2025)", itens=itens_hen_glob),
        ],
    )

    todos_nd, resid_nd, cheg_nd = carregar_hmrc_nondom()
    anos_nd_tot = sorted(todos_nd, key=int)
    anos_nd_res = sorted(resid_nd, key=int)
    anos_nd_chg = sorted(cheg_nd, key=int)
    conferir(anos_nd_tot[0] == "2008" and anos_nd_tot[-1] == "2025", "HMRC Table_2 período inesperado")
    conferir(anos_nd_res[0] == "2015" and anos_nd_res[-1] == "2025", "HMRC Table_3 período inesperado")
    conferir(anos_nd_chg == ["2022", "2023", "2024", "2025"], "HMRC Table_13 período inesperado")
    for y in anos_nd_res:
        conferir(todos_nd[y] >= resid_nd[y], "HMRC Table_2 < Table_3 em %s" % y)
    print("  HMRC non-doms 2025: total %d, residentes UK %d, novas chegadas ano 1 %d"
          % (todos_nd["2025"], resid_nd["2025"], cheg_nd["2025"]))
    g_nondom = dict(
        id="migracao-saidas-fiscais-uk",
        titulo="Contribuintes non-dom no Reino Unido, 2008–2025",
        subtitulo="Registros oficiais por ano fiscal encerrado em abril (milhares de contribuintes)",
        unidade="mil",
        fonte="HMRC (Statistics on non-domiciled taxpayers in the UK, NONDOMTABLES.ods)",
        variantes=[
            dict(rot="Estoque total e residentes (2008–2025)", buracoMax=12,
                 series=[
                     dict(nome="Todos os non-dom (residentes e não residentes)", cor=AZUL, largura=4.5, rotulo=True,
                          dados=[["%s-01" % y, round(todos_nd[y] / 1000.0, 1)] for y in anos_nd_tot]),
                     dict(nome="Residentes no Reino Unido", cor=VERMELHO, largura=4.5, rotulo=True,
                          dados=[["%s-01" % y, round(resid_nd[y] / 1000.0, 1)] for y in anos_nd_res]),
                 ]),
            dict(rot="Novas chegadas no ano 1 (2022–2025)", categorias=anos_nd_chg, barra=0.55,
                 series=[
                     dict(nome="Novos contribuintes non-dom no 1º ano", cor=AZUL, tipo="barra",
                          dados=[[str(i), round(cheg_nd[y] / 1000.0, 1)] for i, y in enumerate(anos_nd_chg)]),
                 ]),
        ],
    )

    hoje = datetime.date.today().isoformat()
    # 6b. Produtividade e horas: Tabela de Blanchard estendida (PWT 1970 a 2023 + OCDE 2000 a 2025)
    ocde_b = carregar_ocde_blanchard()
    pwt_b = carregar_pwt11_blanchard()
    print("  Blanchard PWT 1970 (EUA=100): EU-15 PIB/p=%.1f, PIB/h=%.1f, h/p=%.1f | FRA PIB/p=%.1f, PIB/h=%.1f, h/p=%.1f"
          % (*pwt_b["EU15"]["1970"], *pwt_b["FRA"]["1970"]))
    print("  Blanchard OCDE 2025 (EUA=100): EU-15 PIB/p=%.1f, PIB/h=%.1f, h/p=%.1f | FRA PIB/p=%.1f, PIB/h=%.1f, h/p=%.1f"
          % (*ocde_b["EU15"]["2025"], *ocde_b["FRA"]["2025"]))

    def _linha_tab_blanchard(idx_m):
        eu15_70_pwt = round(pwt_b["EU15"]["1970"][idx_m])
        fra_70_pwt = round(pwt_b["FRA"]["1970"][idx_m])
        eu15_00 = round(ocde_b["EU15"]["2000"][idx_m])
        eu15_10 = round(ocde_b["EU15"]["2010"][idx_m])
        eu15_25 = round(ocde_b["EU15"]["2025"][idx_m])
        fra_00 = round(ocde_b["FRA"]["2000"][idx_m])
        fra_10 = round(ocde_b["FRA"]["2010"][idx_m])
        fra_25 = round(ocde_b["FRA"]["2025"][idx_m])
        eu27_00 = round(ocde_b["EU27"]["2000"][idx_m])
        eu27_10 = round(ocde_b["EU27"]["2010"][idx_m])
        eu27_25 = round(ocde_b["EU27"]["2025"][idx_m])
        return [
            [dict(t="EUA", forte=True), 100, 100, 100, 100, 100, 100],
            ["EU-15 (15 originais)", BLANCHARD_2004["EU15"]["1970"][idx_m], eu15_70_pwt,
             BLANCHARD_2004["EU15"]["2000"][idx_m], eu15_00, eu15_10, dict(t=eu15_25, forte=True)],
            ["França", BLANCHARD_2004["FRA"]["1970"][idx_m], fra_70_pwt,
             BLANCHARD_2004["FRA"]["2000"][idx_m], fra_00, fra_10, dict(t=fra_25, forte=True)],
            ["UE-27 (bloco atual)", None, None, None, eu27_00, eu27_10, eu27_25],
        ]

    cols_blanchard = [
        dict(rot="Região / País"),
        dict(rot="1970*", num=True),
        dict(rot="1970 (PWT)", num=True),
        dict(rot="2000*", num=True),
        dict(rot="2000 (OCDE)", num=True),
        dict(rot="2010", num=True),
        dict(rot="2025", num=True),
    ]
    g_blanchard_tab = dict(
        id="migracao-blanchard-tabela",
        tipo="tabela",
        titulo="Tabela de Blanchard estendida: PIB por pessoa, por hora e horas por pessoa",
        subtitulo="Índices em PPP corrente (EUA = 100); 1970* e 2000* de Blanchard (2004), 1970 (PWT 11.0) e 2000 a 2025 (OCDE)",
        fonte="Blanchard (2004, JEP), Penn World Table 11.0, OCDE (DSD_PDB@DF_PDB) e FtM",
        variantes=[
            dict(rot="PIB por hora (produtividade)", colunas=cols_blanchard, linhas=_linha_tab_blanchard(1)),
            dict(rot="PIB por pessoa (per capita)", colunas=cols_blanchard, linhas=_linha_tab_blanchard(0)),
            dict(rot="Horas por pessoa", colunas=cols_blanchard, linhas=_linha_tab_blanchard(2)),
        ],
    )
    anos_b = [str(y) for y in range(2000, 2026)]
    anos_pwt = [str(y) for y in range(1970, 2024)]

    def _serie_b(chave, idx_m, nome, cor, largura=4.5):
        return dict(nome=nome, cor=cor, largura=largura, rotulo=True,
                    dados=[["%s-01" % y, round(ocde_b[chave][y][idx_m], 1)] for y in anos_b])

    def _serie_pwt(chave, idx_m, nome, cor, largura=4.5):
        return dict(nome=nome, cor=cor, largura=largura, rotulo=True,
                    dados=[["%s-01" % y, round(pwt_b[chave][y][idx_m], 1)] for y in anos_pwt])

    serie_eua_100 = dict(nome="EUA (base 100)", cor=BRANCO, largura=2.5, tracejada=True, rotulo=True,
                         dados=[["%s-01" % y, 100.0] for y in anos_b])
    serie_eua_pwt = dict(nome="EUA (base 100)", cor=BRANCO, largura=2.5, tracejada=True, rotulo=True,
                         dados=[["%s-01" % y, 100.0] for y in anos_pwt])
    g_blanchard_lin = dict(
        id="migracao-produtividade-blanchard",
        titulo="Produtividade por hora, PIB por pessoa e horas: Europa vs EUA, 1970 a 2025",
        subtitulo="Índice em PPP corrente (EUA = 100 em cada ano); 1970 a 2023 pela PWT 11.0 e 2000 a 2025 pela OCDE",
        unidade="ind", buracoMax=15,
        fonte="Penn World Table 11.0, OCDE (DSD_PDB@DF_PDB) e FtM",
        eventos=[
            dict(em="1973-01", rot="Choque petróleo"),
            dict(em="2000-01", rot="Blanchard 2000"),
            dict(em="2008-01", rot="Crise 2008"),
            dict(em="2020-01", rot="Covid-19"),
        ],
        variantes=[
            dict(rot="PIB por hora (1970 a 2023, PWT)", eixo=dict(zero=False),
                 series=[serie_eua_pwt,
                         _serie_pwt("FRA", 1, "França", AZUL),
                         _serie_pwt("EU15", 1, "EU-15", VERMELHO)]),
            dict(rot="PIB por pessoa (1970 a 2023, PWT)", eixo=dict(zero=False),
                 series=[serie_eua_pwt,
                         _serie_pwt("EU15", 0, "EU-15", VERMELHO),
                         _serie_pwt("FRA", 0, "França", AZUL)]),
            dict(rot="Horas por pessoa (1970 a 2023, PWT)", eixo=dict(zero=False),
                 series=[serie_eua_pwt,
                         _serie_pwt("EU15", 2, "EU-15", VERMELHO),
                         _serie_pwt("FRA", 2, "França", AZUL)]),
            dict(rot="PIB por hora (2000 a 2025, OCDE)", eixo=dict(zero=False),
                 series=[serie_eua_100,
                         _serie_b("FRA", 1, "França", AZUL),
                         _serie_b("EU15", 1, "EU-15", VERMELHO),
                         _serie_b("EU27", 1, "UE-27", VERDE, 3.5)]),
            dict(rot="PIB por pessoa (2000 a 2025, OCDE)", eixo=dict(zero=False),
                 series=[serie_eua_100,
                         _serie_b("EU15", 0, "EU-15", VERMELHO),
                         _serie_b("EU27", 0, "UE-27", VERDE, 3.5),
                         _serie_b("FRA", 0, "França", AZUL)]),
            dict(rot="Horas por pessoa (2000 a 2025, OCDE)", eixo=dict(zero=False),
                 series=[serie_eua_100,
                         _serie_b("EU27", 2, "UE-27", VERDE, 3.5),
                         _serie_b("EU15", 2, "EU-15", VERMELHO),
                         _serie_b("FRA", 2, "França", AZUL)]),
        ],
    )

    # 9. O ímã do bem-estar: seleção na Europa/OCDE e experimento da Dinamarca
    spr24, lbl_spr = eurostat("tps00098", ["geo"], unit="PC_GDP", spdeps="TOTAL", time="2024")
    edu25, _ = eurostat("edat_lfs_9912", ["geo", "c_birth"], sex="T", age="Y25-64", unit="PC",
                        isced11="ED0-2", c_birth=["NAT", "NEU27_2020_FOR"], time="2025")
    emp25, _ = eurostat("lfsa_ergacob", ["geo", "c_birth"], sex="T", age="Y20-64", unit="PC",
                        c_birth=["NAT", "NEU27_2020_FOR"], time="2025")
    destaques = {"DE", "FR", "ES", "IT", "DK", "SE", "PT"}
    nomes_geo_pt = {
        "AT": "Áustria", "BE": "Bélgica", "BG": "Bulgária", "CH": "Suíça", "CY": "Chipre",
        "CZ": "Tchéquia", "DE": "Alemanha", "DK": "Dinamarca", "EE": "Estônia", "EL": "Grécia",
        "ES": "Espanha", "FI": "Finlândia", "FR": "França", "HR": "Croácia", "HU": "Hungria",
        "IE": "Irlanda", "IS": "Islândia", "IT": "Itália", "LT": "Lituânia", "LU": "Luxemburgo",
        "LV": "Letônia", "MT": "Malta", "NL": "Países Baixos", "NO": "Noruega", "PL": "Polônia",
        "PT": "Portugal", "RO": "Romênia", "SE": "Suécia", "SI": "Eslovênia", "SK": "Eslováquia",
        "RS": "Sérvia", "ME": "Montenegro",
    }

    def _ols(pts):
        xs = [p["x"] for p in pts]
        ys = [p["y"] for p in pts]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
        a = my - b * mx
        r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(
            sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
        return a, b, r, min(xs), max(xs)

    pts_edu, pts_emp = [], []
    for g in sorted(spr24):
        if len(g) != 2 or g in ("EA", "EU"):
            continue
        x = spr24[g]
        nome_g = nomes_geo_pt.get(g, lbl_spr.get("geo", {}).get(g, g))
        cor_g = VERMELHO if g in destaques else AZUL
        if (g, "NAT") in edu25 and (g, "NEU27_2020_FOR") in edu25:
            diff_edu = edu25[(g, "NEU27_2020_FOR")] - edu25[(g, "NAT")]
            pts_edu.append(dict(
                x=round(x, 1), y=round(diff_edu, 1), rot=g, cor=cor_g,
                destaque=(g in destaques),
                dica="%s: proteção social %.1f%% do PIB; baixa escolaridade fora da UE %.1f%% vs nativos %.1f%% (%+.1f p.p.)"
                     % (nome_g, x, edu25[(g, "NEU27_2020_FOR")], edu25[(g, "NAT")], diff_edu),
            ))
        if (g, "NAT") in emp25 and (g, "NEU27_2020_FOR") in emp25:
            diff_emp = emp25[(g, "NEU27_2020_FOR")] - emp25[(g, "NAT")]
            pts_emp.append(dict(
                x=round(x, 1), y=round(diff_emp, 1), rot=g, cor=cor_g,
                destaque=(g in destaques),
                dica="%s: proteção social %.1f%% do PIB; emprego fora da UE %.1f%% vs nativos %.1f%% (%+.1f p.p.)"
                     % (nome_g, x, emp25[(g, "NEU27_2020_FOR")], emp25[(g, "NAT")], diff_emp),
            ))

    conferir(len(pts_edu) >= 25 and len(pts_emp) >= 28, "amostra europeia pequena em dispersão")
    a_ed, b_ed, r_ed, x0_ed, x1_ed = _ols(pts_edu)
    a_em, b_em, r_em, x0_em, x1_em = _ols(pts_emp)
    conferir(r_ed > 0.5 and r_em < -0.25, "correlações fora do esperado (r_edu=%.2f, r_emp=%.2f)" % (r_ed, r_em))
    print("  Dispersão Eurostat: n_edu=%d r=%.2f | n_emp=%d r=%.2f" % (len(pts_edu), r_ed, len(pts_emp), r_em))

    g_ima_disp = dict(
        id="migracao-ima-selecao-europa",
        tipo="dispersao",
        titulo="Proteção social vs escolaridade e emprego de nascidos fora da UE, 2024 e 2025",
        subtitulo="Gasto em proteção social (% do PIB, 2024) vs diferença fora da UE menos nativos (p.p., 2025)",
        fonte="Eurostat (tps00098, edat_lfs_9912 e lfsa_ergacob) e FtM",
        legenda=[
            dict(rot="Países europeus", cor=AZUL),
            dict(rot="Principais acompanhados", cor=VERMELHO),
            dict(rot="Tendência linear", cor="linha:" + BRANCO),
        ],
        variantes=[
            dict(rot="Baixa escolaridade: fora da UE menos nativos (2025, r=+0,72)",
                 eixoX=dict(unidade="pct1", rot="Gasto em proteção social (% do PIB, 2024)"),
                 eixoY=dict(unidade="pp", rot="Diferença na baixa escolaridade (p.p.)"),
                 pontos=pts_edu,
                 reta=dict(a=round(a_ed, 4), b=round(b_ed, 4), de=round(x0_ed, 1), ate=round(x1_ed, 1), cor=BRANCO)),
            dict(rot="Taxa de emprego: fora da UE menos nativos (2025, r=-0,41)",
                 eixoX=dict(unidade="pct1", rot="Gasto em proteção social (% do PIB, 2024)"),
                 eixoY=dict(unidade="pp", rot="Diferença na taxa de emprego (p.p.)"),
                 pontos=pts_emp,
                 reta=dict(a=round(a_em, 4), b=round(b_em, 4), de=round(x0_em, 1), ate=round(x1_em, 1), cor=BRANCO)),
        ],
    )

    emp_ocde = carregar_ocde_emprego_mig()
    print("  OCDE emprego 2025:", ", ".join("%s %+.1f p.p." % (n, g) for _, n, _, _, g in emp_ocde[:4] + emp_ocde[-3:]))
    g_ima_emp_ocde = dict(
        id="migracao-emprego-nativos-imigrantes",
        titulo="Taxa de emprego de nativos e nascidos no exterior (OCDE, 2025)",
        subtitulo="População de 15 a 64 anos empregada (%); ordenado pela diferença entre imigrantes e nativos",
        unidade="pct1",
        categorias=[nome for _, nome, _, _, _ in emp_ocde],
        agrupadas=True,
        barra=0.78,
        fonte="OCDE (International Migration Database, DSD_MIG@DF_MIG_NUP_SEX)",
        series=[
            dict(nome="Nativos", cor=AZUL, tipo="barra", valores=True,
                 dados=[[str(i), round(nb, 1)] for i, (_, _, nb, _, _) in enumerate(emp_ocde)]),
            dict(nome="Nascidos no exterior", cor=VERMELHO, tipo="barra", valores=True,
                 dados=[[str(i), round(fb, 1)] for i, (_, _, _, fb, _) in enumerate(emp_ocde)]),
        ],
    )

    dk = carregar_dinamarca_van66()
    anos_dk = sorted(dk.keys(), key=int)
    print("  Dinamarca VAN66 (%s): asilo=%d, família=%d, trabalho=%d, UE=%d, Ucrânia=%d"
          % (anos_dk[-1], dk[anos_dk[-1]]["asilo"], dk[anos_dk[-1]]["familia"],
             dk[anos_dk[-1]]["trabalho"], dk[anos_dk[-1]]["eu"], dk[anos_dk[-1]]["ucrania"]))
    g_dinamarca = dict(
        id="migracao-dinamarca-experimento",
        titulo="Dinamarca: autorizações de residência por motivo, 1997 a 2025",
        subtitulo="Registros anuais; marcos das reformas do benefício assistencial a não europeus (Agersnap, Jensen e Kleven, 2020)",
        unidade="int", buracoMax=15,
        fonte="Statistics Denmark (StatBank VAN66) e Agersnap, Jensen e Kleven (2020)",
        eventos=[
            dict(em="2002-01", rot="Corte 50%"),
            dict(em="2012-01", rot="Revogação"),
            dict(em="2015-01", rot="Reintrodução"),
        ],
        variantes=[
            dict(rot="Asilo e família vs trabalho e UE (1997 a 2025)",
                 series=[
                     dict(nome="Asilo e reagrupamento familiar", cor=VERMELHO, largura=4.5, rotulo=True,
                          dados=[["%s-01" % y, dk[y]["asilo"] + dk[y]["familia"]] for y in anos_dk]),
                     dict(nome="Trabalho (fora da UE/EEE)", cor=AZUL, largura=4.5, rotulo=True,
                          dados=[["%s-01" % y, dk[y]["trabalho"]] for y in anos_dk]),
                     dict(nome="UE e EEE", cor=VERDE, largura=3.5, rotulo=True,
                          dados=[["%s-01" % y, dk[y]["eu"]] for y in anos_dk]),
                 ]),
            dict(rot="Abertura humanitária e Ucrânia (1997 a 2025)",
                 series=[
                     dict(nome="Asilo", cor=VERMELHO, largura=4.5, rotulo=True,
                          dados=[["%s-01" % y, dk[y]["asilo"]] for y in anos_dk]),
                     dict(nome="Reagrupamento familiar", cor=AZUL, largura=4.5, rotulo=True,
                          dados=[["%s-01" % y, dk[y]["familia"]] for y in anos_dk]),
                     dict(nome="Ucrânia (Lei Especial, 2022 a 2025)", cor=AMARELO, largura=3.5, rotulo=True,
                          dados=[["%s-01" % y, dk[y]["ucrania"]] for y in anos_dk if dk[y]["ucrania"] > 0]),
                 ]),
        ],
    )

    div_rows = carregar_diversidade_tributos()
    dest_div = {"USA", "FRA", "DEU", "ITA", "ESP", "GBR", "DNK", "SWE", "CHE", "JPN", "KOR", "CAN"}
    pts_eth = [
        dict(
            x=round(eth, 3), y=round(tax_v, 1), rot=c,
            cor=VERMELHO if c in dest_div else AZUL,
            destaque=(c in dest_div),
            dica="%s: fracionalização étnica %.3f; carga tributária %.1f%% do PIB (%d)" % (nome, eth, tax_v, tax_y),
        )
        for c, nome, eth, _, tax_v, tax_y in div_rows
    ]
    pts_mig = [
        dict(
            x=round(mig_v, 1), y=round(tax_v, 1), rot=c,
            cor=VERMELHO if c in dest_div else AZUL,
            destaque=(c in dest_div),
            dica="%s: nascidos no exterior %.1f%% (2024); carga tributária %.1f%% do PIB (%d)" % (nome, mig_v, tax_v, tax_y),
        )
        for c, nome, _, mig_v, tax_v, tax_y in div_rows
    ]
    a_et, b_et, r_et, x0_et, x1_et = _ols(pts_eth)
    a_mg, b_mg, r_mg, x0_mg, x1_mg = _ols(pts_mig)
    conferir(r_et < -0.20 and r_mg > 0.15, "correlações diversidade x tributos inesperadas: r_eth=%.2f r_mig=%.2f" % (r_et, r_mg))
    print("  Diversidade x Tributos (OCDE n=38): r_étnica=%.2f | r_imigração=%.2f" % (r_et, r_mg))

    g_diversidade_tax = dict(
        id="migracao-diversidade-carga-tributaria",
        tipo="dispersao",
        titulo="Diversidade e carga tributária em % do PIB na OCDE (38 países)",
        subtitulo="Índice de fracionalização étnica de Alesina (0 a 1) e fatia de nascidos no exterior (2024) vs carga tributária total (% do PIB, 2022 a 2023)",
        fonte="QoG (Alesina et al., 2003), ONU DESA (2024) e UNU-WIDER GRD (via OWID) e FtM",
        legenda=[
            dict(rot="Demais países da OCDE", cor=AZUL),
            dict(rot="Principais destacados", cor=VERMELHO),
            dict(rot="Tendência linear", cor="linha:" + BRANCO),
        ],
        variantes=[
            dict(rot="Diversidade étnica histórica (Alesina, r=%s)" % ("%+.2f" % r_et).replace(".", ","),
                 eixoX=dict(unidade="n2", rot="Índice de fracionalização étnica (0 = homogêneo, 1 = diverso)"),
                 eixoY=dict(unidade="pct1", rot="Carga tributária + contribuições (% do PIB)"),
                 pontos=pts_eth,
                 reta=dict(a=round(a_et, 4), b=round(b_et, 4), de=round(x0_et, 3), ate=round(x1_et, 3), cor=BRANCO)),
            dict(rot="Nascidos no exterior (ONU 2024, r=%s)" % ("%+.2f" % r_mg).replace(".", ","),
                 eixoX=dict(unidade="pct1", rot="População nascida no exterior (%, 2024)"),
                 eixoY=dict(unidade="pct1", rot="Carga tributária + contribuições (% do PIB)"),
                 pontos=pts_mig,
                 reta=dict(a=round(a_mg, 4), b=round(b_mg, 4), de=round(x0_mg, 1), ate=round(x1_mg, 1), cor=BRANCO)),
        ],
    )

    doc = dict(assunto="Migração na Europa", grupo="Análises Variadas",
               fonte="Eurostat, OCDE, Statistics Denmark, ONU (via OWID), UNU-WIDER, QoG (Alesina), Penn World Table 11.0, Banco Mundial, Henley & Partners, HMRC e FtM",
               referencia="2025-12", atualizado=hoje, formato="artigo",
               secoes=[dict(titulo="Fronteiras abertas ou Estado de bem-estar? O dilema de Friedman", texto="", fontes=[], figuras=[],
                            graficos=[g_satisfacao]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_pib_mundial_ppp]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_pib_pc_eua]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_fbcf]),
                       dict(titulo="Horas trabalhadas: escolha ou freio tributário?", texto="", fontes=[], figuras=[],
                            graficos=[g_horas]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_blanchard_tab]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_blanchard_lin]),
                       dict(titulo="O buraco demográfico e o crescimento com e sem migração", texto="", fontes=[], figuras=[],
                            graficos=[g_cresc_hist]),
                       dict(titulo="", texto="", fontes=[], figuras=[],
                            graficos=[g_cresc_extra, g_cresc_extra_qtd]),
                       dict(titulo="Quem chega e quem sai", texto="", fontes=[], figuras=[], graficos=[g_fluxos]),
                       dict(titulo="", texto="", fontes=[], figuras=[],
                            graficos=[g_fluxos_tempo, g_fluxos_tempo_qtd]),
                       dict(titulo="", texto="", fontes=[], figuras=[],
                            graficos=[g_fluxos_fora, g_fluxos_fora_qtd]),
                       dict(titulo="Quantos nasceram fora e de onde vêm", texto="", fontes=[], figuras=[],
                            graficos=[g_estoque]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_europa_an]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_origens, g_origens_qtd]),
                       dict(titulo="A idade de quem chega", texto="", fontes=[], figuras=[],
                            graficos=[g_idade, g_idade_qtd]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_media]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_piramide, g_piramide_qtd]),
                       dict(titulo="O teto tributário e quem sai no topo", texto="", fontes=[], figuras=[],
                            graficos=[g_milionarios]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_nondom]),
                       dict(titulo="O ímã do bem-estar e o experimento da Dinamarca", texto="", fontes=[], figuras=[],
                            graficos=[g_ima_disp]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_ima_emp_ocde]),
                       dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_dinamarca]),
                       dict(titulo="O aperto político: diversidade e vontade de redistribuir", texto="", fontes=[], figuras=[],
                            graficos=[g_diversidade_tax])])
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado", SAIDA)
    sys.path.insert(0, os.path.dirname(__file__))
    import aplicar_texto
    if aplicar_texto.aplicar("migracao-europa.md", "migracao-europa.json"):
        raise RuntimeError("falha ao aplicar textos/migracao-europa.md")


if __name__ == "__main__":
    main()

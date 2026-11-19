#!/usr/bin/env python3
"""
Europa: trabalho, investimento e saída de capital.
Gera dados/europa-competitividade.json a partir de fontes oficiais/abertas:
  1. Horas trabalhadas por trabalhador/ano (1950–2023): Penn World Table (2025) e
     Huberman e Minns (2005) via Our World in Data (annual-working-hours-per-worker).
  2. FBCF / PIB (1970–2025): Banco Mundial (NE.GDI.FTOT.ZS via CSV em ZIP),
     conferido em 2024 contra Eurostat (nama_10_gdp, P51G, PC_GDP).
  3. Saídas de milionários (2025): Henley Private Wealth Migration Report 2025
     (conferido contra o texto oficial publicado em henleyglobal.com).
  4. Saídas fiscais no Reino Unido (2008–2025): HMRC (NONDOMTABLES.ods, gov.uk).

Só biblioteca padrão do Python 3. O texto vem de textos/europa-competitividade.md.
"""
import csv
import datetime
import io
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SAIDA = os.path.join(RAIZ, "dados", "europa-competitividade.json")
UA = {"User-Agent": "ftm-analises"}

OWID_HOURS = "https://ourworldindata.org/grapher/annual-working-hours-per-worker.csv?v=1&csvType=full&useColumnShortNames=true"
WB_GFCF = "https://api.worldbank.org/v2/en/indicator/NE.GDI.FTOT.ZS?downloadformat=csv"
EUROSTAT_GFCF = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "nama_10_gdp?format=JSON&lang=EN&geo=EU27_2020&geo=DE&geo=FR&geo=IT&geo=ES&na_item=P51G&unit=PC_GDP&time=2024"
)
HENLEY_2025 = "https://www.henleyglobal.com/newsroom/press-releases/henley-private-wealth-migration-report-2025"
HMRC_ODS = "https://assets.publishing.service.gov.uk/media/6a5a3d5b5ca06bf11ccb43fe/NONDOMTABLES.ods"

AZUL, VERMELHO, VERDE = "#4F81BD", "#C0504D", "#9BBB59"
AZUL_CLARO, AMARELO, BRANCO = "#8EB4E3", "#FFFF00", "#FFFFFF"


def baixar(url, tentativas=4):
    """Baixa uma URL usando apenas biblioteca padrão, com retentativas."""
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:                               # noqa: BLE001
            ultimo = e
            time.sleep(2 * (i + 1))
    raise RuntimeError("não deu para baixar %s: %s" % (url, ultimo))


def conferir(condicao, msg):
    if not condicao:
        raise RuntimeError("conferência falhou: " + msg)


def carregar_horas():
    """Retorna {entity: [(year_str, float), ...]} de 1950 a 2023."""
    txt = baixar(OWID_HOURS).decode("utf-8")
    out = {}
    for row in csv.DictReader(io.StringIO(txt)):
        y = int(row["year"])
        if y < 1950:
            continue
        v = row.get("working_hours_omm", "").strip()
        if v:
            out.setdefault(row["entity"], []).append((row["year"], float(v)))
    for ent in out:
        out[ent].sort(key=lambda kv: int(kv[0]))
    return out


def carregar_wb_fbcf():
    """Retorna {iso3: [(year_str, float), ...]} de 1970 a 2025."""
    zbytes = baixar(WB_GFCF)
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        fn = [n for n in z.namelist() if n.startswith("API_NE.GDI.FTOT.ZS")][0]
        txt = z.read(fn).decode("utf-8-sig")
    linhas = txt.splitlines()
    # localiza dinamicamente o cabeçalho pelo rótulo "Country Code"
    idx_hdr = next(i for i, l in enumerate(linhas[:10]) if "Country Code" in l)
    reader = csv.DictReader(io.StringIO("\n".join(linhas[idx_hdr:])))
    anos = [str(y) for y in range(1970, 2026)]
    out = {}
    for row in reader:
        cc = row["Country Code"]
        if cc in {"EUU", "DEU", "FRA", "ITA", "ESP", "GBR", "USA", "CAN", "JPN", "KOR"}:
            pts = [(y, float(row[y])) for y in anos if row.get(y, "").strip()]
            out[cc] = pts
    return out


def carregar_eurostat_fbcf_2024():
    """Retorna {geo: float} para P51G PC_GDP em 2024 (conferência cruzada)."""
    r = json.loads(baixar(EUROSTAT_GFCF).decode("utf-8"))
    ids, tam = r["id"], r["size"]
    cats = [sorted(r["dimension"][d]["category"]["index"].items(), key=lambda kv: kv[1]) for d in ids]
    gi = ids.index("geo")
    out = {}
    for pos, v in r["value"].items():
        p, coord = int(pos), []
        for i in reversed(range(len(ids))):
            coord.append(p % tam[i])
            p //= tam[i]
        coord.reverse()
        out[cats[gi][coord[gi]][0]] = float(v)
    return out


def carregar_henley_2025():
    """Baixa o press release oficial da Henley 2025 e verifica os valores por regex."""
    html = baixar(HENLEY_2025).decode("utf-8", errors="ignore")
    txt = re.sub(r"<(script|style).*?</\1>", " ", html, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt)

    # padrões exatos no texto do press release (com sinal oficial)
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
    ods = baixar(HMRC_ODS)
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
        out = {}
        for r in linhas[hdr_idx + 1:]:
            if len(r) > col_n and re.fullmatch(r"\d{4}", r[0]):
                out[r[0]] = int(r[col_n].replace(",", ""))
        return out

    todos = extrair_serie(tabelas["Table_2"])
    resid = extrair_serie(tabelas["Table_3"])
    chegadas = {}
    hdr13 = next(i for i, r in enumerate(tabelas["Table_13"]) if r[0] == "Year of stay")
    for r in tabelas["Table_13"][hdr13 + 1:]:
        if len(r) >= 3 and r[0] == "1" and re.fullmatch(r"\d{4}", r[1]):
            chegadas[r[1]] = int(r[2].replace(",", ""))
    return todos, resid, chegadas


def main():
    # 1. Horas trabalhadas
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
        id="comp-horas-trabalhadas",
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

    # 2. FBCF / PIB
    fbcf = carregar_wb_fbcf()
    eur_24 = carregar_eurostat_fbcf_2024()
    mapa_eur = [("EUU", "EU27_2020"), ("DEU", "DE"), ("FRA", "FR"), ("ITA", "IT"), ("ESP", "ES")]
    for wb_c, eu_c in mapa_eur:
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
        id="comp-fbcf-pib",
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

    # 3A. Saídas de milionários (Henley 2025)
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
        id="comp-milionarios-2025",
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

    # 3B. Saídas fiscais oficiais no Reino Unido (HMRC NONDOMTABLES.ods)
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
        id="comp-saidas-fiscais-uk",
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
    doc = dict(
        assunto="Europa: trabalho, investimento e saída de capital",
        grupo="Análises Variadas",
        fonte="Our World in Data, Banco Mundial, Eurostat, Henley & Partners e HMRC",
        referencia="2025-12",
        atualizado=hoje,
        formato="artigo",
        secoes=[
            dict(titulo="Horas trabalhadas", texto="", fontes=[], figuras=[], graficos=[g_horas]),
            dict(titulo="Investimento (FBCF / PIB)", texto="", fontes=[], figuras=[], graficos=[g_fbcf]),
            dict(titulo="Saídas fiscais e de milionários", texto="", fontes=[], figuras=[],
                 graficos=[g_milionarios, g_nondom]),
        ],
    )
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado", SAIDA)
    sys.path.insert(0, os.path.dirname(__file__))
    import aplicar_texto
    if aplicar_texto.aplicar("europa-competitividade.md", "europa-competitividade.json"):
        raise RuntimeError("falha ao aplicar textos/europa-competitividade.md")


if __name__ == "__main__":
    main()

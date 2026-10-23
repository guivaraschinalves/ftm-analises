"""
As partes de dados/petroleo.json que não vêm do Comex Stat: produção de
petróleo e das refinarias (ANP), refino no mundo (JODI), contribuição do setor
externo para o PIB (IBGE) e o Brent (FRED). Quem monta a página é o
scripts/petroleo.py, que chama `secoes_extra()`.

AS FONTES E AS CONTAS

  - **Produção de petróleo**, ANP, "Produção de petróleo e gás natural por
    estado e localização" (ppgn-el/producao-petroleo-m3.csv): mensal desde
    1997, em m³, por UF e terra/mar. É a produção NACIONAL: a ANP não publica
    a extração por empresa (o arquivo por poço traz o campo, não o operador).
    Os meses ainda não apurados vêm com zero e ficam de fora.
  - **Produção das refinarias**, ANP, "Produção de derivados de petróleo por
    refinaria" (pppd/…-por-refinaria-m3-1990-2025.csv — o nome do arquivo
    para em 2025, o conteúdo não), mensal desde 1990, em m³, por produto.
  - Em mil barris por dia: m³ × 6,2898 ÷ dias do mês ÷ 1.000.
  - **Sazonalidade**: a faixa é o mínimo e o máximo de cada mês nos 5 anos
    anteriores ao corrente, a média deles tracejada, e o ano corrente e o
    anterior em linha.
  - **Refino no mundo**, JODI (Joint Organisations Data Initiative: IEA,
    OPEP, ONU e outras), base "secundária", fluxo REFGROUT (produção bruta das
    refinarias), produtos GASOLINE e GASDIES (gasóleo/diesel), em mil barris por
    dia. Cerca de 60 países informam e a lista muda: a soma usa um PAINEL FIXO
    — só os países com o dado de todos os meses desde jan/2015 até o último mês
    em que todos eles informaram. Não é o mundo inteiro, mas a variação é real.
    O CSV tem 650 MB descompactado e é lido de dentro do zip, sem extrair.
  - **PIB**, IBGE: contribuição de famílias, governo, FBC (FBCF + estoques)
    e exportações líquidas para o crescimento do PIB NOMINAL em 4 trimestres
    (SIDRA 1846). A preços correntes a ótica da demanda é aditiva, então as
    contribuições somam o crescimento sem resíduo — o script confere. E a
    variação real da exportação e da importação que o IBGE publica (SIDRA 5932).
  - **Refino no mundo**: além do nível, a variação contra o mesmo mês do ano
    anterior, que é o que se compara num painel que não é o mundo inteiro.
  - **Petróleo bruto no mundo**, JODI, base "primária" (world_primary_csv.zip),
    CRUDEOIL em mil barris: produção (INDPROD), exportação (TOTEXPSB) e
    importação (TOTIMPSB). Acumulado do ano até o último mês de cada país,
    contra os mesmos meses do ano anterior, em média por dia. Rankings em % (só
    quem passou de 100 mil b/d no ano anterior) e em mil b/d. A exportação
    líquida entra só para quem era exportador líquido; quem não informa
    importação nenhuma (Argentina, Guiana) conta como zero. A Venezuela fica
    fora da exportação: informa só parte do que embarca.
  - **Brent**, FRED, MCOILBRENTEU (média mensal, EIA), CSV sem chave.
  - **Conta corrente**, Banco Central, tabela especial BalPagM.xlsx (BPM6,
    US$ milhões), com as linhas achadas pelo código SGS que o BC põe ao lado
    de cada uma — o mesmo leitor do ftm-dados/scripts/bp.py. Em dez/2026 entra
    a projeção do BC do RPM de setembro de 2026 (PROJ_BC, trocar a cada RPM).
"""
import calendar
import csv
import re
from xml.etree import ElementTree as ET
import io
import json
import os
import time
import urllib.request
import zipfile

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CACHE_ANP = os.path.join(RAIZ, "dados", ".cache-anp")
CACHE_JODI = os.path.join(RAIZ, "dados", ".cache-jodi")

ANP = "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/"
URL_PRODUCAO = ANP + "ppgn-el/producao-petroleo-m3.csv"
URL_REFINARIAS = ANP + "pppd/producao-derivados-petroleo-por-refinaria-m3-1990-2025.csv"
URL_JODI = "https://www.jodidata.org/_resources/files/downloads/oil-data/world_secondary_csv.zip"
URL_JODI_PRIM = "https://www.jodidata.org/_resources/files/downloads/oil-data/world_primary_csv.zip"
URL_ANP_COMERCIO = ANP + "ie/petroleo/importacoes-exportacoes-petroleo-2000-2025.csv"   # vai além de 2025
URL_STEO = "https://www.eia.gov/outlooks/steo/xls/STEO_m.xlsx"
URL_CREA = ("https://api.russiafossiltracker.com/v0/counter?format=json&date_from=2021-01-01"
            "&aggregate_by=commodity,month&commodity_group=oil")
URL_AR_PROD = ("https://apis.datos.gob.ar/series/api/series/?ids=363.3_PRODUCCIONUDO__28"
               "&limit=1000&format=json")
TONELADA_BBL = 7.33     # barris por tonelada, petróleo russo (Urals)
URL_BRENT = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MCOILBRENTEU"
NAVEGADOR = {"User-Agent": "Mozilla/5.0"}

M3_BBL = 6.28981
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MES_NUM = {m.upper(): i + 1 for i, m in enumerate(MESES)}

AZUL, VERMELHO, VERDE, ROXO, CIANO, LARANJA = "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6", "#F79646"
AZUL_ESCURO, BRANCO, CINZA, AREIA = "#1F497D", "#FFFFFF", "#95A5A6", "#D9B382"
AMARELO = "#FFFF00"

ANOS_FAIXA = 5
INICIO_PAINEL = "2015-01"


def baixar(url, destino=None, headers=NAVEGADOR, tentativas=5):
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=300) as r:
                corpo = r.read()
            if destino:
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with open(destino, "wb") as f:
                    f.write(corpo)
            return corpo
        except Exception as e:                       # noqa: BLE001
            ultimo = e
            time.sleep(2 * 2 ** i)
    raise RuntimeError("não deu para baixar %s: %s" % (url, ultimo))


def serie(nome, cor, dados, casas=2, **extra):
    # no eixo de categorias a chave é "0"…"11": como texto, "10" viria antes
    # de "2" e a linha sairia em ziguezague
    ordem = (lambda kv: int(kv[0])) if all(k.isdigit() for k in dados) else (lambda kv: kv[0])
    return dict(nome=nome, cor=cor, dados=[[m, round(v, casas)] for m, v in sorted(dados.items(), key=ordem)],
                **extra)


def kbd(m3, mes):
    """m³ no mês → mil barris por dia."""
    a, mm = int(mes[:4]), int(mes[5:7])
    return m3 * M3_BBL / calendar.monthrange(a, mm)[1] / 1000


def media_n(d, n):
    """Média móvel dos n meses até cada mês."""
    ms = sorted(d)
    return {ms[i]: sum(d[m] for m in ms[i - n + 1:i + 1]) / n for i in range(n - 1, len(ms))}


def var_anual(d):
    """% contra o mesmo mês do ano anterior."""
    return {m: (v / d["%04d-%s" % (int(m[:4]) - 1, m[5:])] - 1) * 100 for m, v in d.items()
            if "%04d-%s" % (int(m[:4]) - 1, m[5:]) in d}


def media_12(d):
    return media_n(d, 12)


def sazonal(mensal, nome, cor, unidade, titulo, subtitulo, id_, fonte):
    """Faixa de mínimo e máximo dos ANOS_FAIXA anos anteriores, a média deles
    e as linhas do ano corrente e do anterior, num eixo de jan a dez."""
    atual = max(mensal)[:4]
    anteriores = [str(int(atual) - k) for k in range(ANOS_FAIXA, 0, -1)]
    faixa, media = [], {}
    for k in range(12):
        vs = [mensal["%s-%02d" % (a, k + 1)] for a in anteriores if "%s-%02d" % (a, k + 1) in mensal]
        if len(vs) == ANOS_FAIXA:
            faixa.append([str(k), round(min(vs), 1), round(max(vs), 1)])
            media[str(k)] = sum(vs) / len(vs)
    ano = lambda a: {str(int(m[5:7]) - 1): v for m, v in mensal.items() if m[:4] == a}   # noqa: E731
    rot = "%s a %s" % (anteriores[0], anteriores[-1])
    return dict(id=id_, titulo=titulo, subtitulo=subtitulo, unidade=unidade, fonte=fonte, categorias=MESES,
                series=[dict(nome="Mínimo e máximo de " + rot, cor=cor, tipo="faixa", dados=faixa, opacidade=0.3),
                        serie("Média de " + rot, CINZA, media, 1, traco="pontilhado", largura=4),
                        serie(anteriores[-1], AZUL, ano(anteriores[-1]), 1),
                        serie(atual, BRANCO, ano(atual), 1, rotulo=True, largura=8)])


# --------------------------------------------------------------------------
# ANP
# --------------------------------------------------------------------------

def linhas_anp(url, nome):
    caminho = os.path.join(CACHE_ANP, nome)
    baixar(url, caminho)
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def producao_petroleo():
    """{"mar"|"terra": {mês: m³}} — sem os meses ainda zerados."""
    fora = {"MAR": {}, "TERRA": {}}
    for l in linhas_anp(URL_PRODUCAO, "producao-petroleo-m3.csv"):
        mes = "%s-%02d" % (l["ANO"], MES_NUM[l["MÊS"].strip().upper()[:3]])
        v = float(l["PRODUÇÃO"].replace(",", ".") or 0)
        loc = l["LOCALIZAÇÃO"].strip().upper()
        fora[loc][mes] = fora[loc].get(mes, 0.0) + v
    total = {m: fora["MAR"].get(m, 0) + fora["TERRA"].get(m, 0) for m in set(fora["MAR"]) | set(fora["TERRA"])}
    ultimo = max(m for m, v in total.items() if v > 0)
    return {k: {m: v for m, v in d.items() if m <= ultimo} for k, d in fora.items()}


def graficos_producao():
    p = producao_petroleo()
    mar = {m: kbd(v, m) for m, v in p["MAR"].items()}
    terra = {m: kbd(v, m) for m, v in p["TERRA"].items()}
    total = {m: mar.get(m, 0) + terra.get(m, 0) for m in mar}
    print("  produção de petróleo até %s: %.0f mil barris/dia" % (max(total), total[max(total)]))
    fonte = "ANP e FtM"
    return dict(titulo="Produção de petróleo", graficos=[
        dict(id="producao-petroleo", titulo="Produção de petróleo no Brasil",
             subtitulo="Mil barris por dia, mensal; produção nacional, todas as empresas", unidade="kbd",
             fonte=fonte, barra=1,
             series=[serie("Mar", AZUL_ESCURO, mar, 0, tipo="barra"),
                     serie("Terra", AREIA, terra, 0, tipo="barra"),
                     serie("Total", BRANCO, total, 0, rotulo=True)]),
        sazonal(total, "", AZUL, "kbd", "Produção de petróleo no Brasil: sazonalidade",
                "Mil barris por dia; faixa = mínimo e máximo de cada mês nos %d anos anteriores" % ANOS_FAIXA,
                "producao-petroleo-sazonal", fonte),
    ])


PRODUTOS_REFINO = [("ÓLEO DIESEL", "Diesel", VERMELHO), ("GASOLINA A", "Gasolina A", AZUL),
                   ("QUEROSENE DE AVIAÇÃO", "QAV", CIANO), ("ÓLEO COMBUSTÍVEL", "Óleo combustível", ROXO),
                   ("GLP", "GLP", LARANJA)]


def graficos_refino_brasil():
    por = {}
    for l in linhas_anp(URL_REFINARIAS, "refinarias.csv"):
        mes = "%s-%02d" % (l["ANO"], MES_NUM[l["MÊS"].strip().upper()[:3]])
        prod = l["PRODUTO"].strip().upper()
        v = float(l["PRODUÇÃO"].replace(",", ".") or 0)
        por.setdefault(prod, {})
        por[prod][mes] = por[prod].get(mes, 0.0) + v
    total = {}
    for d in por.values():
        for m, v in d.items():
            total[m] = total.get(m, 0.0) + v
    ultimo = max(m for m, v in total.items() if v > 0)
    nomes = {p for p, _, _ in PRODUTOS_REFINO}
    outros = {m: sum(d.get(m, 0) for p, d in por.items() if p not in nomes) for m in total if m <= ultimo}
    kb = lambda d: {m: kbd(v, m) for m, v in d.items() if m <= ultimo}          # noqa: E731
    produtos = [(n, c, kb(por[p])) for p, n, c in PRODUTOS_REFINO] + [("Outros", CINZA, kb(outros))]
    tot = kb(total)
    diesel, gasolina = kb(por["ÓLEO DIESEL"]), kb(por["GASOLINA A"])
    print("  refino no Brasil até %s: %.0f mil barris/dia" % (ultimo, tot[ultimo]))

    def variantes(series_de):
        """Mensal, média móvel de 3 meses e de 12 meses, num botão."""
        return [dict(rot=rot, unidade="kbd", series=series_de(f))
                for rot, f in (("Mensal", lambda d: d), ("Média de 3 meses", lambda d: media_n(d, 3)),
                               ("Média de 12 meses", lambda d: media_n(d, 12)))]
    fonte = "ANP e FtM"
    return [
        dict(id="refino-brasil", titulo="Produção das refinarias no Brasil",
             subtitulo="Mil barris por dia, por derivado", unidade="kbd", fonte=fonte, barra=1,
             variantes=variantes(lambda f: [serie(n, c, f(d), 0, tipo="barra") for n, c, d in produtos]
                                 + [serie("Total", BRANCO, f(tot), 0, rotulo=True)])),
        dict(id="refino-brasil-diesel-gasolina", titulo="Produção de diesel e gasolina A nas refinarias do Brasil",
             subtitulo="Mil barris por dia", unidade="kbd", fonte=fonte,
             variantes=variantes(lambda f: [serie("Diesel", VERMELHO, f(diesel), 0, rotulo=True),
                                            serie("Gasolina A", AZUL, f(gasolina), 0, rotulo=True)])),
    ]


# --------------------------------------------------------------------------
# JODI
# --------------------------------------------------------------------------

def refino_mundo():
    """{produto: {mês: kbd}} do painel fixo, e o número de países."""
    zipado = os.path.join(CACHE_JODI, "world_secondary_csv.zip")
    baixar(URL_JODI, zipado)
    dados = {}
    with zipfile.ZipFile(zipado) as z:
        nome = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        with z.open(nome) as bruto:
            for l in csv.DictReader(io.TextIOWrapper(bruto, encoding="utf-8", errors="replace")):
                if (l["FLOW_BREAKDOWN"] != "REFGROUT" or l["UNIT_MEASURE"] != "KBD"
                        or l["ENERGY_PRODUCT"] not in ("GASOLINE", "GASDIES")
                        or l["TIME_PERIOD"] < INICIO_PAINEL):
                    continue
                try:
                    v = float(l["OBS_VALUE"])
                except ValueError:
                    continue
                dados.setdefault(l["ENERGY_PRODUCT"], {}).setdefault(l["REF_AREA"], {})[l["TIME_PERIOD"]] = v
    # O mês final: o último em que o painel (países com todos os meses desde
    # 2015 até ele) ainda tem pelo menos 95% dos países que tinha três meses
    # antes. É o que corta o mês mais recente quando só parte dos países já
    # informou (ago/2026 tinha 40 contra 47). O mesmo mês vale para os dois
    # produtos. País que parou de informar sai da série inteira — a Índia,
    # depois de mar/2026 —, porque somá-lo só até onde ele vai faria o nível
    # cair sem nada ter caído; os ausentes vão para o subtítulo.
    def painel(paises, meses, fim):
        janela = [m for m in meses if m <= fim]
        return [p for p, d in paises.items() if all(m in d for m in janela)], janela

    fins = []
    for prod, paises in dados.items():
        meses = sorted({m for d in paises.values() for m in d})
        for k in range(len(meses) - 1, 2, -1):
            if len(painel(paises, meses, meses[k])[0]) >= 0.95 * len(painel(paises, meses, meses[k - 3])[0]):
                fins.append(meses[k])
                break
    fim = min(fins)
    fora = {}
    for prod, paises in dados.items():
        meses = sorted({m for d in paises.values() for m in d})
        p_fim, janela = painel(paises, meses, fim)
        # quem informava em 2025 e ficou fora do painel por ter parado
        sairam = sorted(p for p, d in paises.items() if p not in p_fim and "2025-12" in d
                        and d["2025-12"] > 300)
        fora[prod] = ({m: sum(paises[p][m] for p in p_fim) for m in janela}, len(p_fim), fim, sairam)
    return fora


def graficos_refino_mundo():
    r = refino_mundo()
    gas, n_g, fim_g, sai_g = r["GASOLINE"]
    die, n_d, fim_d, sai_d = r["GASDIES"]
    print("  JODI: gasolina %d países até %s, diesel %d países até %s; grandes fora: %s"
          % (n_g, fim_g, n_d, fim_d, sorted(set(sai_g) | set(sai_d))))
    fonte = "JODI e FtM"
    NOMES = {"IN": "Índia", "ID": "Indonésia", "KW": "Kuwait", "MY": "Malásia", "CN": "China",
             "US": "EUA", "RU": "Rússia", "SA": "Arábia Saudita", "KR": "Coreia do Sul", "JP": "Japão"}
    sairam = [NOMES.get(p, p) for p in sorted(set(sai_g) | set(sai_d))]
    nota_fora = ""
    if sairam:
        lista = sairam[0] if len(sairam) == 1 else ", ".join(sairam[:-1]) + " e " + sairam[-1]
        nota_fora = "; fora do painel por buraco na série: " + lista
    sub = ("Produção bruta das refinarias; soma de %d países com dado completo desde 2015"
           + nota_fora)
    return [
        dict(id="refino-mundo", titulo="Produção de diesel e gasolina nas refinarias do mundo",
             subtitulo=sub % min(n_g, n_d), unidade="kbd", fonte=fonte,
             variantes=[
                 dict(rot="Mil b/d", unidade="kbd", series=[
                     serie("Gasóleo/diesel (%d países)" % n_d, VERMELHO, die, 0, rotulo=True),
                     serie("Gasolina (%d países)" % n_g, AZUL, gas, 0, rotulo=True)]),
                 dict(rot="Média de 12 meses (mil b/d)", unidade="kbd", series=[
                     serie("Gasóleo/diesel (%d países)" % n_d, VERMELHO, media_12(die), 0, rotulo=True),
                     serie("Gasolina (%d países)" % n_g, AZUL, media_12(gas), 0, rotulo=True)]),
                 # o nível é de um painel, não do mundo; a variação é o que se compara
                 dict(rot="Variação anual (%)", unidade="%", series=[
                     serie("Gasóleo/diesel (%d países)" % n_d, VERMELHO, var_anual(die), 1, rotulo=True),
                     serie("Gasolina (%d países)" % n_g, AZUL, var_anual(gas), 1, rotulo=True)]),
             ]),
    ]


# Petróleo bruto no mundo: produção, exportação e exportação líquida no
# acumulado do ano contra o mesmo período do ano anterior (JODI, base primária)

PAISES_JODI = {
    "AE": "Emirados Árabes", "AO": "Angola", "AR": "Argentina", "AU": "Austrália", "AZ": "Azerbaijão",
    "BH": "Bahrein", "BN": "Brunei", "BO": "Bolívia", "BR": "Brasil", "CA": "Canadá", "CN": "China",
    "CO": "Colômbia", "DE": "Alemanha", "DK": "Dinamarca", "DZ": "Argélia", "EC": "Equador", "EG": "Egito",
    "FR": "França", "GA": "Gabão", "GB": "Reino Unido", "GY": "Guiana", "ID": "Indonésia", "IN": "Índia",
    "IQ": "Iraque", "IR": "Irã", "IT": "Itália", "JP": "Japão", "KR": "Coreia do Sul", "KW": "Kuwait",
    "KZ": "Cazaquistão", "LY": "Líbia", "MX": "México", "MY": "Malásia", "NG": "Nigéria", "NL": "Holanda",
    "NO": "Noruega", "NZ": "Nova Zelândia", "OM": "Omã", "PE": "Peru", "QA": "Catar", "RO": "Romênia",
    "RU": "Rússia", "SA": "Arábia Saudita", "SG": "Cingapura", "TH": "Tailândia", "TN": "Tunísia",
    "TR": "Turquia", "TT": "Trinidad e Tobago", "US": "EUA", "VE": "Venezuela", "VN": "Vietnã",
    "YE": "Iêmen", "HU": "Hungria", "PL": "Polônia", "ES": "Espanha",
}
# a Venezuela informa à JODI só parte da exportação (perto de 200 mil b/d
# contra os ~800 mil que ela de fato embarca): fica fora dos rankings de
# exportação, e entra no de produção
FORA_EXPORTACAO = {"VE"}
PISO_KBD = 100      # no ranking em %, só quem passa disso em 2025 (país pequeno distorce)


def jodi_bruto(desde="2025-01"):
    """{(país, fluxo): {mês: mil barris}} do petróleo bruto, de `desde` em diante."""
    zipado = os.path.join(CACHE_JODI, "world_primary_csv.zip")
    baixar(URL_JODI_PRIM, zipado)
    d = {}
    with zipfile.ZipFile(zipado) as z:
        nome = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        with z.open(nome) as bruto:
            for l in csv.DictReader(io.TextIOWrapper(bruto, encoding="utf-8", errors="replace")):
                if (l["ENERGY_PRODUCT"] != "CRUDEOIL" or l["UNIT_MEASURE"] != "KBBL"
                        or l["FLOW_BREAKDOWN"] not in ("INDPROD", "TOTEXPSB", "TOTIMPSB")
                        or l["TIME_PERIOD"] < desde):
                    continue
                try:
                    d.setdefault((l["REF_AREA"], l["FLOW_BREAKDOWN"]), {})[l["TIME_PERIOD"]] = float(l["OBS_VALUE"])
                except ValueError:
                    pass
    return d


def xlsx_steo(conteudo, aba, codigo):
    """{mês: mil b/d} de uma linha do STEO da EIA, só os meses históricos."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    textos = ["".join(t.text or "" for t in si.iter(ns + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    abas = {a.get("name"): rels[a.get(rns + "id")] for a in ET.fromstring(z.read("xl/workbook.xml")).iter(ns + "sheet")}

    def linhas(nome):
        alvo = abas[nome].lstrip("/")
        alvo = alvo if alvo.startswith("xl/") else "xl/" + alvo
        out = {}
        for c in ET.fromstring(z.read(alvo)).iter(ns + "c"):
            v = c.find(ns + "v")
            if v is not None and v.text is not None:
                ref = c.get("r")
                col = re.match(r"[A-Z]+", ref).group(0)
                out.setdefault(int(ref[len(col):]), {})[col] = textos[int(v.text)] if c.get("t") == "s" else v.text
        return out
    datas = linhas("Dates")
    def numero(c):
        for k in sorted(c, key=lambda x: (len(x), x)):
            try:
                return str(int(float(c[k])))
            except ValueError:
                pass
    ultimo = next(numero(c) for c in datas.values() if str(c.get("A", "")).startswith("Last Historical"))
    ultimo = ultimo[:4] + "-" + ultimo[4:]
    t = linhas(aba)
    MES = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
    ordem = lambda c: sum((ord(ch) - 64) * 26 ** k for k, ch in enumerate(reversed(c)))   # noqa: E731
    ano, cols = None, {}
    for c in sorted(t[4], key=ordem):
        ano = t[3].get(c, ano)
        if t[4][c] in MES and ano:
            cols[c] = "%s-%02d" % (ano, MES[t[4][c]])
    r = next(c for c in t.values() if c.get("A") == codigo)
    out = {}
    for c, m in cols.items():
        try:
            if m <= ultimo:
                out[m] = float(r[c]) * 1000
        except (KeyError, ValueError):
            pass
    return out


def dias_mes(m):
    return calendar.monthrange(int(m[:4]), int(m[5:]))[1]


def base_petroleo():
    """{(país, fluxo): {mês: mil barris}} desde 2002: a JODI, com os buracos
    dos países que comparamos ao Brasil cobertos por outras fontes.

      - Brasil: tudo da ANP (é dela que a JODI tira o Brasil, e falta 2023).
      - Guiana: a JODI erra o começo de 2025 (~890 mil b/d, quando o Ministério
        das Finanças informou ~640 mil) e tem buraco de 2017 a 2024. Fica a EIA
        (STEO), de 2022 em diante; exportação = produção (sem refinaria).
      - Argentina: produção de 2020 a 2024 do governo (datos.gob.ar, série
        363.3_PRODUCCIONUDO__28, igual à JODI onde as duas existem). A
        exportação desses anos fica em branco: não há o volume mensal aberto.
      - Rússia: produção da JODI até mar/2023 e depois a EIA (STEO, copr_rs),
        multiplicada pela razão média JODI/EIA de 2022 (~1,02, o condensado);
        exportação da JODI até dez/2021 e depois a do CREA (petróleo por navio e
        oleoduto, em toneladas, x 7,33 barris), multiplicada pela razão JODI/CREA
        de 2021 (~1,16: o rastreamento de navios não pega tudo).
      - Argentina, Guiana e Rússia não importam petróleo bruto: importação zero
        onde não há o dado."""
    d = jodi_bruto("2002-01")
    # Brasil, ANP
    for k in [k for k in d if k[0] == "BR"]:
        del d[k]
    p = producao_petroleo()
    d[("BR", "INDPROD")] = {m: (p["MAR"].get(m, 0) + p["TERRA"].get(m, 0)) * M3_BBL / 1000
                            for m in set(p["MAR"]) | set(p["TERRA"]) if m >= "2002-01"}
    for l in linhas_anp(URL_ANP_COMERCIO, "comercio-petroleo.csv"):
        if l["PRODUTO"].strip().upper() != "PETRÓLEO":
            continue
        m = "%s-%02d" % (l["ANO"], MES_NUM[l["MÊS"].strip().upper()[:3]])
        f = "TOTEXPSB" if l["OPERAÇÃO COMERCIAL"].strip().upper().startswith("EXP") else "TOTIMPSB"
        if m >= "2002-01":
            d.setdefault(("BR", f), {})[m] = float(l["IMPORTADO / EXPORTADO"].replace(",", ".") or 0) * M3_BBL / 1000
    steo = baixar(URL_STEO)
    # Guiana, EIA
    for k in [k for k in d if k[0] == "GY"]:
        del d[k]
    gy = {m: v * dias_mes(m) for m, v in xlsx_steo(steo, "3btab", "papr_GY").items()}
    d[("GY", "INDPROD")], d[("GY", "TOTEXPSB")] = gy, dict(gy)
    # Argentina, produção do governo onde a JODI tem buraco
    ar = json.loads(baixar(URL_AR_PROD).decode("utf-8"))["data"]
    prod_ar = d.setdefault(("AR", "INDPROD"), {})
    for data, v in ar:
        if v is not None and data[:7] not in prod_ar and data[:7] >= "2002-01":
            prod_ar[data[:7]] = v * 1000 * M3_BBL / 1000
    # Rússia
    ru_p = d.setdefault(("RU", "INDPROD"), {})
    eia = {m: v * dias_mes(m) for m, v in xlsx_steo(steo, "3dtab", "copr_rs").items()}
    comum = [m for m in eia if m in ru_p and m < "2023-01"]
    k_p = sum(ru_p[m] for m in comum) / sum(eia[m] for m in comum)
    for m, v in eia.items():
        if m not in ru_p:
            ru_p[m] = v * k_p
    crea = {}
    for r in json.loads(baixar(URL_CREA).decode("utf-8"))["data"]:
        if r["commodity"] in ("crude_oil", "pipeline_oil"):
            crea[r["month"][:7]] = crea.get(r["month"][:7], 0) + r["value_tonne"] * TONELADA_BBL / 1000
    ultimo_crea = max(crea)                     # o mês corrente vem pela metade
    crea.pop(ultimo_crea)
    ru_e = d.setdefault(("RU", "TOTEXPSB"), {})
    comum = [m for m in crea if m in ru_e and m.startswith("2021")]
    k_e = sum(ru_e[m] for m in comum) / sum(crea[m] for m in comum)
    for m, v in crea.items():
        if m not in ru_e:
            ru_e[m] = v * k_e
    # mês isolado que falta (a Rússia em 2013, a Argentina em 2017) apagaria
    # 12 médias de 12 meses: vira a média dos dois vizinhos
    for serie_ in d.values():
        for m in sorted(serie_):
            a, mm = int(m[:4]), int(m[5:])
            seg = "%04d-%02d" % (a + mm // 12, mm % 12 + 1)
            depois = "%04d-%02d" % (a + (mm + 1) // 12, (mm + 1) % 12 + 1)
            if seg not in serie_ and depois in serie_:
                serie_[seg] = (serie_[m] + serie_[depois]) / 2
    print("  base: Rússia produção x%.3f (EIA), exportação x%.3f (CREA)" % (k_p, k_e))
    return d


SEM_IMPORTACAO = {"AR", "GY", "RU"}     # não importam petróleo bruto
FONTE_PETROLEO_MUNDO = "JODI, ANP, EIA, CREA, Secretaría de Energía (Argentina) e FtM"


def liquida(d, pais):
    e, i = d.get((pais, "TOTEXPSB")), d.get((pais, "TOTIMPSB"), {})
    if not e:
        return None
    if pais in SEM_IMPORTACAO or not i:
        return {m: v - i.get(m, 0) for m, v in e.items()}
    return {m: v - i[m] for m, v in e.items() if m in i}


def soma_12(s):
    """{mês: média em mil b/d dos 12 meses até ele}, só com os 12 meses."""
    out = {}
    for m in s:
        a, mm = int(m[:4]), int(m[5:])
        janela = ["%04d-%02d" % (a + (mm - k - 1) // 12, (mm - k - 1) % 12 + 1) for k in range(12)]
        if all(j in s for j in janela):
            out[m] = sum(s[j] for j in janela) / sum(dias_mes(j) for j in janela)
    return out


PARES = [("BR", "Brasil", AMARELO), ("US", "EUA", BRANCO), ("CA", "Canadá", VERMELHO),
         ("NO", "Noruega", AZUL), ("GY", "Guiana", VERDE), ("AR", "Argentina", CIANO),
         ("SA", "Arábia Saudita", LARANJA), ("RU", "Rússia", ROXO)]


def graficos_pares(d):
    def series(fluxo, var, sem=()):
        out = []
        for pais, nome, cor in PARES:
            if pais in sem:
                continue
            s = liquida(d, pais) if fluxo == "LIQ" else d.get((pais, fluxo))
            if not s:
                continue
            m12 = soma_12(s)
            if var:
                # base pequena faz a variação explodir (EUA antes de 2016,
                # Argentina): só com mais de PISO_KBD nos 12 meses anteriores
                v = {m: x for m, x in var_anual({m: x for m, x in m12.items() if x > 0}).items()
                     if m12.get("%04d-%s" % (int(m[:4]) - 1, m[5:]), 0) >= PISO_KBD}
            else:
                v = m12
            if v:
                extra = dict(largura=6) if pais == "BR" else {}
                out.append(serie(nome, cor, v, 1 if var else 0, rotulo=pais == "BR" or not var, **extra))
        return out
    sub = "Petróleo bruto, média de 12 meses em mil barris por dia"
    fonte = FONTE_PETROLEO_MUNDO
    def grafico(id_, titulo, fluxo, sub_extra="", sem=(), eixo=None):
        var = dict(rot="Variação em 12 meses (%%), com base acima de %d mil b/d" % PISO_KBD, unidade="pct1",
                   series=series(fluxo, True, sem))
        if eixo:
            var["eixo"] = eixo      # picos de base pequena (EUA em 2015, Brasil líquido) saem do quadro
        return dict(id=id_, titulo=titulo, subtitulo=sub + sub_extra, unidade="kbd", fonte=fonte, variantes=[
            dict(rot="Mil b/d", unidade="kbd", series=series(fluxo, False, sem)), var])
    return [
        grafico("pares-producao-petroleo", "Produção de petróleo: o Brasil e os pares", "INDPROD"),
        grafico("pares-exportacao-petroleo", "Exportação de petróleo: o Brasil e os pares", "TOTEXPSB",
                "; Argentina sem dado de 2020 a 2024", eixo=dict(min=-60, max=100)),
        grafico("pares-exportacao-liquida-petroleo", "Exportação líquida de petróleo: o Brasil e os pares", "LIQ",
                "; exportação menos importação; Argentina sem dado de 2020 a 2024; EUA fora (importador líquido)",
                sem=("US",), eixo=dict(min=-60, max=100)),
    ]


def acumulado_ano(serie_, ano):
    """(meses de `ano` que têm o mesmo mês no ano anterior, média em mil b/d no
    ano anterior, média no ano) — None com menos de 3 meses."""
    ms = [m for m in sorted(serie_) if m.startswith(str(ano)) and "%d%s" % (ano - 1, m[4:]) in serie_]
    if len(ms) < 3:
        return None
    ant = ["%d%s" % (ano - 1, m[4:]) for m in ms]
    dias = lambda xs: sum(calendar.monthrange(int(m[:4]), int(m[5:]))[1] for m in xs)   # noqa: E731
    return ms, sum(serie_[m] for m in ant) / dias(ant), sum(serie_[m] for m in ms) / dias(ms)


def graficos_petroleo_mundo(d=None):
    d = d or jodi_bruto()
    ano = max(int(m[:4]) for s_ in d.values() for m in s_)
    linhas = {"INDPROD": [], "TOTEXPSB": [], "LIQ": []}
    for pais in {p for p, _ in d}:
        nome = PAISES_JODI.get(pais)
        if not nome:
            continue
        for fluxo in ("INDPROD", "TOTEXPSB"):
            r = d.get((pais, fluxo)) and acumulado_ano(d[(pais, fluxo)], ano)
            if r and r[1] > 0 and not (fluxo == "TOTEXPSB" and pais in FORA_EXPORTACAO):
                linhas[fluxo].append((pais, nome) + r)
        # exportação líquida: quem informa exportação e importação nos mesmos
        # meses e era exportador líquido no ano anterior. Quem não informa
        # importação nenhuma (Argentina, Guiana) não importa petróleo bruto:
        # conta como zero
        liq = liquida(d, pais)
        r = liq and acumulado_ano(liq, ano)
        if r and r[1] > 0 and pais not in FORA_EXPORTACAO:
            linhas["LIQ"].append((pais, nome) + r)
    fim_comum = max((r[2][-1] for r in linhas["INDPROD"]), key=lambda m: sum(r[2][-1] == m for r in linhas["INDPROD"]))

    def ranking(rows, chave, unidade, casas):
        ordem = sorted(rows, key=chave, reverse=True)
        def item(r, pos=None):
            pais, nome, ms = r[0], r[1], r[2]
            rot = nome + ("" if ms[-1] == fim_comum else " (até %s)" % MESES[int(ms[-1][5:]) - 1])
            if pos:
                rot += " (%dº)" % pos
            br = pais == "BR"
            return [rot, round(chave(r), casas), AMARELO if br else AZUL] + ([1] if br else [])
        top = [item(r) for r in ordem[:10]]
        if not any(r[0] == "BR" for r in ordem[:10]):
            pos = next((k + 1 for k, r in enumerate(ordem) if r[0] == "BR"), None)
            if pos:
                top.append(item(ordem[pos - 1], pos))
        rot = "Em %%, países acima de %d mil b/d em %d" % (PISO_KBD, ano - 1) if unidade == "pct1" else "Em mil barris por dia"
        return dict(rot=rot, unidade=unidade, itens=top)

    pct = lambda r: 100 * (r[4] / r[3] - 1)          # noqa: E731
    dif = lambda r: r[4] - r[3]                      # noqa: E731
    mes_fim = "%s/%s" % (MESES[int(fim_comum[5:]) - 1], fim_comum[2:4])
    sub = "Petróleo bruto, jan a %s de %d contra o mesmo período de %d" % (mes_fim.split("/")[0], ano, ano - 1)
    def grafico(id_, titulo, rows, extra=""):
        grandes = [r for r in rows if r[3] >= PISO_KBD]
        return dict(id=id_, tipo="ranking", titulo=titulo, subtitulo=sub + extra, unidade="pct1", sinal=True,
                    fonte=FONTE_PETROLEO_MUNDO, variantes=[ranking(grandes, pct, "pct1", 1), ranking(rows, dif, "kbd", 0)])
    for k, v in linhas.items():
        print("  JODI bruto %s: %d países, até %s na maioria" % (k, len(v), fim_comum))
    return [
        grafico("mundo-producao-petroleo", "Maiores variações na produção de petróleo em %d" % ano, linhas["INDPROD"]),
        grafico("mundo-exportacao-petroleo", "Maiores variações na exportação de petróleo em %d" % ano,
                linhas["TOTEXPSB"], "; sem a Venezuela, que informa só parte"),
        grafico("mundo-exportacao-liquida-petroleo", "Maiores variações na exportação líquida de petróleo em %d" % ano,
                linhas["LIQ"], "; exportação menos importação dos exportadores líquidos de %d" % (ano - 1)),
    ]


# --------------------------------------------------------------------------
# IBGE
# --------------------------------------------------------------------------

COMP = {"90707": "PIB", "93404": "Consumo das famílias", "93405": "Consumo do governo",
        "93406": "FBCF", "102880": "Variação de estoque", "93407": "Exportação", "93408": "Importação"}
TRI = {"1": "03", "2": "06", "3": "09", "4": "12"}


def sidra(tabela):
    url = ("https://apisidra.ibge.gov.br/values/t/%d/n1/all/v/all/p/all/c11255/%s"
           % (tabela, ",".join(COMP)))
    d = json.loads(baixar(url, headers={"User-Agent": "Mozilla/5.0 (ftm-analises)"}).decode("utf-8"))
    fora = {}
    for l in d[1:]:
        try:
            v = float(l["V"])
        except ValueError:
            continue
        mes = "%s-%s" % (l["D3C"][:4], TRI[l["D3C"][-1]])
        fora.setdefault(COMP[l["D4C"]], {})[mes] = v
    return fora


def soma4(d):
    ms = sorted(d)
    return {ms[i]: sum(d[m] for m in ms[i - 3:i + 1]) for i in range(3, len(ms))}


def taxa_4tri(codigos):
    """Taxa acumulada em 4 trimestres publicada pelo IBGE (SIDRA 5932, v6562),
    {nome: {mês: %}}."""
    url = ("https://apisidra.ibge.gov.br/values/t/5932/n1/all/v/6562/p/all/c11255/%s" % ",".join(codigos))
    d = json.loads(baixar(url, headers={"User-Agent": "Mozilla/5.0 (ftm-analises)"}).decode("utf-8"))
    fora = {}
    for l in d[1:]:
        try:
            fora.setdefault(COMP[l["D4C"]], {})["%s-%s" % (l["D3C"][:4], TRI[l["D3C"][-1]])] = float(l["V"])
        except (ValueError, KeyError):
            pass
    return fora


def graficos_pib():
    """Dois gráficos, sem conta que deixe resíduo:

      - contribuição para o crescimento do PIB NOMINAL em 4 trimestres:
        (componente_t − componente_t−4) ÷ PIB_t−4, somas de 4 trimestres a
        preços correntes (SIDRA 1846). Em valores correntes a ótica da demanda
        é aditiva — famílias + governo + FBCF + estoques + exportação −
        importação = PIB, conferido a cada rodada —, então as contribuições
        somam exatamente o crescimento nominal. Em volume (encadeado) isso
        não vale, e era daí que vinha o resíduo de estoques da versão anterior;
      - variação real em 4 trimestres que o próprio IBGE publica (SIDRA 5932)."""
    nominal = sidra(1846)
    n4 = {k: soma4(v) for k, v in nominal.items()}
    pior = max(abs(n4["Consumo das famílias"][m] + n4["Consumo do governo"][m] + n4["FBCF"][m]
                   + n4["Variação de estoque"].get(m, 0) + n4["Exportação"][m] - n4["Importação"][m]
                   - n4["PIB"][m]) / n4["PIB"][m] * 100 for m in n4["PIB"])
    if pior > 0.01:
        raise RuntimeError("a ótica da demanda não fecha o PIB nominal (%.3f%% do PIB)" % pior)
    comp = {
        "Consumo das famílias": n4["Consumo das famílias"],
        "Consumo do governo": n4["Consumo do governo"],
        "FBC (FBCF + estoques)": {m: n4["FBCF"][m] + n4["Variação de estoque"].get(m, 0) for m in n4["FBCF"]},
        "Exportações líquidas": {m: n4["Exportação"][m] - n4["Importação"][m] for m in n4["Exportação"]},
    }

    def ant(m):
        return "%04d-%s" % (int(m[:4]) - 1, m[5:])
    contrib = {k: {m: (d[m] - d[ant(m)]) / n4["PIB"][ant(m)] * 100 for m in d if ant(m) in d and ant(m) in n4["PIB"]}
               for k, d in comp.items()}
    pib = {m: (n4["PIB"][m] / n4["PIB"][ant(m)] - 1) * 100 for m in n4["PIB"] if ant(m) in n4["PIB"]}
    fecha = max(abs(sum(c[m] for c in contrib.values()) - pib[m]) for m in pib)
    print("  PIB nominal: contribuições somam o crescimento, diferença máxima %.4f p.p.; último %s %.1f%%"
          % (fecha, max(pib), pib[max(pib)]))
    taxa = taxa_4tri(["90707", "93407", "93408"])
    fonte = "IBGE e FtM"
    cores = {"Consumo das famílias": VERDE, "Consumo do governo": VERMELHO,
             "FBC (FBCF + estoques)": AZUL, "Exportações líquidas": LARANJA}
    return dict(titulo="PIB", graficos=[
        dict(id="pib-nominal-contribuicao", titulo="Contribuição para o crescimento do PIB nominal",
             subtitulo="p.p., acumulado em 4 trimestres contra os 4 anteriores, a preços correntes",
             unidade="pp", fonte=fonte, barra=2.6, buracoMax=3,
             series=[serie(k, cores[k], contrib[k], 2, tipo="barra") for k in comp]
             + [serie("PIB nominal (variação %)", BRANCO, pib, 2, rotulo=True)]),
        dict(id="pib-setor-externo-real", titulo="Variação real da exportação e da importação",
             subtitulo="% acumulada em 4 trimestres contra os 4 anteriores", unidade="%", fonte=fonte,
             buracoMax=3,
             series=[serie("Exportação", AZUL, taxa["Exportação"], 1, rotulo=True),
                     serie("Importação", LARANJA, taxa["Importação"], 1, rotulo=True),
                     serie("PIB", CINZA, taxa["PIB"], 1, rotulo=True, traco="pontilhado", largura=4)]),
    ])


def brent():
    txt = baixar(URL_BRENT, headers={}).decode("utf-8")
    fora = {}
    for l in csv.DictReader(io.StringIO(txt)):
        chave = [k for k in l if k.lower() != "observation_date" and k.upper() != "DATE"][0]
        try:
            fora[(l.get("observation_date") or l.get("DATE"))[:7]] = float(l[chave])
        except ValueError:
            pass
    return fora


# --------------------------------------------------------------------------
# conta corrente (BC)
# --------------------------------------------------------------------------

URL_BP = "https://www.bcb.gov.br/content/estatisticas/Documents/Tabelas_especiais/BalPagM.xlsx"
COD_CC = dict(cc=22701, comercial=22707, servicos=22719, renda1=22800, renda2=22838)

# RPM de setembro de 2026, boxe "Projeções para a evolução das contas
# externas", Tabela 1, coluna "Proj. 2026 Atual", US$ bilhões. A renda
# secundária não está na tabela: é o que fecha a conta (−60 − 75 + 56 + 85).
PROJ_BC = dict(mes="2026-12", rpm="RPM de setembro de 2026", cc=-60.0, comercial=75.0,
               servicos=-56.0, renda1=-85.0)
PROJ_BC["renda2"] = PROJ_BC["cc"] - PROJ_BC["comercial"] - PROJ_BC["servicos"] - PROJ_BC["renda1"]
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MESES_BP = {m: i + 1 for i, m in enumerate(MESES)}


def tabela_bp():
    """{código SGS: {mês: US$ milhões}} da primeira aba do BalPagM.xlsx."""
    corpo = baixar(URL_BP)
    if not corpo.startswith(b"PK"):
        raise RuntimeError("a tabela do BC não veio como .xlsx")
    z = zipfile.ZipFile(io.BytesIO(corpo))
    textos = ["".join(x.text or "" for x in si.iter(NS + "t"))
              for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    aba = next(ET.fromstring(z.read("xl/workbook.xml")).iter(NS + "sheet"))
    alvo = rels[aba.get(RNS + "id")].lstrip("/")
    alvo = alvo if alvo.startswith("xl/") else "xl/" + alvo

    def col(ref):
        n = 0
        for ch in re.match(r"[A-Z]+", ref).group(0):
            n = n * 26 + ord(ch) - 64
        return n
    linhas = {}
    for c in ET.fromstring(z.read(alvo)).iter(NS + "c"):
        v = c.find(NS + "v")
        if v is None or v.text is None:
            continue
        val = textos[int(v.text)] if c.get("t") == "s" else v.text
        linhas.setdefault(int(re.search(r"\d+", c.get("r")).group(0)), {})[col(c.get("r"))] = val
    lm = next(r for r in sorted(linhas) if "Jan" in linhas[r].values())
    ano, meses = None, {}
    for c in sorted(linhas[lm]):
        if str(linhas.get(lm - 1, {}).get(c, "")).strip().isdigit():
            ano = int(str(linhas[lm - 1][c]).strip())
        m = MESES_BP.get(str(linhas[lm][c]).strip().lower()[:3])
        if m and ano:
            meses[c] = "%04d-%02d" % (ano, m)
    col_cod = next(c for r in (lm - 1, lm) for c, x in linhas.get(r, {}).items() if "digo no SGS" in str(x))
    fora = {}
    for cel in linhas.values():
        cod = str(cel.get(col_cod, "")).strip()
        if cod.isdigit() and int(cod) not in fora:
            d = {}
            for c, mes in meses.items():
                try:
                    d[mes] = float(cel[c])
                except (KeyError, ValueError):
                    pass
            fora[int(cod)] = d
    return fora


def graficos_conta_corrente():
    s = tabela_bp()
    def a12(d):
        ms = sorted(d)
        return {ms[i]: sum(d[m] for m in ms[i - 11:i + 1]) / 1000 for i in range(11, len(ms))}
    acc = {k: a12(s[c]) for k, c in COD_CC.items()}
    soma = max(abs(sum(acc[k][m] for k in ("comercial", "servicos", "renda1", "renda2")) - acc["cc"][m])
               for m in acc["cc"])
    print("  conta corrente até %s: os componentes somam o saldo, diferença máxima US$ %.4f bi"
          % (max(acc["cc"]), soma))
    if soma > 0.001:
        raise RuntimeError("os componentes da conta corrente não somam o saldo")
    ult = max(acc["cc"])
    nomes = [("comercial", "Balança Comercial", AZUL), ("servicos", "Serviços", VERMELHO),
             ("renda1", "Renda Primária", VERDE), ("renda2", "Renda Secundária", AZUL_ESCURO)]
    series = [serie(n, c, acc[k], 2, tipo="barra") for k, n, c in nomes]
    series.append(serie("Saldo Conta Corrente", BRANCO, acc["cc"], 2, rotulo=True))
    m = PROJ_BC["mes"]
    if m > ult:                               # o ano fechou: a projeção sai sozinha
        series += [serie(n + " (proj. BC)", c, {m: PROJ_BC[k]}, 2, tipo="barra", opacidade=0.4, legenda=False)
                   for k, n, c in nomes]
        series.append(serie("Projeção do BC para 2026 (%s)" % PROJ_BC["rpm"], CINZA,
                            {ult: acc["cc"][ult], m: PROJ_BC["cc"]}, 2, traco="pontilhado", rotulo=True))
    return dict(titulo="Conta corrente", graficos=[
        dict(id="conta-corrente-projecao", titulo="Conta Corrente do Brasil",
             subtitulo="US$ bilhões, acumulado em 12 meses; em dez/2026, a projeção do BC",
             unidade="usd-bi", fonte="Banco Central e FtM", barra=1, buracoMax=5, series=series),
    ])


# --------------------------------------------------------------------------
# diesel importado: origem e importador (ANP, Relatório de Desembaraços)
# --------------------------------------------------------------------------

# O line up da Abicom (navios de diesel S10 programados para o mês, mil m³),
# revisão de 29/09/2026. A Abicom não publica série: é um retrato, digitado
# do quadro dela, que entra apagado nos meses que a ANP ainda não fechou.
# Trocar a cada revisão. Só S10 — o realizado da ANP inclui o S500.
LINE_UP = dict(revisao="29/09/2026", meses={
    "2026-09": {"EUA": 754.0, "Rússia": 27.0, "Índia": 126.2, "Golfo Árabe": 0.0, "Outros": 28.5,
                "Petrobras": 365.2, "Outras empresas": 570.5},
    "2026-10": {"EUA": 562.2, "Rússia": 16.7, "Índia": 207.8, "Golfo Árabe": 43.9, "Outros": 0.0,
                "Petrobras": 407.1, "Outras empresas": 423.5},
})
GOLFO = ("EMIRADOS ARABES", "ARABIA SAUDITA", "OMA", "KUWAIT", "BAREIN", "BAHREIN", "CATAR", "QATAR",
         "IRAQUE")
ORIGENS = [("EUA", AZUL), ("Rússia", VERMELHO), ("Índia", LARANJA), ("Golfo Árabe", AREIA), ("Outros", CINZA)]


def origem(pais):
    import unicodedata
    p = "".join(c for c in unicodedata.normalize("NFD", pais or "") if unicodedata.category(c) != "Mn")
    p = p.upper().strip()
    if p == "ESTADOS UNIDOS":
        return "EUA"
    if p == "RUSSIA":
        return "Rússia"
    if p == "INDIA":
        return "Índia"
    if any(p == g or p.startswith(g) for g in GOLFO):
        return "Golfo Árabe"
    return "Outros"


def diesel_importado():
    """({mês: {origem: mil m³}}, {mês: {"Petrobras"|"Outras empresas": mil m³}}).

    Mesmo arquivo e mesma conta do planilhas/scripts/oferta_diesel.py (kg ÷
    0,84 t/m³), lido aqui com o país de origem. O ano corrente é baixado de
    novo se o arquivo tiver mais de 5 dias: a ANP republica o mesmo .xlsx
    a cada mês."""
    import datetime as dt
    sys_path = os.path.join(RAIZ, "planilhas", "scripts")
    import sys
    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    import anp_desembaracos as ad
    cache = os.path.join(RAIZ, "planilhas", "dados", ".cache-anp-oferta")
    atual = os.path.join(cache, "desembaraco-%d.xlsx" % dt.date.today().year)
    if os.path.exists(atual) and time.time() - os.path.getmtime(atual) > 5 * 86400:
        os.remove(atual)
    por_origem, por_quem = {}, {}
    for ano in ad.anos(cache):
        for r in ad.linhas(ano, cache):
            if r["ncm"] != ad.NCM_DIESEL:
                continue
            m3 = r["kg"] / 1000 / ad.DENSIDADE[ad.NCM_DIESEL] / 1000
            o = por_origem.setdefault(r["mes"], {})
            o[origem(r["pais"])] = o.get(origem(r["pais"]), 0.0) + m3
            k = "Petrobras" if ad.classe(r["importador"]) == "Petrobras" else "Outras empresas"
            q = por_quem.setdefault(r["mes"], {})
            q[k] = q.get(k, 0.0) + m3
    return por_origem, por_quem


def graficos_diesel_importado():
    por_origem, por_quem = diesel_importado()
    ult = max(por_origem)
    pior = max(abs(sum(por_origem[m].values()) - sum(por_quem.get(m, {}).values())) for m in por_origem)
    print("  diesel importado (ANP) até %s: %.0f mil m³ no mês; origem e importador somam igual (máx %.4f)"
          % (ult, sum(por_origem[ult].values()), pior))

    def pct(d):
        return {m: {k: v / sum(x.values()) * 100 for k, v in x.items()} for m, x in d.items() if sum(x.values())}

    def series(d, grupos, unidade_pct):
        out = [serie(n, c, {m: x.get(n, 0.0) for m, x in d.items()}, 1, tipo="barra") for n, c in grupos]
        lu = {m: x for m, x in LINE_UP["meses"].items() if m > ult}
        if lu:
            if unidade_pct:
                lu = pct({m: {n: x[n] for n, _ in grupos} for m, x in lu.items()})
            out += [serie(n + " (line up Abicom)", c, {m: x[n] for m, x in lu.items()}, 1, tipo="barra",
                          opacidade=0.35, legenda=False) for n, c in grupos]
        return out

    quem = [("Petrobras", VERDE), ("Outras empresas", AZUL_ESCURO)]
    nota = "; meses apagados: line up da Abicom de %s, só S10" % LINE_UP["revisao"]
    fonte = "ANP, Abicom e FtM"
    return dict(titulo="Diesel importado", graficos=[
        dict(id="diesel-importado-origem", titulo="Importação de diesel por origem",
             subtitulo="Mil m³, mensal, desembaraçado" + nota, unidade="mil m³", fonte=fonte, barra=0.8,
             variantes=[dict(rot="Mil m³", unidade="mil m³", series=series(por_origem, ORIGENS, False)),
                        dict(rot="% do total", unidade="%", eixo=dict(max=100),
                             series=series(pct(por_origem), ORIGENS, True))]),
        dict(id="diesel-importado-petrobras", titulo="Importação de diesel: Petrobras e outras empresas",
             subtitulo="Mil m³, mensal, desembaraçado" + nota, unidade="mil m³", fonte=fonte, barra=0.8,
             variantes=[dict(rot="Mil m³", unidade="mil m³", series=series(por_quem, quem, False)),
                        dict(rot="% do total", unidade="%", eixo=dict(max=100),
                             series=series(pct(por_quem), quem, True))]),
    ])


# --------------------------------------------------------------------------
# termos de troca (Funcex, via Ipeadata)
# --------------------------------------------------------------------------

URL_IPEA = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='%s')"


def termos_de_troca():
    """Funcex, "Termos de troca - índice (média 2018 = 100)", FUNCEX12_TTR12:
    preço das exportações ÷ preço das importações, mensal desde 1978."""
    d = json.loads(baixar(URL_IPEA % "FUNCEX12_TTR12", headers={}).decode("utf-8"))["value"]
    serie_ = {x["VALDATA"][:7]: float(x["VALVALOR"]) for x in d if x["VALVALOR"] is not None}
    print("  termos de troca até %s: %.1f" % (max(serie_), serie_[max(serie_)]))
    return dict(titulo="Termos de troca", graficos=[
        dict(id="termos-de-troca", titulo="Termos de troca do Brasil",
             subtitulo="Preço das exportações ÷ preço das importações, índice (média de 2018 = 100)",
             unidade="pts", fonte="Funcex (Ipeadata) e FtM", eixo=dict(zero=False),
             variantes=[dict(rot="Mensal", unidade="pts", series=[serie("Termos de troca", BRANCO, serie_, 1,
                                                                          rotulo=True)]),
                        dict(rot="Média de 12 meses", unidade="pts",
                             series=[serie("Termos de troca", BRANCO, media_12(serie_), 1, rotulo=True)])]),
    ])


def secoes_extra():
    print("Conta corrente (BC)…")
    cc = graficos_conta_corrente()
    print("ANP…")
    diesel = graficos_diesel_importado()
    prod = graficos_producao()
    refino = graficos_refino_brasil()
    print("JODI…")
    mundo = graficos_refino_mundo()
    print("JODI, petróleo bruto…")
    base = base_petroleo()
    bruto = dict(titulo="Petróleo no mundo", graficos=graficos_petroleo_mundo(base) + graficos_pares(base))
    print("IBGE…")
    pib = graficos_pib()
    return [cc, diesel, prod, bruto, dict(titulo="Refino", graficos=refino + mundo), pib]


if __name__ == "__main__":
    for s in secoes_extra():
        for g in s["graficos"]:
            ss = g.get("series") or g["variantes"][0]["series"]
            print(g["id"], "; ".join("%s=%s" % (x["nome"][:20], x["dados"][-1]) for x in ss if x["dados"]))

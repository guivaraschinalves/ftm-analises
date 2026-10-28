#!/usr/bin/env python3
"""
Monta dados/cenario-2026-10-28-fomc.json, a análise de cenário "28/10/26 -
Decisão do FOMC": inflação, mercado de trabalho, atividade, moeda, contas do
governo, crédito, data centers, fluxo de capital e juros dos bancos centrais.

Uso:
    python3 scripts/cenario_fomc.py

Só biblioteca padrão. Rodado à mão: é o retrato de uma data, não um painel que
se atualiza sozinho. O texto vem de textos/cenario-2026-10-28-fomc.md
(aplicar_texto, no fim).

AS FONTES E AS ARMADILHAS DE CADA UMA

  - FRED (fredgraph.csv, sem chave): quase tudo. Trava (timeout, não 403)
    quando a requisição manda User-Agent próprio ou de navegador. Com o
    padrão do urllib responde em menos de um segundo. Uma série por pedido:
    num lote, um id inexistente derruba o lote inteiro com 404.
    As séries de spread da ICE BofA no FRED só têm os últimos 3 anos (é a
    licença).
  - CPI em 12 meses usa o índice SEM ajuste sazonal (CPIAUCNS, CPILFENS), que
    é o número oficial. Com ajuste, o 12 meses de set/26 sai 4,0% em vez de
    3,7%: o fator sazonal é revisto e a conta não fecha com o divulgado. Mês a
    mês e 3 meses anualizado usam o índice com ajuste.
  - PPI por componente: API pública do BLS (v1, sem chave, 25 séries e 25
    pedidos por dia). O FRED só tem parte dos códigos WPSFD4xx.
  - ISM: o histórico não está no FRED desde 2016. Vem do gráfico de eventos
    do investing.com (manufatura desde 1970, serviços desde 1997). A data ali
    é a da divulgação, no 1º dia útil do mês seguinte: o mês de referência é
    o anterior.
  - CPI por componente: Excel do Fed de San Francisco ("CPI inflation
    contributions from goods and services"). O link muda a cada atualização;
    o script o acha na página.
  - Contas do governo: MTS do Tesouro (FRED para a série mensal; a API Fiscal
    Data, tabela 9, para receita por fonte e despesa por função).
  - Data centers: planilha de construção privada do Census (privsatime.xlsx),
    em taxa anual com ajuste sazonal. Não inclui servidores nem racks: é o
    prédio e a obra.
  - TIC: dois arquivos do Tesouro emendados, o antigo (s1_globl, de 1977 a
    jan/2023) e a tabela 1 do SLT (de fev/2023 em diante).    Conferido contra o balanço de pagamentos (BEA, via FMI): correlação de
    0,90 nos totais anuais; a diferença grande é 2020, quando estrangeiros
    compraram T-bills, que a TIC de longo prazo não pega.
  - Juros dos bancos centrais: BIS (WS_CBPOL, diário, uma semana de atraso).
    O Fed vem do FRED (teto da faixa, DFEDTARU), que sai no mesmo dia.
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
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
NOME = "cenario-2026-10-28-fomc"
SAIDA = os.path.join(RAIZ, "dados", NOME + ".json")

ASSUNTO = "28/10/26 - Decisão do FOMC"
GRUPO = "Análise de Cenário"

BRANCO, AZUL, VERMELHO, VERDE, ROXO, CIANO, LARANJA = (
    "#FFFFFF", "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6", "#F79646")
AMARELO, CINZA, AREIA, AZUL_ESCURO = "#FFFF00", "#95A5A6", "#D9B382", "#1F497D"

NAVEGADOR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/131.0 Safari/537.36"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


# ---------------------------------------------------------------- download

def baixar(url, headers=None, dados=None, tentativas=4):
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, data=dados, headers=headers or {})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:                       # noqa: BLE001
            ultimo = e
            time.sleep(2 * (i + 1))
    raise RuntimeError("não deu para baixar %s: %s" % (url, ultimo))


_FRED = {}


def fred(sid, mensal=True):
    """{chave: valor}; chave "AAAA-MM" se mensal, senão "AAAA-MM-DD".
    Sem headers: com User-Agent o FRED trava."""
    if (sid, mensal) in _FRED:
        return _FRED[(sid, mensal)]
    txt = baixar("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + sid).decode("utf-8-sig")
    linhas = list(csv.reader(io.StringIO(txt)))
    if sid not in linhas[0][1]:
        raise RuntimeError("cabeçalho inesperado em %s: %r" % (sid, linhas[0]))
    out = {}
    for d, v in (l[:2] for l in linhas[1:] if len(l) >= 2):
        if v.strip() in ("", "."):
            continue
        out[d[:7] if mensal else d] = float(v)
    _FRED[(sid, mensal)] = out
    return out


def bls(ids, ini, fim):
    """API pública do BLS (v1): {id: {"AAAA-MM": valor}}."""
    out = {}
    for i in range(0, len(ids), 25):
        corpo = json.dumps({"seriesid": ids[i:i + 25], "startyear": str(ini), "endyear": str(fim)}).encode()
        r = json.loads(baixar("https://api.bls.gov/publicAPI/v1/timeseries/data/", dados=corpo,
                              headers={"Content-Type": "application/json"}))
        if r.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError("BLS: %s" % r.get("message"))
        for s in r["Results"]["series"]:
            out[s["seriesID"]] = {d["year"] + "-" + d["period"][1:]: float(d["value"])
                                  for d in s["data"] if re.match(r"M(0[1-9]|1[0-2])$", d["period"])}
    return out


# ---------------------------------------------------------------- contas

def mes_mais(m, k):
    a, mm = int(m[:4]), int(m[5:7]) - 1 + k
    return "%04d-%02d" % (a + mm // 12, mm % 12 + 1)


def var(s, n=12):
    """% sobre n meses antes."""
    return {m: 100 * (v / s[mes_mais(m, -n)] - 1) for m, v in s.items() if mes_mais(m, -n) in s}


def anualizado(s, n=3):
    return {m: 100 * ((v / s[mes_mais(m, -n)]) ** (12 / n) - 1) for m, v in s.items() if mes_mais(m, -n) in s}


def dif(s, n=1):
    return {m: v - s[mes_mais(m, -n)] for m, v in s.items() if mes_mais(m, -n) in s}


def media(s, n=3):
    """Média móvel dos n períodos até cada um (só onde os n existem)."""
    ks = sorted(s)
    return {ks[i]: sum(s[k] for k in ks[i - n + 1:i + 1]) / n for i in range(n - 1, len(ks))}


def soma12(s):
    ks = sorted(s)
    return {ks[i]: sum(s[k] for k in ks[i - 11:i + 1]) for i in range(11, len(ks))
            if mes_mais(ks[i - 11], 11) == ks[i]}


def desde(s, ini):
    return {k: v for k, v in s.items() if k >= ini}


def serie(nome, cor, dados, casas=2, **extra):
    return dict(nome=nome, cor=cor, dados=[[k, round(v, casas)] for k, v in sorted(dados.items())], **extra)


def br(v, casas=1, sinal=False):
    v = round(v, casas) + 0.0          # sem "-0,0"
    if v == 0:
        v = 0.0
    t = ("%+.*f" if sinal else "%.*f") % (casas, v)
    return t.replace(".", ",")


def rot_mes(m):
    return "%s/%s" % (MESES[int(m[5:7]) - 1], m[2:4])


def ultimo(s):
    k = max(s)
    return k, s[k]


# recessões do NBER (USREC): faixas cinza atrás das linhas
def recessoes(diario=False):
    r = fred("USREC")
    ks = sorted(k for k in r if k >= "1913-01")
    faixas, ini = [], None
    for k in ks:
        if r[k] == 1 and ini is None:
            ini = k
        if r[k] == 0 and ini is not None:
            faixas.append((ini, mes_mais(k, -1)))
            ini = None
    if ini is not None:
        faixas.append((ini, ks[-1]))
    if not diario:
        return [dict(de=a, ate=b) for a, b in faixas]
    fim_mes = lambda m: (datetime.date(int(m[:4]), int(m[5:7]), 1).replace(day=28)        # noqa: E731
                         + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    return [dict(de=a + "-01", ate=fim_mes(b).isoformat()) for a, b in faixas]


SUB_RECESSAO = "faixas cinza = recessões (NBER)"


# ================================================================ inflação

def graficos_inflacao():
    rec = recessoes()
    cheio, nucleo = var(fred("CPIAUCNS")), var(fred("CPILFENS"))
    g1 = dict(id="cpi-cheio-nucleo", titulo="Inflação ao consumidor (CPI): cheio e núcleo",
              subtitulo="%% em 12 meses; núcleo = sem alimentos e energia; %s" % SUB_RECESSAO,
              unidade="%", fonte="BLS, NBER (via FRED) e FtM", sombras=rec, periodoPadrao="tudo",
              series=[serie("CPI cheio", BRANCO, desde(cheio, "1958-01"), rotulo=True),
                      serie("Núcleo", LARANJA, desde(nucleo, "1958-01"), rotulo=True)])

    npce = var(fred("PCEPILFE"))
    comum = {m: nucleo[m] - npce[m] for m in npce if m in nucleo}
    g4 = dict(id="nucleo-pce-cpi", titulo="Núcleo do PCE e núcleo do CPI",
              subtitulo="Sem alimentos e energia; %s" % SUB_RECESSAO, unidade="%",
              fonte="BLS, BEA, NBER (via FRED) e FtM", sombras=rec, variantes=[
                  dict(rot="% em 12 meses", series=[
                      serie("Núcleo do CPI", LARANJA, desde(nucleo, "1960-01"), rotulo=True),
                      serie("Núcleo do PCE", CIANO, desde(npce, "1960-01"), rotulo=True)]),
                  dict(rot="Diferença, CPI menos PCE, p.p.", unidade="pp", series=[
                      serie("CPI menos PCE", AZUL, desde(comum, "1960-01"), tipo="barra", legenda=False)]),
              ])
    return [g1] + graficos_frbsf() + [graficos_frbsf_pce(), g4, tabela_ppi()]


# ---- contribuições por componente: Fed de San Francisco
#
# A página "CPI inflation contributions from goods and services" publica um
# Excel com a contribuição de cada grupo para o CPI (12 meses sem ajuste
# sazonal; mês com ajuste) e de cada um dos 68 itens do núcleo para o núcleo
# no mês. O link do Excel muda o "?data" a cada atualização: o script o acha
# na própria página. O total do último mês às vezes vem "NA" antes dos
# componentes; a linha do total sai da aba do CPI cheio, que é a oficial.
FRBSF_PAGINA = ("https://www.frbsf.org/research-and-insights/data-and-indicators/"
                "cpi-inflation-contributions-from-goods-and-services/")
FRBSF_GRUPOS = [("Alimentos", "Food", VERDE), ("Energia", "Energy", AMARELO), ("Bens do núcleo", "Core Goods", AZUL),
                ("Serviços sem moradia", "Core Services ex. Shelter", LARANJA), ("Moradia", "Shelter", CIANO)]
ITENS_NUCLEO = {
    "Alcoholic beverages at home": "Bebidas alcoólicas em casa", "Alcoholic beverages away from home": "Bebidas alcoólicas fora",
    "Appliances": "Eletrodomésticos", "Educational books and supplies": "Livros e material escolar",
    "Footwear": "Calçados", "Furniture and bedding": "Móveis e cama", "Housekeeping supplies": "Produtos de limpeza",
    "Infants and toddlers apparel": "Roupa infantil", "IT commodities": "Informática",
    "Jewelry and watches": "Joias e relógios", "Medical equipment and supplies": "Equipamento médico",
    "Mens and boys apparel": "Roupa masculina", "Misc. personal goods": "Outros bens pessoais",
    "Motor vehicle parts and equipment": "Peças de veículos", "New vehicles": "Carros novos",
    "Nonprescription drugs": "Remédios sem receita", "Other HH equipment and furnishings": "Outros itens do lar",
    "Other recreational goods": "Outros bens de lazer", "Personal care products": "Higiene pessoal",
    "Pets and pet products": "Animais e produtos pet", "Photographic equipment and supplies": "Equipamento fotográfico",
    "Prescription drugs": "Remédios com receita", "Recreational reading materials": "Livros e revistas",
    "Sporting goods": "Artigos esportivos", "Tobacco and smoking products": "Cigarros e fumo",
    "Tools, hardware, outdoor equipment": "Ferramentas e jardim", "Used cars and trucks": "Carros usados",
    "Video and audio products": "Áudio e vídeo", "Window and floor coverings": "Cortinas e pisos",
    "Womens and girls apparel": "Roupa feminina", "Housing at school, excluding board": "Moradia estudantil",
    "Other lodging, incl. hotels": "Hotéis e hospedagem", "Owners equivalent rent of residences": "Aluguel imputado (OER)",
    "Rent of primary residence": "Aluguel", "Tenants and household insurance": "Seguro residencial",
    "Airline fares": "Passagens aéreas", "Cable, satellite, other TV service": "TV por assinatura",
    "Car and truck rental": "Aluguel de carros", "Care of invalids and elderly at home": "Cuidador em casa",
    "College tuition and fees": "Mensalidade universitária", "Day care and preschool": "Creche e pré-escola",
    "Dental services": "Dentista", "Elementary and high school tuition": "Mensalidade escolar",
    "Eyeglasses and eye care": "Óculos e oftalmologia", "Garbage and trash collection": "Coleta de lixo",
    "Health insurance": "Plano de saúde", "Hospital services": "Hospital", "Internet services": "Internet",
    "Intracity transportation": "Transporte urbano", "Misc. personal services": "Outros serviços pessoais",
    "Motor vehicle fees": "Taxas de veículos", "Motor vehicle insurance": "Seguro de carro",
    "Motor vehicle maintenance and repair": "Manutenção de carro", "Nursing homes and adult day services": "Casas de repouso",
    "Other intercity transportation": "Transporte intermunicipal", "Other recreation services": "Outros serviços de lazer",
    "Personal care services": "Cabeleireiro e estética", "Pet services including veterinary": "Veterinário",
    "Photos and photo processing": "Revelação de fotos", "Physicians services": "Consultas médicas",
    "Postage and delivery services": "Correio e entregas", "Residential telephone services": "Telefone fixo",
    "Services by other medical professionals": "Outros profissionais de saúde",
    "Technical & bus. school tuition": "Cursos técnicos", "Video rentals/subscriptions": "Streaming e locação de vídeo",
    "Water and sewerage maintenance": "Água e esgoto", "Wireless telephone services": "Celular"}


def data_excel(v):
    return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(v)))).isoformat()[:7]


def numero(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None                                      # "NA" e vazio


def frbsf_excel(pagina_url, arquivo):
    """Função que lê uma aba do Excel do FRBSF: {"AAAA-MM": {coluna: valor}}.
    O link tem um "?data" que muda a cada atualização, e às vezes vem
    relativo ("/wp-content/..."): por isso sai da página."""
    pagina = baixar(pagina_url, headers=NAVEGADOR).decode("utf-8", "replace")
    url = re.search(r'href="([^"]*%s[^"]*)"' % re.escape(arquivo), pagina).group(1).replace("&amp;", "&")
    conteudo = baixar(urllib.parse.urljoin(pagina_url, url), headers=NAVEGADOR)

    def aba(nome, col_data="A"):
        linhas = xlsx_aba(conteudo, nome)
        cab = min(linhas)
        nomes = {c: str(v).strip() for c, v in linhas[cab].items()}
        out = {}
        for r in sorted(linhas):
            if r == cab or col_data not in linhas[r]:
                continue
            m = data_excel(linhas[r][col_data])
            out[m] = {nomes[c]: numero(v) for c, v in linhas[r].items() if c in nomes and c != col_data}
        return out
    return aba


def graficos_frbsf():
    aba = frbsf_excel(FRBSF_PAGINA, "cpi-contributors-data.xlsx")
    a12, am = aba("chart2_headlineCPI_contr_YoY"), aba("chart4_headlineCPI_contr_MoM")
    t12, tm = aba("chart1_CPI_YoY"), aba("chart3_CPI_MoM")

    def variante(rot, contr, total, chave_total, ini):
        series = [serie(n, cor, {m: r[k] for m, r in contr.items() if m >= ini and r.get(k) is not None}, 2, tipo="barra")
                  for n, k, cor in FRBSF_GRUPOS]
        series.append(serie("CPI cheio", BRANCO, {m: r[chave_total] for m, r in total.items()
                                                    if m >= ini and r.get(chave_total) is not None}, 2, rotulo=True))
        return dict(rot=rot, series=series)
    ult = max(m for m, r in a12.items() if r.get("Energy") is not None)
    g = dict(id="cpi-componentes", titulo="Contribuição de cada componente para a inflação ao consumidor (CPI)",
             subtitulo="Barras = contribuição em p.p.; linha = CPI cheio, %; núcleo = sem alimentos e energia",
             unidade="%", barra=1, periodoPadrao="5",
             fonte="Federal Reserve Bank of San Francisco, BLS e FtM",
             nota="Não há CPI de out/25: o BLS não coletou preços durante a paralisação do governo americano.",
             variantes=[variante("em 12 meses, sem ajuste sazonal", a12, t12, "Headline CPI, YoY", "1999-01"),
                        variante("no mês, com ajuste sazonal", am, tm, "Headline CPI, MoM", "1999-01")])

    itens = aba("chart5_coreCPI_granularCont_MoM", "B")
    m = max(k for k, r in itens.items() if sum(v is not None for v in r.values()) > 30)
    r = {k.split(": ", 1)[1]: v for k, v in itens[m].items() if ": " in k and not k.startswith("Total") and v is not None}
    falta = [k for k in r if k not in ITENS_NUCLEO]
    if falta:
        raise RuntimeError("itens do núcleo sem tradução: %s" % falta)
    ordem = sorted(r.items(), key=lambda kv: -kv[1])
    escolha = ordem[:10] + ordem[-5:]
    total = tm[m]["Core CPI, MoM"]
    g_itens = dict(id="cpi-nucleo-itens", tipo="ranking", sinal=True, unidade="pb",
                   titulo="Os itens que mais pesaram no núcleo do CPI em %s" % rot_mes(m),
                   subtitulo="Contribuição para a variação do núcleo no mês, em pontos-base; núcleo %s%% no mês; "
                             "os 10 maiores e os 5 menores de 68 itens" % br(total, 2, True),
                   fonte="Federal Reserve Bank of San Francisco, BLS e FtM",
                   itens=[[ITENS_NUCLEO[k], round(100 * v, 1), VERMELHO if v > 0 else AZUL] for k, v in escolha])
    print("  FRBSF: contribuições até %s, itens do núcleo até %s" % (ult, m))
    return [g, g_itens]


FRBSF_PCE = ("https://www.frbsf.org/research-and-insights/data-and-indicators/"
             "pce-inflation-contributions-from-goods-and-services/")
PCE_GRUPOS = {"Energy": ("Energia", AMARELO), "Food": ("Alimentos", VERDE), "Core Goods": ("Bens do núcleo", AZUL),
              "Core Services exc. Housing": ("Serviços sem moradia", LARANJA), "Housing": ("Moradia", CIANO),
              "Health Care": ("Saúde", VERDE), "Financial & Insurance": ("Serviços financeiros e seguros", ROXO),
              "Financial Services & Insurance": ("Serviços financeiros e seguros", ROXO),
              "Food Services & Accommodations": ("Restaurantes e hospedagem", LARANJA),
              "Transportation Services": ("Transporte", AZUL), "Other Services": ("Outros serviços", CINZA)}


def graficos_frbsf_pce():
    """O mesmo gráfico do CPI, com o Excel do PCE do FRBSF: contribuição para
    o PCE cheio, para o núcleo e para o supercore (serviços sem energia e
    moradia), em 12 meses e no mês, desde 1960."""
    aba = frbsf_excel(FRBSF_PCE, "pce-contributions-data.xlsx")
    recortes = [("PCE cheio", "chart1_headlinePCEPI_YoY", "chart2_headlinePCEPI_MoM"),
                ("Núcleo", "chart3_corePCEPI_YoY", "extra_corePCEPI_MoM"),
                ("Supercore (serviços sem energia e moradia)", "chart4_supercorePCEPI_YoY",
                 "extra_supercorePCEPI_MoM")]
    variantes, ult = [], None
    for nome, a12, am in recortes:
        for quando, nome_aba in (("em 12 meses", a12), ("no mês", am)):
            d = aba(nome_aba)
            total = next(k for k in next(iter(d.values())) if k.startswith("Total"))
            grupos = [k for k in next(iter(d.values())) if k in PCE_GRUPOS]
            series = [serie(PCE_GRUPOS[k][0], PCE_GRUPOS[k][1],
                            {m: r[k] for m, r in d.items() if m >= "1990-01" and r.get(k) is not None}, 2,
                            tipo="barra") for k in grupos]
            series.append(serie(nome.split(" (")[0], BRANCO,
                                {m: r[total] for m, r in d.items() if m >= "1990-01" and r.get(total) is not None},
                                2, rotulo=True))
            variantes.append(dict(rot="%s, %s" % (nome, quando), series=series))
            ult = max(m for m, r in d.items() if r.get(total) is not None)
    print("  FRBSF PCE até %s" % ult)
    return dict(id="pce-componentes", titulo="Contribuição de cada componente para a inflação do consumo (PCE)",
                subtitulo="Barras = contribuição em p.p.; linha = inflação, %; com ajuste sazonal",
                unidade="%", barra=1, periodoPadrao="5", variantes=variantes,
                fonte="Federal Reserve Bank of San Francisco, BEA e FtM")


PPI = [("FD4", "Demanda final", True), ("FD41", "Bens", False), ("FD411", "Alimentos", False),
       ("FD412", "Energia", False), ("FD413", "Bens sem alimentos e energia", False),
       ("FD42", "Serviços", False), ("FD421", "Comércio (margens)", False),
       ("FD422", "Transporte e armazenagem", False), ("FD423", "Demais serviços", False),
       ("FD49104", "Sem alimentos e energia", True), ("FD49116", "Sem alimentos, energia e comércio", True)]


def tabela_ppi():
    hoje = datetime.date.today().year
    d = bls(["WPS" + c for c, _, _ in PPI] + ["WPU" + c for c, _, _ in PPI], hoje - 2, hoje)
    linhas, ref = [], None

    def cel(v, casas=1):
        return {"t": br(v, casas, True) + "%", "cor": VERMELHO if v > 0 else AZUL}
    for c, nome, forte in PPI:
        sa, nsa = d["WPS" + c], d["WPU" + c]
        m = max(sa)
        ref = ref or m
        mm = 100 * (sa[m] / sa[mes_mais(m, -1)] - 1)
        a3 = 100 * ((sa[m] / sa[mes_mais(m, -3)]) ** 4 - 1)
        a12 = 100 * (nsa[m] / nsa[mes_mais(m, -12)] - 1)
        a12p = 100 * (nsa[mes_mais(m, -1)] / nsa[mes_mais(m, -13)] - 1)
        linhas.append([{"t": nome, "forte": forte}, cel(mm, 2), cel(a3), cel(a12), cel(a12p)])
    ant = mes_mais(ref, -1)
    print("  PPI até %s" % ref)
    return dict(id="ppi-componentes", tipo="tabela", titulo="Inflação ao produtor (PPI) por componente",
                subtitulo="Demanda final, %s; mês e 3 meses com ajuste sazonal, 12 meses sem" % rot_mes(ref),
                fonte="BLS e FtM",
                colunas=[{"rot": "Componente"}, {"rot": "No mês", "num": True},
                         {"rot": "3 meses anualizado", "num": True}, {"rot": "12 meses", "num": True},
                         {"rot": "12 meses até %s" % rot_mes(ant), "num": True}],
                linhas=linhas)


# ================================================================ trabalho

SETORES = [("Mineração e extração", "USMINE"), ("Construção", "USCONS"), ("Manufatura", "MANEMP"),
           ("Atacado", "USWTRADE"), ("Varejo", "USTRADE"), ("Transporte e armazenagem", "CES4300000001"),
           ("Utilidades (luz, água, gás)", "CES4422000001"), ("Informação", "USINFO"),
           ("Financeiro", "USFIRE"), ("Serviços profissionais e técnicos", "CES6054000001"),
           ("Gestão de empresas", "CES6055000001"), ("Serviços administrativos e de apoio", "CES6056000001"),
           ("Educação privada", "CES6561000001"), ("Saúde e assistência social", "CES6562000001"),
           ("Lazer e hospedagem", "USLAH"), ("Outros serviços", "USSERV"),
           ("Governo federal", "CES9091000001"), ("Governo estadual", "CES9092000001"),
           ("Governo local", "CES9093000001")]
# períodos-base da comparação dos setores ("ult" = até o último mês)
BASES_SETORES = [("1990 a 2019", "1990-01", "2019-12"), ("2008 a 2019", "2008-01", "2019-12"),
                 ("2022 a 2026", "2022-01", "ult")]


def graficos_trabalho():
    rec, rec_d = recessoes(), recessoes(True)
    total, gov, bens, serv = (fred(i) for i in ("PAYEMS", "USGOVT", "USGOOD", "CES0800000001"))
    ini = "2022-01"
    g_pay = dict(id="payroll-setores", titulo="Criação de vagas (payroll) por grande setor",
                 subtitulo="Mil vagas por mês, média móvel de 3 meses", unidade="mil", barra=1,
                 fonte="BLS (via FRED) e FtM", series=[
                     serie("Privado: serviços", AZUL, desde(media(dif(serv)), ini), 0, tipo="barra"),
                     serie("Privado: bens", LARANJA, desde(media(dif(bens)), ini), 0, tipo="barra"),
                     serie("Governo", CINZA, desde(media(dif(gov)), ini), 0, tipo="barra"),
                     serie("Total", BRANCO, desde(media(dif(total)), ini), 0, rotulo=True)])

    # O que está fora do padrão: a variação de 12 meses de cada setor contra a
    # distribuição das variações de 12 meses dele mesmo num período-base.
    # Três bases (BASES_SETORES): duas pré-pandemia, uma longa e uma que é um
    # ciclo completo (a crise de 2008 e a expansão até 2019), e uma recente,
    # que começa em 2022. 2020 e 2021 ficam fora de todas: o tombo e o rebote
    # multiplicam o desvio-padrão (lazer e hospedagem: de 1,5 para 14,8 p.p.)
    # e qualquer coisa passa a parecer normal.
    ult = max(total)
    cor = lambda v: VERDE if v > 0 else VERMELHO                                          # noqa: E731
    series_setor = {sid: fred(sid) for _, sid in SETORES}

    def estatisticas(ini, fim):
        stats = []
        for nome, sid in SETORES:
            s = series_setor[sid]
            v12 = var(s)
            hist = [v for m, v in v12.items() if ini <= m <= fim]
            mu = sum(hist) / len(hist)
            dp = math.sqrt(sum((x - mu) ** 2 for x in hist) / (len(hist) - 1))
            x = v12[ult]
            stats.append(dict(nome=nome, x=x, mil=s[ult] - s[mes_mais(ult, -12)], mu=mu, dp=dp,
                              z=(x - mu) / dp, pctl=100 * sum(h <= x for h in hist) / len(hist),
                              peso=100 * s[ult] / total[ult],
                              a3=100 * ((s[ult] / s[mes_mais(ult, -3)]) ** 4 - 1)))
        return sorted(stats, key=lambda r: r["z"], reverse=True)

    bases = [(rot, estatisticas(a, b if b != "ult" else ult)) for rot, a, b in BASES_SETORES]
    stats = bases[0][1]
    g_atip = dict(id="setores-atipicos", tipo="ranking",
                  titulo="Emprego por setor: o quanto os últimos 12 meses fogem do normal",
                  subtitulo="Variação em 12 meses até %s" % rot_mes(ult), unidade="dp", sinal=True,
                  fonte="BLS (via FRED) e FtM", variantes=[
                      dict(rot="em desvios-padrão contra a média de %s" % rot, unidade="dp",
                           itens=[[r["nome"], round(r["z"], 2), cor(r["z"])] for r in st])
                      for rot, st in bases] + [
                      dict(rot="em %", unidade="pct1",
                           itens=[[r["nome"], round(r["x"], 1), cor(r["x"])]
                                  for r in sorted(stats, key=lambda r: -r["x"])]),
                      dict(rot="em mil vagas", unidade="mil",
                           itens=[[r["nome"], round(r["mil"]), cor(r["mil"])]
                                  for r in sorted(stats, key=lambda r: -r["mil"])]),
                  ])

    def tabela(rot, st):
        linhas = []
        for r in st:
            fora = abs(r["z"]) >= 1.5
            linhas.append([{"t": r["nome"], "forte": fora}, {"t": br(r["peso"])},
                           {"t": br(r["mil"], 0, True)}, {"t": br(r["x"], 1, True) + "%", "cor": cor(r["x"])},
                           {"t": br(r["a3"], 1, True) + "%", "cor": cor(r["a3"])}])
        return dict(rot="base de %s" % rot, linhas=linhas,
                    colunas=[{"rot": "Setor"}, {"rot": "% do emprego", "num": True},
                             {"rot": "12 meses, mil vagas", "num": True}, {"rot": "12 meses", "num": True},
                             {"rot": "3 meses anualizado", "num": True}])
    g_tab = dict(id="setores-estatisticas", tipo="tabela",
                 titulo="Emprego por setor: as estatísticas da comparação",
                 subtitulo="Até %s; na ordem do ranking acima; em negrito, os setores a 1,5 desvio-padrão ou mais "
                           "da média da base" % rot_mes(ult),
                 fonte="BLS (via FRED) e FtM", variantes=[tabela(rot, st) for rot, st in bases])

    saude = fred("CES6562000001")
    d12 = lambda s: {m: v - s[mes_mais(m, -12)] for m, v in s.items() if mes_mais(m, -12) in s}  # noqa: E731
    t12, s12, g12 = d12(total), d12(saude), d12(gov)
    resto = {m: t12[m] - s12[m] - g12[m] for m in t12 if m in s12 and m in g12}
    ini12 = "2023-01"
    g_conc = dict(id="payroll-concentracao", titulo="De onde vieram as vagas nos últimos 12 meses",
                  subtitulo="Mil vagas, variação em 12 meses", unidade="mil", barra=1,
                  fonte="BLS (via FRED) e FtM", series=[
                      serie("Saúde e assistência social", VERDE, desde(s12, ini12), 0, tipo="barra"),
                      serie("Governo", CINZA, desde(g12, ini12), 0, tipo="barra"),
                      serie("Resto da economia", AZUL, desde(resto, ini12), 0, tipo="barra"),
                      serie("Total", BRANCO, desde(t12, ini12), 0, rotulo=True)])

    g_des = dict(id="desemprego-participacao", titulo="Desemprego e participação na força de trabalho",
                 subtitulo="Faixas cinza = recessões (NBER)", unidade="%", sombras=rec,
                 fonte="BLS, NBER (via FRED) e FtM", variantes=[
                     dict(rot="Taxa de desemprego, % da força de trabalho", series=[
                         serie("Desemprego", BRANCO, fred("UNRATE"), 1, rotulo=True, legenda=False)]),
                     dict(rot="Taxa de participação, % da população de 16 anos ou mais", series=[
                         serie("Participação", BRANCO, fred("CIVPART"), 1, rotulo=True, legenda=False)]),
                 ])

    # Breakeven, pelo método do St. Louis Fed ("Breakeven employment growth:
    # a simple, useful benchmark", abr/2025):
    #
    #   breakeven = crescimento da população de 16+ × participação
    #               × (1 − desemprego) × (emprego do payroll ÷ emprego da
    #               pesquisa domiciliar)
    #
    # A participação é a média de 12 meses, como lá; a razão entre as duas
    # pesquisas (0,979 no artigo) sai dos dados, também em média de 12 meses.
    # O St. Louis usa a projeção de população do CBO; aqui o crescimento é o
    # realizado da pesquisa domiciliar, em média dos últimos 12 meses SEM os
    # janeiros: em janeiro entra o ajuste anual de população do Census (nos
    # últimos anos, a revisão da imigração), que muda o nível de uma vez e não
    # é crescimento. O mês sem pesquisa (out/2025) fica fora.
    pop, emp = fred("CNP16OV"), fred("CE16OV")
    part12, u = media(fred("CIVPART"), 12), fred("UNRATE")
    razao = media({m: total[m] / emp[m] for m in emp if m in total}, 12)
    dpop = {m: pop[m] - pop[mes_mais(m, -1)] for m in pop if mes_mais(m, -1) in pop and m[5:] != "01"}
    be = {}
    for m in pop:
        janela = [dpop[k] for k in (mes_mais(m, -i) for i in range(12)) if k in dpop]
        if len(janela) >= 9 and m in part12 and m in u and m in razao:
            be[m] = sum(janela) / len(janela) * part12[m] / 100 * (1 - u[m] / 100) * razao[m]
    # a faixa do próprio St. Louis Fed para 2026 (mar/2026): 15 mil no cenário
    # baixo de imigração da AEI-Brookings, 87 mil no do CBO
    faixa_stl = {m: (15, 87) for m in sorted(be) if m >= "2026-01"}
    g_be = dict(id="payroll-breakeven", titulo="Payroll e o breakeven do mercado de trabalho",
                subtitulo="Mil vagas por mês; breakeven = vagas que mantêm o desemprego estável (método do St. Louis Fed)",
                unidade="mil", fonte="BLS (via FRED), St. Louis Fed e FtM", series=[
                    dict(nome="Faixa do St. Louis Fed para 2026 (cenários de imigração)", cor=CINZA, tipo="faixa",
                         dados=[[m, a, b] for m, (a, b) in faixa_stl.items()]),
                    serie("Payroll, média de 3 meses", BRANCO, desde(media(dif(total)), ini), 0, rotulo=True),
                    serie("Breakeven estimado", LARANJA, desde(be, ini), 0, rotulo=True)])

    sal = fred("CES0500000003")
    cpi12 = var(fred("CPIAUCNS"))
    real = {m: 100 * ((1 + v / 100) / (1 + cpi12[m] / 100) - 1) for m, v in var(sal).items() if m in cpi12}
    g_sal = dict(id="salario-horas", titulo="Salário por hora e horas trabalhadas",
                 subtitulo="Setor privado; %s" % SUB_RECESSAO, unidade="%", sombras=rec,
                 fonte="BLS, NBER (via FRED) e FtM", variantes=[
                     dict(rot="Salário por hora, % em 12 meses", series=[
                         serie("Todos os empregados", BRANCO, var(sal), rotulo=True),
                         serie("Produção e não supervisores", CIANO, desde(var(fred("AHETPI")), "1990-01"),
                               rotulo=True),
                         serie("CPI cheio", LARANJA, desde(cpi12, "1990-01"), traco="pontilhado")]),
                     dict(rot="Salário real (descontado o CPI), % em 12 meses", series=[
                         serie("Salário real", BRANCO, real, rotulo=True, legenda=False)]),
                     dict(rot="Horas semanais médias", unidade="h", eixo={"zero": False}, series=[
                         serie("Horas por semana", BRANCO, fred("AWHAETP"), 1, rotulo=True, legenda=False)]),
                 ])

    jol = fred("JTSJOL")
    des = fred("UNEMPLOY")
    g_jolts = dict(id="jolts", titulo="Contratações, demissões e vagas abertas (JOLTS)",
                   subtitulo="Faixas cinza = recessões (NBER)", unidade="%", sombras=rec, fonte="BLS, NBER (via FRED) e FtM",
                   variantes=[
                       dict(rot="Contratações e demissões", series=[
                           serie("Contratações", BRANCO, fred("JTSHIR"), 1, rotulo=True),
                           serie("Demissões voluntárias (quits)", CIANO, fred("JTSQUR"), 1, rotulo=True),
                           serie("Demissões", VERMELHO, fred("JTSLDR"), 1, rotulo=True)]),
                       dict(rot="Vagas abertas por desempregado", unidade="x", series=[
                           serie("Vagas por desempregado", BRANCO, {m: v / des[m] for m, v in jol.items() if m in des},
                                 2, rotulo=True, legenda=False)]),
                   ])

    ic, cc = fred("ICSA", False), fred("CCSA", False)
    forca = fred("CLF16OV")
    ic4, cc4 = media(ic, 4), media(cc, 4)
    ic_pct = {d: 100 * v / forca[d[:7]] / 1000 for d, v in ic4.items() if d[:7] in forca}
    mil = lambda s: {k: v / 1000 for k, v in s.items()}                                   # noqa: E731
    g_claims = dict(id="seguro-desemprego", titulo="Pedidos de seguro-desemprego",
                    subtitulo="Semanal, com ajuste sazonal; %s" % SUB_RECESSAO, unidade="mil",
                    diario=True, periodoPadrao="5", sombras=rec_d, buracoMax=8, fonte="Departamento do Trabalho, NBER (via FRED) e FtM",
                    variantes=[
                        dict(rot="Pedidos iniciais, mil", series=[
                            serie("Semana", CINZA, desde(mil(ic), "2015-01-01"), 0),
                            serie("Média de 4 semanas", BRANCO, mil(ic4), 0, rotulo=True)]),
                        dict(rot="Pedidos contínuos, mil", series=[
                            serie("Semana", CINZA, desde(mil(cc), "2015-01-01"), 0),
                            serie("Média de 4 semanas", BRANCO, mil(cc4), 0, rotulo=True)]),
                        dict(rot="Pedidos iniciais em % da força de trabalho, média de 4 semanas", unidade="%",
                             series=[serie("Pedidos iniciais ÷ força de trabalho", BRANCO, ic_pct, 3,
                                           rotulo=True, legenda=False)]),
                    ])
    print("  trabalho até %s; breakeven %.0f mil, payroll 3m %.0f mil" %
          (ult, be[max(be)], media(dif(total))[ult]))
    return [g_pay, g_conc, g_atip, g_tab, g_des, g_be, g_sal, g_jolts, g_claims]


# ================================================================ atividade

def ism(evento):
    d = json.loads(baixar("https://sbcharts.investing.com/events_charts/us/%d.json" % evento, headers=NAVEGADOR))
    out = {}
    for p in sorted(d["attr"], key=lambda p: p["timestamp"]):
        if p.get("actual") is None:
            continue
        dt = datetime.datetime.fromtimestamp(p["timestamp"] / 1000, datetime.timezone.utc)
        out[mes_mais("%04d-%02d" % (dt.year, dt.month), -1)] = float(p["actual"])
    return out


def desde_quando(s, comparar):
    """Desde quando o último valor não era tão alto (ou tão baixo)."""
    m, v = ultimo(s)
    for k in sorted(s, reverse=True)[1:]:
        if comparar(s[k], v):
            return k
    return None


def graficos_atividade():
    man, srv = ism(173), ism(176)
    partes = []
    for nome, s in (("manufatura", man), ("serviços", srv)):
        # o mês isolado oscila; a média de 3 meses é o que diz se o ciclo está
        # no alto
        m3 = media(s, 3)
        m, v = ultimo(m3)
        k = desde_quando(m3, lambda a, b: a >= b)
        partes.append("%s %s, a maior desde %s" % (nome, br(v), rot_mes(k)) if k else "%s %s" % (nome, br(v)))
        print("  ISM %s %s: mês %.1f, média 3m %.2f; maior desde %s" % (nome, m, s[m], v, k))
    rec = recessoes()
    return [dict(id="ism-pmi", titulo="Índice de gerentes de compras (PMI) do ISM",
                 subtitulo="Acima de 50 = expansão; média de 3 meses: %s; %s" % (", ".join(partes), SUB_RECESSAO),
                 unidade="pts", eixo={"zero": False}, sombras=rec, periodoPadrao="10",
                 fonte="ISM (via investing.com), NBER e FtM", series=[
                     serie("Manufatura", AZUL, man, 1, rotulo=True),
                     serie("Serviços", LARANJA, srv, 1, rotulo=True)])]


# ================================================================ moeda

def graficos_moeda():
    rec = recessoes()
    m2, base = fred("M2SL"), fred("BOGMBASE")
    g1 = dict(id="m2-base", titulo="Agregados monetários: M2 e base monetária",
              subtitulo="%% em 12 meses; %s" % SUB_RECESSAO, unidade="%", sombras=rec,
              fonte="Federal Reserve, NBER (via FRED) e FtM", variantes=[
                  dict(rot="M2", series=[serie("M2", BRANCO, var(m2), 1, rotulo=True, legenda=False)]),
                  dict(rot="Base monetária", series=[serie("Base monetária", CIANO, var(base), 1, rotulo=True,
                                                           legenda=False)])])

    # Em mai/2020 o Fed passou a poupança para o M1 e juntou poupança e
    # "outros depósitos à vista" (OCD) em "outros depósitos líquidos". Antes
    # disso, a soma das duas séries antigas é a mesma coisa.
    liq = dict(fred("MDLM"))
    sav, ocd = fred("SAVINGSL"), fred("OCDSL")
    for m in sav:
        if m not in liq and m in ocd:
            liq[m] = sav[m] + ocd[m]
    vista = fred("DEMDEPSL")
    ini = "2000-01"
    v2 = var(m2)

    def contribuicoes(comp):
        series, soma = [], {}
        for nome, s, cor in comp:
            c = {m: 100 * (s[m] - s[mes_mais(m, -12)]) / m2[mes_mais(m, -12)]
                 for m in m2 if m >= ini and m in s and mes_mais(m, -12) in s}
            for m, v in c.items():
                soma[m] = soma.get(m, 0) + v
            series.append(serie(nome, cor, c, 2, tipo="barra"))
        series.append(serie("Ajustes (IRA e Keogh)", CINZA, {m: v2[m] - soma[m] for m in soma}, 2, tipo="barra"))
        series.append(serie("M2", BRANCO, desde(v2, ini), 2, rotulo=True))
        return series
    resto_comp = [("Depósitos a prazo", fred("STDSL"), ROXO), ("Fundos monetários de varejo", fred("RMFSL"), LARANJA)]
    separados = [("Papel-moeda", fred("CURRSL"), VERDE), ("Depósitos à vista", vista, AZUL),
                 ("Poupança e outros líquidos", liq, CIANO)] + resto_comp
    juntos = [("Papel-moeda", fred("CURRSL"), VERDE),
              ("Depósitos à vista e poupança", {m: vista[m] + liq[m] for m in liq if m in vista}, AZUL)] + resto_comp
    g2 = dict(id="m2-componentes", titulo="Contribuição de cada componente para o crescimento do M2",
              subtitulo="p.p. do crescimento em 12 meses", unidade="pp", barra=1, periodoPadrao="5",
              fonte="Federal Reserve (via FRED) e FtM", variantes=[
                  dict(rot="componentes separados", series=contribuicoes(separados)),
                  dict(rot="depósitos à vista e poupança somados", series=contribuicoes(juntos))],
              nota="Em nov e dez/25, cerca de US$ 900 bilhões passaram de poupança e outros depósitos líquidos "
                   "para depósitos à vista, sem mudar o M2. É reclassificação, não dinheiro novo: o recorte com "
                   "os dois somados tira esse degrau.")
    print("  M2 até %s: %.1f%%" % ultimo(v2))
    return [g1, g2]


# ================================================================ governo

def mts_tabela9():
    url = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_9"
           "?sort=-record_date&page%5Bsize%5D=1")
    data = json.loads(baixar(url))["data"][0]["record_date"]
    url = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_9"
           "?filter=record_date:eq:%s&page%%5Bsize%%5D=300" % data)
    linhas = json.loads(baixar(url))["data"]
    return data, linhas


NOMES_RECEITA = {"Individual Income Taxes": "IR pessoa física", "Corporation Income Taxes": "IR pessoa jurídica",
                 "Employment and General Retirement": "Contribuição previdenciária",
                 "Unemployment Insurance": "Seguro-desemprego", "Other Retirement": "Outras aposentadorias",
                 "Excise Taxes": "Impostos seletivos (excise)", "Estate and Gift Taxes": "Herança e doações",
                 "Customs Duties": "Tarifas de importação", "Miscellaneous Receipts": "Outras (inclui o Fed)"}
NOMES_DESPESA = {
    "National Defense": "Defesa", "International Affairs": "Relações internacionais",
    "General Science, Space, and Technology": "Ciência e espaço", "Energy": "Energia",
    "Natural Resources and Environment": "Recursos naturais e ambiente", "Agriculture": "Agricultura",
    "Commerce and Housing Credit": "Comércio e crédito habitacional", "Transportation": "Transporte",
    "Community and Regional Development": "Desenvolvimento regional",
    "Education, Training, Employment, and Social Services": "Educação e emprego", "Health": "Saúde (Medicaid etc.)",
    "Medicare": "Medicare", "Income Security": "Assistência social", "Social Security": "Previdência (Social Security)",
    "Veterans Benefits and Services": "Veteranos", "Administration of Justice": "Justiça",
    "General Government": "Administração geral", "Net Interest": "Juros líquidos",
    "Undistributed Offsetting Receipts": "Receitas compensatórias"}


def graficos_governo():
    rec = recessoes()
    r, o = fred("MTSR133FMS"), fred("MTSO133FMS")
    r12, o12 = soma12(r), soma12(o)
    g1 = dict(id="governo-receita-despesa", titulo="Receita e despesa do governo federal",
              subtitulo="Soma de 12 meses; %s" % SUB_RECESSAO, sombras=rec, unidade="%",
              fonte="Tesouro (MTS), NBER (via FRED) e FtM", periodoPadrao="20", variantes=[
                  dict(rot="% sobre os 12 meses anteriores", series=[
                      serie("Receita", VERDE, var(r12), 1, rotulo=True),
                      serie("Despesa", VERMELHO, var(o12), 1, rotulo=True)]),
                  dict(rot="US$ bilhões", unidade="usd-bi", series=[
                      serie("Receita", VERDE, {m: v / 1e3 for m, v in r12.items()}, 0, rotulo=True),
                      serie("Despesa", VERMELHO, {m: v / 1e3 for m, v in o12.items()}, 0, rotulo=True),
                      serie("Déficit", CINZA, {m: (r12[m] - o12[m]) / 1e3 for m in r12}, 0, tipo="barra")]),
              ])

    data, linhas = mts_tabela9()
    pai = {l["classification_id"]: l["classification_desc"] for l in linhas}
    receitas, despesas = [], []
    for l in linhas:
        a, b = l["current_fytd_rcpt_outly_amt"], l["prior_fytd_rcpt_outly_amt"]
        if a in ("null", None) or b in ("null", None) or l["classification_desc"] == "Total":
            continue
        nome = l["classification_desc"]
        item = (nome, float(a) / 1e9, float(b) / 1e9)
        if nome in NOMES_DESPESA:
            despesas.append(item)
        elif nome in NOMES_RECEITA:
            receitas.append(item)
    tot = {l["classification_desc"] + "|" + pai.get(l["parent_id"], ""): (float(l["current_fytd_rcpt_outly_amt"]) / 1e9,
                                                                          float(l["prior_fytd_rcpt_outly_amt"]) / 1e9)
           for l in linhas if l["classification_desc"] == "Total"}
    tr, to = tot["Total|Receipts"], tot["Total|Net Outlays"]
    ano = int(data[:4]) + (1 if data[5:7] >= "10" else 0)
    parcial = data[5:7] != "09"
    quando = ("ano fiscal %d (out/%d a set/%d) contra %d" % (ano, ano - 1, ano, ano - 1) if not parcial
              else "ano fiscal %d até %s contra o mesmo período de %d" % (ano, rot_mes(data[:7]), ano - 1))

    def ranking(itens, total_ant, nomes, cor_pos, cor_neg):
        def lista(f, chave):
            return [[nomes[n], round(f(a, b), 2), cor_pos if f(a, b) > 0 else cor_neg]
                    for n, a, b in sorted(itens, key=lambda x: -chave(x))]
        return [dict(rot="contribuição para o crescimento, p.p.", unidade="pp",
                     itens=lista(lambda a, b: 100 * (a - b) / total_ant, lambda x: x[1] - x[2])),
                dict(rot="variação em US$ bilhões", unidade="usd-bi",
                     itens=lista(lambda a, b: a - b, lambda x: x[1] - x[2])),
                dict(rot="variação em %", unidade="pct1",
                     itens=[x for x in lista(lambda a, b: 100 * (a / b - 1) if b > 0 else 0,
                                              lambda x: (x[1] / x[2] - 1) if x[2] > 0 else -9)])]
    g2 = dict(id="despesa-contribuicao", tipo="ranking", sinal=True, unidade="pp",
              titulo="O que puxou a despesa do governo federal",
              subtitulo="Por função, %s; despesa total %s%%" % (quando, br(100 * (to[0] / to[1] - 1), 1, True)),
              fonte="Tesouro (MTS, tabela 9) e FtM", variantes=ranking(despesas, to[1], NOMES_DESPESA, VERMELHO, VERDE))
    g3 = dict(id="receita-contribuicao", tipo="ranking", sinal=True, unidade="pp",
              titulo="O que puxou a receita do governo federal",
              subtitulo="Por fonte, %s; receita total %s%%" % (quando, br(100 * (tr[0] / tr[1] - 1), 1, True)),
              fonte="Tesouro (MTS, tabela 9) e FtM", variantes=ranking(receitas, tr[1], NOMES_RECEITA, VERDE, VERMELHO))
    print("  MTS tabela 9 até %s: receita %.0f, despesa %.0f bi" % (data, tr[0], to[0]))
    return [g1, g2, g3]


# ================================================================ crédito

def graficos_credito():
    hy, ig, bbb = (fred(i, False) for i in ("BAMLH0A0HYM2", "BAMLC0A0CM", "BAMLC0A4CBBB"))
    print("  spreads até %s: HY %.2f, IG %.2f" % (max(hy), hy[max(hy)], ig[max(ig)]))
    um = lambda rot, cor, s: dict(rot=rot, series=[serie(rot, cor, s, rotulo=True, legenda=False)])  # noqa: E731
    return [dict(id="spreads-credito", titulo="Spreads de crédito corporativo nos EUA",
                 subtitulo="Pontos percentuais sobre o Treasury, diário; ICE BofA, ajustado por opções",
                 unidade="pp", diario=True, fonte="ICE BofA (via FRED) e FtM", variantes=[
                     um("High yield", LARANJA, hy), um("BBB", CIANO, bbb), um("Grau de investimento", BRANCO, ig)])]


# ================================================================ data centers

def xlsx_aba(conteudo, aba):
    """{linha: {coluna: valor}} de uma aba de .xlsx (biblioteca padrão)."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    textos = ["".join(t.text or "" for t in si.iter(ns + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    alvo = next(rels[a.get(rns + "id")] for a in ET.fromstring(z.read("xl/workbook.xml")).iter(ns + "sheet")
                if a.get("name") == aba).lstrip("/")
    alvo = alvo if alvo.startswith("xl/") else "xl/" + alvo
    out = {}
    for c in ET.fromstring(z.read(alvo)).iter(ns + "c"):
        v = c.find(ns + "v")
        if v is not None and v.text is not None:
            ref = c.get("r")
            col = re.match(r"[A-Z]+", ref).group(0)
            out.setdefault(int(ref[len(col):]), {})[col] = textos[int(v.text)] if c.get("t") == "s" else v.text
    return out


MES_EN = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def construcao_privada():
    linhas = xlsx_aba(baixar("https://www.census.gov/construction/c30/xlsx/privsatime.xlsx", headers=NAVEGADOR),
                      "Private SA")
    cab = next(r for r in sorted(linhas) if linhas[r].get("A") == "Date")
    nomes = {c: re.sub(r"\s+", " ", v).strip() for c, v in linhas[cab].items()}
    col = lambda prefixo: next(c for c, v in nomes.items() if v.startswith(prefixo))     # noqa: E731
    cols = {"dc": col("Data center"), "nres": col("Nonresidential"), "manu": col("Manufacturing")}
    out = {k: {} for k in cols}
    for r in sorted(linhas):
        m = re.match(r"([A-Z][a-z]{2})-(\d{2})", str(linhas[r].get("A", "")))
        if not m or r <= cab:
            continue
        aa = int(m.group(2))                                  # a planilha começa em 1993: "Jan-93"
        mes = "%04d-%02d" % (aa + (1900 if aa > 50 else 2000), MES_EN[m.group(1)])
        for k, c in cols.items():
            try:
                out[k][mes] = float(linhas[r][c]) / 1e3          # US$ milhões → bilhões
            except (KeyError, ValueError):
                pass
    return out


def graficos_datacenters():
    d = construcao_privada()
    dc, manu, nres = d["dc"], d["manu"], d["nres"]
    m, v = ultimo(dc)
    print("  data centers até %s: US$ %.1f bi" % (m, v))
    sub = "Gasto com a obra, sem servidores nem racks"
    return [dict(id="datacenters-construcao", titulo="Construção de data centers e de fábricas nos EUA",
                 subtitulo="US$ bilhões, taxa anual com ajuste sazonal; %s" % sub.lower(), unidade="usd-bi",
                 fonte="Census Bureau e FtM", series=[
                     serie("Data centers", CIANO, dc, 1, rotulo=True),
                     serie("Fábricas (manufatura)", LARANJA, manu, 1, rotulo=True)]),
            dict(id="datacenters-participacao", titulo="Peso dos data centers na construção privada não residencial",
                 subtitulo="Census Bureau, com ajuste sazonal", unidade="%", fonte="Census Bureau e FtM", variantes=[
                     dict(rot="% do total não residencial", series=[
                         serie("Data centers", CIANO, {k: 100 * x / nres[k] for k, x in dc.items() if k in nres}, 1,
                               rotulo=True, legenda=False)]),
                     dict(rot="% em 12 meses", series=[
                         serie("Data centers", CIANO, var(dc), 1, rotulo=True),
                         serie("Não residencial, total", BRANCO, var(nres), 1, rotulo=True)]),
                 ])]


# ================================================================ TIC

def graficos_tic():
    """Compras líquidas de títulos americanos de longo prazo por estrangeiros,
    por mês, desde 1977. Dois arquivos do Tesouro emendados: o antigo
    (s1_globl, compras brutas menos vendas brutas, de jan/1977 a jan/2023) e o
    novo (tabela 1 do SLT, de fev/2023 em diante, quando a coleta mudou de
    formulário). Os dois não se sobrepõem: um acaba onde o outro começa."""
    tipos = [("Treasuries", AZUL), ("Agências (hipotecas)", CIANO), ("Títulos corporativos", LARANJA), ("Ações", VERDE)]
    dados = {n: {} for n, _ in tipos}

    def num(x):
        x = x.replace(",", "").replace('"', "").strip()
        return None if x in ("", "n.a.") else float(x)      # "n.a.": fora do período do arquivo

    # antigo: colunas 3 a 6 são as compras brutas dos 4 tipos americanos, 9 a 12 as vendas
    for l in baixar("https://ticdata.treasury.gov/Publish/s1_globl.txt", headers=NAVEGADOR).decode("latin-1").splitlines():
        c = l.rstrip("\r").split("\t")
        if len(c) > 12 and c[1].strip() == "99996" and re.match(r"\d{4}-\d{2}$", c[2].strip()):
            v = [num(x) for x in c[3:13]]
            if None in v[:4] or None in v[6:10]:
                continue
            for k, (n, _) in enumerate(tipos):
                dados[n][c[2].strip()] = (v[k] - v[k + 6]) / 1e3
    fim_antigo = max(dados["Treasuries"])
    # novo: "net U.S. sales" de cada tipo, que é a compra líquida dos estrangeiros
    for l in baixar("https://ticdata.treasury.gov/Publish/slt_table1.txt", headers=NAVEGADOR).decode("latin-1").splitlines():
        c = l.split("\t")
        if len(c) > 16 and c[1].strip() == "99996" and re.match(r"\d{4}-\d{2}$", c[2].strip()):
            m = c[2].strip()
            if num(c[4]) is None or m <= fim_antigo:
                continue
            for (n, _), k in zip(tipos, (7, 10, 13, 16)):
                dados[n][m] = (num(c[k]) or 0) / 1e3
    meses = sorted(set.intersection(*(set(d) for d in dados.values())))
    total = {m: sum(dados[n][m] for n, _ in tipos) for m in meses}
    print("  TIC de %s a %s (emenda em %s): US$ %.1f bi no último mês" % (meses[0], meses[-1], fim_antigo, total[meses[-1]]))
    return [dict(id="tic-fluxo", titulo="Compras líquidas de títulos americanos por estrangeiros",
                 subtitulo="Títulos de longo prazo, US$ bilhões; positivo = estrangeiros compram", unidade="usd-bi",
                 barra=1, periodoPadrao="10", fonte="Tesouro (TIC: S até jan/23, SLT depois) e FtM", variantes=[
                     dict(rot="soma de 12 meses", series=[serie(n, cor, soma12(dados[n]), 1, tipo="barra")
                                                         for n, cor in tipos]
                          + [serie("Total", BRANCO, soma12(total), 1, rotulo=True)]),
                     dict(rot="por mês", series=[serie(n, cor, dados[n], 1, tipo="barra") for n, cor in tipos]
                          + [serie("Total", BRANCO, total, 1, rotulo=True)]),
                 ])]


# ================================================================ juros

BCS = [("XM", "BCE (depósito)", CIANO, "des"), ("GB", "Banco da Inglaterra", VERMELHO, "des"),
       ("JP", "Banco do Japão", AREIA, "des"), ("CA", "Banco do Canadá", ROXO, "des"),
       ("AU", "Banco da Austrália", VERDE, "des"), ("CH", "Banco Nacional Suíço", CINZA, "des"),
       ("BR", "Brasil (Selic)", VERDE, "emg"), ("MX", "México", LARANJA, "emg"), ("CL", "Chile", AZUL, "emg"),
       ("CO", "Colômbia", AMARELO, "emg"), ("ZA", "África do Sul", ROXO, "emg"), ("IN", "Índia", CIANO, "emg"),
       ("CN", "China (LPR de 1 ano)", VERMELHO, "emg")]
INI_JUROS = "2019-01-01"


def degraus(s):
    """Série diária de taxa de política → só os pontos de mudança, com o dia
    anterior repetindo a taxa antiga (o desenho sai em degrau, e o arquivo
    fica com dezenas de pontos em vez de milhares)."""
    ks = sorted(s)
    out = {ks[0]: s[ks[0]]}
    for a, b in zip(ks, ks[1:]):
        if s[b] != s[a]:
            out[a] = s[a]
            out[b] = s[b]
    out[ks[-1]] = s[ks[-1]]
    return out


def ultima_mudanca(s):
    ks = sorted(s)
    for a, b in zip(reversed(ks[:-1]), reversed(ks[1:])):
        if s[b] != s[a]:
            return b, s[b] - s[a]
    return None, 0


def graficos_juros():
    url = ("https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.%s?startPeriod=%s&format=csv"
           % ("+".join(c for c, _, _, _ in BCS), INI_JUROS))
    bis = {}
    for l in csv.DictReader(io.StringIO(baixar(url).decode("utf-8-sig"))):
        v = l["OBS_VALUE"].strip()
        if v and v.lower() != "nan":                        # fim de semana vem como NaN
            bis.setdefault(l["REF_AREA"], {})[l["TIME_PERIOD"]] = float(l["OBS_VALUE"])
    fed = desde(fred("DFEDTARU", False), INI_JUROS)
    todos = [("US", "Fed (teto da faixa)", BRANCO, "des", fed)] + [(c, n, cor, g, bis[c]) for c, n, cor, g in BCS]
    fed_s = serie("Fed (teto da faixa)", BRANCO, degraus(fed), 2, rotulo=True)

    linhas = []
    for c, n, cor, g, s in todos:
        k, v = ultimo(s)
        quando, tam = ultima_mudanca(s)
        ano = (datetime.date.fromisoformat(k) - datetime.timedelta(days=365)).isoformat()
        antes = s[max(x for x in s if x <= ano)]
        cel = lambda x: {"t": br(x, 2, True), "cor": VERMELHO if x > 0 else (VERDE if x < 0 else None)}  # noqa: E731
        linhas.append([{"t": n, "forte": c == "US"}, {"t": br(v, 2) + "%"},
                       {"t": "%s/%s/%s" % (quando[8:], quando[5:7], quando[:4]) if quando else "-"},
                       cel(tam), cel(v - antes)])
    ref = max(max(s) for _, _, _, _, s in todos[1:])
    print("  BIS até %s; Fed até %s" % (ref, max(fed)))
    return [dict(id="juros-bancos-centrais", titulo="Taxa de juros dos bancos centrais",
                 subtitulo="% ao ano, taxa de política monetária", unidade="%", diario=True, buracoMax=4000,
                 fonte="BIS, Federal Reserve (via FRED) e FtM", variantes=[
                     dict(rot="Desenvolvidos", series=[fed_s] + [
                         serie(n, cor, degraus(s), 2, rotulo=True) for c, n, cor, g, s in todos[1:] if g == "des"]),
                     dict(rot="Emergentes", series=[fed_s] + [
                         serie(n, cor, degraus(s), 2, rotulo=True) for c, n, cor, g, s in todos[1:] if g == "emg"]),
                 ]),
            dict(id="juros-bancos-centrais-tabela", tipo="tabela", titulo="Última decisão de cada banco central",
                 subtitulo="Taxa de política monetária; BIS até %s, Fed até %s"
                           % (rotulo_dia(ref), rotulo_dia(max(fed))),
                 fonte="BIS, Federal Reserve (via FRED) e FtM",
                 colunas=[{"rot": "Banco central"}, {"rot": "Taxa", "num": True}, {"rot": "Última mudança"},
                          {"rot": "Tamanho, p.p.", "num": True}, {"rot": "Em 12 meses, p.p.", "num": True}],
                 linhas=linhas)]


def rotulo_dia(d):
    return "%s/%s/%s" % (d[8:], d[5:7], d[:4])


# ================================================================ montagem

SECOES = [("Inflação", graficos_inflacao), ("Mercado de trabalho", graficos_trabalho),
          ("Atividade", graficos_atividade), ("Moeda", graficos_moeda), ("Contas do governo", graficos_governo),
          ("Crédito", graficos_credito), ("Data centers", graficos_datacenters),
          ("Fluxo de capital", graficos_tic), ("Juros", graficos_juros)]


def main():
    secoes = []
    for titulo, f in SECOES:
        print(titulo + "…")
        secoes.append(dict(titulo=titulo, texto="", fontes=[], figuras=[], graficos=f()))
    cpi = fred("CPIAUCNS")
    doc = dict(atualizado=datetime.date.today().isoformat(), referencia=max(cpi), formato="artigo",
               grupo=GRUPO, assunto=ASSUNTO, fonte="FRED, BLS, BEA, Fed de San Francisco, Tesouro, Census, ISM, BIS e FtM",
               secoes=secoes)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado %s (%.0f KB)" % (SAIDA, os.path.getsize(SAIDA) / 1024))
    import aplicar_texto
    aplicar_texto.aplicar(NOME + ".md", NOME + ".json")


if __name__ == "__main__":
    main()

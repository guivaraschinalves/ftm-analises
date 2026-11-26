#!/usr/bin/env python3
"""
Gasto público em % do PIB contra o PIB per capita, 2026 (um ponto por país,
tamanho da bolha pelo PIB em PPC, com a reta de mínimos quadrados). Refaz o gráfico do
Our World in Data ("Government spending as share of GDP vs. GDP per capita",
2022) com os dados de 2026. Gera dados/gasto-publico.json. Só biblioteca padrão.
Rodado à mão. Página própria: gasto-publico.html.

Pedido dele em 25/11/2026.

DE ONDE VEM CADA COISA (FMI, World Economic Outlook, API SDMX 3.0 do portal
de dados do FMI, dataflow IMF.RES/WEO; a edição vem no atributo de cada série)

  - GGX_NGDP: despesa total do governo geral, % do PIB (inclui juros), a
    mesma medida do gráfico do OWID, que também usa o FMI.
  - PPPPC: PIB per capita em paridade de poder de compra, dólares
    internacionais correntes. O OWID usava o Maddison (dólares de 2011), que
    não chega a 2026; por isso a escala do eixo X não é a mesma do original.
  - PPPGDP: PIB em PPC, dólares internacionais correntes (tamanho da bolha).
  - LP: população (corte de 1 milhão de habitantes e dica).
  - 2026 é estimativa do FMI na edição corrente do WEO, não dado fechado.

CONFERÊNCIAS QUE ABORTAM
  - GGX_NGDP = GGX / NGDP × 100 em cada país e ano (≤ 0,05 p.p.); exceções
    em TOL_GGX (países de ano fiscal, Venezuela e Polônia).
  - PPPPC = PPPGDP / LP em cada país (≤ 0,5%).
  - Amostra de pelo menos 150 países e Brasil presente.

O GASTO AO LONGO DO TEMPO (seção nova, 25/11/2026)

  - Gasto total, 1830 em diante: Our World in Data (historical-gov-spending-gdp),
    que junta o "Public Finances in Modern History" e o WEO do FMI. É uma
    safra anterior do FMI: de 2011 a 2019 fica a até 1,5 p.p. do WEO atual
    (conferência que aborta), mas nos anos 1990 e 2000 o Reino Unido chega a
    7 p.p. de diferença. Por isso o OWID só entra na série longa; a
    decomposição usa o WEO atual.
  - Consumo e investimento do governo geral: contas nacionais da OCDE
    (DSD_NASEC10@DF_TABLE12, setor S13, P3 = despesa de consumo final, P51G =
    formação bruta de capital fixo), em moeda local, divididos pelo PIB nominal
    do Banco Mundial (NY.GDP.MKTP.CN). Conferência: P3/PIB contra a série
    pronta do Banco Mundial (NE.CON.GOVT.ZS), ≤ 1 p.p. (o Reino Unido difere
    0,9 p.p. no começo dos anos 1990 por revisão).
  - Demais despesas = gasto total do WEO menos consumo menos investimento:
    transferências, juros, subsídios e outras. O total da OCDE (OTE) não serve
    de teto: para o Brasil passa de 60% do PIB, contra uns 48% do FMI.
    Conferência: o resto não pode ser negativo.
  - China só a partir de 2008 (INICIO_COMP).
  - Brasil só vai até 2020 (o último ano com investimento do governo na
    OCDE); Japão começa em 2005, Alemanha em 1995, Reino Unido em 1990.

CRÉDITO AO SETOR NÃO FINANCEIRO (seção nova, 26/11/2026)

  - BIS, "Credit to the non-financial sector" (WS_TC, API v1), trimestral, em
    % do PIB, credor = todos os setores, ajustado a quebras. Tomadores: G
    (governo geral), H (famílias e ISFLSF), N (empresas não financeiras), P
    (setor privado não financeiro = H + N) e C (setor não financeiro = G + P).
  - O total do BIS usa o governo a valor de mercado quando há essa série e a
    valor nominal quando não há; aqui o governo segue a mesma regra, para as
    partes somarem o total. Conferências: P = H + N e C = G + H + N (≤ 0,3 p.p.
    do PIB) em cada país; só países (sem agregados) e todos no mesmo trimestre.
  - O "crédito ao governo" do BIS é a dívida do governo geral (títulos e
    empréstimos, com qualquer credor), não só crédito bancário; pode diferir da
    dívida bruta publicada por cada país.

APOSENTADORIAS (seção nova, 26/11/2026)

  - OCDE, Pensions at a Glance: taxa bruta de reposição (GPRR100, homens, regimes
    obrigatórios) da API (DSD_PAG@DF_PRR, só a edição corrente) e idade futura de
    aposentadoria (DF_DPS, FRPLF22). As edições anteriores ficam em PRR_EDICOES.
  - Conferência: as médias da OCDE (38) e da UE (27) refeitas como média simples
    dos membros batem com as publicadas (≤ 0,1 p.p.).

A reta: gasto (% do PIB) = a + b · log10(PIB per capita), mínimos quadrados
sem ponderação (cada país conta um). Como o eixo X é logarítmico, ela sai reta.

Os nomes dos países em português foram gerados uma vez pela tabela CLDR
(Intl.DisplayNames, pt-BR) a partir do código ISO; trocar só se o FMI mudar
a lista de países.
"""
import datetime
import json
import math
import os
import sys
import time
import urllib.request

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SAIDA = os.path.join(RAIZ, "dados", "gasto-publico.json")
API = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.RES/WEO/+/"
UA = {"User-Agent": "ftm-analises"}
ANO = "2026"
DESTAQUE = "BRA"
ANO_INI = "2001"   # o primeiro ano com Brasil e EUA no WEO (GGX_NGDP)
# países com o nome escrito ao lado da bolha (os demais só na dica)
ROTULADOS = ["USA", "CHN", "IND", "FRA", "DEU", "ARG", "CHL", "MEX", "JPN", "NGA", "SGP", "NOR", "RUS", "ZAF"]
OWID = "https://ourworldindata.org/grapher/historical-gov-spending-gdp.csv?v=1&csvType=full&useColumnShortNames=true"
OCDE = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.NAD,DSD_NASEC10@DF_TABLE12,/"
WB = "https://api.worldbank.org/v2/country/%s/indicator/%s?format=json&per_page=5000&date=1950:2030"
# os seis países do gráfico do OWID, na ordem da legenda; o Brasil é a série principal
HIST = [("BRA", "Brasil"), ("DEU", "Alemanha"), ("GBR", "Reino Unido"), ("JPN", "Japão"),
        ("USA", "Estados Unidos"), ("CHN", "China")]
AZUL, VERDE, AZUL_CLARO, AMARELO = "#4F81BD", "#9BBB59", "#8EB4E3", "#FFFF00"
COR_HIST = {"BRA": "#FFFFFF", "DEU": "#4F81BD", "GBR": "#8EB4E3", "JPN": "#9BBB59", "USA": "#C0504D",
            "CHN": "#FFFF00"}
# Antes de 2008 o total do WEO para a China cobre só parte do governo geral (salta de
# 17,9% para 22,1% do PIB em 2008): consumo e investimento das contas nacionais passam
# do total e o resto sairia negativo. A decomposição da China começa em 2008.
INICIO_COMP = {"CHN": "2008"}
BIS = "https://stats.bis.org/api/v1/data/WS_TC/Q..C+G+H+N+P.A..770.A?format=csv&startPeriod=%s"
# nomes dos países do BIS (WS_TC), gerados uma vez pela tabela CLDR pt-BR a partir do código ISO
NOMES_BIS = {"AR": "Argentina", "AT": "Áustria", "AU": "Austrália", "BE": "Bélgica", "BR": "Brasil", "CA": "Canadá",
             "CH": "Suíça", "CL": "Chile", "CN": "China", "CO": "Colômbia", "CZ": "Tchéquia", "DE": "Alemanha",
             "DK": "Dinamarca", "ES": "Espanha", "FI": "Finlândia", "FR": "França", "GB": "Reino Unido",
             "GR": "Grécia", "HK": "Hong Kong", "HU": "Hungria", "ID": "Indonésia", "IE": "Irlanda",
             "IL": "Israel", "IN": "Índia", "IT": "Itália", "JP": "Japão", "KR": "Coreia do Sul",
             "LU": "Luxemburgo", "MX": "México", "MY": "Malásia", "NL": "Países Baixos", "NO": "Noruega",
             "NZ": "Nova Zelândia", "PL": "Polônia", "PT": "Portugal", "RU": "Rússia", "SA": "Arábia Saudita",
             "SE": "Suécia", "SG": "Singapura", "TH": "Tailândia", "TR": "Turquia", "US": "Estados Unidos",
             "ZA": "África do Sul"}
TOP_CREDITO = 20
OCDE_PRR = ("https://sdmx.oecd.org/public/rest/data/OECD.ELS.SPD,DSD_PAG@DF_PRR,/"
            "all?format=csvfilewithlabels")
OCDE_DPS = ("https://sdmx.oecd.org/public/rest/data/OECD.ELS.SPD,DSD_PAG@DF_DPS,/"
            "all?format=csvfilewithlabels")
# Taxa bruta de reposição da aposentadoria, homem com salário médio, regimes obrigatórios, nas
# edições anteriores do Pensions at a Glance (a API da OCDE só tem a edição corrente). Extraídas
# em 26/11/2026 por código das tabelas oficiais: PDFs de 2011 a 2021 (tabela "Gross pension
# replacement rates by earnings", coluna 1,0 vez o salário médio, homens) e página HTML de 2023;
# 2019 e 2021 conferidos PDF x HTML sem diferença. Trocar só se a OCDE corrigir uma edição antiga.
# Média da OCDE: OECD34 até 2015 e todos os membros depois; UE: EU27 ou EU28, conforme a edição.
PRR_EDICOES = {
    "2011": dict(BRA=85.9, CHN=77.9, ESP=81.2, ITA=64.5, FRA=49.1, GBR=31.9, USA=39.4, JPN=34.5, OECD=57.3, EU=61.6, media_ocde="OECD34", media_ue="EU27", tabela="II.2"),
    "2013": dict(BRA=57.5, CHN=77.9, ESP=73.9, ITA=71.2, FRA=58.8, GBR=32.6, USA=38.3, JPN=35.6, OECD=54.4, EU=58.0, media_ocde="OECD34", media_ue="EU27", tabela="4.1"),
    "2015": dict(BRA=69.5, CHN=74.0, ESP=82.1, ITA=69.5, FRA=55.4, GBR=21.6, USA=35.2, JPN=35.1, OECD=52.9, EU=59.0, media_ocde="OECD34", media_ue="EU28", tabela="6.1"),
    "2017": dict(BRA=69.5, CHN=76.0, ESP=72.3, ITA=83.1, FRA=60.5, GBR=22.1, USA=38.3, JPN=34.6, OECD=52.9, EU=58.3, media_ocde="OECD", media_ue="EU28", tabela="4.2"),
    "2019": dict(BRA=58.9, CHN=71.6, ESP=72.3, ITA=79.5, FRA=60.1, GBR=21.7, USA=39.4, JPN=32.0, OECD=49.0, EU=52.0, media_ocde="OECD", media_ue="EU28", tabela="5.1"),
    "2021": dict(BRA=88.4, CHN=71.6, ESP=73.9, ITA=74.6, FRA=60.2, GBR=49.0, USA=39.2, JPN=32.4, OECD=51.8, EU=53.4, media_ocde="OECD", media_ue="EU27", tabela="4.1"),
    "2023": dict(BRA=88.4, CHN=68.3, ESP=80.4, ITA=76.1, FRA=57.6, GBR=41.9, USA=39.1, JPN=32.4, OECD=50.7, EU=54.8, media_ocde="OECD", media_ue="EU27", tabela="4.1"),
}
PRR_PAISES = [("BRA", "Brasil"), ("CHN", "China"), ("ESP", "Espanha"), ("ITA", "Itália"), ("FRA", "França"),
              ("GBR", "Reino Unido"), ("USA", "Estados Unidos"), ("JPN", "Japão")]
PRR_COR = {"BRA": "#FFFFFF", "CHN": "#FFFF00", "ESP": "#C0504D", "ITA": "#9BBB59", "FRA": "#4F81BD",
           "GBR": "#8EB4E3", "USA": "#1F497D", "JPN": "#632523"}
# os 26 países do gráfico do Financial Times (fonte: OCDE), para a versão "seleção"
PRR_FT = ["BRA", "CHN", "ESP", "GRC", "NLD", "AUT", "DNK", "PRT", "ITA", "TUR", "FIN", "FRA", "HUN", "NOR", "GBR",
          "BEL", "CHE", "DEU", "AUS", "USA", "NZL", "CAN", "JPN", "POL", "IRL", "ZAF"]
MEMBROS_OCDE = ["AUS", "AUT", "BEL", "CAN", "CHL", "COL", "CRI", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN",
                "ISL", "IRL", "ISR", "ITA", "JPN", "KOR", "LVA", "LTU", "LUX", "MEX", "NLD", "NZL", "NOR", "POL", "PRT",
                "SVK", "SVN", "ESP", "SWE", "CHE", "TUR", "GBR", "USA"]
MEMBROS_UE = ["AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "IRL", "ITA",
              "LVA", "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE"]
# GGX_NGDP x GGX / NGDP: tolerância por país (p.p.), de 2001 a 2026 no WEO de set/2026.
# Ano fiscal: o FMI divide pelo PIB do ano fiscal (diferença de até 4,2 p.p., Dominica).
# Venezuela: na hiperinflação o FMI usa outra base de PIB (até 7,9 p.p.). Polônia: 0,17 p.p.
ANO_FISCAL = {"BHS", "BRB", "BWA", "DMA", "FJI", "HKG", "JAM", "LBR", "LCA", "MUS", "SGP", "SWZ", "THA", "TTO"}
TOL_GGX = dict({c: 5.0 for c in ANO_FISCAL}, VEN=10.0, POL=0.25)
VERMELHO, BRANCO, CINZA = "#C0504D", "#FFFFFF", "#8a8a86"

NOMES = {
    "AFG": "Afeganistão", "ECU": "Equador", "ERI": "Eritreia", "LBN": "Líbano", "SEN": "Senegal", "SYR": "Síria",
    "VEN": "Venezuela", "WBG": "Cisjordânia e Gaza",
    "ABW": "Aruba", "AGO": "Angola", "ALB": "Albânia", "AND": "Andorra", "ARE": "Emirados Árabes Unidos",
    "ARG": "Argentina", "ARM": "Armênia", "ATG": "Antígua e Barbuda", "AUS": "Austrália", "AUT": "Áustria",
    "AZE": "Azerbaijão", "BDI": "Burundi", "BEL": "Bélgica", "BEN": "Benin", "BFA": "Burquina Faso",
    "BGD": "Bangladesh", "BGR": "Bulgária", "BHR": "Barein", "BHS": "Bahamas", "BIH": "Bósnia e Herzegovina",
    "BLR": "Bielorrússia", "BLZ": "Belize", "BOL": "Bolívia", "BRA": "Brasil", "BRB": "Barbados",
    "BRN": "Brunei", "BTN": "Butão", "BWA": "Botsuana", "CAF": "República Centro-Africana", "CAN": "Canadá",
    "CHE": "Suíça", "CHL": "Chile", "CHN": "China", "CIV": "Costa do Marfim", "CMR": "Camarões",
    "COD": "Congo - Kinshasa", "COG": "República do Congo", "COL": "Colômbia", "COM": "Comores",
    "CPV": "Cabo Verde", "CRI": "Costa Rica", "CYP": "Chipre", "CZE": "Tchéquia", "DEU": "Alemanha",
    "DJI": "Djibuti", "DMA": "Dominica", "DNK": "Dinamarca", "DOM": "República Dominicana", "DZA": "Argélia",
    "EGY": "Egito", "ESP": "Espanha", "EST": "Estônia", "ETH": "Etiópia", "FIN": "Finlândia", "FJI": "Fiji",
    "FRA": "França", "FSM": "Micronésia", "GAB": "Gabão", "GBR": "Reino Unido", "GEO": "Geórgia",
    "GHA": "Gana", "GIN": "Guiné", "GMB": "Gâmbia", "GNB": "Guiné-Bissau", "GNQ": "Guiné Equatorial",
    "GRC": "Grécia", "GRD": "Granada", "GTM": "Guatemala", "GUY": "Guiana", "HKG": "Hong Kong, RAE da China",
    "HND": "Honduras", "HRV": "Croácia", "HTI": "Haiti", "HUN": "Hungria", "IDN": "Indonésia", "IND": "Índia",
    "IRL": "Irlanda", "IRN": "Irã", "IRQ": "Iraque", "ISL": "Islândia", "ISR": "Israel", "ITA": "Itália",
    "JAM": "Jamaica", "JOR": "Jordânia", "JPN": "Japão", "KAZ": "Cazaquistão", "KEN": "Quênia",
    "KGZ": "Quirguistão", "KHM": "Camboja", "KIR": "Quiribati", "KNA": "São Cristóvão e Névis",
    "KOR": "Coreia do Sul", "KOS": "Kosovo", "KWT": "Kuwait", "LAO": "Laos", "LBR": "Libéria", "LBY": "Líbia",
    "LCA": "Santa Lúcia", "LIE": "Liechtenstein", "LKA": "Sri Lanka", "LSO": "Lesoto", "LTU": "Lituânia",
    "LUX": "Luxemburgo", "LVA": "Letônia", "MAC": "Macau, RAE da China", "MAR": "Marrocos", "MDA": "Moldávia",
    "MDG": "Madagascar", "MDV": "Maldivas", "MEX": "México", "MHL": "Ilhas Marshall",
    "MKD": "Macedônia do Norte", "MLI": "Mali", "MLT": "Malta", "MMR": "Mianmar (Birmânia)",
    "MNE": "Montenegro", "MNG": "Mongólia", "MOZ": "Moçambique", "MRT": "Mauritânia", "MUS": "Maurício",
    "MWI": "Malaui", "MYS": "Malásia", "NAM": "Namíbia", "NER": "Níger", "NGA": "Nigéria", "NIC": "Nicarágua",
    "NLD": "Países Baixos", "NOR": "Noruega", "NPL": "Nepal", "NRU": "Nauru", "NZL": "Nova Zelândia",
    "OMN": "Omã", "PAK": "Paquistão", "PAN": "Panamá", "PER": "Peru", "PHL": "Filipinas", "PLW": "Palau",
    "PNG": "Papua-Nova Guiné", "POL": "Polônia", "PRI": "Porto Rico", "PRT": "Portugal", "PRY": "Paraguai",
    "QAT": "Catar", "ROU": "Romênia", "RUS": "Rússia", "RWA": "Ruanda", "SAU": "Arábia Saudita",
    "SDN": "Sudão", "SGP": "Singapura", "SLB": "Ilhas Salomão", "SLE": "Serra Leoa", "SLV": "El Salvador",
    "SMR": "San Marino", "SOM": "Somália", "SRB": "Sérvia", "SSD": "Sudão do Sul",
    "STP": "São Tomé e Príncipe", "SUR": "Suriname", "SVK": "Eslováquia", "SVN": "Eslovênia", "SWE": "Suécia",
    "SWZ": "Essuatíni", "SYC": "Seicheles", "TCD": "Chade", "TGO": "Togo", "THA": "Tailândia",
    "TJK": "Tadjiquistão", "TKM": "Turcomenistão", "TLS": "Timor-Leste", "TON": "Tonga",
    "TTO": "Trinidad e Tobago", "TUN": "Tunísia", "TUR": "Turquia", "TUV": "Tuvalu", "TWN": "Taiwan",
    "TZA": "Tanzânia", "UGA": "Uganda", "UKR": "Ucrânia", "URY": "Uruguai", "USA": "Estados Unidos",
    "UZB": "Uzbequistão", "VCT": "São Vicente e Granadinas", "VNM": "Vietnã", "VUT": "Vanuatu", "WSM": "Samoa",
    "YEM": "Iêmen", "ZAF": "África do Sul", "ZMB": "Zâmbia", "ZWE": "Zimbábue",
}


def baixar(url, tentativas=4):
    ultimo = None
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                return r.read()
        except Exception as e:                               # noqa: BLE001
            ultimo = e
            time.sleep(3 * (i + 1))
    raise RuntimeError("não deu para baixar %s: %s" % (url, ultimo))


def conferir(condicao, msg):
    if not condicao:
        raise RuntimeError("conferência falhou: " + msg)


def weo(indicador):
    """{país: {ano: valor}} de um indicador do WEO, e a edição (data da série)."""
    d = json.loads(baixar(API + "*.%s.A" % indicador))
    st = d["data"]["structures"][0]
    paises = [v["id"] for v in st["dimensions"]["series"][0]["values"]]
    anos = [v["value"] for v in st["dimensions"]["observation"][0]["values"]]
    out, edicoes = {}, set()
    for chave, s in d["data"]["dataSets"][0]["series"].items():
        pais = paises[int(chave.split(":")[0])]
        if s["attributes"][-1]:
            edicoes.add(s["attributes"][-1])
        obs = {}
        for i, v in s["observations"].items():
            if v and v[0] not in (None, "", "NaN"):
                obs[anos[int(i)]] = float(v[0])
        out[pais] = obs
    return out, edicoes


def carregar_owid():
    """{iso3: {ano: gasto % PIB}} do OWID (FMI histórico)."""
    import csv
    import io
    out = {}
    for r in csv.DictReader(io.StringIO(baixar(OWID).decode("utf-8"))):
        if r["code"] in dict(HIST) and r["expenditure"]:
            out.setdefault(r["code"], {})[r["year"]] = float(r["expenditure"])
    return out


def carregar_ocde():
    """{(iso3, P3|P51G): {ano: valor em moeda local}} das contas do governo geral."""
    import csv
    import io
    chave = ".".join(["A", "+".join(c for c, _ in HIST), "S13", "", "", "P51G+P3", "", "", "", "", "", "", ""])
    txt = baixar(OCDE + chave + "?startPeriod=1950&format=csvfilewithlabels").decode("utf-8")
    out = {}
    for r in csv.DictReader(io.StringIO(txt)):
        conferir(r["UNIT_MEASURE"] == "XDC" and r["ACCOUNTING_ENTRY"] == "D", "OCDE: unidade ou lançamento inesperado")
        out.setdefault((r["REF_AREA"], r["TRANSACTION"]), {})[r["TIME_PERIOD"]] = \
            float(r["OBS_VALUE"]) * 10 ** int(r["UNIT_MULT"])
    return out


def carregar_wb(indicador):
    d = json.loads(baixar(WB % (";".join(c for c, _ in HIST), indicador)))[1]
    out = {}
    for r in d:
        if r["value"] is not None:
            out.setdefault(r["countryiso3code"], {})[r["date"]] = float(r["value"])
    return out


def br(v, casas=1):
    s = "{:,.{c}f}".format(v, c=casas)
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def historico(gasto):
    """Gasto total desde 1830 (OWID) e a decomposição consumo, investimento e o resto."""
    owid = carregar_owid()
    ocde = carregar_ocde()
    pib = carregar_wb("NY.GDP.MKTP.CN")
    cons_wb = carregar_wb("NE.CON.GOVT.ZS")

    # 1) série longa do OWID e conferência contra o WEO atual (2011 a 2019)
    for c, nome in HIST:
        conferir(c in owid and len(owid[c]) >= 40, "OWID sem %s" % nome)
        for y in map(str, range(2011, 2020)):
            if y in owid[c] and y in gasto.get(c, {}):
                conferir(abs(owid[c][y] - gasto[c][y]) <= 1.5,
                         "OWID e WEO divergem em %s %s (%.2f x %.2f)" % (nome, y, owid[c][y], gasto[c][y]))
    print("  OWID, último ano:", ", ".join("%s %s %.1f%%" % (n, max(owid[c], key=int), owid[c][max(owid[c], key=int)])
                                         for c, n in HIST))
    # continuação pelo WEO atual: do último ano do OWID até ANO, pontilhada. Começa no
    # valor do próprio WEO no último ano do OWID (não no do OWID), para não criar um
    # degrau artificial entre as duas edições do FMI.
    fim_owid = max(max(owid[c], key=int) for c, _ in HIST)
    anos_weo = [str(y) for y in range(int(fim_owid), int(ANO) + 1)]
    dif = {}
    for c, nome in HIST:
        conferir(all(y in gasto.get(c, {}) for y in anos_weo), "WEO sem %s em %s" % (nome, anos_weo))
        dif[c] = owid[c][fim_owid] - gasto[c][fim_owid]
        conferir(abs(dif[c]) <= 2.5, "OWID e WEO divergem demais em %s %s (%.2f)" % (nome, fim_owid, dif[c]))
    print("  WEO %s a %s:" % (fim_owid, ANO), ", ".join("%s %.1f%% (OWID - WEO em %s: %+.2f)"
          % (n, gasto[c][ANO], fim_owid, dif[c]) for c, n in HIST))
    pior = max(HIST, key=lambda cn: abs(dif[cn[0]]))
    g_total = dict(
        id="gasto-publico-historico",
        titulo="Gasto do governo em %% do PIB, %s a %s" % (min(min(owid[c], key=int) for c, _ in HIST), ANO),
        subtitulo="Despesa total do governo em % do PIB, inclusive juros da dívida; pontilhado: FMI atual",
        unidade="%", buracoMax=12,
        fonte="FMI (Public Finances in Modern History e World Economic Outlook) via Our World in Data e FMI "
              "(World Economic Outlook)",
        nota=("Governo geral (central, estados, municípios e previdência) quando disponível; nos anos mais antigos, "
              "só o governo central. Linha cheia: série do Our World in Data, que usa uma edição anterior do FMI. "
              "Linha pontilhada: World Economic Outlook atual (set/2026), de %s a %s; %s é estimativa do FMI e %s "
              "também pode ser, conforme o país. Em %s as duas edições diferem em até %s pontos do PIB (%s), por "
              "isso a linha pontilhada não começa exatamente no fim da cheia."
              % (fim_owid, ANO, ANO, int(ANO) - 1, fim_owid, br(abs(dif[pior[0]])), pior[1])),
        series=[dict(nome=n, cor=COR_HIST[c], largura=5.0 if c == "BRA" else 4.0,
                     dados=[["%s-01" % y, round(owid[c][y], 2)] for y in sorted(owid[c], key=int)])
                for c, n in HIST]
               + [dict(nome="%s (WEO, %s a %s)" % (n, fim_owid, ANO), cor=COR_HIST[c], legenda=False, rotulo=True,
                       traco="pontilhado", largura=5.0 if c == "BRA" else 4.0,
                       dados=[["%s-01" % y, round(gasto[c][y], 2)] for y in anos_weo])
                  for c, n in HIST],
    )

    # 2) consumo e investimento em % do PIB (OCDE / PIB do Banco Mundial)
    cons, inv = {}, {}
    for c, nome in HIST:
        for t, dest in (("P3", cons), ("P51G", inv)):
            for y, v in ocde.get((c, t), {}).items():
                if y in pib.get(c, {}):
                    dest.setdefault(c, {})[y] = v / pib[c][y] * 100
        for y, v in cons.get(c, {}).items():
            if y in cons_wb.get(c, {}):
                conferir(abs(v - cons_wb[c][y]) <= 1.0, "consumo do governo %s %s: OCDE/PIB %.2f x Banco Mundial %.2f"
                         % (nome, y, v, cons_wb[c][y]))
        conferir(c in cons and c in inv, "OCDE sem consumo ou investimento de %s" % nome)

    def linhas(dic):
        return [dict(nome=n, cor=COR_HIST[c], largura=5.0 if c == "BRA" else 4.0, rotulo=True,
                     dados=[["%s-01" % y, round(dic[c][y], 2)] for y in sorted(dic[c], key=int)])
                for c, n in HIST if c in dic]
    g_ci = dict(
        id="gasto-publico-consumo-investimento",
        titulo="Consumo e investimento do governo geral em % do PIB",
        subtitulo="Contas nacionais: consumo final do governo (o G do PIB pela ótica da demanda) e formação bruta "
                  "de capital fixo",
        unidade="%", buracoMax=12,
        fonte="OCDE (contas do governo geral), Banco Mundial e FtM",
        nota=("Consumo do governo (P3): salários dos servidores, compras de bens e serviços e a depreciação do "
              "capital público, menos o que o governo vende, mais os bens e serviços que entrega às famílias (como "
              "remédios e serviços de saúde comprados do setor privado). Investimento (P51G): obras, equipamentos e "
              "softwares do governo geral. Os dois em moeda local, divididos pelo PIB nominal do Banco Mundial. Na "
              "China, as contas da OCDE vão até 2023; no Brasil, o investimento vai até 2020."),
        variantes=[dict(rot="Consumo do governo", series=linhas(cons)),
                   dict(rot="Investimento do governo", series=linhas(inv))],
    )
    g_ci["series"] = g_ci["variantes"][0]["series"]

    # 3) decomposição do gasto total (WEO atual) por país
    variantes = []
    for c, nome in HIST:
        anos = sorted((y for y in gasto.get(c, {}) if y in cons.get(c, {}) and y in inv.get(c, {})), key=int)
        anos = [y for y in anos if int(INICIO_COMP.get(c, "0")) <= int(y) <= datetime.date.today().year - 1]
        conferir(len(anos) >= 15, "decomposição curta para %s (%d anos)" % (nome, len(anos)))
        resto = {y: gasto[c][y] - cons[c][y] - inv[c][y] for y in anos}
        for y, v in resto.items():
            conferir(v >= 0, "resto negativo em %s %s (%.2f)" % (nome, y, v))
        u = anos[-1]
        print("  %s %s: total %.1f = consumo %.1f + investimento %.1f + demais %.1f (%% do PIB)"
              % (nome, u, gasto[c][u], cons[c][u], inv[c][u], resto[u]))
        variantes.append(dict(
            rot="%s (%s a %s)" % (nome, anos[0], u), categorias=anos, barra=1,
            series=[dict(nome="Consumo do governo", cor=AZUL, tipo="barra",
                         dados=[[str(i), round(cons[c][y], 2)] for i, y in enumerate(anos)]),
                    dict(nome="Investimento do governo", cor=VERDE, tipo="barra",
                         dados=[[str(i), round(inv[c][y], 2)] for i, y in enumerate(anos)]),
                    dict(nome="Demais despesas (transferências, juros, subsídios e outras)", cor=VERMELHO, tipo="barra",
                         dados=[[str(i), round(resto[y], 2)] for i, y in enumerate(anos)])]))
    g_comp = dict(
        id="gasto-publico-composicao",
        titulo="Composição do gasto do governo geral em % do PIB",
        subtitulo="Consumo e investimento do governo e as demais despesas, que não entram no PIB pela demanda",
        unidade="%", fonte="FMI (World Economic Outlook), OCDE, Banco Mundial e FtM",
        nota=("Gasto total do World Economic Outlook do FMI, inclusive juros. Consumo e investimento pelas contas "
              "nacionais (OCDE). Demais despesas: o total menos consumo e investimento, isto é, aposentadorias, "
              "benefícios sociais em dinheiro, juros da dívida, subsídios e outras transferências; são despesas "
              "que mudam a renda de quem recebe, mas não são compra do governo e não somam no PIB pela ótica da "
              "demanda. Como as duas fontes usam conceitos um pouco diferentes (o consumo das contas nacionais "
              "inclui a depreciação do capital público), o resto é uma aproximação. Na China, a decomposição começa em "
              "2008: antes disso, o total do FMI não cobre todo o governo geral."),
        variantes=variantes,
    )
    for k in ("categorias", "barra", "series"):
        g_comp[k] = variantes[0][k]
    return [g_total, g_comp, g_ci]


def credito_bis():
    """Composição do crédito ao setor não financeiro (BIS), os TOP_CREDITO países com a maior fatia do governo."""
    import csv
    import io
    ini = "%d-Q1" % (datetime.date.today().year - 2)
    ult = {}
    for r in csv.DictReader(io.StringIO(baixar(BIS % ini).decode("utf-8"))):
        if r["OBS_VALUE"] in ("", "NaN") or r["BORROWERS_CTY"] not in NOMES_BIS:
            continue
        k = (r["BORROWERS_CTY"], r["TC_BORROWERS"], r["VALUATION"])
        if r["TIME_PERIOD"] > ult.get(k, ("", 0))[0]:
            ult[k] = (r["TIME_PERIOD"], float(r["OBS_VALUE"]))
    linhas, trimestres = [], set()
    for c, nome in NOMES_BIS.items():
        gov = ult.get((c, "G", "M")) or ult.get((c, "G", "N"))
        partes = [gov, ult.get((c, "H", "M")), ult.get((c, "N", "M")), ult.get((c, "P", "M")), ult.get((c, "C", "M"))]
        conferir(all(partes), "BIS sem algum setor para %s" % nome)
        trimestres.update(x[0] for x in partes)
        G, H, N, P, C = (x[1] for x in partes)
        conferir(abs(P - H - N) <= 0.3, "BIS %s: privado %.1f != famílias + empresas %.1f" % (nome, P, H + N))
        conferir(abs(C - G - H - N) <= 0.3, "BIS %s: total %.1f != governo + famílias + empresas %.1f" % (nome, C, G + H + N))
        conferir(min(G, H, N) >= 0, "BIS %s: setor negativo" % nome)
        linhas.append(dict(c=c, nome=nome, G=G, H=H, N=N, P=P, C=G + H + N,
                           valor_gov="mercado" if (c, "G", "M") in ult else "nominal"))
    conferir(len(trimestres) == 1, "países do BIS em trimestres diferentes: %s" % sorted(trimestres))
    tri = trimestres.pop()
    for d in linhas:
        d["sG"], d["sH"], d["sN"], d["sP"] = (100 * d[k] / d["C"] for k in ("G", "H", "N", "P"))
    top = sorted(linhas, key=lambda d: -d["sG"])[:TOP_CREDITO]
    print("  BIS %s, %d países; maior fatia do governo:" % (tri, len(linhas)),
          ", ".join("%s %.1f%%" % (d["nome"], d["sG"]) for d in top[:6]), "...", "%s %.1f%%" % (top[-1]["nome"], top[-1]["sG"]))
    rot_tri = "%sº tri/%s" % (tri[-1], tri[:4])

    def itens(chaves):
        return [[d["nome"], round(sum(d[k] for k in chaves), 1), None, d["c"] == "BR", None,
                 [round(d[k], 1) for k in chaves]] for d in top]
    GOV = dict(nome="Governo geral", cor=VERMELHO)
    FAM = dict(nome="Famílias", cor=AZUL)
    EMP = dict(nome="Empresas não financeiras", cor=VERDE)
    variantes = [
        dict(rot="Governo, famílias e empresas (% do total)", semTotal=True, eixoMax=100,
             partes=[GOV, FAM, EMP], itens=itens(["sG", "sH", "sN"])),
        dict(rot="Governo e setor privado (% do total)", semTotal=True, eixoMax=100,
             partes=[GOV, dict(nome="Setor privado não financeiro (famílias + empresas)", cor=AZUL_CLARO)],
             itens=itens(["sG", "sP"])),
        dict(rot="Governo, famílias e empresas (% do PIB)", semTotal=False, eixoMax=None,
             partes=[GOV, FAM, EMP], itens=itens(["G", "H", "N"])),
    ]
    g = dict(
        id="credito-setor-nao-financeiro-composicao",
        tipo="ranking", unidade="pct1",
        titulo="Composição do crédito ao setor não financeiro, %s" % rot_tri,
        subtitulo="Os %d países com a maior fatia do governo geral no total, entre os %d do BIS"
                  % (TOP_CREDITO, len(linhas)),
        fonte="BIS (Credit to the non-financial sector) e FtM",
        nota=("Crédito de todos os credores (bancos, mercado de títulos, estrangeiros e o próprio banco central) ao "
              "setor não financeiro, em %% do PIB, ajustado a quebras pelo BIS. Para o governo geral é a dívida do "
              "governo (títulos e empréstimos), que pode diferir da dívida bruta publicada por cada país; o governo "
              "entra a valor de mercado quando o BIS tem essa série e a valor nominal quando não tem, como no total "
              "do BIS. Setor privado não financeiro = famílias (com as instituições sem fins lucrativos) + empresas "
              "não financeiras; por isso ele aparece numa versão separada, para não ser contado duas vezes. Países "
              "ordenados pela fatia do governo no total, também na versão em %% do PIB. Dados de %s."
              % rot_tri),
        variantes=variantes,
    )
    for k in ("partes", "itens", "semTotal", "eixoMax"):
        if k in variantes[0]:
            g[k] = variantes[0][k]
    return g


def aposentadorias():
    """Taxa bruta de reposição (OCDE): ranking da edição corrente e a série das edições desde 2011."""
    import csv
    import io
    prr, idade, ano_par = {}, {}, set()
    for r in csv.DictReader(io.StringIO(baixar(OCDE_PRR).decode("utf-8-sig"))):
        if r["MEASURE"] == "GPRR100" and r["SEX"] == "M" and r["OPTIONALITY"] == "M":
            prr[r["REF_AREA"]] = float(r["OBS_VALUE"])
            ano_par.add(r["TIME_PERIOD"])
    for r in csv.DictReader(io.StringIO(baixar(OCDE_DPS).decode("utf-8-sig"))):
        if r["MEASURE"] == "FRPLF22" and r["SEX"] == "M" and r["OBS_VALUE"]:
            idade[r["REF_AREA"]] = float(r["OBS_VALUE"])
    conferir(len(ano_par) == 1, "OCDE: mais de um ano de parâmetros na taxa de reposição (%s)" % sorted(ano_par))
    ano_par = ano_par.pop()
    edicao = str(int(ano_par) + 1)          # parâmetros de 2024 = Pensions at a Glance 2025
    conferir(edicao not in PRR_EDICOES, "a edição %s já está em PRR_EDICOES" % edicao)
    for nome, membros, cod in (("OCDE", MEMBROS_OCDE, "OECD_REP"), ("UE", MEMBROS_UE, "EU27")):
        falta = [c for c in membros if c not in prr]
        conferir(not falta, "OCDE: média da %s sem %s" % (nome, falta))
        media = sum(prr[c] for c in membros) / len(membros)
        conferir(abs(media - prr[cod]) <= 0.1, "média da %s refeita %.2f x OCDE %.2f" % (nome, media, prr[cod]))
    for c, _ in PRR_PAISES:
        conferir(c in prr, "OCDE sem taxa de reposição de %s" % c)
    print("  OCDE, taxa de reposição (parâmetros de %s): " % ano_par
          + ", ".join("%s %.1f%%" % (c, prr[c]) for c in ("BRA", "CHN", "ESP", "OECD_REP", "EU27")))

    def nome(c):
        return {"OECD_REP": "Média da OCDE", "EU27": "Média da UE-27"}.get(c, NOMES.get(c, c))

    def itens(codigos):
        cods = sorted(codigos + ["OECD_REP", "EU27"], key=lambda c: -prr[c])
        out = []
        for c in cods:
            rot = nome(c) + (" (%d)" % round(idade[c]) if c in idade and c not in ("OECD_REP", "EU27") else "")
            cor = VERMELHO if c == DESTAQUE else (CINZA if c in ("OECD_REP", "EU27") else AZUL)
            out.append([rot, round(prr[c], 1), cor, c in (DESTAQUE, "OECD_REP", "EU27")])
        return out
    todos = [c for c in prr if c not in ("OECD_REP", "EU27")]
    nota_base = ("Taxa bruta de reposição: aposentadoria dos regimes obrigatórios (públicos e privados) em %% do "
                 "salário, para um homem que ganha o salário médio e trabalha a carreira inteira, desde os 22 anos, "
                 "até a idade normal de aposentadoria, entre parênteses. É uma projeção do modelo da OCDE para quem "
                 "começa a trabalhar hoje, com as regras de %s (Pensions at a Glance %s). Médias simples dos 38 "
                 "países da OCDE e dos 27 da UE." % (ano_par, edicao))
    g_rank = dict(
        id="aposentadoria-taxa-reposicao-ranking", tipo="ranking", unidade="pct1",
        titulo="Taxa bruta de reposição da aposentadoria, regras de %s" % ano_par,
        subtitulo="Aposentadoria em % do salário, homem com salário médio; idade de aposentadoria entre parênteses",
        fonte="OCDE (Pensions at a Glance %s) e FtM" % edicao, nota=nota_base,
        itens=itens(PRR_FT),
        variantes=[dict(rot="Países do gráfico do Financial Times", itens=itens(PRR_FT)),
                   dict(rot="Todos os países da base (%d)" % len(todos), itens=itens(todos))],
    )

    serie = {e: dict(v) for e, v in PRR_EDICOES.items()}
    serie[edicao] = dict({c: prr[c] for c, _ in PRR_PAISES}, OECD=prr["OECD_REP"], EU=prr["EU27"])
    eds = sorted(serie, key=int)

    def linha(chave, nome_s, cor, principal=False):
        return dict(nome=nome_s, cor=cor, largura=5.0 if principal else 4.0, rotulo=True,
                    dados=[["%s-01" % e, round(serie[e][chave], 1)] for e in eds])
    nota_t = ("Cada ponto é uma edição do Pensions at a Glance (%s a %s): a taxa bruta de reposição projetada para "
              "um homem com salário médio e carreira completa, sob as regras em vigor na época da edição. As "
              "mudanças vêm de reformas, como a do Brasil em 2019 (idade mínima de 65 anos para homens), e também de "
              "revisões do modelo da OCDE: a carreira começa aos 20 anos até a edição de 2017 e aos 22 a partir de "
              "2019. Média da OCDE: 34 países até 2015 e todos os membros depois; UE: 27 ou 28 países, conforme a "
              "edição. Edições de %s a %s extraídas das tabelas oficiais (PDF e página); %s, da API da OCDE."
              % (eds[0], eds[-1], eds[0], eds[-2], edicao))
    g_paises = dict(
        id="aposentadoria-taxa-reposicao-paises", titulo="Taxa bruta de reposição da aposentadoria, %s a %s"
        % (eds[0], eds[-1]),
        subtitulo="Aposentadoria em % do salário, homem com salário médio; por edição do Pensions at a Glance",
        unidade="pct1", buracoMax=25, fonte="OCDE (Pensions at a Glance, edições de %s a %s) e FtM" % (eds[0], eds[-1]),
        nota=nota_t,
        series=[linha(c, n, PRR_COR[c], c == "BRA") for c, n in PRR_PAISES],
    )
    g_medias = dict(
        id="aposentadoria-taxa-reposicao-medias",
        titulo="Taxa bruta de reposição: Brasil, EUA e médias da OCDE e da UE, %s a %s" % (eds[0], eds[-1]),
        subtitulo="Aposentadoria em % do salário, homem com salário médio; por edição do Pensions at a Glance",
        unidade="pct1", buracoMax=25, fonte="OCDE (Pensions at a Glance, edições de %s a %s) e FtM" % (eds[0], eds[-1]),
        nota=nota_t,
        series=[linha("BRA", "Brasil", BRANCO, True), linha("USA", "Estados Unidos", VERMELHO),
                linha("OECD", "Média da OCDE", AZUL), linha("EU", "Média da UE", VERDE)],
    )
    return [g_rank, g_paises, g_medias]


def main():
    gasto, ed = weo("GGX_NGDP")
    ppc, _ = weo("PPPPC")
    pop, _ = weo("LP")
    ggx, _ = weo("GGX")
    ngdp, _ = weo("NGDP")
    pppgdp, _ = weo("PPPGDP")
    print("  WEO, datas das séries:", ", ".join(sorted(ed)))

    def paises_de(ano):
        return sorted(c for c in gasto if ano in gasto[c] and ano in ppc.get(c, {}) and ano in pop.get(c, {})
                      and ano in pppgdp.get(c, {}))

    anos = [str(y) for y in range(int(ANO_INI), int(ANO) + 1)]
    for ano in anos:
        lista = paises_de(ano)
        for c in lista:
            g = gasto[c][ano]
            if ano in ggx.get(c, {}) and ano in ngdp.get(c, {}) and ngdp[c][ano]:
                calc = ggx[c][ano] / ngdp[c][ano] * 100
                tol = TOL_GGX.get(c, 0.05)
                conferir(abs(calc - g) <= tol, "GGX/NGDP de %s %s (%.3f) != GGX_NGDP (%.3f)" % (c, ano, calc, g))
            if pop[c][ano]:
                calc = pppgdp[c][ano] / pop[c][ano]
                conferir(abs(calc / ppc[c][ano] - 1) <= 0.005,
                         "PPPGDP/LP de %s %s (%.0f) != PPPPC (%.0f)" % (c, ano, calc, ppc[c][ano]))
            conferir(c in NOMES, "país sem nome em português: %s" % c)
            conferir(0 < g < 150 and ppc[c][ano] > 100, "valor suspeito em %s %s" % (c, ano))
        conferir(len(lista) >= 150 and DESTAQUE in lista and "USA" in lista,
                 "amostra pequena em %s (%d países)" % (ano, len(lista)))

    def ols(lista, ano):
        xs = [math.log10(ppc[c][ano]) for c in lista]
        ys = [gasto[c][ano] for c in lista]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        syy = sum((y - my) ** 2 for y in ys)
        b = sxy / sxx
        a = my - b * mx
        ep_b = math.sqrt(sum((y - a - b * x) ** 2 for x, y in zip(xs, ys)) / (n - 2) / sxx)
        return a, b, sxy / math.sqrt(sxx * syy), ep_b

    # o raio é fixo entre os anos: o maior PIB em PPC de ANO (China) tem o maior raio
    ref = max(pppgdp[c][ANO] for c in paises_de(ANO))

    def quadro(lista, ano, imprime=False):
        a, b, r, ep_b = ols(lista, ano)
        n = len(lista)
        if imprime:
            bx, by = ppc[DESTAQUE][ano], gasto[DESTAQUE][ano]
            print("  %s, %d países: gasto = %.2f + %.2f·log10(PIB pc) (ep %.2f), r = %+.2f; Brasil %.2f%% contra %.2f%% "
                  "da reta" % (ano, n, a, b, ep_b, r, by, a + b * math.log10(bx)))
        pontos = []
        for c in sorted(lista, key=lambda k: -pppgdp[k][ano]):
            g, x, p, y = gasto[c][ano], ppc[c][ano], pop[c][ano], pppgdp[c][ano]
            ponto = dict(x=round(x, 0), y=round(g, 2), raio=round(0.7 + 3.3 * math.sqrt(y / ref), 3),
                         n=NOMES[c], pib=round(y / 1e9, 0), pop=round(p / 1e6, 1))
            if c == DESTAQUE:
                ponto.update(destaque=True, rot=NOMES[c], nota="%s%% do PIB" % br(g), cor=VERMELHO, opacidade=1)
            elif c in ROTULADOS:
                ponto["rot"] = NOMES[c]
            pontos.append(ponto)
        pontos.sort(key=lambda q: 1 if q.get("destaque") else 0)   # o Brasil por cima
        return dict(
            legenda=[dict(rot="Brasil", cor=VERMELHO), dict(rot="Demais países (%d)" % (n - 1), cor=CINZA),
                     dict(rot="Tendência linear (r = %s)" % br(r, 2).replace("-", "−"), cor="linha:" + BRANCO)],
            pontos=pontos,
            reta=dict(a=round(a, 4), b=round(b, 4), de=round(min(ppc[c][ano] for c in lista), 0),
                      ate=round(max(ppc[c][ano] for c in lista), 0), cor=BRANCO),
        )

    def variante(rot, filtro):
        listas = {ano: [c for c in paises_de(ano) if filtro(c, ano)] for ano in anos}
        quadros = {ano: quadro(listas[ano], ano, imprime=ano in (ANO_INI, ANO)) for ano in anos}
        todos = [(ppc[c][ano], gasto[c][ano]) for ano in anos for c in listas[ano]]
        x_min, x_max = min(v[0] for v in todos), max(v[0] for v in todos)
        y_max = max(v[1] for v in todos)
        v = dict(rot=rot, anoPadrao=ANO, quadros=quadros,
                 eixoX=dict(unidade="usd", log=True, min=round(x_min / 1.15, 0), max=round(x_max * 1.15, 0),
                            rot="PIB per capita (US$ internacionais em PPC, escala logarítmica)"),
                 eixoY=dict(unidade="pct0", rot="Gasto do governo geral (% do PIB)", zero=True,
                            max=10 * math.ceil(y_max / 10)))
        v.update(quadros[ANO])
        return v

    v1 = variante("Países com 1 milhão de habitantes ou mais", lambda c, ano: pop[c][ano] >= 1e6)
    v2 = variante("Todos os países (inclui microestados)", lambda c, ano: True)
    g_disp = dict(
        id="gasto-publico-pib-per-capita-2026",
        tipo="dispersao",
        titulo="Gasto público em %% do PIB vs PIB per capita, %s" % ANO,
        subtitulo="Despesa do governo geral (% do PIB) e PIB per capita em PPC; tamanho da bolha pelo PIB",
        nota=("Despesa total do governo geral, inclusive juros da dívida (GGX_NGDP do FMI). PIB per capita em "
              "paridade de poder de compra, em dólares internacionais correntes (PPPPC), no eixo em escala "
              "logarítmica. Tamanho da bolha proporcional ao PIB em PPC (PPPGDP), na mesma escala em todos os anos. "
              "Anos de %s a %s, no World Economic Outlook de set/2026; %s é estimativa do FMI e %s também pode ser, "
              "conforme o país. Reta de tendência por mínimos quadrados do gasto sobre o logaritmo do PIB per capita, "
              "com o mesmo peso para cada país." % (ANO_INI, ANO, ANO, int(ANO) - 1)),
        fonte="FMI (World Economic Outlook) e FtM",
        pontoPadrao=dict(cor=CINZA, opacidade=0.55),
        dicaModelo=["{n}", "Gasto do governo: {y:1}% do PIB", "PIB per capita (PPC): US$ {x:0}",
                    "PIB (PPC): US$ {pib:0} bilhões", "População: {pop:1} milhões"],
        variantes=[v1, v2],
    )
    for k in ("legenda", "eixoX", "eixoY", "pontos", "reta"):
        g_disp[k] = v1[k]
    meses = sorted((int(d.split("/")[2]), int(d.split("/")[0])) for d in ed)
    referencia = "%04d-%02d" % meses[-1]

    graficos_hist = historico(gasto)

    hoje = datetime.date.today().isoformat()
    doc = dict(assunto="Gasto público", grupo="Análises Variadas",
               fonte="FMI, OCDE, Banco Mundial, BIS, Our World in Data e FtM", referencia=referencia, atualizado=hoje, formato="artigo",
               secoes=[dict(titulo="O gasto ao longo do tempo", texto="", fontes=[], figuras=[], graficos=graficos_hist),
                       dict(titulo="Gasto público e renda", texto="", fontes=[], figuras=[], graficos=[g_disp]),
                       dict(titulo="Crédito ao setor não financeiro", texto="", fontes=[], figuras=[],
                            graficos=[credito_bis()]),
                       dict(titulo="Aposentadorias", texto="", fontes=[], figuras=[], graficos=aposentadorias())])
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado", SAIDA)


if __name__ == "__main__":
    sys.exit(main())

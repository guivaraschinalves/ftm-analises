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
  - GGX_NGDP = GGX / NGDP × 100 em cada país (≤ 0,05 p.p.). Exceção: os
    países de ANO_FISCAL, em que o FMI divide pelo PIB do ano fiscal e a conta
    com o PIB do ano civil difere em até 1,4 p.p. (WEO de set/2026); para eles
    a tolerância é 2 p.p.
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
# países com o nome escrito ao lado da bolha (os demais só na dica)
ROTULADOS = ["USA", "CHN", "IND", "FRA", "DEU", "ARG", "CHL", "MEX", "JPN", "NGA", "SGP", "NOR", "RUS", "ZAF"]
# conta de despesa no ano fiscal (a razão do FMI não bate com GGX / NGDP do ano civil)
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
ANO_FISCAL = {"BHS", "BRB", "BWA", "DMA", "FJI", "HKG", "JAM", "LCA", "MUS", "SGP", "SWZ", "THA", "TTO"}
VERMELHO, BRANCO, CINZA = "#C0504D", "#FFFFFF", "#8a8a86"

NOMES = {
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


def main():
    gasto, ed = weo("GGX_NGDP")
    ppc, _ = weo("PPPPC")
    pop, _ = weo("LP")
    ggx, _ = weo("GGX")
    ngdp, _ = weo("NGDP")
    pppgdp, _ = weo("PPPGDP")
    print("  WEO, datas das séries:", ", ".join(sorted(ed)))

    paises = sorted(c for c in gasto if ANO in gasto[c] and ANO in ppc.get(c, {}) and ANO in pop.get(c, {}))
    for c in paises:
        g = gasto[c][ANO]
        if ANO in ggx.get(c, {}) and ANO in ngdp.get(c, {}) and ngdp[c][ANO]:
            calc = ggx[c][ANO] / ngdp[c][ANO] * 100
            tol = 2.0 if c in ANO_FISCAL else 0.05
            conferir(abs(calc - g) <= tol, "GGX/NGDP de %s (%.3f) != GGX_NGDP (%.3f)" % (c, calc, g))
        conferir(ANO in pppgdp.get(c, {}), "sem PIB em PPC: %s" % c)
        if pop[c][ANO]:
            calc = pppgdp[c][ANO] / pop[c][ANO]
            conferir(abs(calc / ppc[c][ANO] - 1) <= 0.005, "PPPGDP/LP de %s (%.0f) != PPPPC (%.0f)" % (c, calc, ppc[c][ANO]))
        conferir(c in NOMES, "país sem nome em português: %s" % c)
        conferir(0 < g < 150 and ppc[c][ANO] > 100, "valor suspeito em %s" % c)
    conferir(len(paises) >= 150 and DESTAQUE in paises, "amostra pequena (%d países)" % len(paises))

    def ols(lista):
        xs = [math.log10(ppc[c][ANO]) for c in lista]
        ys = [gasto[c][ANO] for c in lista]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        syy = sum((y - my) ** 2 for y in ys)
        b = sxy / sxx
        a = my - b * mx
        ep_b = math.sqrt(sum((y - a - b * x) ** 2 for x, y in zip(xs, ys)) / (n - 2) / sxx)
        return a, b, sxy / math.sqrt(sxx * syy), ep_b

    ref = max(pppgdp[c][ANO] for c in paises)   # o maior PIB (China) tem o maior raio

    def variante(rot, lista):
        a, b, r, ep_b = ols(lista)
        n = len(lista)
        bx, by = ppc[DESTAQUE][ANO], gasto[DESTAQUE][ANO]
        print("  %s: %d países; gasto = %.2f + %.2f·log10(PIB pc) (ep %.2f), r = %+.2f; Brasil %.2f%% contra %.2f%% da reta"
              % (rot, n, a, b, ep_b, r, by, a + b * math.log10(bx)))
        pontos = []
        for c in sorted(lista, key=lambda k: -pppgdp[k][ANO]):
            g, x, p, y = gasto[c][ANO], ppc[c][ANO], pop[c][ANO], pppgdp[c][ANO]
            ponto = dict(
                x=round(x, 0), y=round(g, 2),
                raio=round(0.7 + 3.3 * math.sqrt(y / ref), 3),
                cor=VERMELHO if c == DESTAQUE else CINZA,
                dica="%s: gasto de %s%% do PIB; PIB per capita de US$ %s e PIB de US$ %s bilhões (PPC); população de %s milhões"
                     % (NOMES[c], br(g), br(x, 0), br(y / 1e9, 0), br(p / 1e6, 1)),
            )
            if c == DESTAQUE:
                ponto.update(destaque=True, rot=NOMES[c], nota="%s%% do PIB" % br(g))
            else:
                ponto["opacidade"] = 0.55
                if c in ROTULADOS:
                    ponto["rot"] = NOMES[c]
            pontos.append(ponto)
        pontos.sort(key=lambda q: 1 if q.get("destaque") else 0)   # o Brasil por cima
        return dict(
            rot=rot,
            legenda=[
                dict(rot="Brasil", cor=VERMELHO),
                dict(rot="Demais países (%d)" % (n - 1), cor=CINZA),
                dict(rot="Tendência linear (r = %s)" % br(r, 2).replace("-", "−"), cor="linha:" + BRANCO),
            ],
            eixoX=dict(unidade="usd", log=True, rot="PIB per capita (US$ internacionais em PPC, escala logarítmica)"),
            eixoY=dict(unidade="pct0", rot="Gasto do governo geral (% do PIB)", zero=True),
            pontos=pontos,
            reta=dict(a=round(a, 4), b=round(b, 4), de=round(min(ppc[c][ANO] for c in lista), 0),
                      ate=round(max(ppc[c][ANO] for c in lista), 0), cor=BRANCO),
        )

    grandes = [c for c in paises if pop[c][ANO] >= 1e6]
    conferir(DESTAQUE in grandes and len(grandes) >= 140, "amostra de países com 1 milhão+ pequena (%d)" % len(grandes))
    v1 = variante("Países com 1 milhão de habitantes ou mais", grandes)
    v2 = variante("Todos os países (inclui microestados)", paises)
    g_disp = dict(
        id="gasto-publico-pib-per-capita-2026",
        tipo="dispersao",
        titulo="Gasto público em %% do PIB vs PIB per capita, %s" % ANO,
        subtitulo="Despesa do governo geral (% do PIB) e PIB per capita em PPC; tamanho da bolha pelo PIB",
        nota=("Despesa total do governo geral, inclusive juros da dívida (GGX_NGDP do FMI). PIB per capita em "
              "paridade de poder de compra, em dólares internacionais correntes (PPPPC), no eixo em escala "
              "logarítmica. Tamanho da bolha proporcional ao PIB em PPC (PPPGDP). Valores de %s são estimativas "
              "do FMI no World Economic Outlook. Reta de tendência por mínimos quadrados do gasto sobre o "
              "logaritmo do PIB per capita, com o mesmo peso para cada país." % ANO),
        fonte="FMI (World Economic Outlook) e FtM",
        legenda=v1["legenda"], eixoX=v1["eixoX"], eixoY=v1["eixoY"], pontos=v1["pontos"], reta=v1["reta"],
        variantes=[v1, v2],
    )
    meses = sorted((int(d.split("/")[2]), int(d.split("/")[0])) for d in ed)
    referencia = "%04d-%02d" % meses[-1]

    graficos_hist = historico(gasto)

    hoje = datetime.date.today().isoformat()
    doc = dict(assunto="Gasto público", grupo="Análises Variadas",
               fonte="FMI, OCDE, Banco Mundial, Our World in Data e FtM", referencia=referencia, atualizado=hoje, formato="artigo",
               secoes=[dict(titulo="O gasto ao longo do tempo", texto="", fontes=[], figuras=[], graficos=graficos_hist),
                       dict(titulo="Gasto público e renda", texto="", fontes=[], figuras=[], graficos=[g_disp])])
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado", SAIDA)


if __name__ == "__main__":
    sys.exit(main())

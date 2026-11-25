#!/usr/bin/env python3
"""
Gasto público em % do PIB contra o PIB per capita, 2026 (um ponto por país,
tamanho pelo PIB em PPC, com a reta de mínimos quadrados). Refaz o gráfico do
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
  - PPPGDP: PIB em PPC, dólares internacionais correntes (tamanho da bolinha).
  - LP: população (corte de 1 milhão de habitantes e dica).
  - 2026 é estimativa do FMI na edição corrente do WEO, não dado fechado.

CONFERÊNCIAS QUE ABORTAM
  - GGX_NGDP = GGX / NGDP × 100 em cada país (≤ 0,05 p.p.). Exceção: os
    países de ANO_FISCAL, em que o FMI divide pelo PIB do ano fiscal e a conta
    com o PIB do ano civil difere em até 1,4 p.p. (WEO de set/2026); para eles
    a tolerância é 2 p.p.
  - PPPPC = PPPGDP / LP em cada país (≤ 0,5%).
  - Amostra de pelo menos 150 países e Brasil presente.

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
# países com o nome escrito ao lado da bolinha (os demais só na dica)
ROTULADOS = ["USA", "CHN", "IND", "FRA", "DEU", "ARG", "CHL", "MEX", "JPN", "NGA", "SGP", "NOR", "RUS", "ZAF"]
# conta de despesa no ano fiscal (a razão do FMI não bate com GGX / NGDP do ano civil)
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


def br(v, casas=1):
    s = "{:,.{c}f}".format(v, c=casas)
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


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
        subtitulo="Despesa total do governo geral (inclui juros) e PIB per capita em PPC (US$ internacionais "
                  "correntes, eixo logarítmico); %s é estimativa do FMI; bolinha proporcional ao PIB em PPC" % ANO,
        fonte="FMI (World Economic Outlook) e FtM",
        legenda=v1["legenda"], eixoX=v1["eixoX"], eixoY=v1["eixoY"], pontos=v1["pontos"], reta=v1["reta"],
        variantes=[v1, v2],
    )
    meses = sorted((int(d.split("/")[2]), int(d.split("/")[0])) for d in ed)
    referencia = "%04d-%02d" % meses[-1]

    hoje = datetime.date.today().isoformat()
    doc = dict(assunto="Gasto público e renda per capita", grupo="Análises Variadas",
               fonte="FMI (World Economic Outlook) e FtM", referencia=referencia, atualizado=hoje, formato="artigo",
               secoes=[dict(titulo="Gasto público e renda", texto="", fontes=[], figuras=[], graficos=[g_disp])])
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado", SAIDA)


if __name__ == "__main__":
    sys.exit(main())

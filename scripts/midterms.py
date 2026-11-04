#!/usr/bin/env python3
"""
Monta dados/midterms-2026.json: o assunto "Midterms de 2026 nos EUA", uma
explicação de como funcionam as eleições de meio de mandato, com a composição
da Câmara e do Senado de antes da votação de 03/11/2026.

Uso:
    python3 scripts/midterms.py               (usa o que já foi baixado)
    python3 scripts/midterms.py --atualizar   (baixa de novo Michigan, CNN e UCSB)

A seção "Os motivos da virada" vem de scripts/midterms_motivos.py, que baixa
os dados dela; o resto deste arquivo é digitado.

Só usa a biblioteca padrão. Rodado à mão: os números abaixo são digitados.

DE ONDE VÊM OS NÚMEROS

  Câmara      House Press Gallery (pressgallery.house.gov, party breakdown),
              conferido em 04/11/2026: 218 R, 214 D, 1 independente (Kevin
              Kiley, CA-3, saiu do partido em 2026 e continua na bancada
              republicana), 2 vagas (Tony Gonzales, R-TX, renunciou em
              14/04/2026; Sheila Cherfilus-McCormick, D-FL, em 21/04/2026).
  Senado      53 R, 45 D, 2 independentes que votam com os democratas (Angus
              King, ME, e Bernie Sanders, VT; nenhum dos dois em disputa).
              Em disputa: a classe 2 inteira (33 cadeiras) e duas eleições
              especiais da classe 3, Ohio (vaga de JD Vance) e Flórida (vaga
              de Marco Rubio), para o resto do mandato, até jan/2029.
  Governador  36 estados: os 34 de mandato de 4 anos eleitos no meio do
              mandato presidencial, mais New Hampshire e Vermont, que elegem
              governador a cada 2 anos. Partido = o do governador no cargo.
  Cadeiras    distribuição do censo de 2020 (vale de 2022 a 2030).
  Redesenho   Wikipedia, "2025-2026 United States redistricting", lida em
              04/11/2026: só os mapas em vigor na eleição de 2026, com o número
              de cadeiras que o lado que aprovou o mapa esperava virar.
              Missouri (barrado pela Suprema Corte estadual para 2026) e
              Virgínia (anulado pela Suprema Corte estadual) ficam de fora.
  Mapa        us-atlas 3 (states-albers-10m), feito dos limites cartográficos
              do Census Bureau e já projetado em Albers, com Alasca e Havaí
              deslocados para baixo, numa tela de 975 x 610.

O mapa é guardado uma vez, em "formas" no topo do arquivo; os cartões do tipo
"estados" só dizem a cor e o texto de cada estado.
"""
import datetime as dt
import json
import math
import urllib.request
from pathlib import Path

import midterms_motivos
import midterms_resultados
import midterms_economia
import midterms_historia

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "dados" / "midterms-2026.json"
CACHE = RAIZ / "dados" / ".cache-atlas" / "states-albers-10m.json"
URL_ATLAS = "https://cdn.jsdelivr.net/npm/us-atlas@3/states-albers-10m.json"

D, R, I = "#3B7DD8", "#D9453D", "#A979D9"
CINZA = "#8A9096"

FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
    "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
    "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
    "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}
NOME = {
    "AL": "Alabama", "AK": "Alasca", "AZ": "Arizona", "AR": "Arkansas", "CA": "Califórnia",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "Distrito de Colúmbia",
    "FL": "Flórida", "GA": "Geórgia", "HI": "Havaí", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Luisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "Nova Jersey", "NM": "Novo México", "NY": "Nova York",
    "NC": "Carolina do Norte", "ND": "Dakota do Norte", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pensilvânia", "RI": "Rhode Island", "SC": "Carolina do Sul",
    "SD": "Dakota do Sul", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virgínia", "WA": "Washington", "WV": "Virgínia Ocidental", "WI": "Wisconsin",
    "WY": "Wyoming",
}

# Cadeiras na Câmara por estado, censo de 2020
CADEIRAS = {
    "AL": 7, "AK": 1, "AZ": 9, "AR": 4, "CA": 52, "CO": 8, "CT": 5, "DE": 1, "FL": 28, "GA": 14,
    "HI": 2, "ID": 2, "IL": 17, "IN": 9, "IA": 4, "KS": 4, "KY": 6, "LA": 6, "ME": 2, "MD": 8,
    "MA": 9, "MI": 13, "MN": 8, "MS": 4, "MO": 8, "MT": 2, "NE": 3, "NV": 4, "NH": 2, "NJ": 12,
    "NM": 3, "NY": 26, "NC": 14, "ND": 1, "OH": 15, "OK": 5, "OR": 6, "PA": 17, "RI": 2, "SC": 7,
    "SD": 1, "TN": 9, "TX": 38, "UT": 4, "VT": 1, "VA": 11, "WA": 10, "WV": 2, "WI": 8, "WY": 1,
}

# Senado: cadeiras em disputa em 2026, pelo partido de quem as ocupa hoje
SENADO_D = ["CO", "DE", "GA", "IL", "MA", "MI", "MN", "NH", "NJ", "NM", "OR", "RI", "VA"]
SENADO_R = ["AL", "AK", "AR", "ID", "IA", "KS", "KY", "LA", "ME", "MS", "MT", "NE", "NC", "OK",
            "SC", "SD", "TN", "TX", "WV", "WY"]
SENADO_ESPECIAL = {"OH": "JD Vance, eleito vice-presidente", "FL": "Marco Rubio, secretário de Estado"}

# Governadores em disputa em 2026, pelo partido do governador no cargo
GOV_D = ["AZ", "CA", "CO", "CT", "HI", "IL", "KS", "ME", "MD", "MA", "MI", "MN", "NM", "NY", "OR",
         "PA", "RI", "WI"]
GOV_R = ["AL", "AK", "AR", "FL", "GA", "ID", "IA", "NE", "NV", "NH", "OH", "OK", "SC", "SD", "TN",
         "TX", "VT", "WY"]
# os outros 14 e o ano da próxima eleição deles
GOV_FORA = {"KY": 2027, "LA": 2027, "MS": 2027, "NJ": 2029, "VA": 2029, "DE": 2028, "IN": 2028,
            "MO": 2028, "MT": 2028, "NC": 2028, "ND": 2028, "UT": 2028, "WA": 2028, "WV": 2028}

# Estados pequenos demais para o rótulo caber dentro: vão para uma coluna à
# direita do mapa, com um traço até o estado
FORA_DO_MAPA = ["VT", "NH", "MA", "RI", "CT", "NJ", "DE", "MD"]
# onde o rótulo fica melhor que no centroide (coordenadas da tela 975 x 610)
AJUSTE = {"FL": (12, 8), "LA": (-10, 0), "MI": (8, 14), "KY": (6, 2), "CA": (-8, 10),
          "ID": (0, 18), "AK": (0, 6), "VA": (8, 2), "WV": (-3, 4),
          "NY": (6, 0), "TN": (0, 1), "MN": (-6, 6), "OK": (12, 0), "TX": (4, 8)}


# ---------- mapa ----------
def carregar_atlas():
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL_ATLAS, headers={"User-Agent": "ftm-analises/1.0"})
        CACHE.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    return json.loads(CACHE.read_text())


def decodificar_arcos(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcos = []
    for arco in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arco:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcos.append(pts)
    return arcos


def anel(indices, arcos):
    pts = []
    for i in indices:
        a = arcos[i] if i >= 0 else list(reversed(arcos[~i]))
        pts.extend(a if not pts else a[1:])
    return pts


def simplificar(pts, tol=0.45):
    # tira pontos a menos de `tol` do último guardado; o desenho sai a 2x no
    # máximo, então meio ponto da tela original não aparece
    out = [pts[0]]
    for p in pts[1:-1]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= tol:
            out.append(p)
    out.append(pts[-1])
    return out


def area_centroide(pts):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    a /= 2
    if abs(a) < 1e-9:
        return 0, pts[0]
    return abs(a), (cx / (6 * a), cy / (6 * a))


def formas():
    topo = carregar_atlas()
    arcos = decodificar_arcos(topo)
    saida = {}
    for geo in topo["objects"]["states"]["geometries"]:
        uf = FIPS[geo["id"]]
        polis = geo["arcs"] if geo["type"] == "MultiPolygon" else [geo["arcs"]]
        d, maior = [], (0, None)
        for poli in polis:
            for k, idx in enumerate(poli):
                pts = anel(idx, arcos)
                if k == 0:
                    ar, c = area_centroide(pts)
                    if ar > maior[0]:
                        maior = (ar, c)
                pts = simplificar(pts)
                if len(pts) < 4:
                    continue
                d.append("M" + "L".join("%.1f,%.1f" % p for p in pts) + "Z")
        cx, cy = maior[1]
        dx, dy = AJUSTE.get(uf, (0, 0))
        saida[uf] = {"d": "".join(d), "c": [round(cx + dx, 1), round(cy + dy, 1)]}
    return saida


# ---------- cartões ----------
def legenda(*itens):
    return [{"rot": r, "cor": c} for r, c in itens]


def mapa_camara():
    est = []
    mx = max(CADEIRAS.values())
    for uf, n in sorted(CADEIRAS.items()):
        # uma cor só, mais escura com mais cadeiras (raiz: a Califórnia não
        # apaga os outros)
        est.append({"uf": uf, "int": round(math.sqrt(n / mx), 3), "rot": str(n),
                    "dica": "%s: %d %s" % (NOME[uf], n, "cadeira" if n == 1 else "cadeiras")})
    est.append({"uf": "DC", "dica": "Distrito de Colúmbia: uma delegada, sem voto em plenário"})
    return {
        "id": "midterms-mapa-camara", "tipo": "estados",
        "titulo": "Câmara dos Representantes: cadeiras por estado",
        "subtitulo": "Número de deputados de cada estado, pela população do censo de 2020; todas em disputa em 2026",
        "fonte": "Census Bureau (censo de 2020)",
        "cor": "#3B7DD8", "estados": est, "foraDoMapa": FORA_DO_MAPA,
        "legenda": legenda(("1 cadeira", "escala:0.14"), ("52 cadeiras (Califórnia)", "escala:1")),
    }


def mapa_senado():
    est = []
    for uf in NOME:
        if uf == "DC":
            est.append({"uf": uf, "dica": "Distrito de Colúmbia: não tem senador"})
            continue
        if uf in SENADO_ESPECIAL:
            est.append({"uf": uf, "cor": R, "rot": uf + "*",
                        "dica": "%s: eleição especial para a cadeira republicana de %s, até 2029"
                                % (NOME[uf], SENADO_ESPECIAL[uf])})
        elif uf in SENADO_D:
            est.append({"uf": uf, "cor": D, "rot": uf, "dica": "%s: cadeira democrata em disputa" % NOME[uf]})
        elif uf in SENADO_R:
            est.append({"uf": uf, "cor": R, "rot": uf, "dica": "%s: cadeira republicana em disputa" % NOME[uf]})
        else:
            est.append({"uf": uf, "rot": uf, "dica": "%s: sem eleição para o Senado em 2026" % NOME[uf]})
    return {
        "id": "midterms-mapa-senado", "tipo": "estados",
        "titulo": "Senado: estados com cadeira em disputa em 2026",
        "subtitulo": "Pelo partido de quem ocupa a cadeira hoje; * eleição especial, para o resto de um mandato que termina em 2029",
        "fonte": "Senado dos EUA; mapa: Census Bureau",
        "estados": est, "foraDoMapa": FORA_DO_MAPA,
        "legenda": legenda(("Democrata (13)", D), ("Republicana (22)", R), ("Sem eleição (15)", "nenhuma")),
    }


def mapa_governadores():
    est = []
    for uf in NOME:
        if uf == "DC":
            est.append({"uf": uf, "dica": "Distrito de Colúmbia: tem prefeita, não governador"})
        elif uf in GOV_D:
            est.append({"uf": uf, "cor": D, "rot": uf, "dica": "%s: governador democrata hoje" % NOME[uf]})
        elif uf in GOV_R:
            est.append({"uf": uf, "cor": R, "rot": uf, "dica": "%s: governador republicano hoje" % NOME[uf]})
        else:
            est.append({"uf": uf, "rot": uf, "dica": "%s: sem eleição para governador em 2026 (próxima em %d)"
                                                     % (NOME[uf], GOV_FORA[uf])})
    return {
        "id": "midterms-mapa-governadores", "tipo": "estados",
        "titulo": "Governadores: estados com eleição em 2026",
        "subtitulo": "Pelo partido do governador no cargo",
        "fonte": "National Governors Association; mapa: Census Bureau",
        "estados": est, "foraDoMapa": FORA_DO_MAPA,
        "legenda": legenda(("Democrata (18)", D), ("Republicano (18)", R), ("Sem eleição (14)", "nenhuma")),
    }


def hemiciclo_camara():
    return {
        "id": "midterms-hemiciclo-camara", "tipo": "hemiciclo",
        "titulo": "Câmara dos Representantes: composição antes da eleição",
        "subtitulo": "435 cadeiras, todas em disputa; maioria de 218",
        "fonte": "House Press Gallery",
        "centro": ["435", "cadeiras"], "maioria": 218,
        "grupos": [
            {"nome": "Democratas", "n": 214, "cor": D},
            {"nome": "Vagas", "n": 2, "cor": "vazio"},
            {"nome": "Independente (na bancada republicana)", "n": 1, "cor": I},
            {"nome": "Republicanos", "n": 218, "cor": R},
        ],
    }


def hemiciclo_senado():
    return {
        "id": "midterms-hemiciclo-senado", "tipo": "hemiciclo",
        "titulo": "Senado: composição antes da eleição",
        "subtitulo": "100 cadeiras, 35 em disputa; maioria de 51, ou 50 mais o voto do vice-presidente",
        "fonte": "Senado dos EUA",
        "centro": ["35", "em disputa"], "maioria": 51,
        "grupos": [
            {"nome": "Democratas fora da eleição", "n": 32, "cor": D, "apagado": True},
            {"nome": "Independentes que votam com os democratas", "n": 2, "cor": I, "apagado": True},
            {"nome": "Democratas em disputa", "n": 13, "cor": D},
            {"nome": "Republicanos em disputa", "n": 22, "cor": R},
            {"nome": "Republicanos fora da eleição", "n": 31, "cor": R, "apagado": True},
        ],
    }


def ranking_governadores():
    return {
        "id": "midterms-governadores-por-ano", "tipo": "ranking", "unidade": "n",
        "titulo": "Eleições para governador por ano",
        "subtitulo": "Número de estados que elegem governador, de 2024 a 2028",
        "fonte": "National Governors Association",
        "itens": [
            ["2024 (presidencial)", 11, CINZA],
            ["2025", 2, CINZA],
            ["2026 (meio de mandato)", 36, "#4F81BD", True],
            ["2027", 3, CINZA],
            ["2028 (presidencial)", 11, CINZA],
        ],
    }


def ranking_redesenho():
    itens = [
        ["Texas (R)", 5, R], ["Califórnia (D)", 5, D], ["Flórida (R)", 4, R], ["Ohio (R)", 2, R],
        ["Carolina do Norte (R)", 1, R], ["Tennessee (R)", 1, R], ["Luisiana (R)", 1, R],
        ["Alabama (R)", 1, R], ["Utah (D)", 1, D],
    ]
    return {
        "id": "midterms-redesenho", "tipo": "ranking", "unidade": "n",
        "titulo": "Mapas da Câmara redesenhados para 2026: cadeiras visadas",
        "subtitulo": "Cadeiras que o lado que aprovou o novo mapa esperava ganhar; entre parênteses, o partido beneficiado",
        "fonte": "Wikipedia (2025-2026 United States redistricting)",
        "itens": itens,
    }


# O exemplo de gerrymandering: 50 eleitores, 60% azul (A) e 40% vermelho
# (V), cinco distritos de 10. Os eleitores não mudam de lugar; só as linhas.
ELEITORES = ["AAAAAAVVVV"] * 5
PAINEIS = [
    ("Linhas que acompanham os grupos", ["0011223344"] * 5),
    ("Azul divide o vermelho", ["0000000000", "1111111111", "2222222222", "3333333333", "4444444444"]),
    ("Vermelho concentra o azul", ["3300000000", "3311111100", "3333331111", "4422222222", "4444444422"]),
]


def conferir_distritos():
    print("distritos do exemplo:")
    for rot, mapa in PAINEIS:
        cont = {}
        for lin_e, lin_d in zip(ELEITORES, mapa):
            for e, d in zip(lin_e, lin_d):
                cont.setdefault(d, {"A": 0, "V": 0})[e] += 1
        assert all(c["A"] + c["V"] == 10 for c in cont.values()), (rot, cont)
        # cada distrito tem de ser uma peça só
        for d in cont:
            cel = {(i, j) for i, l in enumerate(mapa) for j, x in enumerate(l) if x == d}
            vistos, fila = set(), [next(iter(cel))]
            while fila:
                i, j = fila.pop()
                if (i, j) in vistos:
                    continue
                vistos.add((i, j))
                fila += [p for p in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)) if p in cel]
            assert vistos == cel, (rot, d)
        a = sum(c["A"] > c["V"] for c in cont.values())
        print("  %-36s azul %d x %d vermelho" % (rot, a, 5 - a))


def distritos():
    conferir_distritos()
    return {
        "id": "midterms-distritos", "tipo": "distritos",
        "titulo": "Os mesmos 50 eleitores em três mapas de cinco distritos",
        "subtitulo": "30 eleitores azuis (60%) e 20 vermelhos (40%); cada distrito tem 10 eleitores e elege um deputado",
        "fonte": "exemplo ilustrativo",
        "partidos": {"A": {"nome": "Azul", "cor": D}, "V": {"nome": "Vermelho", "cor": R}},
        "eleitores": ELEITORES,
        "paineis": [{"rot": r, "distritos": m} for r, m in PAINEIS],
    }


# ---------- texto ----------
APRESENTACAO = (
    "Em 3 de novembro de 2026, no meio do mandato de Donald Trump, os americanos elegeram a Câmara "
    "inteira, 35 das 100 cadeiras do Senado e os governadores de 36 dos 50 estados. É a eleição de meio "
    "de mandato, a **midterm**: o presidente não está na cédula, mas é ela que decide se ele governa os "
    "dois anos seguintes com o Congresso a favor ou contra. A explicação usa a composição de antes da "
    "votação; depois dela vêm os resultados e os motivos da virada. Em azul, os democratas; em vermelho, os "
    "republicanos."
)

SECOES = [
    {
        "titulo": "Como funciona",
        "texto": (
            "**A data é fixa**: a primeira terça-feira depois da primeira segunda-feira de novembro, nos anos "
            "pares. A cada quatro anos ela coincide com a presidencial; dois anos depois de cada uma vem a de "
            "meio de mandato. É dia útil e o voto "
            "não é obrigatório.\n\n"
            "**Não existe uma Justiça Eleitoral nacional**, como o TSE. Quem organiza a eleição é cada estado, "
            "e quase sempre cada condado dentro dele: são eles que definem se há voto antecipado, voto pelo "
            "correio, que documento o eleitor apresenta e em que ordem os votos são contados. Por isso o "
            "resultado não sai de uma vez. Os estados que contam o voto pelo correio depois do dia da eleição, "
            "como a Califórnia, levam dias, e a certificação oficial sai semanas depois.\n\n"
            "**Os candidatos saem das primárias**, eleições internas de cada partido feitas entre março e "
            "setembro, também com regras que mudam de estado para estado. Em alguns, só vota quem é filiado; "
            "em outros, qualquer eleitor.\n\n"
            "**Na grande maioria das disputas vence quem tem mais votos**, mesmo sem maioria absoluta, e não há "
            "segundo turno. As exceções são poucas: a Geórgia exige mais da metade dos votos e faz segundo turno, "
            "e o Maine e o Alasca usam voto ranqueado, em que o eleitor ordena os candidatos.\n\n"
            "**O novo Congresso toma posse em 3 de janeiro.** Até lá, o Congresso antigo continua votando, "
            "inclusive os parlamentares que perderam: é a chamada sessão do pato manco."
        ),
        "graficos": [{
            "id": "midterms-calendario", "tipo": "tabela",
            "titulo": "Calendário da eleição de 2026",
            "subtitulo": "Do início das primárias à posse",
            "fonte": "legislação federal e calendários estaduais",
            "colunas": [{"rot": "Etapa"}, {"rot": "Quando"}, {"rot": "Quem decide"}],
            "linhas": [
                [{"t": "Primárias", "forte": True}, "março a setembro de 2026", "cada estado e cada partido"],
                [{"t": "Votação", "forte": True}, "3 de novembro de 2026", "data fixada em lei federal"],
                [{"t": "Apuração e certificação", "forte": True}, "novembro e dezembro de 2026",
                 "cada estado, com prazo próprio"],
                [{"t": "Posse do novo Congresso", "forte": True}, "3 de janeiro de 2027", "Constituição (20ª emenda)"],
                [{"t": "Posse dos governadores", "forte": True}, "janeiro de 2027, na maioria dos estados",
                 "constituição de cada estado"],
            ],
        }],
    },
    {
        "titulo": "A Câmara",
        "texto": (
            "**As 435 cadeiras vão a voto a cada dois anos**, porque o mandato de deputado é de dois anos. "
            "Cada estado é dividido em distritos, e cada distrito elege um único deputado: não há lista de "
            "partido nem voto proporcional, como no Brasil. Quem tiver mais votos no distrito leva a cadeira, "
            "e o partido que fizer 218 cadeiras controla a Câmara: escolhe o presidente da Casa, os presidentes "
            "das comissões e o que vai a voto.\n\n"
            "Antes da eleição, os republicanos tinham a maioria mínima: 218 cadeiras, contra 214 dos democratas, "
            "um independente que continua na bancada republicana (Kevin Kiley, da Califórnia) e duas cadeiras "
            "vagas por renúncia (Tony Gonzales, republicano do Texas, e Sheila Cherfilus-McCormick, democrata da "
            "Flórida)."
        ),
        "graficos": [hemiciclo_camara()],
    },
    {
        "titulo": "",
        "texto": (
            "**O número de deputados de cada estado segue a população**, recontada no censo a cada dez anos. "
            "Com o censo de 2020, cada distrito tem cerca de 760 mil habitantes. Todo estado tem pelo menos um "
            "deputado, e seis têm só um: Alasca, Delaware, Dakota do Norte, Dakota do Sul, Vermont e Wyoming. "
            "Nesses, o distrito é o estado inteiro. Washington, a capital, não é estado e tem só uma delegada "
            "sem voto."
        ),
        "graficos": [mapa_camara()],
    },
    {
        "titulo": "O Senado",
        "texto": (
            "**Cada estado tem dois senadores, qualquer que seja a população**: Wyoming, com menos de 600 mil habitantes, "
            "pesa o mesmo que a Califórnia, com 39 milhões. O mandato é de seis anos, e as 100 cadeiras são "
            "divididas em três turmas que se renovam em rodízio, uma a cada dois anos. Por isso só um terço do "
            "Senado vai a voto em cada eleição, e os dois senadores de um estado nunca são eleitos juntos, a não "
            "ser quando uma vaga precisa ser preenchida.\n\n"
            "**Em 2026 são 35 cadeiras**: as 33 da turma que vence agora e duas eleições especiais, em Ohio e na "
            "Flórida, para os lugares de JD Vance, eleito vice-presidente, e de Marco Rubio, que virou secretário "
            "de Estado. Os dois foram substituídos por senadores nomeados pelos governadores, que agora "
            "precisam passar pelo voto.\n\n"
            "**O mapa da disputa favorece os democratas no número e os republicanos na geografia.** Os "
            "republicanos defendem 22 das 35 cadeiras, e os democratas, 13; mas a maior parte das cadeiras "
            "republicanas está em estados onde o partido vence com folga. Para tirar a maioria, que hoje é de "
            "53 a 47, os democratas precisam ganhar quatro cadeiras sem perder nenhuma: com 50 a 50, desempata "
            "o vice-presidente, que é republicano.\n\n"
            "O Senado tem poderes que a Câmara não tem: confirma ministros, juízes da Suprema Corte e "
            "embaixadores, ratifica tratados e julga o impeachment que a Câmara aprova."
        ),
        "graficos": [hemiciclo_senado(), mapa_senado()],
    },
    {
        "titulo": "Os governadores: por que 36",
        "texto": (
            "**Cada estado escolhe quando elege o próprio governador**, e a maioria escolheu o meio do mandato "
            "presidencial. São 34 estados com mandato de quatro anos que votam nesse ano, mais New Hampshire e "
            "Vermont, onde o mandato de governador ainda é de dois anos e há eleição em todo ano par: 36.\n\n"
            "Os outros 14 se espalham pelo calendário. Nove elegem governador junto com o presidente (Carolina "
            "do Norte, Delaware, Dakota do Norte, Indiana, Missouri, Montana, Utah, Virgínia Ocidental e "
            "Washington), e cinco em anos ímpares, sem nenhuma eleição federal junto: Kentucky, Luisiana e "
            "Mississippi no ano anterior à presidencial, Nova Jersey e Virgínia no ano seguinte.\n\n"
            "A concentração no meio do mandato é escolha do século 20. Ao longo dele, quase todos os estados "
            "trocaram o mandato de dois anos pelo de quatro (Arkansas em 1986 e Rhode Island em 1994 foram os "
            "últimos) e, ao fazer a troca, a maioria pôs a eleição no ano sem presidente na cédula, para que a "
            "disputa estadual não fosse arrastada pela nacional."
        ),
        "graficos": [ranking_governadores()],
    },
    {
        "titulo": "",
        "texto": (
            "**Em 2026, as 36 disputas se dividem ao meio**: 18 estados têm hoje governador democrata, e 18, "
            "republicano. Na mesma cédula vão também as assembleias estaduais, cargos como procurador-geral e "
            "secretário de Estado, e consultas diretas ao eleitor sobre temas como aborto, impostos e o próprio "
            "mapa eleitoral."
        ),
        "graficos": [mapa_governadores()],
    },
    {
        "titulo": "Gerrymandering",
        "texto": (
            "**Quem desenha os distritos da Câmara são os próprios estados**, quase sempre a assembleia "
            "estadual, depois de cada censo. Em alguns, como Arizona, Colorado e Michigan, a tarefa é de uma "
            "comissão independente; quando ninguém se entende, um tribunal desenha. Gerrymandering é desenhar "
            "essas linhas para que um partido ganhe mais cadeiras do que os votos dele dariam. O nome vem de "
            "Elbridge Gerry, governador de Massachusetts que em 1812 aprovou um distrito tão retorcido que um "
            "jornal o comparou a uma salamandra (salamander): Gerry + mander.\n\n"
            "**O jeito mais fácil de entender é com um exemplo.** Abaixo, um estado de 50 eleitores, 30 do "
            "partido azul (60%) e 20 do vermelho (40%), que precisa ser dividido em cinco distritos de 10 "
            "eleitores. Os eleitores são os mesmos nos três quadros, no mesmo lugar; só mudam as linhas, e a "
            "cor de fundo de cada distrito é a de quem ganha nele."
        ),
        "graficos": [distritos()],
    },
    {
        "titulo": "",
        "texto": (
            "- **No primeiro mapa**, as linhas acompanham onde cada grupo mora: três distritos só de azuis e dois "
            "só de vermelhos. Resultado: 3 a 2, a proporção dos votos.\n"
            "- **No segundo**, o azul desenha faixas que cortam o estado de ponta a ponta. Cada distrito fica "
            "com 6 azuis e 4 vermelhos, e o azul vence os cinco. Com 40% dos votos, o vermelho não elege "
            "ninguém. É a técnica de **dividir** (cracking): espalhar o adversário para que ele seja minoria em "
            "todo lugar.\n"
            "- **No terceiro**, o vermelho faz o contrário. Junta muitos azuis em dois distritos, que o azul "
            "ganha com sobra (10 a 0 e 8 a 2), e monta outros três em que o vermelho vence por 6 a 4. "
            "Resultado: 3 a 2 para o vermelho, que tem menos votos. É a técnica de **concentrar** (packing): "
            "o voto do adversário sobra onde ele já ganharia de qualquer jeito.\n\n"
            "Na prática as duas técnicas andam juntas, com dados de votação de cada quarteirão e programas que "
            "testam milhares de mapas. Usar o desenho para diluir o voto de minorias raciais é proibido pela Lei "
            "dos Direitos de Voto; usá-lo a favor de um partido, não: em 2019, no caso Rucho contra Common Cause, a Suprema Corte decidiu que a Justiça "
            "federal não julga gerrymandering partidário. Sobram as constituições e os tribunais estaduais."
        ),
        "graficos": [],
    },
    {
        "titulo": "",
        "texto": (
            "**Em 2025 e 2026 houve uma guerra de mapas fora de hora.** O normal é redesenhar uma vez por "
            "década, depois do censo. Em agosto de 2025, a pedido de Trump, o Texas refez o seu mapa para "
            "virar cinco cadeiras para os republicanos. A Califórnia respondeu em novembro com a Proposição 50, "
            "aprovada no voto, que suspendeu a comissão independente até 2030 e redesenhou o estado para virar "
            "cinco cadeiras para os democratas. Outros estados seguiram. Missouri e Virgínia também aprovaram "
            "mapas novos, mas a Justiça estadual barrou os dois para 2026."
        ),
        "graficos": [ranking_redesenho()],
    },
]


# Pesquisa Markets Pulse da Bloomberg, feita de 2 a 17/10/2026 com participantes
# do mercado, digitada do quadro que a Bloomberg publicou. Em %, por cenário:
# controle democrata do Congresso, dividido e republicano.
BLOOMBERG = "https://www.bloomberg.com/graphics/2026-us-election-results/markets/?leadSource=uverify%20wall"
PESQUISA = {
    "juros_bolsa": {"ambos sobem": (10, 22, 39), "juros sobem, S&P cai": (37, 42, 35),
                    "juros caem, S&P sobe": (32, 26, 22), "ambos caem": (21, 10, 4)},
    "sp500": {"acelera": (8, 7, 20), "segue igual": (29, 37, 45), "desacelera": (41, 42, 22),
              "vira perda": (22, 14, 14)},
    "bitcoin": {"acima de US$ 100 mil": (8, 14, 29), "sobe até US$ 100 mil": (20, 40, 43),
                "cai até US$ 60 mil": (55, 42, 22), "abaixo de US$ 60 mil": (16, 5, 5)},
    "ia": {"ajuda a alta": 22, "sem efeito": 16, "prejudica": 62},
    "vender": {"controle democrata": 22, "dividido": 7, "controle republicano": 17, "não venderia": 55},
}


def secao_mercado():
    p = PESQUISA
    pior_sp = p["sp500"]["desacelera"][0] + p["sp500"]["vira perda"][0]
    queda_btc = p["bitcoin"]["cai até US$ 60 mil"][0] + p["bitcoin"]["abaixo de US$ 60 mil"][0]
    return {
        "titulo": "E o mercado?",
        "fontes": [{"id": "bloomberg", "rot": "Bloomberg, a eleição e os mercados", "url": BLOOMBERG}],
        "texto": (
            "A Bloomberg abriu de graça a cobertura da eleição, e a [página sobre os mercados](fonte:bloomberg) "
            "traz a pesquisa Markets Pulse, feita de 2 a 17 de outubro com participantes do mercado. Ela perguntou "
            "o que cada um esperava para os 12 meses seguintes em três cenários: Congresso democrata, dividido ou "
            "republicano. O que saiu das urnas foi o primeiro.\n\n"
            "**Com o Congresso democrata, a maioria esperava bolsa mais fraca.** %d%% previam que a alta do S&P "
            "500, de cerca de 1,3%% ao mês neste ano, desaceleraria ou viraria perda; com o Congresso republicano, "
            "eram %d%%. A combinação mais citada foi juros dos Treasuries em alta com a bolsa em queda (%d%%); só "
            "%d%% esperavam juros e bolsa subindo juntos, contra %d%% no cenário republicano.\n\n"
            "**No bitcoin, o pessimismo era maior.** Com o bitcoin perto de US$ 83,6 mil no fim de setembro, e "
            "depois que o projeto de regulação das criptomoedas caiu no Senado, %d%% esperavam queda até o fim "
            "do ano se o Congresso fosse democrata, e %d%% esperavam o bitcoin acima de US$ 100 mil.\n\n"
            "**A regulação de inteligência artificial aparece como risco.** Se a troca de controle do Congresso "
            "trouxer regras mais duras para a IA, %d%% acham que isso prejudica as ações americanas, e %d%% que "
            "ajuda a alta. Ainda assim, %d%% disseram que nenhum resultado os faria pensar em vender ações "
            "americanas; %d%% considerariam seriamente vender parte das suas com o Congresso democrata, e %d%% "
            "com o republicano."
        ) % (pior_sp, p["sp500"]["desacelera"][2] + p["sp500"]["vira perda"][2], p["juros_bolsa"]["juros sobem, S&P cai"][0],
             p["juros_bolsa"]["ambos sobem"][0], p["juros_bolsa"]["ambos sobem"][2],
             queda_btc, p["bitcoin"]["acima de US$ 100 mil"][0],
             p["ia"]["prejudica"], p["ia"]["ajuda a alta"], p["vender"]["não venderia"],
             p["vender"]["controle democrata"], p["vender"]["controle republicano"]),
        "graficos": [],
    }


SECAO_MERCADO = secao_mercado()


def main():
    for s in SECOES:
        for g in s["graficos"]:
            g.setdefault("fonte", "")
    assert len(SENADO_D) == 13 and len(SENADO_R) + len(SENADO_ESPECIAL) == 22
    assert len(GOV_D) == 18 and len(GOV_R) == 18 and len(GOV_FORA) == 14
    assert not (set(GOV_D) | set(GOV_R)) & set(GOV_FORA)
    assert sum(CADEIRAS.values()) == 435
    # dados até o momento da apuração da CNN (horário de Brasília)
    ts = max(r["extractedAt"] for t in ("HG", "SG", "GG") for r in midterms_resultados.disputas(t))
    apuracao = (dt.datetime.fromisoformat(ts[:19]) - dt.timedelta(hours=3)).date().isoformat()
    dados = {
        "atualizado": dt.date.today().isoformat(),
        "referencia": apuracao,
        "fonte": "House Press Gallery, Senado dos EUA, Census Bureau, Universidade de Michigan, Edison Research/CNN, UCSB, BLS, BEA, Fed, Freddie Mac e Bloomberg",
        "assunto": "Midterms de 2026 nos EUA",
        "grupo": "Análises Variadas",
        "apresentacao": APRESENTACAO,
        "formato": "artigo",
        "formas": formas(),
        "secoes": [{"fontes": [], "figuras": [], **s} for s in SECOES + midterms_resultados.secoes(NOME)
                   + midterms_historia.secoes(set(SENADO_R) | set(SENADO_ESPECIAL), NOME) + midterms_motivos.secoes() + midterms_economia.secoes() + [SECAO_MERCADO]],
    }
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    print("gravado %s (%.0f KB)" % (SAIDA.relative_to(RAIZ), SAIDA.stat().st_size / 1024))


if __name__ == "__main__":
    main()

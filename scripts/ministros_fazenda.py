#!/usr/bin/env python3
"""Ministros da Fazenda desde Antonio Palocci: dados/ministros-fazenda.json.

Pedido dele em 27/11/2026: séries no estilo do FtM com a ideia do Poder &
Mercado (faixa e retrato de cada ministro) e, para cada ministro, o início, o
final e a variação de cada indicador.

Indicadores (todos mensais, BCB/SGS salvo indicação):
  - resultado primário do setor público consolidado, % do PIB em 12 meses
    (5793, NFSP sem desvalorização cambial; o SGS publica a necessidade de
    financiamento, então o sinal é invertido: superávit positivo);
  - resultado nominal, idem (5727), conferido pela identidade
    nominal = primário + juros nominais (5760);
  - dívida bruta do governo geral, % do PIB, metodologia usada até 2007
    (conceito FMI): saldo em R$ milhões (4502) dividido pelo PIB acumulado
    em 12 meses (4382), conferido contra a série em % do PIB (4537);
  - IPCA acumulado em 12 meses (13522), refeito a partir da variação mensal
    (433) como conferência, e comparado à meta de inflação (13521) com o
    intervalo de tolerância do CMN;
  - meta da Selic (432, diária): o valor no último dia do mês;
  - câmbio: PTAX de venda (1, diária) no último dia útil do mês, conferida
    contra a série mensal de fim de período (3696);
  - câmbio pela PPC: a série do FtM Dados (dados/moedas.json), base única
    R$ 1,00 = US$ 1,00 em junho de 1994 corrigida pelo IPCA sobre o CPI dos
    EUA, contra o dólar de mercado (PTAX média do mês); conferidas contra a
    PTAX diária e contra o IPCA (433) ÷ CPI-U (FRED CPIAUCNS, conferido contra
    o FMI) em janelas de 12 meses;
  - juro real ex post da taxa básica: a série do FtM Dados (dados/juros.json),
    Selic efetiva em 12 meses (4390) sobre o IPCA (433), refeita aqui;
  - fatores condicionantes da DBGG no conceito FMI: o gráfico do FtM Dados
    (dados/fiscal.json), cuja variação em 12 meses tem de bater com a nossa
    dívida; cores trocadas pelas da paleta oficial;
  - primário e nominal por mês de mandato: fluxo mensal (4649 e 4583) a preços
    do último IPCA, somado em 12 meses (conferido contra 5793 e 5727 com o PIB
    4382), menos o valor do mês-base de cada ministro;
  - rating soberano em moeda estrangeira, longo prazo (Moody's, S&P e Fitch),
    lido do JSON do Poder & Mercado (aba "Base Rating 2" da planilha), no
    GitHub.

Atribuição dos meses: cada mês é de quem era ministro no último dia dele.
"Início" na tabela é o mês anterior ao primeiro mês do ministro (o último do
antecessor; para Palocci, dez/2002) e "Final" é o último mês dele (para quem
está no cargo, o último dado publicado). Assim as variações se encadeiam.

Rodar à mão: python3 scripts/ministros_fazenda.py
"""
import csv
import datetime
import io
import json
import os
import sys
import time
import urllib.request

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SAIDA = os.path.join(RAIZ, "dados", "ministros-fazenda.json")
SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.%d/dados?formato=json&dataInicial=%s&dataFinal=%s"
PM = "https://raw.githubusercontent.com/guivaraschinalves/poder-e-mercado/main/dados/indicadores.json"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS"
YAHOO_IBOV = "https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP?period1={}&period2={}&interval=1d"
TOL_IBOV = 1.0                # Ibovespa do SGS (7) × fechamento do Yahoo (pontos)
FMI_CPI = ("https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/CPI/+/USA.CPI._T.IX.M"
           "?dimensionAtObservation=TIME_PERIOD&attributes=dsd&measures=all")
UA = {"User-Agent": "Mozilla/5.0 (ftm-analises)", "Accept": "application/json"}
INICIO = "2002-12"            # mês-base de Palocci
TOL_IDENT = 0.02              # nominal = primário + juros (p.p. do PIB, arredondamento do SGS)
TOL_IPCA = 0.02               # 12 meses refeito × 13522 (p.p.)
TOL_PTAX = 0.00005            # PTAX diária no último dia útil × 3696 (R$)
TOL_CPI = 0.0002              # FRED ÷ FMI constante (desvio relativo)

BRANCO, AZUL, VERMELHO, VERDE, AZUL_ESC = "#FFFFFF", "#4F81BD", "#C0504D", "#9BBB59", "#1F497D"
LARANJA, CINZA = "#F79646", "#8a8a86"
AMARELO, AZUL_CLARO, VINHO = "#FFFF00", "#8EB4E3", "#632523"
# uma cor por ministro nos gráficos por mês de mandato: as 7 cromáticas da
# paleta oficial mais branco e cinza (as escuras nos mandatos curtos)
CORES_MINISTRO = {"palocci": AZUL, "mantega": VERMELHO, "levy": VERDE, "barbosa": VINHO, "meirelles": AZUL_CLARO,
                  "guardia": AZUL_ESC, "guedes": AMARELO, "haddad": BRANCO, "durigan": CINZA}
# condicionantes: as cores do FtM Dados trocadas pelas da paleta oficial
# (laranja com verde e roxo com azul se confundem no daltonismo)
CORES_CONDICIONANTES = {"Juros nominais": VERMELHO, "Emissões líquidas": AZUL, "Variação cambial": VERDE,
                        "Outros": CINZA, "Carteira do BC menos compromissadas": AMARELO,
                        "Efeito do crescimento do PIB": AZUL_CLARO, "Variação da dívida/PIB": BRANCO}

# o FtM Dados (repositório privado): PPC, juro real ex post e fatores
# condicionantes saem das mesmas séries publicadas lá, lidas do clone local
FTM_DADOS = os.environ.get("FTM_DADOS", os.path.expanduser("~/projetos/ftm-dados"))
TOL_PTAX_MEDIA = 0.0006       # dólar de mercado do FtM Dados × média da PTAX diária no mês (R$)
TOL_PPC = 0.006               # PPC ÷ (PPC de 12 meses antes × IPCA ÷ CPI de 12 meses) − 1
TOL_EXPOST = 0.02             # juro real ex post do FtM Dados × refeito pela 4390 e 433 (p.p.)
TOL_COND = 0.03               # variação da dívida/PIB em 12 meses nos condicionantes × a nossa (p.p.)
TOL_FLUXO = 0.02              # soma de 12 meses do fluxo ÷ PIB × 5793/5727 (p.p.)

# (id, nome, nome curto, posse, saída). Datas: lista oficial de ministros da
# Fazenda (Economia de 2019 a 2022). A interinidade de Bernard Appy (3 a
# 14/01/2007) não troca o dono do mês e fica fora.
MINISTROS = [
    ("palocci", "Antonio Palocci", "Palocci", "2003-01-01", "2006-03-27"),
    ("mantega", "Guido Mantega", "Mantega", "2006-03-27", "2015-01-01"),
    ("levy", "Joaquim Levy", "Levy", "2015-01-01", "2015-12-18"),
    ("barbosa", "Nelson Barbosa", "Barbosa", "2015-12-18", "2016-05-12"),
    ("meirelles", "Henrique Meirelles", "Meirelles", "2016-05-12", "2018-04-10"),
    ("guardia", "Eduardo Guardia", "Guardia", "2018-04-10", "2019-01-01"),
    ("guedes", "Paulo Guedes", "Guedes", "2019-01-01", "2023-01-01"),
    ("haddad", "Fernando Haddad", "Haddad", "2023-01-01", "2026-03-19"),
    ("durigan", "Dario Durigan", "Durigan", "2026-03-19", None),
]
# Presidente em exercício por mês (maio/2016 conta para Temer, que assumiu em
# 12/05/2016 no afastamento de Dilma, junto com a posse de Meirelles).
PRESIDENTES = [
    ("Lula I", "2003-01", "2006-12"),
    ("Lula II", "2007-01", "2010-12"),
    ("Dilma I", "2011-01", "2014-12"),
    ("Dilma II", "2015-01", "2016-04"),
    ("Temer", "2016-05", "2018-12"),
    ("Bolsonaro", "2019-01", "2022-12"),
    ("Lula III", "2023-01", None),
]
DESTAQUE_VERMELHO = {
    "primario": "mantega",
    "nominal": "haddad",
    "divida": ("levy", "meirelles"),
    "ipca": "levy",
    "selic": "guedes",
    "juro-real": "palocci",
    "cambio": "levy",
    "cambio-ppc": "levy",
    "rating": ("levy", "barbosa"),
}
PERSPECTIVAS = ("Positiva", "Estável", "Negativa")
TOL_DIVIDA = 0.02             # 4502 / 4382 * 100 × 4537 (p.p. do PIB)
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
NOTAS_SP = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
            "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C"]
NOTAS_MOODYS = ["Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3", "Baa1", "Baa2", "Baa3", "Ba1", "Ba2", "Ba3",
                "B1", "B2", "B3", "Caa1", "Caa2", "Caa3", "Ca", "C"]


# ---------- utilidades ----------
def baixar(url, headers=UA, tentativas=5):
    for k in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=headers) if headers else urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if k == tentativas - 1:
                raise RuntimeError("falhou %s: %s" % (url, e))
            time.sleep(3 * (k + 1))


def ordem(m):
    a, b = m.split("-")[:2]
    return int(a) * 12 + int(b) - 1


def mes_de(i):
    return "%04d-%02d" % (i // 12, i % 12 + 1)


def mes_curto(m):
    return "%s/%s" % (MESES[int(m[5:7]) - 1], m[2:4])


def sgs(codigo, ini="01/01/1999", diario=False):
    """{AAAA-MM: v} (mensal) ou {AAAA-MM-DD: v} (diário). Diário em janelas de
    9 anos (o SGS recusa mais de 10); resposta de erro com HTTP 200 vira falha."""
    d0 = datetime.datetime.strptime(ini, "%d/%m/%Y").date()
    hoje = datetime.date.today()
    out = {}
    while d0 <= hoje:
        d1 = min(hoje, d0.replace(year=d0.year + 9) - datetime.timedelta(days=1))
        url = SGS % (codigo, d0.strftime("%d/%m/%Y"), d1.strftime("%d/%m/%Y"))
        for k in range(5):
            try:
                lst = json.loads(baixar(url).decode("utf-8"))
            except ValueError:            # o SGS às vezes responde 200 com corpo vazio
                lst = None
            if isinstance(lst, list):
                break
            if k == 4:
                raise RuntimeError("SGS %d respondeu %r" % (codigo, lst))
            time.sleep(3)
        for x in lst:
            if x["valor"] in (None, ""):
                continue
            dd, mm, aa = x["data"].split("/")
            out[("%s-%s-%s" % (aa, mm, dd)) if diario else ("%s-%s" % (aa, mm))] = float(x["valor"])
        d0 = d1 + datetime.timedelta(days=1)
    if not out:
        raise RuntimeError("SGS %d vazio" % codigo)
    print("SGS %-5d %6d pontos, %s a %s" % (codigo, len(out), min(out), max(out)))
    return out


def fim_do_mes(diaria, ate_mes):
    """Último valor publicado de cada mês, só meses fechados (até ate_mes)."""
    out = {}
    for d in sorted(diaria):
        if d[:7] <= ate_mes:
            out[d[:7]] = diaria[d]
    return out


def br(v, casas):
    s = ("{:,.%df}" % casas).format(abs(v)).replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if v < 0 and round(abs(v), casas) > 0 else "") + s


def sinal(v, casas):
    if round(v, casas) == 0:
        return br(0, casas)
    return ("+" if v > 0 else "−") + br(abs(v), casas)


# ---------- ministros e meses ----------
def meses_dos_ministros(ultimo):
    """Primeiro e último mês de cada ministro: o mês é de quem estava no cargo no
    último dia dele, então começa no mês da posse e acaba no mês anterior ao
    da posse do sucessor."""
    out = []
    for k, (mid, nome, curto, posse, saida) in enumerate(MINISTROS):
        de = posse[:7]
        prox = MINISTROS[k + 1][3][:7] if k + 1 < len(MINISTROS) else None
        ate = mes_de(ordem(prox) - 1) if prox else ultimo
        if saida and prox and saida != MINISTROS[k + 1][3]:
            raise RuntimeError("saída de %s não é a posse do sucessor" % nome)
        out.append(dict(id=mid, nome=nome, curto=curto, de=de, ate=ate, base=mes_de(ordem(de) - 1),
                        posse=posse, saida=saida, foto="assets/ministros/%s.jpg" % mid))
    # os meses fecham sem buraco nem sobreposição
    for a, b in zip(out, out[1:]):
        if ordem(b["de"]) != ordem(a["ate"]) + 1:
            raise RuntimeError("meses de %s e %s não se encaixam" % (a["nome"], b["nome"]))
    if out[0]["base"] != INICIO:
        raise RuntimeError("mês-base de Palocci deveria ser %s" % INICIO)
    return out


def presidentes_faixas(ultimo):
    return [dict(nome=nome, de=de, ate=ate or ultimo) for nome, de, ate in PRESIDENTES]


def presidente_do_ministro(mi, pres_fx):
    nomes = [p["nome"] for p in pres_fx
             if ordem(p["de"]) <= ordem(mi["ate"]) and ordem(p["ate"]) >= ordem(mi["de"])]
    if nomes == ["Lula I", "Lula II", "Dilma I"]:
        return "Lula I, II e Dilma I"
    return ", ".join(nomes)


def faixas(mins):
    return [dict(id=m["id"], base=m["base"], de=m["de"], ate=m["ate"], nome=m["nome"],
                 curto=m["curto"], foto=m["foto"]) for m in mins]


# ---------- fontes ----------
def fiscal():
    prim, nom, jur = sgs(5793, "01/01/2002"), sgs(5727, "01/01/2002"), sgs(5760, "01/01/2002")
    for m in prim:
        if m in nom and m in jur and abs(nom[m] - prim[m] - jur[m]) > TOL_IDENT + 1e-9:
            raise RuntimeError("NFSP de %s: nominal %.2f ≠ primário %.2f + juros %.2f" % (m, nom[m], prim[m], jur[m]))
    print("conferência: nominal = primário + juros em %d meses" % len([m for m in prim if m in nom and m in jur]))
    # o SGS publica a necessidade de financiamento: superávit fica positivo
    return {m: -v for m, v in prim.items()}, {m: -v for m, v in nom.items()}


def divida_ate2007():
    saldo, pib12, ref = sgs(4502, "01/01/2002"), sgs(4382, "01/01/2002"), sgs(4537, "01/01/2002")
    div = {m: saldo[m] / pib12[m] * 100 for m in saldo if m in pib12}
    difs = [abs(div[m] - ref[m]) for m in div if m in ref]
    if not difs or max(difs) > TOL_DIVIDA:
        raise RuntimeError("DBGG até 2007: 4502 / 4382 × 100 difere %.4f p.p. da 4537" % (max(difs) if difs else 999))
    print("conferência: DBGG até 2007 bate com a 4537 em %d meses (máx %.4f p.p.)" % (len(difs), max(difs)))
    return div


def tolerancia_meta(ano):
    if ano <= 2002:
        return 2.0
    if ano <= 2005:
        return 2.5
    if ano <= 2016:
        return 2.0
    return 1.5


def ipca():
    a12, mens, meta_a = sgs(13522, "01/01/2000"), sgs(433, "01/01/1999"), sgs(13521, "01/01/2000")
    n = 0
    for m in a12:
        i = ordem(m)
        jan = [mes_de(i - k) for k in range(12)]
        if m < "2001-01" or not all(x in mens for x in jan):
            continue
        p = 1.0
        for x in jan:
            p *= 1 + mens[x] / 100
        if abs((p - 1) * 100 - a12[m]) > TOL_IPCA:
            raise RuntimeError("IPCA 12 meses de %s: refeito %.3f × SGS %.2f" % (m, (p - 1) * 100, a12[m]))
        n += 1
    print("conferência: IPCA 12 meses refeito bate em %d meses" % n)
    centros = {int(m[:4]): v for m, v in meta_a.items()}
    ultimo_c = centros[max(centros)]
    meta, piso, teto = {}, {}, {}
    for m in a12:
        ano = int(m[:4])
        c = centros.get(ano, ultimo_c)
        t = tolerancia_meta(ano)
        meta[m] = c
        piso[m] = c - t
        teto[m] = c + t
    return a12, mens, meta, piso, teto


def selic(ate):
    diaria = sgs(432, "01/01/2002", diario=True)
    return fim_do_mes(diaria, ate), diaria


def cambio(ate):
    diaria = sgs(1, "01/01/2002", diario=True)
    mens = fim_do_mes(diaria, ate)
    ref = sgs(3696, "01/01/2002")
    n = 0
    for m, v in mens.items():
        if m in ref:
            if abs(v - ref[m]) > TOL_PTAX:
                raise RuntimeError("PTAX de fim de %s: diária %.4f × 3696 %.4f" % (m, v, ref[m]))
            n += 1
    print("conferência: PTAX do último dia útil bate com a 3696 em %d meses" % n)
    return mens, diaria


def cpi_eua():
    # FRED sem User-Agent (com ele, trava)
    txt = baixar(FRED, headers=None).decode("utf-8-sig")
    linhas = list(csv.reader(io.StringIO(txt)))
    if "CPIAUCNS" not in linhas[0][1]:
        raise RuntimeError("cabeçalho inesperado no FRED: %r" % linhas[0])
    cpi = {l[0][:7]: float(l[1]) for l in linhas[1:] if len(l) >= 2 and l[1].strip() not in ("", ".")}
    print("FRED CPIAUCNS %d meses, %s a %s" % (len(cpi), min(cpi), max(cpi)))
    # segunda fonte: o mesmo índice no FMI (IMF.STA/CPI, base 2010 = 100). A
    # API do BLS sem chave dá 3 anos por pedido e 25 pedidos por dia; o FMI não
    # tem limite. Como a base é outra, confere a razão entre os dois, que tem
    # de ser constante (a mesma série reescalonada).
    d = json.loads(baixar(FMI_CPI).decode("utf-8"))
    tempos = [v["value"] for v in d["data"]["structures"][0]["dimensions"]["observation"][0]["values"]]
    obs = list(d["data"]["dataSets"][0]["series"].values())[0]["observations"]
    fmi = {tempos[int(k)].replace("-M", "-"): float(v[0]) for k, v in obs.items() if v[0] not in (None, "")}
    comuns = [m for m in fmi if m in cpi and m >= "2002-01"]
    razao = [cpi[m] / fmi[m] for m in comuns]
    media = sum(razao) / len(razao)
    pior = max(abs(r / media - 1) for r in razao)
    if len(comuns) < 250 or pior > TOL_CPI:
        raise RuntimeError("CPI: FRED × FMI difere %.5f%% em %d meses" % (pior * 100, len(comuns)))
    print("conferência: CPI do FRED bate com o do FMI em %d meses (desvio máximo %.4f%%)" % (len(comuns), pior * 100))
    return cpi


def ratings():
    d = json.loads(baixar(PM).decode("utf-8"))
    r = [s for s in d["series"] if s["id"] == "rating"][0]
    # a escala do Poder & Mercado (Baa3/BBB− = 12) é a mesma do FtM (Aaa/AAA = 21)
    for v, moody, spf in r["escala"]:
        if NOTAS_MOODYS[21 - v] != moody or NOTAS_SP[21 - v] != spf:
            raise RuntimeError("escala de rating diferente: %r" % [v, moody, spf])
    if r["grauInvestimento"] != 12:
        raise RuntimeError("grau de investimento fora de 12")
    def expandir(mudancas, fim):
        """[[mês, valor], ...] só nas mudanças -> {mês: valor} em todo mês."""
        degraus = sorted([m, v] for m, v in mudancas)
        out_m, atual = {}, None
        for i in range(ordem(degraus[0][0]), ordem(fim) + 1):
            m = mes_de(i)
            for dm, v in degraus:
                if dm == m:
                    atual = v
            out_m[m] = atual
        return out_m

    out = {}
    for a in r["agencias"]:
        mensal = expandir(a["me"], a["fim"])
        local = expandir(a["ml"], a["fim"])
        persp_m = expandir(a["persp"], a["fim"])
        # conferência: a perspectiva de cada mês é a do último anúncio até ele
        ult_p, n_p = None, 0
        evs = sorted(a["eventos"])
        for i in range(ordem("2002-01"), ordem(a["fim"]) + 1):
            m = mes_de(i)
            for data, _, pe in evs:
                if data[:7] == m and pe in PERSPECTIVAS:
                    ult_p = pe
            if ult_p and m in persp_m:
                if persp_m[m] != ult_p:
                    raise RuntimeError("%s em %s: perspectiva %s × anúncios %s" % (a["nome"], m, persp_m[m], ult_p))
                n_p += 1
        print("rating %-8s perspectiva conferida contra os anúncios em %d meses" % (a["nome"], n_p))
        # conferência: a nota no fim de cada mês com ação de rating desde 2002 é
        # a da última ação do mês (a Moody's agiu duas vezes em ago/2006)
        ultima_do_mes = {}
        for data, nivel, _ in sorted(a["eventos"]):
            if nivel is not None:
                ultima_do_mes[data[:7]] = (data, nivel)
        n = 0
        for m, (data, nivel) in ultima_do_mes.items():
            if m >= "2002-01" and m in mensal:
                if mensal[m] != nivel:
                    raise RuntimeError("%s em %s: ação diz %s, série mensal diz %s" % (a["nome"], data, nivel, mensal[m]))
                n += 1
        print("rating %-8s até %s; %d ações de rating conferidas" % (a["nome"], a["fim"], n))
        # nota em cada dia de anúncio (para a tabela, que vai pela data da posse)
        dia = {data: nivel for data, nivel, _ in sorted(a["eventos"]) if nivel is not None}
        dia_persp = {data: pe for data, _, pe in sorted(a["eventos"]) if pe in PERSPECTIVAS}
        # um marcador por mês com anúncio: nota e perspectiva do último anúncio do mês
        anuncios = {}
        for data, nivel, pe in sorted(a["eventos"]):
            if nivel is not None and pe in PERSPECTIVAS:
                anuncios[data[:7]] = (nivel, pe)
        out[a["id"]] = dict(nome=a["nome"], serie={m: v for m, v in mensal.items() if v is not None},
                            local={m: v for m, v in local.items() if v is not None},
                            dia=dia, dia_persp=dia_persp, anuncios=anuncios, fim=a["fim"])
    return out


def ftm_dados(arquivo, gid):
    """O gráfico `gid` de dados/<arquivo> no clone local do FtM Dados."""
    caminho = os.path.join(FTM_DADOS, "dados", arquivo)
    with open(caminho, encoding="utf-8") as f:
        d = json.load(f)
    achado = []

    def andar(o):
        if isinstance(o, dict):
            if o.get("id") == gid:
                achado.append(o)
            for v in o.values():
                andar(v)
        elif isinstance(o, list):
            for v in o:
                andar(v)
    andar(d)
    if not achado:
        raise RuntimeError("FtM Dados: %s sem o gráfico %s" % (arquivo, gid))
    return achado[0]


def serie_de(g, comeco):
    return {m: v for m, v in next(s for s in g["series"] if s["nome"].startswith(comeco))["dados"]}


def ppc_ftm(ipca_m, cpi, cambio_d):
    """Dólar de mercado (PTAX média do mês) e câmbio pela PPC do FtM Dados, base
    única: R$ 1,00 = US$ 1,00 em junho de 1994, corrigido pela inflação relativa."""
    g = ftm_dados("moedas.json", "moedas-cambio-ppc")
    mercado, ppc_s = serie_de(g, "Dólar de mercado"), serie_de(g, "Câmbio pela PPC")
    ult = max(ppc_s)
    mercado = {m: v for m, v in mercado.items() if m <= ult}        # o último ponto lá é o fechamento do dia
    # conferência 1: o dólar de mercado é a média da PTAX diária no mês
    dias = {}
    for d, v in cambio_d.items():
        dias.setdefault(d[:7], []).append(v)
    difs = [abs(mercado[m] - sum(dias[m]) / len(dias[m])) for m in mercado if m in dias and m >= "2002-01"]
    if len(difs) < 280 or max(difs) > TOL_PTAX_MEDIA:
        raise RuntimeError("PPC: dólar de mercado do FtM Dados × PTAX média difere R$ %.4f" % max(difs))
    print("conferência: dólar de mercado do FtM Dados = PTAX média do mês em %d meses (máx R$ %.4f)"
          % (len(difs), max(difs)))
    # conferência 2: a PPC anda pelo IPCA sobre o CPI dos EUA. Mês a mês a
    # planilha do FtM Dados se afasta até 0,3% (calendário do índice de poder de
    # compra do BLS), mas em 12 meses e no período todo a conta fecha
    rel = []
    for m in ppc_s:
        a = mes_de(ordem(m) - 12)
        janela = [mes_de(ordem(m) - k) for k in range(12)]
        if a >= "2002-01" and a in ppc_s and m in cpi and a in cpi and all(x in ipca_m for x in janela):
            f = 1.0
            for x in janela:
                f *= 1 + ipca_m[x] / 100
            rel.append(abs(ppc_s[m] / (ppc_s[a] * f / (cpi[m] / cpi[a])) - 1))
    if len(rel) < 270 or max(rel) > TOL_PPC:
        raise RuntimeError("PPC do FtM Dados não anda pelo IPCA ÷ CPI em 12 meses (desvio %.3f%%)" % (max(rel) * 100))
    print("conferência: PPC do FtM Dados anda pelo IPCA ÷ CPI em %d janelas de 12 meses (desvio máximo %.3f%%)"
          % (len(rel), max(rel) * 100))
    return mercado, ppc_s


def juro_real_ftm(ipca_m):
    """Juro real ex post da taxa básica do FtM Dados: Selic efetivamente paga em
    12 meses (4390) deflacionada pelo IPCA dos mesmos 12 meses (433)."""
    g = ftm_dados("juros.json", "juros-expost")
    jr = serie_de(g, "Brasil")
    selic_mes = sgs(4390, "01/01/1999")
    n, pior = 0, 0.0
    for m in jr:
        janela = [mes_de(ordem(m) - k) for k in range(12)]
        if not all(x in selic_mes and x in ipca_m for x in janela):
            continue
        s = i = 1.0
        for x in janela:
            s *= 1 + selic_mes[x] / 100
            i *= 1 + ipca_m[x] / 100
        pior = max(pior, abs((s / i - 1) * 100 - jr[m]))
        n += 1
    if n < 280 or pior > TOL_EXPOST:
        raise RuntimeError("juro real ex post do FtM Dados × refeito: %.3f p.p." % pior)
    print("conferência: juro real ex post do FtM Dados refeito pela 4390 e 433 em %d meses (máx %.4f p.p.)" % (n, pior))
    return jr, selic_mes


def juro_real_medio(selic_mes, ipca_m, mi):
    """Juro real dos meses do ministro, anualizado: produto da Selic sobre produto do IPCA."""
    ms = [mes_de(i) for i in range(ordem(mi["de"]), ordem(mi["ate"]) + 1)]
    ms = [m for m in ms if m in selic_mes and m in ipca_m]
    if not ms:
        return None
    s = i = 1.0
    for m in ms:
        s *= 1 + selic_mes[m] / 100
        i *= 1 + ipca_m[m] / 100
    return ((s / i) ** (12 / len(ms)) - 1) * 100


def condicionantes_ftm(divida):
    """Fatores condicionantes da DBGG no conceito FMI (a nossa metodologia até
    2007), do FtM Dados; a linha de variação tem de bater com a nossa dívida."""
    g = ftm_dados("fiscal.json", "fiscal-divida-condicionantes-fmi")
    v12 = next(v for v in g["variantes"] if v["rot"] == "Em 12 meses")
    var = serie_de(v12, "Variação da dívida")
    difs = []
    for m, v in var.items():
        a = mes_de(ordem(m) - 12)
        if m in divida and a in divida:
            difs.append(abs(v - (divida[m] - divida[a])))
    if len(difs) < 150 or max(difs) > TOL_COND:
        raise RuntimeError("condicionantes do FtM Dados × nossa dívida: %.3f p.p." % max(difs))
    print("conferência: variação da dívida em 12 meses dos condicionantes bate com a nossa em %d meses (máx %.3f p.p.)"
          % (len(difs), max(difs)))
    return g


def fiscal_real(prim, nom, ipca_m):
    """Primário e nominal acumulados em 12 meses, em R$ milhões a preços do último
    IPCA: fluxo mensal (4649 e 4583, sinal invertido) deflacionado mês a mês."""
    pib12 = sgs(4382, "01/01/2001")
    idx, nivel = {}, 1.0
    for m in sorted(ipca_m):
        nivel *= 1 + ipca_m[m] / 100
        idx[m] = nivel
    ref = max(idx)
    out = {}
    # PIB mensal (4380), para as médias no mandato; somado em 12 meses tem de dar a 4382
    pib_m = sgs(4380, "01/01/2001")
    erros = [abs(sum(pib_m[mes_de(ordem(m) - k)] for k in range(12)) - pib12[m]) for m in pib12
             if all(mes_de(ordem(m) - k) in pib_m for k in range(12))]
    if len(erros) < 250 or max(erros) > 2:
        raise RuntimeError("PIB: 12 meses da 4380 não dão a 4382 (R$ %.0f mi)" % max(erros))
    print("conferência: PIB mensal 4380 somado em 12 meses = 4382 em %d meses (máx R$ %.1f mi)" % (len(erros), max(erros)))
    out["pib_mensal"] = pib_m
    for chave, cod, pct in (("primario", 4649, prim), ("nominal", 4583, nom)):
        fluxo = {m: -v for m, v in sgs(cod, "01/01/2001").items()}
        out["fluxo_" + chave] = fluxo
        doze_nom, doze_real = {}, {}
        for m in fluxo:
            janela = [mes_de(ordem(m) - k) for k in range(12)]
            if all(x in fluxo and x in idx for x in janela):
                doze_nom[m] = sum(fluxo[x] for x in janela)
                doze_real[m] = sum(fluxo[x] * idx[ref] / idx[x] for x in janela)
        difs = [abs(doze_nom[m] / pib12[m] * 100 - pct[m]) for m in doze_nom if m in pib12 and m in pct]
        if len(difs) < 250 or max(difs) > TOL_FLUXO:
            raise RuntimeError("%s: soma de 12 meses da %d ÷ PIB difere %.3f p.p. da série em %% do PIB"
                               % (chave, cod, max(difs)))
        print("conferência: %s, 12 meses da %d ÷ 4382 bate com a série em %% do PIB em %d meses (máx %.4f p.p.)"
              % (chave, cod, len(difs), max(difs)))
        out[chave] = doze_real
    return out, ref


def grafico_mandato(gid, titulo, doze_real, mins, ref, fonte):
    """Uma linha por ministro: variação real do acumulado em 12 meses desde o
    mês-base, em R$ bilhões; no eixo X, os meses no cargo."""
    series, nmax = [], 0
    for mi in mins:
        b = mi["base"]
        if b not in doze_real:
            continue
        pts = [["0", 0.0]]
        for k, i in enumerate(range(ordem(mi["de"]), ordem(mi["ate"]) + 1), 1):
            m = mes_de(i)
            if m in doze_real:
                pts.append([str(k), round((doze_real[m] - doze_real[b]) / 1000, 1)])
        nmax = max(nmax, int(pts[-1][0]))
        series.append(dict(nome=mi["nome"], cor=CORES_MINISTRO[mi["id"]], dados=pts, rotulo=True, largura=4))
    cats = [str(k) if k % 12 == 0 else "" for k in range(nmax + 1)]
    longas = ["Mês anterior à posse"] + ["%dº mês no cargo" % k for k in range(1, nmax + 1)]
    return dict(id=gid, titulo=titulo,
                subtitulo="Variação real do acumulado em 12 meses desde o mês anterior ao do ministro, em R$ bilhões "
                          "a preços de %s pelo IPCA" % mes_curto(ref),
                unidade="bi", fonte=fonte, categorias=cats, categoriasLongas=longas, apresentarDaqui=True,
                series=series)


# ---------- um ministro semana a semana ----------
def ibovespa(ini, fim):
    """Ibovespa diário (SGS 7, fechamento em pontos), conferido contra o Yahoo."""
    d0 = datetime.date.fromisoformat(ini)
    # só a janela pedida: o SGS responde 404 às janelas da série 7 sem dado
    url = SGS % (7, d0.strftime("%d/%m/%Y"), datetime.date.fromisoformat(fim).strftime("%d/%m/%Y"))
    lst = json.loads(baixar(url).decode("utf-8"))
    if not isinstance(lst, list) or not lst:
        raise RuntimeError("SGS 7 respondeu %r" % (lst,))
    ib = {}
    for x in lst:
        dd, mm, aa = x["data"].split("/")
        ib["%s-%s-%s" % (aa, mm, dd)] = float(x["valor"])
    ib = {d: v for d, v in ib.items() if d <= fim}
    a = int(datetime.datetime(d0.year, d0.month, d0.day, tzinfo=datetime.timezone.utc).timestamp())
    f = datetime.date.fromisoformat(fim) + datetime.timedelta(days=2)
    b = int(datetime.datetime(f.year, f.month, f.day, tzinfo=datetime.timezone.utc).timestamp())
    try:
        r = json.loads(baixar(YAHOO_IBOV.format(a, b), headers={"User-Agent": "Mozilla/5.0"}).decode("utf-8"))
        res = r["chart"]["result"][0]
        fuso = datetime.timezone(datetime.timedelta(seconds=res["meta"].get("gmtoffset", -10800)))
        yh = {datetime.datetime.fromtimestamp(t, fuso).date().isoformat(): c
              for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]) if c is not None}
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("Ibovespa: Yahoo indisponível para a conferência (%s)" % e)
    comuns = [d for d in ib if d in yh]
    ruins = {d: (ib[d], yh[d]) for d in comuns if abs(ib[d] - yh[d]) > TOL_IBOV}
    # um dia isolado pode divergir (10/11/2015: 46.206 no SGS, 46.179 no Yahoo);
    # quem usa a série confere que nenhum dia divergente entrou na amostra
    if len(comuns) < len(ib) * 0.95 or len(ruins) > 1:
        raise RuntimeError("Ibovespa: SGS 7 × Yahoo diverge em %d dias: %r" % (len(ruins), ruins))
    print("conferência: Ibovespa do SGS 7 bate com o Yahoo (até %.0f ponto) em %d de %d dias; fora: %r"
          % (TOL_IBOV, len(comuns) - len(ruins), len(comuns), ruins))
    return ib, set(ruins)


def semanal(diaria, posse, saida):
    """A véspera da posse (último dado antes dela) e o último dado de cada
    semana (segunda a domingo) no cargo, até o dia anterior à posse do sucessor."""
    ds = sorted(d for d in diaria if d < saida)
    base = max(d for d in ds if d < posse)
    semanas = {}
    for d in ds:
        if d >= posse:
            semanas[datetime.date.fromisoformat(d).isocalendar()[:2]] = d
    return {d: diaria[d] for d in [base] + sorted(semanas.values())}


def variacoes(s, fmt):
    ks = sorted(s)
    return {b: fmt(s[a], s[b]) for a, b in zip(ks, ks[1:])}


def secao_semana(mi, cambio_d, selic_d, divida):
    """Gráficos que se completam um passo por vez (semana; mês na dívida), com a
    variação do último passo ao lado do ponto."""
    fim = mi["saida"]
    ib, ib_ruins = ibovespa("2014-12-01", fim)
    uteis = {d: selic_d[d] for d in cambio_d if d in selic_d}      # a meta nos dias de PTAX
    cam, ibs, sel = semanal(cambio_d, mi["posse"], fim), semanal(ib, mi["posse"], fim), semanal(uteis, mi["posse"], fim)
    div = {m: divida[m] for m in divida if ordem(mi["base"]) <= ordem(m) <= ordem(mi["ate"])}
    if ib_ruins & set(ibs):
        raise RuntimeError("Ibovespa: dia divergente do Yahoo na amostra semanal: %r" % sorted(ib_ruins & set(ibs)))
    for nome, ss in (("câmbio", cam), ("Ibovespa", ibs), ("Selic", sel)):
        print("%s: %s semanal, %d pontos (%s a %s)" % (mi["curto"], nome, len(ss), min(ss), max(ss)))
    pct = lambda a, b: sinal((b / a - 1) * 100, 2) + "%"
    var_cam = variacoes(cam, lambda a, b: "%sR$ %s (%s)" % ("+" if b - a > 0 else "−" if round(b - a, 2) else "",
                                                             br(abs(b - a), 2), pct(a, b)))
    var_ib = variacoes(ibs, lambda a, b: "%s %s (%s)" % (sinal(b - a, 0), "ponto" if abs(round(b - a)) == 1 else "pontos",
                                                         pct(a, b)))
    var_sel = variacoes(sel, lambda a, b: sinal(b - a, 2) + " p.p.")
    var_div = variacoes(div, lambda a, b: sinal(b - a, 2) + " p.p. do PIB")
    nome = mi["nome"]
    sem = dict(unidade="Semana")

    def g(gid, titulo, sub, unidade, fonte, serie_, revelar, **extra):
        return dict(id="levy-" + gid, titulo=titulo, subtitulo=sub, unidade=unidade, fonte=fonte,
                    eixo={"zero": False}, revelar=revelar, apresentarDaqui=True, series=[serie_], **extra)
    dados = lambda s_: [[k, v] for k, v in sorted(s_.items())]
    graficos = [
        g("cambio", "Câmbio com %s" % nome, "R$ por US$, PTAX no fim da semana", "brl", "BCB (PTAX, SGS 1)",
          dict(nome="Câmbio (PTAX)", cor=BRANCO, dados=[[k, round(v, 4)] for k, v in sorted(cam.items())],
               rotulo=True, largura=5, variacoes=var_cam), sem, diario=True, buracoMax=8),
        g("ibovespa", "Ibovespa com %s" % nome, "Pontos, fechamento da semana", "int", "B3 (via BCB, SGS 7)",
          dict(nome="Ibovespa", cor=VERDE, dados=dados(ibs), rotulo=True, largura=5, variacoes=var_ib),
          sem, diario=True, buracoMax=8),
        g("selic", "Meta da Selic com %s" % nome, "% a.a., no fim da semana", "%", "BCB (SGS 432)",
          dict(nome="Meta da Selic", cor=AZUL, dados=dados(sel), rotulo=True, largura=5, variacoes=var_sel),
          sem, diario=True, buracoMax=8),
        g("divida", "Dívida bruta do governo geral com %s" % nome, "% do PIB, metodologia até 2007; dado mensal", "%",
          "BCB (SGS 4502 e 4382) e FtM",
          dict(nome="Dívida bruta", cor=LARANJA, dados=[[k, round(v, 2)] for k, v in sorted(div.items())],
               rotulo=True, largura=5, variacoes=var_div), dict(unidade="Mês")),
    ]
    return dict(titulo="%s semana a semana" % nome, texto="", graficos=graficos)


# ---------- gráficos e tabelas ----------
def serie(nome, s, casas, ini=INICIO, **extra):
    return dict(nome=nome, dados=[[m, round(s[m], casas)] for m in sorted(s, key=ordem) if m >= ini], **extra)


def ponta(s, m_ini, m_fim):
    """(mês, valor) no início e no final; o final é o último dado até m_fim."""
    ini = (m_ini, s[m_ini]) if m_ini in s else None
    ms = [m for m in s if m_ini <= m <= m_fim] if ini else [m for m in s if m <= m_fim and m > m_ini]
    fim = max(ms, key=ordem) if ms else None
    return ini, ((fim, s[fim]) if fim else None)


def dia_curto(d):
    return "%s/%s/%s" % (d[8:10], d[5:7], d[2:4])


def vespera(d):
    return (datetime.date.fromisoformat(d) - datetime.timedelta(days=1)).isoformat()


def ponta_dia(diaria, mi):
    """Valor na véspera da posse (último dado antes dela) e no último dia no
    cargo (último dado antes da posse do sucessor; para quem está no cargo, o
    último publicado)."""
    antes = [d for d in diaria if d < mi["posse"]]
    dentro = [d for d in diaria if mi["posse"] <= d and (not mi["saida"] or d < mi["saida"])]
    ini = max(antes) if antes else None
    fim = max(dentro) if dentro else ini
    return ((ini, diaria[ini]) if ini else None), ((fim, diaria[fim]) if fim else None)


def celula(p, fmt):
    return {"t": "n.d."} if p is None else {"t": "%s (%s)" % (fmt(p[1]), mes_curto(p[0]))}


def pintar_linha(linha, ind_id, mid):
    alvo = DESTAQUE_VERMELHO.get(ind_id)
    if mid == alvo or (isinstance(alvo, tuple) and mid in alvo):
        for c in linha:
            c["cor"] = VERMELHO
    return linha


def linha_ind(nome, pres, s, mi, fmt, var, diaria=None):
    if diaria:
        ini, fim = ponta_dia(diaria, mi)
        cel = lambda p: {"t": "n.d."} if p is None else {"t": "%s (%s)" % (fmt(p[1]), dia_curto(p[0]))}
        v = var(ini[1], fim[1]) if ini and fim else "n.d."
        return [{"t": nome, "forte": True}, {"t": pres}, cel(ini), cel(fim), {"t": v, "forte": True}]
    ini, fim = ponta(s, mi["base"], mi["ate"])
    v = var(ini[1], fim[1]) if ini and fim and fim[0] != ini[0] else "n.d."
    return [{"t": nome, "forte": True}, {"t": pres}, celula(ini, fmt), celula(fim, fmt), {"t": v, "forte": True}]


def media_dia(diaria, mi):
    """Média simples dos dias com dado, da posse ao último dia no cargo."""
    vs = [v for d, v in diaria.items() if mi["posse"] <= d and (not mi["saida"] or d < mi["saida"])]
    return sum(vs) / len(vs) if vs else None


def var_media_mensal(s, mi):
    """(final − início) / número de meses entre eles, em p.p. por mês."""
    ini, fim = ponta(s, mi["base"], mi["ate"])
    if not (ini and fim) or fim[0] == ini[0]:
        return None
    return (fim[1] - ini[1]) / (ordem(fim[0]) - ordem(ini[0]))


def contagem_meta_ipca(ipca12, meta, teto, mi):
    ms = [mes_de(i) for i in range(ordem(mi["de"]), ordem(mi["ate"]) + 1)]
    validos = [m for m in ms if m in ipca12]
    acima_m = sum(1 for m in validos if ipca12[m] > meta[m])
    acima_t = sum(1 for m in validos if ipca12[m] > teto[m])
    return "%d/%d" % (acima_m, len(validos)), "%d/%d" % (acima_t, len(validos))


def nota_dia(r, mi):
    """Nota na véspera da posse e no último dia no cargo, pelas datas das ações
    (a série mensal põe a ação no mês, e o mês pode ser do sucessor: a Fitch
    rebaixou em 05/05/2016, com Barbosa, e maio é de Meirelles)."""
    def em(d):
        ant = [x for x in r["dia"] if x < d]
        return r["dia"][max(ant)] if ant else None
    # para quem está no cargo, a nota vale até o fim dos dados do Poder & Mercado
    return em(mi["posse"]), em(mi["saida"] or "9999-12-31"), (None if mi["saida"] else r["fim"])


def persp_dia(r, mi):
    """Perspectiva na véspera da posse e no último dia no cargo (último anúncio antes)."""
    def em(d):
        ant = [x for x in r["dia_persp"] if x < d]
        return r["dia_persp"][max(ant)] if ant else None
    return em(mi["posse"]), em(mi["saida"] or "9999-12-31")


def nota_p(v, pe, agencia):
    return nota(v, agencia) + (" " + pe.lower() if pe else "")


def nota(v, agencia):
    return (NOTAS_MOODYS if agencia == "moodys" else NOTAS_SP)[21 - v].replace("-", "\u2212")


def degraus(a, b):
    d = b - a
    if d == 0:
        return "0"
    return "%s%d %s" % ("+" if d > 0 else "−", abs(d), "degrau" if abs(d) == 1 else "degraus")


def doze_meses(mensal):
    """{mês: soma dos 12 meses até ele}, só onde os 12 meses existem."""
    out = {}
    for m in mensal:
        ms = [mes_de(ordem(m) - k) for k in range(12)]
        if all(x in mensal for x in ms):
            out[m] = sum(mensal[x] for x in ms)
    return out


def rtn_pib():
    """Receita líquida e despesa primária do governo central em 12 meses, em %
    do PIB (RTN, tabela 1.1, sobre o PIB de 12 meses do BC, SGS 4382).
    Confere: receita líquida menos despesa total = primário acima da linha."""
    sys.path.insert(0, os.path.join(FTM_DADOS, "scripts"))
    import rtn                                   # noqa: E402
    tab, unidade = rtn.tabela("1.1")
    if "Correntes" not in unidade:
        raise RuntimeError("RTN: aba 1.1 não está em valores correntes (%s)" % unidade)

    def linha(prefixo):
        rot = [k for k in tab if k.startswith(prefixo)]
        if len(rot) != 1:
            raise RuntimeError("RTN: linha %r não encontrada uma única vez" % prefixo)
        return tab[rot[0]]
    rec, desp = linha("3. RECEITA LÍQUIDA"), linha("4. DESPESA TOTAL")
    prim = linha("5. RESULTADO PRIMÁRIO GOVERNO CENTRAL - ACIMA DA LINHA")
    erro = max(abs(rec[m] - desp[m] - prim[m]) for m in prim if m in rec and m in desp)
    if erro > 1:
        raise RuntimeError("RTN: receita líquida − despesa ≠ primário (R$ %.1f mi)" % erro)
    pib = sgs(4382, "01/01/1997")
    pct = lambda d: {m: v / pib[m] * 100 for m, v in doze_meses(d).items() if m in pib}   # noqa: E731
    r12, d12 = pct(rec), pct(desp)
    u = max(r12, key=ordem)
    print("RTN até %s: receita líquida %.2f%% e despesa primária %.2f%% do PIB (12 meses); "
          "conferência do primário, maior diferença R$ %.2f mi" % (u, r12[u], d12[u], erro))
    return r12, d12


def levy_trabuco(mins, INDS, desvio_ppc, pct2, pp, r12, d12):
    """Levy na véspera da posse (dez/14; Selic e câmbio em 31/12/14)
    contra o último dado publicado, o quadro que Trabuco recebe."""
    levy, atual = next(mi for mi in mins if mi["id"] == "levy"), mins[-1]

    def mensal(nome, s, fmt, var):
        a = (levy["base"], s[levy["base"]])
        u = max(s, key=ordem)
        b = (u, s[u])
        return [{"t": nome, "forte": True}, celula(a, fmt), celula(b, fmt), {"t": var(a[1], b[1]), "forte": True}]

    def diaria(nome, d, fmt, var):
        a, b = ponta_dia(d, levy)[0], ponta_dia(d, atual)[1]
        cel = lambda p: {"t": "%s (%s)" % (fmt(p[1]), dia_curto(p[0]))}   # noqa: E731
        return [{"t": nome, "forte": True}, cel(a), cel(b), {"t": var(a[1], b[1]), "forte": True}]

    nomes = {"primario": "Resultado primário do setor público (% do PIB)",
             "nominal": "Resultado nominal do setor público (% do PIB)",
             "divida": "Dívida bruta do governo geral (% do PIB)", "ipca": "IPCA em 12 meses",
             "selic": "Meta da Selic (% a.a.)", "juro-real": "Juro real ex post (% a.a.)",
             "cambio": "Câmbio (R$ por US$)"}
    pct_s = lambda v: sinal(v, 2) + "%"                              # noqa: E731
    linhas = []
    for ind in INDS:
        fmt = pct_s if ind["id"] in ("primario", "nominal") else ind["fmt"]
        if ind.get("diaria"):
            linhas.append(diaria(nomes[ind["id"]], ind["diaria"], fmt, ind["var"]))
        else:
            linhas.append(mensal(nomes[ind["id"]], ind["s"], fmt, ind["var"]))
        if ind["id"] == "nominal":
            linhas.append(mensal("Receita líquida do governo central (% do PIB)", r12, pct2, pp))
            linhas.append(mensal("Despesa primária do governo central (% do PIB)", d12, pct2, pp))
    linhas.append(mensal("Sobre/(sub)valorização do real pela PPC", desvio_ppc, lambda v: sinal(v, 1) + "%",
                         lambda a, b: sinal(b - a, 1) + " p.p."))
    return dict(id="ministros-levy-trabuco", tipo="tabela",
                titulo="Levy na posse e o quadro que Trabuco recebe",
                subtitulo="Fluxos em 12 meses",
                fonte="BCB, IBGE, Tesouro Nacional (RTN), BLS e FtM",
                colunas=[{"rot": "Indicador"}, {"rot": "Levy (início)", "num": True},
                         {"rot": "Trabuco (último dado)", "num": True}, {"rot": "Variação", "num": True}],
                linhas=linhas)


def montar():
    hoje = datetime.date.today()
    fechado = mes_de(ordem(hoje.strftime("%Y-%m")) - 1)        # último mês fechado
    prim, nom = fiscal()
    divida = divida_ate2007()
    ipca12, ipca_m, meta_ipca, piso_ipca, teto_ipca = ipca()
    selic_m, selic_d = selic(fechado)
    cambio_m, cambio_d = cambio(fechado)
    cpi = cpi_eua()
    rat = ratings()
    mercado_ppc, ppc_s = ppc_ftm(ipca_m, cpi, cambio_d)
    juro_real, selic_mes = juro_real_ftm(ipca_m)
    cond = condicionantes_ftm(divida)
    doze_real, ref_real = fiscal_real(prim, nom, ipca_m)
    desvio_ppc = {m: (ppc_s[m] / mercado_ppc[m] - 1) * 100 for m in ppc_s if m in mercado_ppc}

    ultimo = max(max(prim), max(ipca12), max(selic_m), max(cambio_m))
    mins = meses_dos_ministros(ultimo)
    pres_fx = presidentes_faixas(ultimo)
    for mi in mins:
        mi["pres"] = presidente_do_ministro(mi, pres_fx)
    fx = faixas(mins)

    pct2 = lambda v: br(v, 2) + "%"
    pp = lambda a, b: sinal(b - a, 2) + " p.p."
    rs = lambda v: "R$ " + br(v, 2)
    pctvar = lambda a, b: sinal((b / a - 1) * 100, 1) + "%"

    INDS = [
        dict(id="primario", sec="Resultado primário", s=prim, unidade="%", fmt=pct2, var=pp, cor=VERDE,
             cor_neg=VERMELHO,
             titulo="Resultado primário do setor público consolidado",
             sub="% do PIB, acumulado em 12 meses; superávit positivo",
             fonte="BCB (NFSP, SGS 5793) e FtM", rot="Primário"),
        dict(id="nominal", sec="Resultado nominal", s=nom, unidade="%", fmt=pct2, var=pp, cor=BRANCO,
             titulo="Resultado nominal do setor público consolidado",
             sub="% do PIB, acumulado em 12 meses",
             fonte="BCB (NFSP, SGS 5727) e FtM", rot="Nominal"),
        dict(id="divida", sec="Dívida bruta do governo geral", s=divida, unidade="%", fmt=pct2, var=pp, cor=LARANJA,
             titulo="Dívida bruta do governo geral",
             sub="% do PIB; metodologia usada pelo BC até 2007 (conceito FMI, com toda a carteira do Tesouro no BC)",
             fonte="BCB (SGS 4502, 4382 e 4537) e FtM", rot="Dívida bruta (DBGG)"),
        dict(id="ipca", sec="Inflação", s=ipca12, unidade="%", fmt=pct2, var=pp, cor=VERDE,
             titulo="IPCA", sub="Variação % acumulada em 12 meses",
             fonte="IBGE (IPCA, via BCB, SGS 13522 e 13521)", rot="IPCA em 12 meses"),
        dict(id="selic", sec="Selic", s=selic_m, unidade="%", fmt=pct2, var=pp, cor=AZUL,
             titulo="Meta da taxa Selic", sub="% a.a.; valor no último dia do mês",
             fonte="BCB (SGS 432)", rot="Meta da Selic", diaria=selic_d),
        dict(id="juro-real", sec="Selic", s=juro_real, unidade="%", fmt=pct2, var=pp, cor=AZUL_CLARO,
             titulo="Juro real ex post da taxa básica",
             sub="% a.a.; Selic efetivamente paga em 12 meses deflacionada pelo IPCA dos mesmos 12 meses",
             fonte="BCB (Selic, SGS 4390; IPCA, SGS 433) e FtM", rot="Juro real ex post"),
        dict(id="cambio", sec="Câmbio", s=cambio_m, unidade="brl", fmt=rs, var=pctvar, cor=BRANCO,
             titulo="Taxa de câmbio", sub="R$ por US$; PTAX de venda no último dia útil do mês",
             fonte="BCB (PTAX, SGS 1)", rot="Câmbio (PTAX)", diaria=cambio_d),
    ]

    secoes = []
    for ind in INDS:
        extra_ser = dict(rotulo=True, legenda=False)
        if ind.get("cor_neg"):
            extra_ser["corNegativa"] = ind["cor_neg"]
        if ind["id"] == "ipca":
            faixa_meta = [[m, round(piso_ipca[m], 2), round(teto_ipca[m], 2)]
                          for m in sorted(ipca12, key=ordem) if m >= INICIO]
            g = dict(id="ministros-" + ind["id"], titulo=ind["titulo"], subtitulo=ind["sub"], unidade=ind["unidade"],
                     fonte=ind["fonte"], ministros=fx, presidentes=pres_fx, apresentarDaqui=True,
                     variantes=[
                         dict(rot="IPCA",
                              series=[serie(ind["rot"], ind["s"], 2, cor=ind["cor"], rotulo=True, legenda=False)]),
                         dict(rot="Com meta e intervalo",
                              series=[
                                  dict(nome="Intervalo de tolerância", cor=CINZA, tipo="faixa",
                                       opacidade=0.22, dados=faixa_meta),
                                  serie("Centro da meta", meta_ipca, 2, cor=BRANCO, traco="pontilhado", largura=3),
                                  serie(ind["rot"], ind["s"], 2, cor=ind["cor"], rotulo=True),
                              ]),
                     ])
        else:
            g = dict(id="ministros-" + ind["id"], titulo=ind["titulo"], subtitulo=ind["sub"], unidade=ind["unidade"],
                     fonte=ind["fonte"], ministros=fx, presidentes=pres_fx, apresentarDaqui=True,
                     series=[serie(ind["rot"], ind["s"], 4 if ind["unidade"] == "brl" else 2, cor=ind["cor"],
                                   **extra_ser)])
        linhas = []
        colunas = [{"rot": "Ministro"}, {"rot": "Presidente"}, {"rot": "Início", "num": True},
                   {"rot": "Final", "num": True}, {"rot": "Variação", "num": True}]
        # a regra dos meses (início e final) só aparece na primeira tabela, a do primário
        if ind.get("diaria"):
            sub_tab = "Início: véspera da posse; final: último dia no cargo ou último dado"
        elif ind["id"] == "primario":
            sub_tab = "Início: mês anterior ao primeiro mês do ministro; final: último mês no cargo ou último dado"
        else:
            sub_tab = ""
        if ind["id"] == "ipca":
            colunas.extend([{"rot": "Acima da meta", "num": True}, {"rot": "Acima do intervalo", "num": True}])
            sub_tab += "; meses acima do centro da meta (SGS 13521) e acima do teto do intervalo do CMN, do total de meses"
        if ind["id"] in ("selic", "cambio"):
            colunas.append({"rot": "Média no período", "num": True})
            # a meta da Selic (432) tem valor em todo dia corrido; a PTAX, só nos dias úteis
            sub_tab += "; média: média simples dos dias %s no cargo" % ("corridos" if ind["id"] == "selic" else "úteis")
        if ind["id"] == "divida":
            colunas.append({"rot": "Variação média mensal", "num": True})
            sub_tab += "; variação média mensal: variação total dividida pelo número de meses"
        if ind["id"] == "juro-real":
            colunas.append({"rot": "Média anualizada no período", "num": True})
            sub_tab += "; média: Selic sobre IPCA nos meses do ministro, anualizada"
        for mi in mins:
            l = linha_ind(mi["nome"], mi["pres"], ind["s"], mi, ind["fmt"], ind["var"], ind.get("diaria"))
            if ind["id"] == "ipca":
                am, at = contagem_meta_ipca(ipca12, meta_ipca, teto_ipca, mi)
                l.extend([{"t": am}, {"t": at}])
            if ind["id"] in ("selic", "cambio"):
                med = media_dia(ind["diaria"], mi)
                l.append({"t": "n.d." if med is None else ind["fmt"](med)})
            if ind["id"] == "divida":
                vm = var_media_mensal(ind["s"], mi)
                l.append({"t": "n.d." if vm is None else sinal(vm, 2) + " p.p."})
            if ind["id"] == "juro-real":
                jm = juro_real_medio(selic_mes, ipca_m, mi)
                l.append({"t": "n.d." if jm is None else pct2(jm)})
            pintar_linha(l, ind["id"], mi["id"])
            linhas.append(l)
        sub_tab = sub_tab.lstrip("; ")
        tab = dict(id="ministros-" + ind["id"] + "-tabela", tipo="tabela",
                   titulo=ind["titulo"] + " por ministro", fonte=ind["fonte"], colunas=colunas, linhas=linhas)
        if sub_tab:
            tab["subtitulo"] = sub_tab[0].upper() + sub_tab[1:]
        graficos = [g, tab]
        if ind["id"] in ("primario", "nominal"):
            graficos.append(grafico_mandato(
                "ministros-%s-mandato" % ind["id"], "%s por mês de mandato" % ind["titulo"],
                doze_real[ind["id"]], mins, ref_real,
                "BCB (NFSP, SGS %s; IPCA, SGS 433) e FtM" % ("4649" if ind["id"] == "primario" else "4583")))
        if ind["id"] == "divida":
            gc = json.loads(json.dumps({k: v for k, v in cond.items() if k not in ("id", "selecao")}))
            # só "Em 12 meses" e "No ano" (pedido dele: sem o de 4 anos)
            gc["variantes"] = [v for v in gc["variantes"] if v["rot"] in ("Em 12 meses", "No ano")]
            if len(gc["variantes"]) != 2:
                raise RuntimeError("condicionantes: faltam as variantes Em 12 meses e No ano no FtM Dados")
            for var_c in gc["variantes"]:
                for se in var_c["series"]:
                    se["cor"] = CORES_CONDICIONANTES[se["nome"]]
            gc.update(id="ministros-divida-condicionantes", ministros=fx, presidentes=pres_fx, apresentarDaqui=True,
                      subtitulo="Contribuição para a variação da dívida bruta no conceito FMI, em p.p. do PIB")
            graficos.append(gc)
        if secoes and secoes[-1]["titulo"] == ind["sec"]:
            secoes[-1]["graficos"].extend(graficos)
        else:
            secoes.append(dict(titulo=ind["sec"], texto="", graficos=graficos))
        ind["linhas"] = linhas

    # receita líquida e despesa primária do governo central (RTN), logo depois do nominal
    r12, d12 = rtn_pib()
    # eixo a partir de um piso par abaixo do menor valor do período: do zero, as linhas ficam achatadas
    piso = min(v for d in (r12, d12) for m, v in d.items() if ordem(m) >= ordem(INICIO))
    rd_g = dict(id="ministros-receita-despesa", titulo="Receita líquida e despesa primária do governo central",
                subtitulo="% do PIB, acumulado em 12 meses", unidade="%", eixo=dict(min=int(piso // 2) * 2 - 2),
                fonte="Tesouro Nacional (RTN, tabela 1.1), BCB (PIB, SGS 4382) e FtM",
                ministros=fx, presidentes=pres_fx, apresentarDaqui=True,
                series=[serie("Receita líquida", r12, 2, cor=AZUL, rotulo=True),
                        serie("Despesa primária", d12, 2, cor=VERMELHO, rotulo=True)])
    pos = next(i for i, sec in enumerate(secoes) if sec["titulo"] == "Resultado nominal") + 1
    secoes.insert(pos, dict(titulo="Receita e despesa do governo central", texto="", graficos=[rd_g]))

    # câmbio pela PPC (bônus): a série do FtM Dados, com base única em jun/1994
    ppc_g = dict(id="ministros-cambio-ppc", titulo="Câmbio de mercado e câmbio pela PPC",
                 subtitulo="R$ por US$, média do mês",
                 unidade="brl", fonte="BCB (PTAX, SGS 1; IPCA, SGS 433), BLS (CPI-U) e FtM",
                 ministros=fx, presidentes=pres_fx, apresentarDaqui=True,
                 variantes=[
                     dict(rot="Câmbio e PPC", unidade="brl", series=[
                         serie("Dólar de mercado", mercado_ppc, 4, cor=VERDE, rotulo=True, largura=5),
                         serie("Câmbio pela PPC", ppc_s, 4, cor=AZUL, rotulo=True, largura=5)]),
                     dict(rot="Sobre/(sub)valorização", unidade="%",
                          subtitulo="Dólar pela PPC ÷ dólar de mercado − 1, em %; positivo, real sobrevalorizado",
                          series=[serie("Sobre/(sub)valorização do real", desvio_ppc, 2, cor=LARANJA,
                                        area=True, rotulo=True, largura=4)]),
                 ])
    linhas_ppc = []
    for mi in mins:
        ini, fim = ponta(desvio_ppc, mi["base"], mi["ate"])
        pc = lambda p: {"t": "n.d."} if p is None else {"t": "%s%% (%s)" % (sinal(p[1], 1), mes_curto(p[0]))}
        v = sinal(fim[1] - ini[1], 1) + " p.p." if ini and fim and fim[0] != ini[0] else "n.d."
        lp = [{"t": mi["nome"], "forte": True}, {"t": mi["pres"]},
              pc(ini), pc(fim), {"t": v, "forte": True}]
        # picos nos meses do ministro (do primeiro ao último mês no cargo)
        no_cargo = [mes_de(i) for i in range(ordem(mi["de"]), ordem(mi["ate"]) + 1) if mes_de(i) in desvio_ppc]
        if no_cargo:
            mx = max(no_cargo, key=lambda m: desvio_ppc[m])
            mn = min(no_cargo, key=lambda m: desvio_ppc[m])
            lp.extend([pc((mx, desvio_ppc[mx])), pc((mn, desvio_ppc[mn]))])
        else:
            lp.extend([{"t": "n.d."}, {"t": "n.d."}])
        pintar_linha(lp, "cambio-ppc", mi["id"])
        linhas_ppc.append(lp)
    ppc_tab = dict(id="ministros-cambio-ppc-tabela", tipo="tabela",
                   titulo="Câmbio pela PPC por ministro",
                   subtitulo="Positivo: real sobrevalorizado; negativo: real subvalorizado",
                   fonte="BCB, BLS e FtM",
                   colunas=[{"rot": "Ministro"}, {"rot": "Presidente"},
                            {"rot": "Sobre/(sub)valorização no início", "num": True},
                            {"rot": "No final", "num": True}, {"rot": "Variação", "num": True},
                            {"rot": "Máximo no mandato", "num": True}, {"rot": "Mínimo no mandato", "num": True}],
                   linhas=linhas_ppc)
    secoes.append(dict(titulo="Bônus: câmbio pela PPC", texto="", graficos=[ppc_g, ppc_tab]))

    # rating: uma agência por vez, como no Poder & Mercado (nota em moeda
    # estrangeira, em moeda local e um marcador por anúncio com a forma da
    # perspectiva), e as três juntas na última opção
    meses_r = [m for m in rat["sp"]["serie"] if m >= INICIO]
    gi = dict(nome="Grau de investimento", cor=CINZA, traco="pontilhado", largura=3,
              buracoMax=400, dados=[[min(meses_r, key=ordem), 12], [max(meses_r, key=ordem), 12]])
    formas = {"Positiva": ("triangulo", VERDE), "Estável": ("circulo", CINZA), "Negativa": ("losango", VERMELHO)}
    variantes_r = []
    for aid in ("sp", "moodys", "fitch"):
        ra, un = rat[aid], ("moodys" if aid == "moodys" else "nota-sp")
        ser = [serie("Moeda estrangeira", ra["serie"], 0, cor=BRANCO, largura=5),
               serie("Moeda local", ra["local"], 0, cor=AMARELO, traco="pontilhado", largura=3), gi]
        for pe, (forma, cor) in formas.items():
            pts = {m: v for m, (v, p_) in ra["anuncios"].items() if p_ == pe}
            ser.append(serie("Perspectiva " + pe.lower(), pts, 0, tipo="pontos", forma=forma, cor=cor))
        # a agência no subtítulo do próprio gráfico: em tela cheia e na imagem baixada os botões somem
        variantes_r.append(dict(rot=ra["nome"], unidade=un, series=ser,
                                subtitulo="Nota de longo prazo da %s" % ra["nome"]))
    # o eixo cobre as duas notas das três agências (a local chegou a A−)
    todas = [v for ra in rat.values() for ss in (ra["serie"], ra["local"]) for m, v in ss.items() if m >= INICIO]
    eixo_r = {"min": min(7, min(todas)), "max": max(14, max(todas) + 1), "passo": 1}
    # as três juntas: deslocamento mínimo para as linhas iguais não se
    # esconderem (o valor mostrado é a nota, arredondada)
    desloc = {"sp": 0.08, "moodys": 0.0, "fitch": -0.08}
    cores = {"sp": AZUL, "moodys": VERMELHO, "fitch": VERDE}
    tres = []
    for aid in ("sp", "moodys", "fitch"):
        s3 = {m: v + desloc[aid] for m, v in rat[aid]["serie"].items()}
        tres.append(serie(rat[aid]["nome"] + (" (dir.)" if aid == "moodys" else ""), s3, 2, cor=cores[aid], unidade="moodys" if aid == "moodys" else "nota-sp"))
    variantes_r.append(dict(rot="As três", unidade="nota-sp", eixoDireita="moodys", series=tres + [gi]))
    rat_g = dict(id="ministros-rating", titulo="Rating soberano do Brasil",
                 subtitulo="Nota de longo prazo", varianteNoSubtitulo=False,
                 unidade="nota-sp", eixo=eixo_r,
                 fonte="Moody's, S&P e Fitch (via Poder & Mercado) e FtM", ministros=fx, presidentes=pres_fx,
                 apresentarDaqui=True, variantes=variantes_r)
    linhas_rat = []
    for mi in mins:
        lin = [{"t": mi["nome"], "forte": True}, {"t": mi["pres"]}]
        for aid in ("sp", "moodys", "fitch"):
            a, b, _ = nota_dia(rat[aid], mi)
            pa, pb = persp_dia(rat[aid], mi)
            lin.append({"t": "%s → %s (%s)" % (nota_p(a, pa, aid), nota_p(b, pb, aid), degraus(a, b))})
        pintar_linha(lin, "rating", mi["id"])
        linhas_rat.append(lin)
    rat_tab = dict(id="ministros-rating-tabela", tipo="tabela", titulo="Rating soberano por ministro",
                   subtitulo="Nota e perspectiva na véspera da posse → no último dia no cargo; dados até %s"
                             % mes_curto(max(meses_r, key=ordem)),
                   fonte="Moody's, S&P e Fitch (via Poder & Mercado)",
                   colunas=[{"rot": "Ministro"}, {"rot": "Presidente"}, {"rot": "S&P"}, {"rot": "Moody's"}, {"rot": "Fitch"}],
                   linhas=linhas_rat)
    secoes.append(dict(titulo="Rating soberano", texto="", graficos=[rat_g, rat_tab]))

    # uma tabela por ministro
    por_min = []
    for k, mi in enumerate(mins):
        linhas = []
        for ind in INDS:
            l = ind["linhas"][k]
            nome_ind = ind["titulo"] if ind["id"] != "ipca" else "IPCA em 12 meses"
            linhas.append([{"t": nome_ind, "forte": True}, {"t": l[2]["t"]}, {"t": l[3]["t"]},
                           {"t": l[4]["t"], "forte": True}])
        lp = linhas_ppc[k]
        linhas.append([{"t": "Sobre/(sub)valorização do real pela PPC", "forte": True}, {"t": lp[2]["t"]},
                       {"t": lp[3]["t"]}, {"t": lp[4]["t"], "forte": True}])
        for aid in ("sp", "moodys", "fitch"):
            a, b, ate = nota_dia(rat[aid], mi)
            pa, pb = persp_dia(rat[aid], mi)
            linhas.append([{"t": "Rating " + rat[aid]["nome"], "forte": True},
                           {"t": "%s (%s)" % (nota_p(a, pa, aid), dia_curto(vespera(mi["posse"])))},
                           {"t": "%s (%s)" % (nota_p(b, pb, aid), dia_curto(vespera(mi["saida"])) if mi["saida"] else mes_curto(ate))},
                           {"t": degraus(a, b), "forte": True}])
        cargo = ("No cargo desde %s" % dia_curto(mi["posse"])) if not mi["saida"] else \
                ("No cargo de %s a %s" % (dia_curto(mi["posse"]), dia_curto(mi["saida"])))
        por_min.append(dict(id="ministros-tabela-" + mi["id"], tipo="tabela",
                            titulo="%s (%s)" % (mi["nome"], mi["pres"]),
                            subtitulo="%s; séries mensais: %s a %s; Selic, câmbio e rating: véspera da posse e último dia"
                                      % (cargo, mes_curto(mi["base"]), mes_curto(mi["ate"])),
                            fonte="BCB, IBGE, BLS, Moody's, S&P, Fitch e FtM",
                            colunas=[{"rot": "Indicador"}, {"rot": "Início", "num": True},
                                     {"rot": "Final", "num": True}, {"rot": "Variação", "num": True}],
                            linhas=linhas))

    # resumo: média de cada indicador no mandato, ministros nas colunas
    def meses_de(mi, serie_m):
        return [mes_de(i) for i in range(ordem(mi["de"]), ordem(mi["ate"]) + 1) if mes_de(i) in serie_m]

    def fluxo_pib(chave, mi):
        fl, pib = doze_real["fluxo_" + chave], doze_real["pib_mensal"]
        ms = [m for m in meses_de(mi, fl) if m in pib]
        return sum(fl[m] for m in ms) / sum(pib[m] for m in ms) * 100 if ms else None

    def media_meses(serie_m, mi):
        ms = meses_de(mi, serie_m)
        return sum(serie_m[m] for m in ms) / len(ms) if ms else None

    def ipca_anual(mi):
        ms = meses_de(mi, ipca_m)
        p = 1.0
        for m in ms:
            p *= 1 + ipca_m[m] / 100
        return (p ** (12 / len(ms)) - 1) * 100 if ms else None

    pct_sinal = lambda v: sinal(v, 2) + "%"
    resumo = [
        ("Resultado primário (% do PIB)", lambda mi: fluxo_pib("primario", mi), pct_sinal),
        ("Resultado nominal (% do PIB)", lambda mi: fluxo_pib("nominal", mi), pct_sinal),
        ("Dívida bruta do governo geral (% do PIB)", lambda mi: media_meses(divida, mi), pct2),
        ("IPCA (% a.a.)", ipca_anual, pct2),
        ("Meta da Selic (% a.a.)", lambda mi: media_dia(selic_d, mi), pct2),
        ("Juro real ex post (% a.a.)", lambda mi: juro_real_medio(selic_mes, ipca_m, mi), pct2),
        ("Câmbio (R$ por US$)", lambda mi: media_dia(cambio_d, mi), rs),
        ("Sobre/(sub)valorização pela PPC", lambda mi: media_meses(desvio_ppc, mi), lambda v: sinal(v, 1) + "%"),
    ]
    linhas_res = []
    for nome_ind, f, fmt in resumo:
        lin = [{"t": nome_ind, "forte": True}]
        for mi in mins:
            v = f(mi)
            lin.append({"t": "n.d." if v is None else fmt(v)})
        linhas_res.append(lin)
    res_tab = dict(id="ministros-resumo-medias", tipo="tabela", titulo="Média no mandato de cada ministro",
                   subtitulo="Primário e nominal: resultado no mandato sobre o PIB do período; IPCA e juro real: "
                             "anualizados; Selic: dias corridos; câmbio: dias úteis; dívida e PPC: média dos meses",
                   fonte="BCB, IBGE, BLS e FtM",
                   colunas=[{"rot": "Indicador"}] + [{"rot": mi["curto"], "num": True} for mi in mins],
                   linhas=linhas_res)
    secoes.append(dict(titulo="Levy × Trabuco", texto="", graficos=[levy_trabuco(
        mins, INDS, desvio_ppc, pct2, pp, r12, d12)]))
    secoes.append(dict(titulo="Médias no mandato", texto="", graficos=[res_tab]))
    secoes.append(dict(titulo="Tabela por ministro", texto="", graficos=por_min))
    # pedido dele: um espaço só para o Levy, semana a semana
    secoes.append(secao_semana(next(m for m in mins if m["id"] == "levy"), cambio_d, selic_d, divida))

    doc = dict(assunto="Ministros da Fazenda", grupo="Análises Variadas",
               capaFtm=dict(titulo="Ministros da Fazenda desde Palocci",
                            data="%d/%s/%d" % (hoje.day, MESES[hoje.month - 1].capitalize(), hoje.year)),
               fonte="BCB, IBGE, BLS, Moody's, S&P, Fitch e FtM; fotos: Agência Brasil, Palácio do Planalto, FMI, "
                     "Ministério da Fazenda, Ministério da Indústria e Governo de SP (Wikimedia Commons)",
               referencia=ultimo, atualizado=hoje.isoformat(), formato="artigo", secoes=secoes)
    return doc, mins, INDS, rat, cambio_m


def main():
    doc, mins, inds, rat, cambio_m = montar()
    print("\nministros e meses:")
    for m in mins:
        print("  %-20s %s a %s (base %s)" % (m["nome"], m["de"], m["ate"], m["base"]))
    print("\núltimo ponto de cada gráfico:")
    for sec in doc["secoes"]:
        for g in sec["graficos"]:
            s_lista = g.get("series") or (g["variantes"][0]["series"] if g.get("variantes") else None)
            if s_lista:
                s = s_lista[0]
                print("  %-28s %s %s" % (g["id"], s["dados"][-1][0], s["dados"][-1][1]))
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    print("\ngravado %s (%d KB)" % (os.path.relpath(SAIDA, RAIZ), os.path.getsize(SAIDA) // 1024))


if __name__ == "__main__":
    main()

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
  - câmbio pela PPC: o câmbio do mês anterior ao primeiro mês de cada ministro
    corrigido pela inflação relativa (IPCA, 433, contra o CPI-U dos EUA sem
    ajuste sazonal, FRED CPIAUCNS, conferido contra o mesmo índice no FMI);
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
import time
import urllib.request

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SAIDA = os.path.join(RAIZ, "dados", "ministros-fazenda.json")
SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.%d/dados?formato=json&dataInicial=%s&dataFinal=%s"
PM = "https://raw.githubusercontent.com/guivaraschinalves/poder-e-mercado/main/dados/indicadores.json"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS"
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
    "divida": "meirelles",
    "ipca": "levy",
    "selic": "guedes",
    "cambio": "levy",
    "cambio-ppc": "levy",
    "rating": "mantega",
}
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
            lst = json.loads(baixar(url).decode("utf-8"))
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
    out = {}
    for a in r["agencias"]:
        degraus = sorted([m, v] for m, v in a["me"])
        mensal, atual = {}, None
        for i in range(ordem(degraus[0][0]), ordem(a["fim"]) + 1):
            m = mes_de(i)
            for dm, v in degraus:
                if dm == m:
                    atual = v
            mensal[m] = atual
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
        out[a["id"]] = dict(nome=a["nome"], serie={m: v for m, v in mensal.items() if v is not None},
                            dia=dia, fim=a["fim"])
    return out


def ppc(cambio_m, ipca_m, cpi, mins):
    """Para cada ministro: câmbio do mês-base × (IPCA acumulado / CPI acumulado)."""
    idx, nivel = {}, 100.0
    for m in sorted(ipca_m):
        nivel *= 1 + ipca_m[m] / 100
        idx[m] = nivel
    trechos = []
    for mi in mins:
        b = mi["base"]
        if b not in cambio_m or b not in idx or b not in cpi:
            raise RuntimeError("PPC de %s: falta o mês-base %s" % (mi["nome"], b))
        s = {}
        for i in range(ordem(b), ordem(mi["ate"]) + 1):
            m = mes_de(i)
            if m in idx and m in cpi:
                s[m] = cambio_m[b] * (idx[m] / idx[b]) / (cpi[m] / cpi[b])
        trechos.append(s)
    return trechos


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
    if DESTAQUE_VERMELHO.get(ind_id) == mid:
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


def nota(v, agencia):
    return (NOTAS_MOODYS if agencia == "moodys" else NOTAS_SP)[21 - v].replace("-", "\u2212")


def degraus(a, b):
    d = b - a
    if d == 0:
        return "0"
    return "%s%d %s" % ("+" if d > 0 else "−", abs(d), "degrau" if abs(d) == 1 else "degraus")


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

    ultimo = max(max(prim), max(ipca12), max(selic_m), max(cambio_m))
    mins = meses_dos_ministros(ultimo)
    pres_fx = presidentes_faixas(ultimo)
    for mi in mins:
        mi["pres"] = presidente_do_ministro(mi, pres_fx)
    fx = faixas(mins)
    trechos = ppc(cambio_m, ipca_m, cpi, mins)

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
             sub="% do PIB, acumulado em 12 meses; superávit positivo",
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
        sub_tab = ("Início: véspera da posse; final: último dia no cargo ou último dado" if ind.get("diaria") else
                   "Início: mês anterior ao primeiro mês do ministro; final: último mês no cargo ou último dado")
        if ind["id"] == "ipca":
            colunas.extend([{"rot": "Acima da meta", "num": True}, {"rot": "Acima do intervalo", "num": True}])
            sub_tab += "; meses acima do centro da meta (SGS 13521) e acima do teto do intervalo do CMN, do total de meses"
        if ind["id"] in ("selic", "cambio"):
            colunas.append({"rot": "Média no período", "num": True})
            sub_tab += "; média: média simples dos dias úteis no cargo"
        if ind["id"] == "divida":
            colunas.append({"rot": "Variação média mensal", "num": True})
            sub_tab += "; variação média mensal: variação total dividida pelo número de meses"
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
            pintar_linha(l, ind["id"], mi["id"])
            linhas.append(l)
        tab = dict(id="ministros-" + ind["id"] + "-tabela", tipo="tabela",
                   titulo=ind["titulo"] + " por ministro", subtitulo=sub_tab,
                   fonte=ind["fonte"], colunas=colunas, linhas=linhas)
        secoes.append(dict(titulo=ind["sec"], texto="", graficos=[g, tab]))
        ind["linhas"] = linhas

    # câmbio pela PPC (bônus)
    ppc_series = [serie("Câmbio (PTAX)", cambio_m, 4, cor=BRANCO, rotulo=True)]
    for k, (mi, s) in enumerate(zip(mins, trechos)):
        ppc_series.append(serie("Câmbio pela PPC desde a posse", s, 4, ini=mi["base"], cor=AZUL,
                                legenda=(k == 0), ministro=mi["id"]))
    ppc_g = dict(id="ministros-cambio-ppc", titulo="Câmbio observado e câmbio pela PPC desde a posse",
                 subtitulo="R$ por US$, fim do mês; PPC: câmbio do mês anterior ao do ministro corrigido pelo IPCA sobre o CPI dos EUA; clique na foto para ver só o ministro",
                 unidade="brl", fonte="BCB (PTAX, SGS 1; IPCA, SGS 433), BLS (CPI-U, via FRED) e FtM",
                 ministros=fx, presidentes=pres_fx, apresentarDaqui=True, series=ppc_series)
    linhas_ppc = []
    for mi, s in zip(mins, trechos):
        fim_m = max(s, key=ordem)
        fim_c = max([m for m in cambio_m if m <= mi["ate"]], key=ordem)
        if fim_c != fim_m:
            fim_m = min(fim_m, fim_c, key=ordem)
        base = cambio_m[mi["base"]]
        lp = [{"t": mi["nome"], "forte": True},
              {"t": mi["pres"]},
              {"t": "%s (%s)" % (rs(base), mes_curto(mi["base"]))},
              {"t": "%s (%s)" % (rs(s[fim_m]), mes_curto(fim_m))},
              {"t": "%s (%s)" % (rs(cambio_m[fim_m]), mes_curto(fim_m))},
              {"t": sinal((cambio_m[fim_m] / s[fim_m] - 1) * 100, 1) + "%", "forte": True}]
        pintar_linha(lp, "cambio-ppc", mi["id"])
        linhas_ppc.append(lp)
    ppc_tab = dict(id="ministros-cambio-ppc-tabela", tipo="tabela",
                   titulo="Câmbio observado e câmbio pela PPC por ministro",
                   subtitulo="Desvio: câmbio observado no final sobre o câmbio pela PPC; positivo, real mais depreciado que a PPC indica",
                   fonte="BCB, BLS e FtM",
                   colunas=[{"rot": "Ministro"}, {"rot": "Presidente"}, {"rot": "Câmbio no início", "num": True},
                            {"rot": "Câmbio pela PPC no final", "num": True},
                            {"rot": "Câmbio observado no final", "num": True}, {"rot": "Desvio", "num": True}],
                   linhas=linhas_ppc)
    secoes.append(dict(titulo="Bônus: câmbio pela PPC", texto="", graficos=[ppc_g, ppc_tab]))

    # rating: três agências na mesma escala; deslocamento mínimo para as linhas
    # iguais não se esconderem (o valor mostrado é a nota, arredondada)
    desloc = {"sp": 0.08, "moodys": 0.0, "fitch": -0.08}
    cores = {"sp": AZUL, "moodys": VERMELHO, "fitch": VERDE}
    rat_series = []
    for aid in ("sp", "moodys", "fitch"):
        s = {m: v + desloc[aid] for m, v in rat[aid]["serie"].items()}
        rat_series.append(serie(rat[aid]["nome"], s, 2, cor=cores[aid], unidade="moodys" if aid == "moodys" else "nota-sp"))
    meses_r = [m for m in rat["sp"]["serie"] if m >= INICIO]
    rat_series.append(dict(nome="Grau de investimento", cor=CINZA, traco="pontilhado", largura=3,
                           buracoMax=400, dados=[[min(meses_r, key=ordem), 12], [max(meses_r, key=ordem), 12]]))
    rat_g = dict(id="ministros-rating", titulo="Rating soberano do Brasil",
                 subtitulo="Nota de longo prazo em moeda estrangeira; S&P e Fitch à esquerda, Moody's à direita",
                 unidade="nota-sp", eixoDireita="moodys", eixo={"min": 7, "max": 14, "passo": 1},
                 fonte="Moody's, S&P e Fitch (via Poder & Mercado) e FtM", ministros=fx, presidentes=pres_fx,
                 apresentarDaqui=True, series=rat_series)
    linhas_rat = []
    for mi in mins:
        lin = [{"t": mi["nome"], "forte": True}, {"t": mi["pres"]}]
        for aid in ("sp", "moodys", "fitch"):
            a, b, _ = nota_dia(rat[aid], mi)
            lin.append({"t": "%s → %s (%s)" % (nota(a, aid), nota(b, aid), degraus(a, b))})
        pintar_linha(lin, "rating", mi["id"])
        linhas_rat.append(lin)
    rat_tab = dict(id="ministros-rating-tabela", tipo="tabela", titulo="Rating soberano por ministro",
                   subtitulo="Nota na véspera da posse → nota no último dia no cargo; dados até %s"
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
        linhas.append([{"t": "Câmbio pela PPC desde a posse", "forte": True}, {"t": lp[2]["t"]}, {"t": lp[3]["t"]},
                       {"t": "desvio " + lp[5]["t"], "forte": True}])
        for aid in ("sp", "moodys", "fitch"):
            a, b, ate = nota_dia(rat[aid], mi)
            linhas.append([{"t": "Rating " + rat[aid]["nome"], "forte": True},
                           {"t": "%s (%s)" % (nota(a, aid), dia_curto(vespera(mi["posse"])))},
                           {"t": "%s (%s)" % (nota(b, aid), dia_curto(vespera(mi["saida"])) if mi["saida"] else mes_curto(ate))},
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
    secoes.append(dict(titulo="Tabela por ministro", texto="", graficos=por_min))

    doc = dict(assunto="Ministros da Fazenda", grupo="Análises Variadas",
               capaFtm=dict(titulo="Ministros da Fazenda desde Palocci",
                            data="%d/%s/%d" % (hoje.day, MESES[hoje.month - 1].capitalize(), hoje.year)),
               fonte="BCB, IBGE, BLS, Moody's, S&P, Fitch e FtM; fotos: Agência Brasil, Palácio do Planalto, FMI, "
                     "Ministério da Fazenda, Ministério da Indústria e Governo de SP (Wikimedia Commons)",
               referencia=ultimo, atualizado=hoje.isoformat(), formato="artigo", secoes=secoes)
    return doc, mins, INDS, rat, trechos, cambio_m


def main():
    doc, mins, inds, rat, trechos, cambio_m = montar()
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

#!/usr/bin/env python3
"""
A seção "O custo de vida" do assunto das midterms (dados/midterms-2026.json),
no fim de "Os motivos da virada". Não roda sozinho: o scripts/midterms.py chama
secoes(). Só biblioteca padrão; o que é baixado fica em dados/.cache-midterms/.

DE ONDE VÊM OS NÚMEROS

  FRED (fredgraph.csv, sem chave e SEM User-Agent: com qualquer UA ele trava)
    CPI e componentes, com ajuste sazonal (CUSR...) para a alta acumulada
    desde uma data, e sem ajuste (CUUR...) para a de 12 meses, que é a que o
    BLS publica:
      CPIAUCSL/CPIAUCNS  índice cheio       ...SAH1   moradia (shelter)
      ...SEHA   aluguel                     ...SEHC   aluguel imputado do dono
      ...SEHF01 energia elétrica            ...SAF11  alimentação em casa
      ...SETB01 gasolina                    ...SETA01 carros novos
      ...SETA02 carros usados
    MORTGAGE30US juro de 30 anos da Freddie Mac (PMMS), semanal; aqui, média do mês
    RIFLPBCIANM60NM / ...72NM  juro de carro novo em 60 e 72 meses, bancos
                 comerciais (Fed, G.19)
    UNRATE       taxa de desemprego (BLS); out/2025 não tem (paralisação do governo)
    DSPIC96      renda pessoal disponível real (BEA)
    PCE, PCEPI   consumo pessoal nominal e o deflator dele (BEA): o consumo real
                 é PCE / PCEPI, que é o PCEC96 desde 2007 e vai até 1959
    PSAVERT      taxa de poupança pessoal (BEA)
  BLS (API pública v1, sem chave): seguro de carro, CUSR0000SETE e
    CUUR0000SETE. O FRED não tem essa série.
  Fed de Atlanta, Home Ownership Affordability Monitor (HOAM), planilha
    nacional HOAM_US_Affordability_Index.xlsx: índice de acessibilidade (100 =
    a família de renda mediana paga a casa mediana com 30% da renda; entrada
    de 10%, 30 anos, com impostos, seguro e PMI), a parcela da renda que o
    custo anual come e a diferença entre a renda necessária e a mediana.
    "Change in Affordability" é a variação do índice, em pontos, contra o
    mesmo mês do ano anterior.
  Fed de Atlanta, Wage Growth Tracker, aba "Average Wage Quartile": mediana do
    crescimento do salário-hora em 12 meses de quem foi entrevistado duas
    vezes, em média móvel de 12 meses, por quartil do salário médio.

CONTAS

  Renda contra consumo (a ideia é de um gráfico do Charles Schwab): em cada
    mês, a variação em 12 meses da renda disponível real e a do consumo real;
    conta quantos meses seguidos a renda cresce menos. Regra estrita: empate ou
    renda maior zera a contagem. Com dados revisados a conta muda um pouco em
    relação à de quem fez antes (o Schwab, em jun/2026, tinha 24 meses).

  Salário real: o tracker menos a inflação de 12 meses do CPI (sem ajuste) na
    mesma média móvel de 12 meses do tracker.
"""
import csv
import io
import json
import re
import urllib.request
import zipfile
from datetime import date, timedelta

from midterms_motivos import CACHE, ATUALIZAR, rotulo_mes

CINZA = "#95A5A6"


def baixar_sem_ua(url, nome, dados=None):
    arq = CACHE / nome
    if ATUALIZAR or not arq.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, data=dados,
                                     headers={"Content-Type": "application/json"} if dados else {})
        arq.write_bytes(urllib.request.urlopen(req, timeout=90).read())
    return arq.read_bytes()


def fred(sid):
    txt = baixar_sem_ua("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + sid, "fred-%s.csv" % sid)
    out = {}
    for lin in list(csv.reader(io.StringIO(txt.decode("utf-8-sig"))))[1:]:
        if len(lin) == 2 and lin[1] not in (".", ""):
            out[lin[0]] = float(lin[1])
    return out


def mensal(d):
    """{AAAA-MM-DD: v} -> {AAAA-MM: média do mês}."""
    acc = {}
    for k, v in d.items():
        acc.setdefault(k[:7], []).append(v)
    return {k: sum(v) / len(v) for k, v in sorted(acc.items())}


def bls(sid):
    corpo = json.dumps({"seriesid": [sid], "startyear": "2017", "endyear": str(date.today().year)}).encode()
    d = json.loads(baixar_sem_ua("https://api.bls.gov/publicAPI/v1/timeseries/data/", "bls-%s.json" % sid, corpo))
    if d.get("status") != "REQUEST_SUCCEEDED":
        raise SystemExit("BLS %s: %s" % (sid, d.get("message")))
    return {"%s-%s" % (x["year"], x["period"][1:]): float(x["value"])
            for x in d["Results"]["series"][0]["data"]
            # "-" é mês sem coleta (out/2025, na paralisação do governo)
            if x["period"].startswith("M") and x["period"] != "M13" and x["value"] not in ("-", "")}


def atlanta():
    """{AAAA-MM: (1º quartil, 2º, 3º, 4º, geral)} da aba Average Wage Quartile."""
    z = zipfile.ZipFile(io.BytesIO(baixar_sem_ua(
        "https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/datafiles/chcs/"
        "wage-growth-tracker/wage-growth-data.xlsx", "atl-wgt.xlsx")))
    wb = z.read("xl/workbook.xml").decode()
    rels = z.read("xl/_rels/workbook.xml.rels").decode()
    rid = re.search(r'<sheet [^>]*name="Average Wage Quartile"[^>]*r:id="([^"]+)"', wb).group(1)
    alvo = re.search(r'<Relationship [^>]*Id="%s"[^>]*Target="([^"]+)"' % rid, rels) or \
        re.search(r'<Relationship [^>]*Target="([^"]+)"[^>]*Id="%s"' % rid, rels)
    x = z.read("xl/" + alvo.group(1).lstrip("/").replace("xl/", "")).decode()
    ss = [re.sub("<[^>]+>", "", s) for s in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode(), re.S)]
    out, cab = {}, None
    for lin in re.findall(r"<row [^>]*>(.*?)</row>", x, re.S):
        c = {}
        for ref, t, v in re.findall(r'<c r="([A-Z]+)\d+"([^>]*)>(?:<f>[^<]*</f>)?<v>([^<]*)</v>', lin):
            c[ref] = ss[int(v)] if 't="s"' in t else float(v)
        if c.get("B") == "Lowest quartile of wage distribution":
            cab = c
            assert c["E"].startswith("Highest") and c["F"] == "Overall", c
            continue
        # mês sem pesquisa vem como "." (out/2025, na paralisação do governo)
        if cab and isinstance(c.get("A"), float) and all(isinstance(c.get(k), float) for k in "BCDEF"):
            dia = date(1899, 12, 30) + timedelta(days=int(c["A"]))
            out["%d-%02d" % (dia.year, dia.month)] = tuple(c[k] for k in "BCDEF")
    return out


def var12(d):
    ks = sorted(d)
    return {k: (d[k] / d[a] - 1) * 100 for k in ks
            for a in ["%04d-%s" % (int(k[:4]) - 1, k[5:7])] if a in d}


def media_movel(d, n=12):
    ks = sorted(d)
    return {ks[i]: sum(d[k] for k in ks[i - n + 1:i + 1]) / n for i in range(n - 1, len(ks))}


def nf(v, casas=1):
    return ("%.*f" % (casas, v)).replace(".", ",")


# ---------- gráficos ----------
def grafico_salario():
    wgt = atlanta()
    cpi = media_movel(var12(mensal(fred("CPIAUCNS"))))
    # sem out/2025: nem o CPI nem a pesquisa de emprego foram a campo
    q1 = [[k, wgt[k][0]] for k in sorted(wgt)]
    q4 = [[k, wgt[k][3]] for k in sorted(wgt)]
    ks = [k for k in sorted(wgt) if k in cpi]
    inf = [[k, round(cpi[k], 2)] for k in ks]
    r1 = [[k, round(wgt[k][0] - cpi[k], 2)] for k in ks]
    r4 = [[k, round(wgt[k][3] - cpi[k], 2)] for k in ks]
    g = {
        "id": "midterms-salario-quartil",
        "titulo": "Crescimento do salário por quartil",
        "subtitulo": "Mediana da alta do salário-hora em 12 meses, em média móvel de 12 meses, por quartil do salário",
        "fonte": "Federal Reserve Bank of Atlanta (Wage Growth Tracker) e BLS",
        "unidade": "%", "periodoPadrao": "10", "buracoMax": 2,
        "variantes": [
            {"rot": "nominal, contra a inflação", "series": [
                {"nome": "25% que ganham menos", "cor": "#F2A541", "rotulo": True, "dados": q1},
                {"nome": "25% que ganham mais", "cor": "#1F7F68", "rotulo": True, "dados": q4},
                {"nome": "Inflação (CPI, mesma média de 12 meses)", "cor": "#FFFFFF", "largura": 3,
                 "traco": "pontilhado", "rotulo": True, "dados": inf}]},
            {"rot": "descontada a inflação", "eixo": {"zero": True}, "series": [
                {"nome": "25% que ganham menos", "cor": "#F2A541", "rotulo": True, "dados": r1},
                {"nome": "25% que ganham mais", "cor": "#1F7F68", "rotulo": True, "dados": r4}]},
        ],
    }
    return {"q1": q1, "q4": q4, "r1": r1, "r4": r4}, g


ITENS = [
    # (nome, série com ajuste, série sem ajuste)
    ("Índice cheio", "CPIAUCSL", "CPIAUCNS"),
    ("Moradia", "CUSR0000SAH1", "CUUR0000SAH1"),
    ("Aluguel", "CUSR0000SEHA", "CUUR0000SEHA"),
    ("Aluguel imputado do dono", "CUSR0000SEHC", "CUUR0000SEHC"),
    ("Energia elétrica", "CUSR0000SEHF01", "CUUR0000SEHF01"),
    ("Alimentação em casa", "CUSR0000SAF11", "CUUR0000SAF11"),
    ("Gasolina", "CUSR0000SETB01", "CUUR0000SETB01"),
    ("Seguro de carro", "bls:CUSR0000SETE", "bls:CUUR0000SETE"),
    ("Carros novos", "CUSR0000SETA01", "CUUR0000SETA01"),
    ("Carros usados", "CUSR0000SETA02", "CUUR0000SETA02"),
]


def serie_cpi(sid):
    return bls(sid[4:]) if sid.startswith("bls:") else mensal(fred(sid))


def grafico_itens():
    sa = {n: serie_cpi(a) for n, a, _ in ITENS}
    ns = {n: serie_cpi(b) for n, _, b in ITENS}
    ult = min(max(s) for s in sa.values())         # último mês com todos os itens

    def itens(f):
        lst = sorted(((n, f(n)) for n, _, _ in ITENS), key=lambda x: -x[1])
        return [[n, round(v, 1), CINZA if n == "Índice cheio" else "#E8A33D", n == "Índice cheio"] for n, v in lst]

    acum = lambda d0: (lambda n: (sa[n][ult] / sa[n][d0] - 1) * 100)  # noqa: E731
    ano_ant = "%04d-%s" % (int(ult[:4]) - 1, ult[5:])
    v12 = lambda n: (ns[n][ult] / ns[n][ano_ant] - 1) * 100  # noqa: E731
    vals = {"21": {n: acum("2021-01")(n) for n, _, _ in ITENS}, "25": {n: acum("2025-01")(n) for n, _, _ in ITENS},
            "12": {n: v12(n) for n, _, _ in ITENS}}
    g = {
        "id": "midterms-inflacao-itens",
        "tipo": "ranking", "unidade": "pct1", "sinal": True,
        "titulo": "Inflação dos itens que pesam no orçamento",
        "subtitulo": "Alta de preço de cada item do CPI até %s" % rotulo_mes(ult),
        "fonte": "BLS (CPI), via FRED",
        "variantes": [
            {"rot": "desde jan/2021 (posse de Biden)", "itens": itens(vals["21"].get)},
            {"rot": "desde jan/2025 (posse de Trump)", "itens": itens(vals["25"].get)},
            {"rot": "em 12 meses", "itens": itens(vals["12"].get)},
        ],
    }
    return ult, vals, g


def hoam():
    """{AAAA-MM: (índice, % da renda, renda mediana, renda necessária)} da planilha nacional."""
    z = zipfile.ZipFile(io.BytesIO(baixar_sem_ua(
        "https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/research-and-data/data/hoam/"
        "HOAM_US_Affordability_Index.xlsx", "atl-hoam.xlsx")))
    ss = [re.sub("<[^>]+>", "", s) for s in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode(), re.S)]
    x = z.read("xl/worksheets/sheet1.xml").decode()
    out, cab = {}, None
    for lin in re.findall(r"<row [^>]*>(.*?)</row>", x, re.S):
        c = {ref: (ss[int(v)] if 't="s"' in t else v)
             for ref, t, v in re.findall(r'<c r="([A-Z]+)\d+"([^>]*)>(?:<f>[^<]*</f>)?<v>([^<]*)</v>', lin)}
        if c.get("A") == "Month":
            cab = c
            assert c["B"].startswith("Qualifying vs Actual Income Difference") and c["E"] == "Affordability Index", c
            continue
        if cab and re.match(r"^\d{4}-\d\d$", c.get("A", "")):
            dif, pdif = float(c["B"]), float(c["C"])
            renda = dif / pdif
            out[c["A"]] = (float(c["E"]), float(c["D"]) * 100, renda, renda + dif)
    return out


def grafico_casa():
    h = hoam()
    g = {
        "id": "midterms-hoam",
        "titulo": "Índice de acessibilidade da casa própria",
        "subtitulo": "Fed de Atlanta: 100 = a família de renda mediana paga a casa mediana com 30% da renda; "
                     "abaixo de 100, não paga",
        "fonte": "Federal Reserve Bank of Atlanta, Home Ownership Affordability Monitor",
        "eixo": {"zero": False},
        "variantes": [
            {"rot": "índice", "unidade": "pts", "series": [
                {"nome": "Índice de acessibilidade", "cor": "#E8A33D", "rotulo": True,
                 "dados": [[k, round(v[0], 1)] for k, v in sorted(h.items())]}]},
            {"rot": "custo anual em % da renda mediana", "unidade": "pct1", "series": [
                {"nome": "Custo anual da casa mediana / renda mediana", "cor": "#E8A33D", "rotulo": True,
                 "dados": [[k, round(v[1], 1)] for k, v in sorted(h.items())]}]},
        ],
    }
    return h, mensal(fred("MORTGAGE30US")), g


def grafico_carro():
    a60, a72 = fred("RIFLPBCIANM60NM"), fred("RIFLPBCIANM72NM")
    g = {
        "id": "midterms-juro-carro",
        "titulo": "Juro do financiamento de carro novo",
        "subtitulo": "Taxa média dos bancos comerciais em 60 e 72 meses, em % ao ano",
        "fonte": "Federal Reserve (G.19), via FRED",
        "unidade": "%", "eixo": {"zero": False}, "buracoMax": 3,
        "series": [
            {"nome": "60 meses", "cor": "#4F81BD", "rotulo": True, "dados": [[k[:7], v] for k, v in sorted(a60.items())]},
            {"nome": "72 meses", "cor": "#C0504D", "rotulo": True, "dados": [[k[:7], v] for k, v in sorted(a72.items())]},
        ],
    }
    return a60, a72, g


# ---------- texto ----------
def grafico_trabalho():
    m = lambda d: {k[:7]: v for k, v in d.items()}  # noqa: E731
    u = m(fred("UNRATE"))
    desemprego = {
        "id": "midterms-desemprego",
        "titulo": "Taxa de desemprego",
        "subtitulo": "% da força de trabalho, com ajuste sazonal; out/2025 não foi apurado",
        "fonte": "BLS, via FRED",
        "unidade": "pct1", "eixo": {"zero": False}, "periodoPadrao": "10", "buracoMax": 2,
        "series": [{"nome": "Taxa de desemprego", "cor": "#E8A33D", "rotulo": True,
                    "dados": [[k, v] for k, v in sorted(u.items())]}],
    }
    renda = m(fred("DSPIC96"))
    pce, pi = m(fred("PCE")), m(fred("PCEPI"))
    cons = {k: pce[k] / pi[k] * 100 for k in pce if k in pi}
    yr, yc = var12(renda), var12(cons)
    seq, c = {}, 0
    for k in sorted(yr):
        if k in yc:
            c = c + 1 if yr[k] < yc[k] else 0
            seq[k] = c
    g = {
        "id": "midterms-renda-consumo",
        "titulo": "Meses seguidos com a renda real crescendo menos que o consumo real",
        "subtitulo": "Renda pessoal disponível real contra consumo pessoal real, variação em 12 meses; a contagem zera "
                     "quando a renda cresce mais",
        "fonte": "BEA, via FRED; conta do FtM, a partir de um gráfico do Charles Schwab",
        "unidade": "n", "eixo": {"zero": True},
        "series": [{"nome": "Meses seguidos", "cor": "#E8A33D", "rotulo": True,
                    "dados": [[k, v] for k, v in sorted(seq.items())]}],
    }
    return u, seq, yr, yc, m(fred("PSAVERT")), desemprego, g


def secoes():
    sal, g_sal = grafico_salario()
    ult, vals, g_itens = grafico_itens()
    casa, m30, g_casa = grafico_casa()
    a60, a72, g_carro = grafico_carro()
    u, seq, yr, yc, poup, g_desemp, g_rc = grafico_trabalho()
    print("economia: CPI até %s; salário até %s; hipoteca até %s; casa até %s; carro até %s"
          % (ult, sal["q1"][-1][0], max(m30), max(casa), max(a60)[:7]))

    # ---- salário
    d1, d4 = dict(sal["q1"]), dict(sal["q4"])
    r1, r4 = dict(sal["r1"]), dict(sal["r4"])
    ks = sorted(d1)
    k_ult = ks[-1]
    # último mês em que os de baixo ainda subiam mais que os de cima
    virada = max(k for k in ks if d1[k] > d4[k])
    # e desde quando essa dianteira vinha sem interrupção
    ini = virada
    while ks.index(ini) > 0 and d1[ks[ks.index(ini) - 1]] > d4[ks[ks.index(ini) - 1]]:
        ini = ks[ks.index(ini) - 1]
    texto_sal = (
        "**O salário de quem ganha menos perdeu a dianteira.** De %s a %s, o salário dos 25%% que ganham menos "
        "subiu mais rápido que o dos 25%% que ganham mais, mês a mês. Em %s, pelo Wage Growth "
        "Tracker do Fed de Atlanta, os de baixo tinham alta de %s%% em 12 meses e os de cima, de %s%%. "
        "Descontada a inflação, o ganho real era de %s ponto para os de baixo e de %s para os de cima, contra "
        "%s e %s em junho de 2024."
    ) % (rotulo_mes(ini), rotulo_mes(virada), rotulo_mes(k_ult), nf(d1[k_ult]), nf(d4[k_ult]),
         nf(r1[k_ult]), nf(r4[k_ult]), nf(r1["2024-06"]), nf(r4["2024-06"]))

    # ---- desemprego
    ku = max(u)
    piso = min((x, k) for k, x in u.items() if k >= "2021")
    antes_piso = max(k for k, x in u.items() if k < "2020" and x <= piso[0])
    teto = max((x, k) for k, x in u.items() if k >= "2025")
    texto_desemp = (
        "**O desemprego subiu sem disparar.** A taxa estava em %s%% em %s, contra %s%% em janeiro de 2025, "
        "na posse de Trump, e %s%% em %s, a menor desde %s. O ponto mais alto desde a posse foi %s%%, em %s."
    ) % (nf(u[ku]), rotulo_mes(ku), nf(u["2025-01"]), nf(piso[0]), rotulo_mes(piso[1]), antes_piso[:4],
         nf(teto[0]), rotulo_mes(teto[1]))

    # ---- renda contra consumo
    ks = sorted(seq)
    k_rc = ks[-1]
    fins = [(k, seq[k]) for i, k in enumerate(ks) if seq[k] and (i + 1 == len(ks) or seq[ks[i + 1]] == 0)]
    recorde = max(fins, key=lambda x: x[1])
    # a sequência anterior à atual, e o mês que a interrompeu
    ant = [f for f in fins if f[0] < k_rc][-1]
    corte = ks[ks.index(ant[0]) + 1]
    junto = ant[1] + 1 + seq[k_rc] if seq[ks[ks.index(corte) + 1]] == 1 and seq[k_rc] > 0 else None
    kp = max(poup)
    baixa = max(k for k, x in poup.items() if k < kp[:4] + "-01" and x <= poup[kp])
    texto_rc = (
        "**O consumo cresce mais que a renda.** A renda pessoal disponível real subiu %s%% em 12 meses até %s, "
        "e o consumo real, %s%%. A renda cresce menos que o consumo desde %s, com uma exceção: em %s, a renda "
        "subiu %s%% e o consumo, %s%%, praticamente empatados. Pela conta estrita, que zera a contagem quando a "
        "renda cresce mais, foram %d meses seguidos até %s e são %d desde então%s. O recorde é de %d meses, "
        "até %s.\n\n"
        "Quando o consumo sobe mais que a renda, a diferença sai da poupança ou do crédito: a taxa de poupança "
        "caiu de %s%% em %s para %s%% em %s, a menor desde %s."
    ) % (nf(yr[k_rc]), rotulo_mes(k_rc), nf(yc[k_rc]),
         rotulo_mes(ks[ks.index(ant[0]) - ant[1] + 1]), rotulo_mes(corte), nf(yr[corte], 2), nf(yc[corte], 2),
         ant[1], rotulo_mes(ant[0]), seq[k_rc],
         ("; sem esse mês, seriam %d meses, mais que qualquer sequência da série" % junto)
         if junto and junto > recorde[1] else "",
         recorde[1], rotulo_mes(recorde[0]),
         nf(poup[ks[ks.index(ant[0]) - ant[1] + 1]]), rotulo_mes(ks[ks.index(ant[0]) - ant[1] + 1]),
         nf(poup[kp]), rotulo_mes(kp), rotulo_mes(baixa))

    # ---- itens
    v = vals
    acima = [n for n, x in sorted(v["21"].items(), key=lambda t: -t[1]) if n != "Índice cheio" and x > v["21"]["Índice cheio"]]
    caiu25 = [n for n, x in sorted(v["25"].items(), key=lambda t: t[1]) if x < 0]
    texto_itens = (
        "**Desde 2021, o que mais subiu foi gasolina, seguro de carro e energia elétrica.** Da posse de Biden, "
        "em janeiro de 2021, até %s, o índice cheio do CPI subiu %s%%; acima dele ficaram %s. Desde a posse de "
        "Trump, o índice subiu %s%% e a gasolina, %s%%; em 12 meses, a gasolina sobe %s%%. %s"
    ) % (rotulo_mes(ult), nf(v["21"]["Índice cheio"]),
         lista_pt(["%s (%s%%)" % (n.lower(), nf(v["21"][n])) for n in acima]),
         nf(v["25"]["Índice cheio"]), nf(v["25"]["Gasolina"]), nf(v["12"]["Gasolina"]),
         ("Em sentido contrário, %s ficaram mais baratos que em janeiro de 2025." % lista_pt([n.lower() for n in caiu25]))
         if caiu25 else "")

    # ---- casa
    kc = max(casa)
    idx, parte, renda, nec = casa[kc]
    abaixo = [k for k in sorted(casa) if all(casa[x][0] < 100 for x in sorted(casa) if x >= k)][0]
    piso = min(casa.items(), key=lambda t: t[1][0])
    alta = max(((k, v) for k, v in casa.items() if k >= "2025"), key=lambda t: t[1][0])
    k30 = max(m30)
    texto_casa = (
        "**A casa própria ficou mais longe.** O índice de acessibilidade do Fed de Atlanta vale 100 quando a "
        "família de renda mediana consegue pagar a casa mediana gastando 30%% da renda, com 10%% de entrada, "
        "impostos e seguro. Em %s, estava em %s: o custo anual da casa mediana comia %s%% da renda mediana, de "
        "US$ %s mil, e a renda necessária era de US$ %s mil, %s%% maior. Em dezembro de 2020, o índice estava em "
        "%s, e o custo comia %s%% da renda.\n\n"
        "O índice está abaixo de 100 desde %s e chegou ao menor nível da série, que começa em 2005, em %s: "
        "%s, quando o juro de 30 anos da Freddie Mac estava em %s%%. Com o juro caindo a %s%% em %s, subiu a %s; desde então voltou a cair, "
        "e o juro estava em %s%% em %s."
    ) % (rotulo_mes(kc), nf(idx), nf(parte), nf(renda / 1000), nf(nec / 1000), nf((nec / renda - 1) * 100),
         nf(casa["2020-12"][0]), nf(casa["2020-12"][1]),
         rotulo_mes(abaixo), rotulo_mes(piso[0]), nf(piso[1][0]), nf(m30[piso[0]], 2),
         nf(m30[alta[0]], 2), rotulo_mes(alta[0]), nf(alta[1][0]), nf(m30[k30], 2), rotulo_mes(k30))

    # ---- carro
    k72 = max(a72)
    m72_21 = media([x for k, x in a72.items() if k[:4] == "2021"])
    texto_carro = (
        "**No carro, o que pesa é o crédito.** Desde janeiro de 2021, carros novos subiram %s%% e usados, "
        "%s%%, menos que o índice cheio, mas o seguro subiu %s%%. E o financiamento de carro novo em 72 meses "
        "nos bancos estava em %s%% ao ano em %s, contra %s%% na média de 2021."
    ) % (nf(v["21"]["Carros novos"]), nf(v["21"]["Carros usados"]), nf(v["21"]["Seguro de carro"]),
         nf(a72[k72], 2), rotulo_mes(k72[:7]), nf(m72_21, 2))

    return [
        {"titulo": "O custo de vida", "texto": texto_sal, "graficos": [g_sal]},
        {"titulo": "", "texto": texto_desemp, "graficos": [g_desemp]},
        {"titulo": "", "texto": texto_rc, "graficos": [g_rc]},
        {"titulo": "", "texto": texto_itens, "graficos": [g_itens]},
        {"titulo": "", "texto": texto_casa, "graficos": [g_casa]},
        {"titulo": "", "texto": texto_carro, "graficos": [g_carro]},
    ]


def media(xs):
    return sum(xs) / len(xs)


def lista_pt(xs):
    return (", ".join(xs[:-1]) + " e " + xs[-1]) if len(xs) > 1 else xs[0]

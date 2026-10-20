#!/usr/bin/env python3
"""
Monta dados/petroleo.json — petróleo, derivados e a pauta do comércio exterior
do Brasil, um assunto do índice.

Uso:
    ~/.venvs/dados-economicos/bin/python scripts/petroleo.py

Precisa de openpyxl só para os dois gráficos de fornecimento, que leem as
planilhas de oferta de planilhas/. O resto é biblioteca padrão. NÃO entra na
Action: rodar à mão quando o Comex Stat publicar o mês (começo do mês
seguinte).

AS FONTES

  - **Comex Stat (MDIC)**, os arquivos anuais por NCM, em US$ FOB:
        https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/EXP_AAAA.csv
        https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/IMP_AAAA.csv
    Começam em 1997. A API do Comex Stat (api-comexstat.mdic.gov.br) dá o
    mesmo dado agregado, mas em outubro de 2026 respondia 429 já na primeira
    chamada; os arquivos não têm limite.
  - **SGS do Banco Central**: IC-Br em dólar, total (29042) e energia
    (29039), dez/2005 = 100.
  - **Planilhas de oferta** (planilhas/oferta-diesel.xlsx e
    oferta-gasolina.xlsx): o perfil do fornecimento, Petrobras × importadores.

OS RECORTES (escolhidos por ele em 20/10/2026)

  - Petróleo bruto = SH4 2709. Soja = SH4 1201, só o grão (farelo e óleo
    ficam em "outros"). Derivados de petróleo = SH4 2710 (diesel, gasolina,
    QAV, óleo combustível, nafta, lubrificantes); GLP e coque ficam fora.
  - Importação em US$ FOB, como a exportação, para as duas pontas serem
    comparáveis.
  - Acumulado em 12 meses = soma móvel dos 12 meses até o mês. Variação anual
    = esse acumulado contra o do mesmo mês do ano anterior.
  - Países: os que mais pesaram nos últimos 10 anos ficam em coluna; o resto
    vai para "Outros".

AS ARMADILHAS DO DOWNLOAD

  - O certificado de balanca.economia.gov.br vem com a cadeia incompleta (o
    curl e o Python recusam). Como é dado público e só leitura, o download
    pula a verificação — só para esse host.
  - A conexão cai no meio sem dar erro: em 20/10/2026 o EXP_2026.csv veio com
    68 dos 84 MB, cortado no meio de uma linha. Por isso o download confere o
    tamanho anunciado e retoma com Range até fechar.

O CACHE

Os CSV anuais têm de 20 a 140 MB cada. O script lê cada um uma vez, guarda só
o agregado mensal em dados/.cache-comex/ (KB) e apaga o CSV. Na rodada
seguinte ele pergunta ao servidor a data de cada arquivo (HEAD) e só baixa de
novo o ano que mudou — na prática o ano corrente, e o anterior quando o MDIC
revisa.
"""
import csv
import datetime
import io
import json
import os
import ssl
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import petroleo_extra as pe                                  # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAIDA = os.path.join(RAIZ, "dados", "petroleo.json")
CACHE = os.path.join(RAIZ, "dados", ".cache-comex")
BRUTO = os.path.join(CACHE, "bruto")

BASE_COMEX = "https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/"
URL_PAISES = "https://balanca.economia.gov.br/balanca/bd/tabelas/PAIS.csv"
URL_NCM = "https://balanca.economia.gov.br/balanca/bd/tabelas/NCM.csv"

# Barris por tonelada: o Comex Stat dá o peso, e o preço se lê por barril.
# As densidades são as da ANP: 0,84 t/m³ no diesel e 0,74 na gasolina (as do
# Relatório de Desembaraços) e 0,85 no petróleo importado, que é a densidade
# implícita entre o peso do Comex e o volume da ANP em 2025 (no exportado,
# mais pesado, ela dá 0,88). 1 m³ = 6,28981 barris.
BBL_POR_T = {"Petróleo bruto": 6.28981 / 0.85, "Diesel": 6.28981 / 0.84, "Gasolina": 6.28981 / 0.74}
SSL_COMEX = ssl._create_unverified_context()          # só para o host do MDIC
UA = {"User-Agent": "Mozilla/5.0 (ftm-analises)"}

ANO0 = 1997
BRUTO_SH4, SOJA_SH4, DERIV_SH4 = "2709", "1201", "2710"
SH4 = (BRUTO_SH4, SOJA_SH4, DERIV_SH4)
N_PAISES = 7
INICIO_DESTINOS = "2002-01"     # o 12 meses começa em dez/2002

ICBR_USD, ICBR_ENERGIA_USD = 29042, 29039

AZUL, VERMELHO, VERDE, ROXO, CIANO, LARANJA = "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6", "#F79646"
AZUL_ESCURO, AMARELO, BRANCO, CINZA, AREIA = "#1F497D", "#FFFF00", "#FFFFFF", "#95A5A6", "#D9B382"
CORES_PAISES = [AZUL, VERMELHO, VERDE, ROXO, CIANO, LARANJA, AREIA, AZUL_ESCURO]

FONTE_COMEX = "Comex Stat (MDIC) e FtM"


# --------------------------------------------------------------------------
# download
# --------------------------------------------------------------------------

def cabecalho(url):
    req = urllib.request.Request(url, method="HEAD", headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=SSL_COMEX) as r:
        return int(r.headers["Content-Length"]), r.headers.get("Last-Modified", "")


def baixar_inteiro(url, destino, tamanho, tentativas=8):
    """Baixa retomando com Range até o arquivo ter o tamanho anunciado."""
    for i in range(tentativas):
        feito = os.path.getsize(destino) if os.path.exists(destino) else 0
        if feito == tamanho:
            return
        if feito > tamanho:
            os.remove(destino)
            feito = 0
        h = dict(UA)
        if feito:
            h["Range"] = "bytes=%d-" % feito
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=300, context=SSL_COMEX) as r, \
                    open(destino, "ab" if feito else "wb") as f:
                while True:
                    bloco = r.read(1 << 20)
                    if not bloco:
                        break
                    f.write(bloco)
        except Exception as e:                       # noqa: BLE001
            print("    queda em %s (%s), retomando…" % (os.path.basename(destino), e))
            time.sleep(2 * (i + 1))
    if os.path.getsize(destino) != tamanho:
        raise RuntimeError("%s veio com %d de %d bytes" % (destino, os.path.getsize(destino), tamanho))


VERSAO_CACHE = 2       # sobe quando muda o que o agregado guarda


def agregar(caminho, fluxo):
    """O CSV anual em {mês: {"total": US$, "ncm": {ncm: [US$, kg]},
    "paises": {sh4: {país: [US$, kg]}}}}.

    Guarda o NCM inteiro (e o peso) de todo o capítulo 27 e da soja, para dar
    preço implícito e volume por produto, e o país do petróleo bruto e dos
    derivados nas duas direções. O disco não comporta guardar os CSV."""
    fora = {}
    with open(caminho, encoding="latin-1", newline="") as f:
        for l in csv.DictReader(f, delimiter=";"):
            mes = "%s-%s" % (l["CO_ANO"], l["CO_MES"].zfill(2))
            m = fora.setdefault(mes, {"total": 0.0, "ncm": {}, "paises": {}})
            fob = float(l["VL_FOB"])
            m["total"] += fob
            ncm = l["CO_NCM"]
            if ncm[:2] == "27" or ncm[:4] == SOJA_SH4:
                kg = float(l["KG_LIQUIDO"] or 0)
                x = m["ncm"].setdefault(ncm, [0.0, 0.0])
                x[0] += fob
                x[1] += kg
                if ncm[:4] in (BRUTO_SH4, DERIV_SH4):
                    p = m["paises"].setdefault(ncm[:4], {}).setdefault(l["CO_PAIS"], [0.0, 0.0])
                    p[0] += fob
                    p[1] += kg
    for m in fora.values():                    # a soma por SH4 que o resto usa
        m["sh4"] = {}
        for ncm, (fob, _) in m["ncm"].items():
            if ncm[:4] in SH4:
                m["sh4"][ncm[:4]] = m["sh4"].get(ncm[:4], 0.0) + fob
    return fora


def ano_agregado(fluxo, ano):
    url = BASE_COMEX + "%s_%d.csv" % (fluxo, ano)
    arq = os.path.join(CACHE, "%s_%d.json" % (fluxo, ano))
    tamanho, data = cabecalho(url)
    if os.path.exists(arq):
        with open(arq, encoding="utf-8") as f:
            guardado = json.load(f)
        if (guardado.get("last_modified") == data and guardado.get("tamanho") == tamanho
                and guardado.get("versao") == VERSAO_CACHE):
            return guardado["meses"]
    print("  baixando %s_%d (%.0f MB)…" % (fluxo, ano, tamanho / 1e6))
    os.makedirs(BRUTO, exist_ok=True)
    bruto = os.path.join(BRUTO, "%s_%d.csv" % (fluxo, ano))
    baixar_inteiro(url, bruto, tamanho)
    meses = agregar(bruto, fluxo)
    with open(arq, "w", encoding="utf-8") as f:
        json.dump(dict(versao=VERSAO_CACHE, last_modified=data, tamanho=tamanho, meses=meses), f)
    os.remove(bruto)
    return meses


def comex(fluxo):
    meses = {}
    for ano in range(ANO0, datetime.date.today().year + 1):
        try:
            meses.update(ano_agregado(fluxo, ano))
        except urllib.error.HTTPError as e:
            if e.code == 404 and ano == datetime.date.today().year:
                continue                              # o ano novo ainda não saiu
            raise
    return meses


def nomes_paises():
    req = urllib.request.Request(URL_PAISES, headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=SSL_COMEX) as r:
        txt = r.read().decode("latin-1")
    return {l["CO_PAIS"]: l["NO_PAIS"] for l in csv.DictReader(io.StringIO(txt), delimiter=";")}


def classes_ncm():
    """{ncm: "Diesel" | "Gasolina"} pelo nome na tabela oficial. Pelo nome, e
    não pelo código, porque a NCM do capítulo 27 mudou em 2002 e em 2012: o
    diesel é 27100041 até 2001 e 27101921 depois; a gasolina é 27101159 até
    2011 e 27101259 depois."""
    req = urllib.request.Request(URL_NCM, headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=SSL_COMEX) as r:
        txt = r.read().decode("latin-1")
    fora = {}
    for l in csv.DictReader(io.StringIO(txt), delimiter=";"):
        nome = l["NO_NCM_POR"].strip().lower()
        if not l["CO_NCM"].startswith("2710"):
            continue
        if nome.startswith("gasóleo"):
            fora[l["CO_NCM"]] = "Diesel"
        elif "gasolina" in nome and not nome.startswith(("gasolina de avia", "gasolinas de avia", "gasolinas para avia")):
            fora[l["CO_NCM"]] = "Gasolina"
    return fora


def sgs(codigo):
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.%d/dados?formato=json" % codigo
    for i in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ftm-analises)",
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                dados = json.loads(r.read().decode("utf-8"))
            if isinstance(dados, list) and dados:
                return {"%s-%s" % (d["data"][6:10], d["data"][3:5]): float(d["valor"]) for d in dados}
        except Exception:                             # noqa: BLE001
            pass
        time.sleep(1.5 * 2 ** i)
    raise RuntimeError("SGS %d não respondeu" % codigo)


# --------------------------------------------------------------------------
# contas
# --------------------------------------------------------------------------

def num(mes):
    a, m = mes.split("-")
    return int(a) * 12 + int(m) - 1


def acumulado_12(mensal):
    ms = sorted(mensal)
    fora = {}
    for i in range(11, len(ms)):
        janela = ms[i - 11:i + 1]
        if num(janela[-1]) - num(janela[0]) == 11:
            fora[ms[i]] = sum(mensal[m] for m in janela)
    return fora


def variacao_anual(acc, base_minima=1e9):
    """Só com o acumulado do ano anterior acima de US$ 1 bi: em 1999–2000 o
    Brasil quase não exportava petróleo, e a variação sobre uma base perto de
    zero dava milhões por cento."""
    fora = {}
    for m, v in acc.items():
        a, mm = m.split("-")
        ant = "%04d-%s" % (int(a) - 1, mm)
        if ant in acc and acc[ant] >= base_minima:
            fora[m] = (v / acc[ant] - 1) * 100
    return fora


def pauta(meses, partes):
    """{nome: {mês: US$}} para cada SH4 pedido e "Outros" = total − eles."""
    fora = {nome: {} for nome, _ in partes}
    fora["Outros"] = {}
    for mes, m in meses.items():
        resto = m["total"]
        for nome, sh4 in partes:
            v = m["sh4"].get(sh4, 0.0)
            fora[nome][mes] = v
            resto -= v
        fora["Outros"][mes] = resto
    return fora


def por_pais(meses, sh4, nomes, ref):
    """Os N_PAISES maiores dos últimos 10 anos em coluna; o resto em "Outros"."""
    peso = {}
    corte = "%04d-%s" % (int(ref[:4]) - 10, ref[5:])
    for mes, m in meses.items():
        if mes > corte:
            for p, (v, _) in m["paises"].get(sh4, {}).items():
                peso[p] = peso.get(p, 0.0) + v
    maiores = [p for p, _ in sorted(peso.items(), key=lambda kv: -kv[1])[:N_PAISES]]
    fora = {p: {} for p in maiores}
    fora["Outros"] = {}
    for mes, m in meses.items():
        d = m["paises"].get(sh4, {})
        for p in maiores:
            fora[p][mes] = d.get(p, [0.0])[0]
        fora["Outros"][mes] = sum(v[0] for p, v in d.items() if p not in maiores)
    return [(nomes.get(p, p) if p != "Outros" else "Outros", fora[p]) for p in maiores + ["Outros"]]


def confere_soma(nome, partes, total, folga=1.0):
    """As partes somam o total, mês a mês (US$)."""
    pior = max(abs(sum(p.get(m, 0.0) for p in partes) - t) for m, t in total.items())
    print("  %s: as partes somam o total, diferença máxima US$ %.2f" % (nome, pior))
    if pior > folga:
        raise RuntimeError("%s não fecha (US$ %.0f)" % (nome, pior))


# --------------------------------------------------------------------------
# montagem
# --------------------------------------------------------------------------

def serie(nome, cor, dados, casas=2, **extra):
    return dict(nome=nome, cor=cor, dados=[[m, round(v, casas)] for m, v in sorted(dados.items())], **extra)


def bi(d):
    return {m: v / 1e9 for m, v in d.items()}


def pct_do_total(partes):
    tot = {}
    for _, d in partes:
        for m, v in d.items():
            tot[m] = tot.get(m, 0.0) + v
    return [(n, {m: v / tot[m] * 100 for m, v in d.items() if tot.get(m)}) for n, d in partes]


def barras_12m(partes, cores, como_pct=False):
    acc = [(n, acumulado_12(d)) for n, d in partes]
    acc = pct_do_total(acc) if como_pct else [(n, bi(d)) for n, d in acc]
    return [serie(n, c, d, 2, tipo="barra") for (n, d), c in zip(acc, cores)]


def graficos_pauta(exp, imp):
    pexp = pauta(exp, [("Petróleo bruto", BRUTO_SH4), ("Soja em grão", SOJA_SH4)])
    pimp = pauta(imp, [("Derivados de petróleo", DERIV_SH4), ("Petróleo bruto", BRUTO_SH4)])
    e = [(n, pexp[n]) for n in ("Petróleo bruto", "Soja em grão", "Outros")]
    i = [(n, pimp[n]) for n in ("Derivados de petróleo", "Petróleo bruto", "Outros")]
    cor_e, cor_i = [AZUL_ESCURO, VERDE, CINZA], [LARANJA, AZUL_ESCURO, CINZA]
    sub_bi = "US$ bilhões FOB, acumulado em 12 meses"
    sub_pct = "% do total exportado, acumulado em 12 meses"
    return [
        dict(titulo="Pauta de exportação", graficos=[
            dict(id="exportacao-pauta", titulo="Exportações do Brasil por produto",
                 subtitulo=sub_bi, unidade="usd-bi", barra=1, series=barras_12m(e, cor_e)),
            dict(id="exportacao-pauta-pct", titulo="Exportações do Brasil por produto",
                 subtitulo=sub_pct, unidade="%", barra=1, eixo=dict(max=100),
                 series=barras_12m(e, cor_e, True)),
        ]),
        dict(titulo="Pauta de importação", graficos=[
            dict(id="importacao-pauta", titulo="Importações do Brasil por produto",
                 subtitulo=sub_bi, unidade="usd-bi", barra=1, series=barras_12m(i, cor_i)),
            dict(id="importacao-pauta-pct", titulo="Importações do Brasil por produto",
                 subtitulo="% do total importado, acumulado em 12 meses", unidade="%", barra=1,
                 eixo=dict(max=100), series=barras_12m(i, cor_i, True)),
        ]),
    ], pexp, pimp


def grafico_saldo(exp, imp, pexp, pimp):
    """Saldo da balança comercial em 12 meses: o do petróleo bruto (exportado
    − importado, SH4 2709) e o de todo o resto, que somados dão o total."""
    total = {m: exp[m]["total"] - imp[m]["total"] for m in exp if m in imp}
    bruto = {m: pexp["Petróleo bruto"][m] - pimp["Petróleo bruto"][m] for m in total}
    resto = {m: total[m] - bruto[m] for m in total}
    t12, b12, r12 = (bi(acumulado_12(d)) for d in (total, bruto, resto))
    return dict(titulo="Saldo comercial", graficos=[
        dict(id="saldo-comercial-petroleo", titulo="Saldo da balança comercial: petróleo bruto e o resto",
             subtitulo="US$ bilhões FOB, acumulado em 12 meses; petróleo bruto = exportado − importado",
             unidade="usd-bi", barra=1,
             series=[serie("Petróleo bruto", AZUL_ESCURO, b12, tipo="barra", rotulo=True),
                     serie("Outros produtos", CINZA, r12, tipo="barra", rotulo=True),
                     serie("Saldo total", BRANCO, t12, rotulo=True)]),
    ])


def graficos_petroleo_derivados(pexp, pimp):
    exp12 = acumulado_12(pexp["Petróleo bruto"])
    imp12 = acumulado_12(pimp["Derivados de petróleo"])
    return dict(titulo="Petróleo exportado × derivados importados", graficos=[
        dict(id="petroleo-derivados-12m", titulo="Exportação de petróleo e importação de derivados",
             subtitulo="US$ bilhões FOB, acumulado em 12 meses", unidade="usd-bi",
             series=[serie("Exportação de petróleo bruto", AZUL_ESCURO, bi(exp12), rotulo=True),
                     serie("Importação de derivados", LARANJA, bi(imp12), rotulo=True)]),
        dict(id="petroleo-derivados-var", titulo="Exportação de petróleo e importação de derivados",
             subtitulo="Variação % do acumulado em 12 meses sobre o mesmo período do ano anterior",
             unidade="%",
             series=[serie("Exportação de petróleo bruto", AZUL_ESCURO, variacao_anual(exp12), rotulo=True),
                     serie("Importação de derivados", LARANJA, variacao_anual(imp12), rotulo=True)]),
    ])


def graficos_paises(exp, imp, nomes, ref):
    # o petróleo só passa a ser exportado de fato em 2001: antes disso a
    # divisão por país é de uma base quase nula e não se lê
    destinos = [(n, {m: v for m, v in d.items() if m >= INICIO_DESTINOS})
                for n, d in por_pais(exp, BRUTO_SH4, nomes, ref)]
    origens = por_pais(imp, DERIV_SH4, nomes, ref)
    confere_soma("destinos do petróleo", [d for _, d in destinos],
                 {m: x["sh4"].get(BRUTO_SH4, 0.0) for m, x in exp.items() if m >= INICIO_DESTINOS})
    confere_soma("origens dos derivados", [d for _, d in origens],
                 {m: x["sh4"].get(DERIV_SH4, 0.0) for m, x in imp.items()})
    cores = CORES_PAISES[:N_PAISES] + [CINZA]
    return dict(titulo="Destinos e origens", graficos=[
        dict(id="petroleo-destinos", titulo="Para onde vai o petróleo exportado",
             subtitulo="US$ bilhões FOB, acumulado em 12 meses", unidade="usd-bi", barra=1,
             series=barras_12m(destinos, cores)),
        dict(id="petroleo-destinos-pct", titulo="Para onde vai o petróleo exportado",
             subtitulo="% do petróleo bruto exportado, acumulado em 12 meses", unidade="%", barra=1,
             eixo=dict(max=100), series=barras_12m(destinos, cores, True)),
        dict(id="derivados-origens", titulo="De onde vêm os derivados importados",
             subtitulo="US$ bilhões FOB, acumulado em 12 meses", unidade="usd-bi", barra=1,
             series=barras_12m(origens, cores)),
        dict(id="derivados-origens-pct", titulo="De onde vêm os derivados importados",
             subtitulo="% dos derivados importados, acumulado em 12 meses", unidade="%", barra=1,
             eixo=dict(max=100), series=barras_12m(origens, cores, True)),
    ])


def graficos_preco_volume(imp, classes, brent):
    """Preço implícito (US$ FOB ÷ barris) e volume (mil barris por dia) do
    que o Brasil importa: petróleo bruto, diesel e gasolina."""
    import calendar
    prod = {"Petróleo bruto": {}, "Diesel": {}, "Gasolina": {}}
    for mes, m in imp.items():
        for ncm, (fob, kg) in m["ncm"].items():
            k = "Petróleo bruto" if ncm[:4] == BRUTO_SH4 else classes.get(ncm)
            if k:
                a = prod[k].setdefault(mes, [0.0, 0.0])
                a[0] += fob
                a[1] += kg
    preco, volume = {}, {}
    for k, d in prod.items():
        bbl = {m: kg / 1000 * BBL_POR_T[k] for m, (_, kg) in d.items() if kg}
        # mês com menos de 20 mil barris importados dá preço de amostra
        preco[k] = {m: d[m][0] / b for m, b in bbl.items() if b > 20000}
        volume[k] = {m: b / calendar.monthrange(int(m[:4]), int(m[5:]))[1] / 1000 for m, b in bbl.items()}
    def media12(d):
        ms = sorted(d)
        return {ms[i]: sum(d[x] for x in ms[i - 11:i + 1]) / 12 for i in range(11, len(ms))
                if num(ms[i]) - num(ms[i - 11]) == 11}
    cores = {"Petróleo bruto": VERDE, "Diesel": VERMELHO, "Gasolina": AZUL}
    inicio = "2002-01"
    corta = lambda d: {m: v for m, v in d.items() if m >= inicio}          # noqa: E731
    sp = [serie(k + " importado" if k == "Petróleo bruto" else k + " importada" if k == "Gasolina"
                else k + " importado", cores[k], corta(preco[k]), rotulo=True) for k in prod]
    sp.append(serie("Brent", CINZA, corta(brent), traco="pontilhado", largura=4, rotulo=True))
    sv = lambda f: [serie(s["nome"], s["cor"], corta(f(volume[k])), 1, rotulo=True)    # noqa: E731
                    for s, k in zip(sp, prod)]
    return dict(titulo="Preço e volume do que o Brasil importa", graficos=[
        dict(id="importados-preco", titulo="Preço implícito do petróleo e dos derivados importados",
             subtitulo="US$ FOB por barril, mensal; valor ÷ volume do Comex Stat, contra o Brent",
             unidade="usd-bbl", series=sp, fonte="Comex Stat (MDIC), FRED e FtM"),
        dict(id="importados-volume", titulo="Volume de petróleo e derivados importados",
             subtitulo="Mil barris por dia", unidade="kbd",
             variantes=[dict(rot="Média de 12 meses", unidade="kbd", series=sv(media12)),
                        dict(rot="Mensal", unidade="kbd", series=sv(lambda d: d))]),
    ])


def graficos_fornecimento():
    """O perfil do fornecimento das planilhas de oferta: o mês e a janela de 12
    meses, num botão. As colunas são as da tabela T.1 da FGV; "Importações"
    inclui as tradings, e a Petrobras inclui o que ela própria importa."""
    import openpyxl
    fora = []
    for arq, prod, id_ in (("oferta-diesel.xlsx", "diesel", "fornecimento-diesel"),
                           ("oferta-gasolina.xlsx", "gasolina", "fornecimento-gasolina")):
        wb = openpyxl.load_workbook(os.path.join(RAIZ, "planilhas", arq), read_only=True, data_only=True)
        variantes = []
        for aba, rot in (("Perfil mensal", "No mês"), ("Perfil do fornecimento", "Janela de 12 meses")):
            linhas = list(wb[aba].iter_rows(values_only=True))
            cab = list(linhas[0])
            ls = [dict(zip(cab, l)) for l in linhas[1:] if l[0] and l[1] == "Brasil"]
            col = {c: {str(l["mês"]): float(l[c]) for l in ls if l.get(c) is not None}
                   for c in ("Petrobras", "Importações", "Tradings")}
            variantes.append(dict(rot=rot, unidade="%", series=[
                serie("Petrobras", AZUL, col["Petrobras"], rotulo=True),
                serie("Importações", VERMELHO, col["Importações"], rotulo=True),
                serie("Tradings", VERDE, col["Tradings"], rotulo=True)]))
        fora.append(dict(id=id_, titulo="Fornecimento de %s A no Brasil" % prod,
                         subtitulo="% do volume; importações incluem tradings",
                         unidade="%", fonte="ANP e FtM", variantes=variantes))
    return dict(titulo="Fornecimento de diesel e gasolina", graficos=fora)


def graficos_icbr():
    total, energia = sgs(ICBR_USD), sgs(ICBR_ENERGIA_USD)
    return dict(titulo="Índice de Commodities - Brasil", graficos=[
        dict(id="icbr-usd", titulo="Índice de Commodities - Brasil (IC-Br)",
             subtitulo="Em dólar, dez/2005 = 100", unidade="pts", fonte="Banco Central e FtM",
             series=[serie("IC-Br", BRANCO, total, rotulo=True),
                     serie("IC-Br Energia", LARANJA, energia, rotulo=True)]),
    ]), max(total)


def main():
    print("Comex Stat…")
    exp, imp = comex("EXP"), comex("IMP")
    ref = min(max(exp), max(imp))
    exp = {m: v for m, v in exp.items() if m <= ref}
    imp = {m: v for m, v in imp.items() if m <= ref}
    print("  %d meses de exportação e %d de importação, até %s" % (len(exp), len(imp), ref))
    nomes = nomes_paises()

    secoes, pexp, pimp = graficos_pauta(exp, imp)
    confere_soma("pauta de exportação", list(pexp.values()), {m: x["total"] for m, x in exp.items()})
    confere_soma("pauta de importação", list(pimp.values()), {m: x["total"] for m, x in imp.items()})
    secoes.append(grafico_saldo(exp, imp, pexp, pimp))
    secoes.append(graficos_petroleo_derivados(pexp, pimp))
    secoes.append(graficos_preco_volume(imp, classes_ncm(), pe.brent()))
    secoes.append(graficos_paises(exp, imp, nomes, ref))
    secoes.extend(pe.secoes_extra())
    print("Planilhas de oferta…")
    secoes.append(graficos_fornecimento())
    print("IC-Br…")
    icbr, ref_icbr = graficos_icbr()
    secoes.append(icbr)
    print("Termos de troca…")
    secoes.append(pe.termos_de_troca())

    # Por enquanto, só o título do assunto e os gráficos em sequência: uma
    # seção sem título, no formato de artigo (que não põe seção sem título no
    # índice). A ordem das seções acima continua sendo a ordem dos gráficos.
    todos = [g for s in secoes for g in s["graficos"]]
    doc = dict(atualizado=datetime.date.today().isoformat(), referencia=ref, formato="artigo",
               fonte=FONTE_COMEX, assunto="Petróleo, derivados e comércio exterior",
               secoes=[dict(titulo="", graficos=todos)])
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print("gravado %s (%.0f KB); Comex até %s, IC-Br até %s"
          % (SAIDA, os.path.getsize(SAIDA) / 1024, ref, ref_icbr))
    for sec in doc["secoes"]:
        for g in sec["graficos"]:
            ss = g.get("series") or g["variantes"][-1]["series"]
            print("  %-26s %s" % (g["id"], "; ".join("%s=%s" % (s["nome"][:18], s["dados"][-1][1])
                                                       for s in ss if s["dados"])))


if __name__ == "__main__":
    main()

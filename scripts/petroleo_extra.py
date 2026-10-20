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
  - **Contribuição para o PIB**, IBGE, SIDRA 1846 (valores correntes) e 6612
    (valores encadeados a preços de 1995). Em 4 trimestres contra os 4
    anteriores: peso nominal do componente nos 4 trimestres-base × variação
    real dele, em p.p. A importação entra com sinal trocado. O PIB refeito
    pela mesma soma de 4 trimestres é conferido contra a taxa que o IBGE
    publica (SIDRA 5932).
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
URL_BRENT = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MCOILBRENTEU"
NAVEGADOR = {"User-Agent": "Mozilla/5.0"}

M3_BBL = 6.28981
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MES_NUM = {m.upper(): i + 1 for i, m in enumerate(MESES)}

AZUL, VERMELHO, VERDE, ROXO, CIANO, LARANJA = "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6", "#F79646"
AZUL_ESCURO, BRANCO, CINZA, AREIA = "#1F497D", "#FFFFFF", "#95A5A6", "#D9B382"

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
    # O mês final: o último em que o painel completo até ele ainda tem pelo
    # menos 90% do volume do painel de 12 meses antes. Sem isso, um país
    # grande que para de informar (a Índia depois de mar/2026) sai da série
    # inteira e o nível cai sem nada ter caído.
    fora = {}
    for prod, paises in dados.items():
        meses = sorted({m for d in paises.values() for m in d})

        def painel(fim):
            janela = [m for m in meses if m <= fim]
            return [p for p, d in paises.items() if all(m in d for m in janela)], janela

        base = meses[-13]
        p_base, _ = painel(base)
        vol_base = sum(paises[p][base] for p in p_base)
        for fim in reversed(meses):
            p_fim, janela = painel(fim)
            if sum(paises[p][base] for p in p_fim if base in paises[p]) >= 0.9 * vol_base:
                break
        fora[prod] = fim
    # o mesmo mês final para os dois produtos, para a comparação ser justa
    fim = min(fora.values())
    for prod, paises in dados.items():
        meses = sorted({m for d in paises.values() for m in d})
        janela = [m for m in meses if m <= fim]
        p_fim = [p for p, d in paises.items() if all(m in d for m in janela)]
        fora[prod] = ({m: sum(paises[p][m] for p in p_fim) for m in janela}, len(p_fim), fim)
    return fora


def graficos_refino_mundo():
    r = refino_mundo()
    gas, n_g, fim_g = r["GASOLINE"]
    die, n_d, fim_d = r["GASDIES"]
    print("  JODI: gasolina %d países até %s, diesel %d países até %s" % (n_g, fim_g, n_d, fim_d))
    fonte = "JODI e FtM"
    sub = "Mil barris por dia, produção bruta das refinarias; soma de %d países com dado completo desde 2015"
    return [
        dict(id="refino-mundo", titulo="Produção de diesel e gasolina nas refinarias do mundo",
             subtitulo=sub % min(n_g, n_d), unidade="kbd", fonte=fonte,
             variantes=[
                 dict(rot="Mensal", unidade="kbd", series=[
                     serie("Gasóleo/diesel (%d países)" % n_d, VERMELHO, die, 0, rotulo=True),
                     serie("Gasolina (%d países)" % n_g, AZUL, gas, 0, rotulo=True)]),
                 dict(rot="Média de 12 meses", unidade="kbd", series=[
                     serie("Gasóleo/diesel (%d países)" % n_d, VERMELHO, media_12(die), 0, rotulo=True),
                     serie("Gasolina (%d países)" % n_g, AZUL, media_12(gas), 0, rotulo=True)]),
             ]),
    ]


# --------------------------------------------------------------------------
# IBGE
# --------------------------------------------------------------------------

COMP = {"90707": "PIB", "93404": "Consumo das famílias", "93405": "Consumo do governo",
        "93406": "FBCF", "93407": "Exportação", "93408": "Importação"}
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


def graficos_pib():
    nominal, real = sidra(1846), sidra(6612)
    n4 = {k: soma4(v) for k, v in nominal.items()}
    r4 = {k: soma4(v) for k, v in real.items()}

    def ant(m):
        return "%04d-%s" % (int(m[:4]) - 1, m[5:])

    contrib = {k: {} for k in COMP.values() if k != "PIB"}
    pib = {}
    for m in r4["PIB"]:
        a = ant(m)
        if a not in r4["PIB"] or a not in n4["PIB"]:
            continue
        pib[m] = (r4["PIB"][m] / r4["PIB"][a] - 1) * 100
        for k in contrib:
            if a in r4.get(k, {}) and a in n4.get(k, {}):
                g = r4[k][m] / r4[k][a] - 1
                w = n4[k][a] / n4["PIB"][a]
                contrib[k][m] = (-1 if k == "Importação" else 1) * w * g * 100
    # o PIB pela soma de 4 trimestres contra a taxa publicada pelo IBGE
    pub = json.loads(baixar("https://apisidra.ibge.gov.br/values/t/5932/n1/all/v/6562/p/all/c11255/90707",
                            headers={"User-Agent": "Mozilla/5.0 (ftm-analises)"}).decode("utf-8"))
    oficial = {}
    for l in pub[1:]:
        try:
            oficial["%s-%s" % (l["D3C"][:4], TRI[l["D3C"][-1]])] = float(l["V"])
        except (ValueError, KeyError):
            pass
    difs = [abs(pib[m] - oficial[m]) for m in pib if m in oficial]
    print("  PIB em 4 trimestres confere com o IBGE em %d trimestres, diferença máxima %.2f p.p."
          % (len(difs), max(difs)))
    if max(difs) > 0.06:
        raise RuntimeError("o PIB refeito não bate com a taxa do IBGE (%.2f p.p.)" % max(difs))
    liquido = {m: contrib["Exportação"][m] + contrib["Importação"][m]
               for m in contrib["Exportação"] if m in contrib["Importação"]}
    return dict(titulo="PIB", graficos=[
        dict(id="pib-setor-externo", titulo="Contribuição do setor externo para o crescimento do PIB",
             subtitulo="p.p., acumulado em 4 trimestres contra os 4 anteriores; importação com sinal trocado",
             unidade="pp", fonte="IBGE e FtM", barra=2.6, buracoMax=3,
             series=[serie("Exportação", AZUL, contrib["Exportação"], 2, tipo="barra"),
                     serie("Importação", LARANJA, contrib["Importação"], 2, tipo="barra"),
                     serie("Setor externo líquido", BRANCO, liquido, 2, rotulo=True),
                     serie("PIB (variação %)", CINZA, pib, 2, rotulo=True, traco="pontilhado", largura=4)]),
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


def secoes_extra():
    print("Conta corrente (BC)…")
    cc = graficos_conta_corrente()
    print("ANP…")
    prod = graficos_producao()
    refino = graficos_refino_brasil()
    print("JODI…")
    mundo = graficos_refino_mundo()
    print("IBGE…")
    pib = graficos_pib()
    return [cc, prod, dict(titulo="Refino", graficos=refino + mundo), pib]


if __name__ == "__main__":
    for s in secoes_extra():
        for g in s["graficos"]:
            ss = g.get("series") or g["variantes"][0]["series"]
            print(g["id"], "; ".join("%s=%s" % (x["nome"][:20], x["dados"][-1]) for x in ss if x["dados"]))

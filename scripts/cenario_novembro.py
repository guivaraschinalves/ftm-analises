#!/usr/bin/env python3
"""
Monta dados/cenario-2026-11-08.json, a análise de cenário de novembro de 2026:
primeiro EUA e mundo (FOMC, midterms, a venda das ações de IA, o IPO da
Anthropic), depois Brasil (eleição, Focus, Copom, crédito privado).

Uso:
    python3 scripts/cenario_novembro.py

Só biblioteca padrão. Rodado à mão: é o retrato de uma data. O texto vem de
textos/cenario-2026-11-08.md (aplicar_texto, no fim).

DE ONDE VEM CADA COISA

  - FOMC: as funções do cenario_fomc.py (payroll, Treasuries, juros dos
    bancos centrais, spreads de crédito) rodam de novo, com o dado de hoje.
    Comunicados, dissidentes e CPI são copiados do JSON de 28/10, que não
    mudou desde então (o CPI de outubro sai em 12/11).
  - Midterms: os hemiciclos de resultado, copiados de dados/midterms-2026.json.
  - Ações americanas: FRED, sem chave. Os índices setoriais são os Nasdaq US
    Benchmark por indústria (classificação ICB), que o FRED publica com o
    fechamento do dia seguinte. SOX e o índice de chips de IA (PHLX) também.
  - Anthropic: os números do S-1/A, já organizados em ../ftm-dados
    (dados/acoes-eua.json). Lá o eixo é trimestral; aqui vira categorias.
  - Ibovespa: Ipeadata (GM366_IBVSP366). Dólar: PTAX de venda (SGS 1).
  - Curvas de juros: taxas indicativas da ANBIMA (LTN e NTN-B), do acervo
    diário que o ftm-dados guarda desde 11/09/2026 (a ANBIMA só deixa no ar
    os últimos dias). Lido do origin/main do ftm-dados por git, para não
    depender da cópia local estar atualizada.
  - Focus: API Olinda do BC (ExpectativasMercadoAnuais), mediana diária,
    baseCalculo 0 (todas as respostas dos últimos 30 dias).
  - Copom: comunicados do ../ftm-dados (dados/copom.json, que os baixa da API
    do site do BC); Selic Meta do SGS 432.
  - Crédito às empresas: SGS 21083, 21086 (inadimplência), 20718, 20787
    (taxa e spread do crédito livre), 24440 (concessões com ajuste sazonal).
  - IDA: quadro-resumo diário da ANBIMA (IDA_down.asp). Também só existe para
    os últimos dias; o histórico não está aberto.
"""
import csv
import datetime
import io
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import cenario_fomc as cf                                     # noqa: E402

NOME = "cenario-2026-11-08"
SAIDA = os.path.join(RAIZ, "dados", NOME + ".json")
ASSUNTO = "Relatório Wealth/FtM de Novembro"
GRUPO = "Análise de Cenário"
FTM_DADOS = os.path.join(os.path.dirname(RAIZ), "ftm-dados")

BRANCO, AZUL, VERMELHO, VERDE, ROXO, CIANO, LARANJA = (cf.BRANCO, cf.AZUL, cf.VERMELHO, cf.VERDE, cf.ROXO,
                                                       cf.CIANO, cf.LARANJA)
CINZA, AMARELO = cf.CINZA, cf.AMARELO
serie, baixar, fred, desde = cf.serie, cf.baixar, cf.fred, cf.desde
MESES = cf.MESES

TURNO1, TURNO2, MIDTERMS = "2026-10-04", "2026-10-25", "2026-11-03"


def rotulo_dia(d):
    return "%s/%s/%s" % (d[8:], d[5:7], d[:4])


def br(v, casas=1, sinal=False):
    return cf.br(v, casas, sinal)


def json_ftm_dados(caminho):
    """Um JSON do ftm-dados como está no GitHub (origin/main)."""
    subprocess.run(["git", "-C", FTM_DADOS, "fetch", "-q", "origin"], check=True)
    txt = subprocess.run(["git", "-C", FTM_DADOS, "show", "origin/main:" + caminho], check=True,
                         capture_output=True).stdout
    return json.loads(txt)


def copiar(arquivo, ids):
    """Gráficos de outro JSON deste site, pelo id, sem o comentário do autor."""
    with open(os.path.join(RAIZ, "dados", arquivo), encoding="utf-8") as f:
        doc = json.load(f)
    achados = {g["id"]: g for s in doc["secoes"] for g in s.get("graficos", [])}
    out = []
    for i in ids:
        g = dict(achados[i])
        g.pop("comentario", None)
        out.append(g)
    return out


def sgs(codigo, ini="01/01/2011"):
    """Série do SGS desde ini (dd/mm/aaaa). Série diária só sai em janelas de
    até 10 anos (406 acima disso): o pedido vai em pedaços de 9 anos."""
    d0 = datetime.datetime.strptime(ini, "%d/%m/%Y").date()
    hoje = datetime.date.today()
    out = {}
    while d0 <= hoje:
        d1 = min(hoje, d0.replace(year=d0.year + 9) - datetime.timedelta(days=1))
        url = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.%d/dados?formato=json&dataInicial=%s&dataFinal=%s"
               % (codigo, d0.strftime("%d/%m/%Y"), d1.strftime("%d/%m/%Y")))
        for l in json.loads(baixar(url)):
            d, m, a = l["data"].split("/")
            out["%s-%s-%s" % (a, m, d)] = float(l["valor"])
        d0 = d1 + datetime.timedelta(days=1)
    return out


def serie_cat(nome, cor, valores, casas=2, **extra):
    """Série num eixo de categorias: a chave é a posição, em ordem numérica
    (o sort de texto poria "10" antes de "2" e a linha voltaria para trás)."""
    return dict(nome=nome, cor=cor, dados=[[str(i), round(v, casas)] for i, v in enumerate(valores)], **extra)


def mensal(s):
    """Série SGS mensal ("AAAA-MM-01") com chave "AAAA-MM"."""
    return {k[:7]: v for k, v in s.items()}


# ================================================================ EUA: FOMC

_FOMC = {}


def fomc():
    """Os gráficos da parte do FOMC, calculados uma vez e repartidos entre os
    blocos (cada bloco tem o texto logo antes do seu gráfico)."""
    if _FOMC:
        return _FOMC
    base = "cenario-2026-10-28-fomc.json"
    comunicados, dissidentes, cpi = copiar(base, ["fomc-comunicados", "fomc-dissidentes", "cpi-cheio-nucleo"])
    trabalho = {g["id"]: g for g in cf.graficos_trabalho()}
    treasuries = cf.graficos_treasuries()[0]
    # o arquivo diário desde 2000 pesa 400 KB: aqui bastam os últimos cinco anos
    for s in treasuries["series"]:
        s["dados"] = [p for p in s["dados"] if p[0] >= "2021-01-01"]
    treasuries.pop("periodoPadrao", None)
    _FOMC.update(comunicados=comunicados, dissidentes=dissidentes, cpi=cpi, pce=grafico_pce(),
                 payroll=trabalho["payroll-setores"], treasuries=treasuries)
    _FOMC.update(graficos_ftm_dados_eua())
    return _FOMC


def grafico_pce():
    """PCE cheio, núcleo e supercore (12 meses, calculados do índice) contra as
    medidas que cortam os extremos: média aparada (Fed de Dallas) e mediana do
    CPI (Fed de Cleveland), que o FRED já publica em 12 meses."""
    ini = "2017-01"
    v12 = lambda sid: desde(cf.var(fred(sid)), ini)                       # noqa: E731
    series = [serie("PCE cheio", BRANCO, v12("PCEPI"), rotulo=True),
              serie("Núcleo do PCE", LARANJA, v12("PCEPILFE"), rotulo=True),
              serie("Supercore (serviços sem energia e moradia)", VERMELHO, v12("IA001260M"), rotulo=True),
              serie("Média aparada do PCE (Dallas)", VERDE, desde(fred("PCETRIM12M159SFRBDAL"), ini), rotulo=True),
              serie("Mediana do CPI (Cleveland)", CIANO, desde(fred("MEDCPIM159SFRBCLE"), ini), rotulo=True)]
    return dict(id="pce-nucleos", titulo="Inflação do consumo (PCE) e medidas de núcleo",
                subtitulo="% em 12 meses; supercore = serviços sem energia e moradia; média aparada e mediana tiram "
                          "os itens de variação mais extrema",
                unidade="%", fonte="BEA, Fed de Dallas e Fed de Cleveland (via FRED) e FtM", series=series)


def graficos_ftm_dados_eua():
    """PIB (contribuições), desemprego U-3/U-6 e participação ajustada, do ftm-dados."""
    gs = {}
    for arq in ("dados/trabalho-eua.json", "dados/pib-eua.json"):
        def anda(secs):
            for s in secs:
                for g in s.get("graficos", []):
                    gs[g["id"]] = g
                anda(s.get("subsecoes", []))
        anda(json_ftm_dados(arq)["secoes"])

    # PIB: o eixo trimestral do ftm-dados vira categorias ("3T26"), desde 2021
    p = gs["pib-eua-contribuicoes"]
    ks = sorted({k for s in p["series"] for k, _ in s["dados"] if k >= "2021-Q1"})
    pos = {k: str(i) for i, k in enumerate(ks)}
    pib = dict(id="pib-eua-contribuicoes", titulo=p["titulo"], subtitulo=p["subtitulo"], unidade=p["unidade"],
               fonte=p["fonte"], categorias=["%sT%s" % (k[-1], k[2:4]) for k in ks], barra=1,
               series=[dict(s, dados=[[pos[k], v] for k, v in s["dados"] if k in pos]) for s in p["series"]])

    d, c = gs["eua-desemprego"], gs["eua-u6-composicao"]
    u6 = dict(id="eua-u3-u6", titulo="Taxa de desemprego: U-3 e U-6",
              subtitulo="Com ajuste sazonal; o U-6 soma ao desemprego os desalentados, os marginalmente ligados e "
                        "quem trabalha meio período por falta de opção",
              unidade="pct1", fonte="BLS (via FRED) e FtM", variantes=[
                  dict(rot="U-3 e U-6, % da força de trabalho", series=d["series"]),
                  dict(rot="partes do U-6, em pontos", barra=1, series=c["variantes"][0]["series"],
                       nota=c["variantes"][0].get("nota")),
                  dict(rot="meio período por falta de opção, mil pessoas", unidade="mil", barra=1,
                       series=c["variantes"][1]["series"], nota=c["variantes"][1].get("nota"))])

    pa = gs["eua-participacao"]
    obs, ajust = pa["variantes"][0], pa["variantes"][1]
    participacao = dict(id="eua-participacao", titulo=pa["titulo"], subtitulo="% da população de 16 anos ou mais",
                        unidade=pa["unidade"], fonte=ajust.get("fonte", pa["fonte"]), eixo=pa.get("eixo"),
                        variantes=[
                            dict(rot="observada e ajustada pela composição por idade e sexo de out/26",
                                 series=ajust["series"], nota=ajust.get("nota")),
                            dict(rot="observada, com ajuste sazonal",
                                 series=obs.get("series") or [dict(s) for s in pa["series"]])])
    for v in participacao["variantes"]:
        for s in v["series"]:
            s.pop("hover", None)
    return dict(pib=pib, u6=u6, participacao=participacao)


def graficos_fomc():
    f = fomc()
    return [f["comunicados"], f["pib"], f["dissidentes"]]


def graficos_fomc_inflacao():
    f = fomc()
    return [f["pce"], f["cpi"]]


def graficos_fomc_payroll():
    return [fomc()["payroll"]]


def graficos_fomc_desemprego():
    return [fomc()["u6"]]


def graficos_fomc_participacao():
    return [fomc()["participacao"]]


def graficos_fomc_juros():
    return [fomc()["treasuries"]]


# ================================================================ EUA: midterms

def graficos_midterms():
    return copiar("midterms-2026.json", ["midterms-resultado-camara", "midterms-resultado-senado"])


# ================================================================ EUA: ações de IA

INDICES = [("SP500", "S&P 500", BRANCO), ("NASDAQCOM", "Nasdaq Composite", AZUL), ("DJIA", "Dow Jones", CINZA),
           ("NASDAQSOX", "Semicondutores (SOX)", VERMELHO), ("NASDAQASOX", "Chips de IA (PHLX)", LARANJA),
           ("NASDAQNQUSB10101015", "Software (Nasdaq US)", VERDE)]
SETORES = [("NASDAQNQUSB10", "Tecnologia"), ("NASDAQNQUSB15", "Telecomunicações"), ("NASDAQNQUSB20", "Saúde"),
           ("NASDAQNQUSB30", "Financeiro"), ("NASDAQNQUSB35", "Imobiliário"),
           ("NASDAQNQUSB40", "Consumo discricionário"), ("NASDAQNQUSB45", "Consumo básico"),
           ("NASDAQNQUSB50", "Industrial"), ("NASDAQNQUSB55", "Materiais básicos"), ("NASDAQNQUSB60", "Energia"),
           ("NASDAQNQUSB65", "Utilidades"), ("NASDAQSOX", "Semicondutores (SOX)"),
           ("NASDAQASOX", "Chips de IA (PHLX)"), ("NASDAQNQUSB10101015", "Software")]


def variacao(s, a, b):
    """% de variação do fechamento de a (ou o último antes) até b."""
    ka = max(k for k in s if k <= a)
    kb = max(k for k in s if k <= b)
    return 100 * (s[kb] / s[ka] - 1)


def graficos_ia():
    ini = "2026-06-01"
    base = MIDTERMS
    linhas = []
    fim = None
    for sid, nome, cor in INDICES:
        s = desde(fred(sid, False), ini)
        b0 = s[max(k for k in s if k <= base)]
        fim = max(fim or "", max(s))
        linhas.append(serie(nome, cor, {k: 100 * v / b0 for k, v in s.items()}, 2, rotulo=True))
    g1 = dict(id="ia-indices", titulo="Índices de ações nos EUA", eixo={"zero": False},
              subtitulo="Base 100 no fechamento de %s, dia da eleição" % rotulo_dia(base),
              unidade="pts", diario=True, buracoMax=6, fonte="S&P Dow Jones Indices e Nasdaq (via FRED) e FtM",
              eventos=[dict(em=base, rot="Midterms")], series=linhas)

    dia = "2026-11-05"
    itens_dia, itens_sem = [], []
    for sid, nome in SETORES:
        s = fred(sid, False)
        v1 = variacao(s, "2026-11-04", dia)
        v2 = variacao(s, base, max(s))
        itens_dia.append([nome, round(v1, 1), VERMELHO if v1 < 0 else VERDE])
        itens_sem.append([nome, round(v2, 1), VERMELHO if v2 < 0 else VERDE])
    itens_dia.sort(key=lambda x: -x[1])
    itens_sem.sort(key=lambda x: -x[1])
    g2 = dict(id="ia-setores-dia", tipo="ranking", sinal=True, unidade="pct1",
              titulo="Ações nos EUA por setor: variação em %s" % rotulo_dia(dia),
              subtitulo="Índices Nasdaq US Benchmark por indústria (ICB), SOX e chips de IA (PHLX); "
                        "fechamento de %s sobre o do dia anterior" % rotulo_dia(dia),
              fonte="Nasdaq (via FRED) e FtM", itens=itens_dia)
    g3 = dict(id="ia-setores-semana", tipo="ranking", sinal=True, unidade="pct1",
              titulo="Ações nos EUA por setor: variação desde as midterms",
              subtitulo="Índices Nasdaq US Benchmark por indústria (ICB), SOX e chips de IA (PHLX); "
                        "de %s a %s" % (rotulo_dia(base), rotulo_dia(fim)),
              fonte="Nasdaq (via FRED) e FtM", itens=itens_sem)
    vix = desde(fred("VIXCLS", False), "2025-01-01")
    g4 = dict(id="ia-vix", titulo="Volatilidade implícita do S&P 500 (VIX)", subtitulo="Pontos, diário",
              unidade="pts", diario=True, buracoMax=6, fonte="Cboe (via FRED)",
              eventos=[dict(em=base, rot="Midterms")], series=[serie("VIX", LARANJA, vix, 2, rotulo=True)])
    credito = cf.graficos_credito()
    print("  ações: Nasdaq %s em 5/11; SOX %s; desde as midterms Nasdaq %s"
          % (br(variacao(fred("NASDAQCOM", False), "2026-11-04", dia), 2),
             br(variacao(fred("NASDAQSOX", False), "2026-11-04", dia), 2),
             br(variacao(fred("NASDAQCOM", False), base, fim), 2)))
    return [g1, g2, g3, g4] + credito


# ================================================================ EUA: Anthropic

def tri_rot(k):
    return "%sT%s" % (k[-1], k[2:4])


def graficos_anthropic():
    doc = json_ftm_dados("dados/acoes-eua.json")
    gs = {g["id"]: g for s in doc["secoes"] for sub in s.get("subsecoes", []) for g in sub.get("graficos", [])}

    def trimestral(g, unidade, **extra):
        ks = sorted({k for s in g["series"] for k, _ in s["dados"]})
        idx = {k: str(i) for i, k in enumerate(ks)}
        series = [dict(nome=s["nome"], cor=s["cor"], tipo=s.get("tipo"),
                       dados=[[idx[k], v] for k, v in s["dados"]], legenda=False) for s in g["series"]]
        return dict(id=g["id"], titulo=g["titulo"], subtitulo=g["subtitulo"].split(";")[0], fonte=g["fonte"],
                    categorias=[tri_rot(k) for k in ks], unidade=unidade, valores=True, agrupadas=True,
                    series=series, **extra)

    receita = trimestral(gs["anthropic-receita-trimestral"], "usd-bi")
    receita["subtitulo"] = "Por trimestre, em US$ bilhões"
    margem = trimestral(gs["anthropic-margens"], "pct1")

    def categorias(g, unidade, fator=1.0):
        def conv(series):
            return [dict(nome=s["nome"], cor=s["cor"], tipo="barra",
                         dados=[[k, round(v * fator, 3)] for k, v in s["dados"]]) for s in series]
        out = dict(id=g["id"], titulo=g["titulo"], subtitulo=g["subtitulo"], fonte=g["fonte"],
                   categorias=g["categorias"], unidade=unidade, valores=True, agrupadas=True)
        if "variantes" in g:
            out["variantes"] = [dict(rot=v["rot"], series=conv(v["series"])) for v in g["variantes"]]
        else:
            out["series"] = conv(g["series"])
        return out

    def ranking(g, unidade, fator=1.0, variante=0, sub=None):
        """Comparação entre empresas como ranking: uma barra por empresa, com o
        valor escrito (no gráfico de barras empilhadas o número não aparece)."""
        series = g["variantes"][variante]["series"] if "variantes" in g else g["series"]
        itens = [[g["categorias"][int(k)], round(v * fator, 2), s["cor"]] for s in series for k, v in s["dados"]]
        itens.sort(key=lambda x: -x[1])
        return dict(id=g["id"], tipo="ranking", unidade=unidade, titulo=g["titulo"],
                    subtitulo=sub or g["subtitulo"], fonte=g["fonte"], itens=itens)

    valor = ranking(gs["anthropic-valor-mercado"], "usd-tri", 1 / 1000)
    pv = ranking(gs["anthropic-preco-vendas"], "x",
                 sub="Valor de mercado ÷ receita do último trimestre × 4")
    rodadas = categorias(gs["anthropic-captado-rodadas"], "usd-bi")
    rodadas.pop("variantes", None)
    v0 = gs["anthropic-captado-rodadas"]["variantes"][0]
    rodadas["series"] = [dict(nome="Dinheiro novo", cor=AZUL, tipo="barra", dados=v0["series"][0]["dados"],
                              legenda=False)]
    return [receita, margem, rodadas, valor, pv]


# ================================================================ Brasil: eleição

def ibovespa():
    url = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='GM366_IBVSP366')"
    out = {}
    for l in json.loads(baixar(url))["value"]:
        if l["VALVALOR"] is not None:
            out[l["VALDATA"][:10]] = float(l["VALVALOR"])
    return out


def curva(acervo, papel, dia):
    """{vencimento: taxa} do papel no dia (ou no último dia útil antes)."""
    d = max(k for k in acervo if k <= dia)
    return d, {k.split("|")[1]: v for k, v in acervo[d].items() if k.startswith(papel + "|")}


def graficos_eleicao():
    reacao = copiar("eleicoes.json", ["eleicoes-reacao"])[0]
    ev = [dict(em=TURNO1, rot="1º turno"), dict(em=TURNO2, rot="2º turno")]

    ibov = desde(ibovespa(), "2026-01-01")
    g_ibov = dict(id="br-ibovespa", titulo="Ibovespa em 2026", subtitulo="Pontos, fechamento diário",
                  unidade="pts", diario=True, buracoMax=6, fonte="B3 (via Ipeadata)", eventos=ev,
                  series=[serie("Ibovespa", AZUL, ibov, 0, rotulo=True)])
    dolar = sgs(1, "02/01/2026")
    g_dolar = dict(id="br-dolar", titulo="Dólar em 2026", subtitulo="R$ por US$, PTAX de venda",
                   unidade="brl", diario=True, buracoMax=6, fonte="Banco Central do Brasil", eventos=ev,
                   series=[serie("Dólar (PTAX)", VERDE, dolar, 4, rotulo=True)])

    acervo = json_ftm_dados("dados/anbima-indicativas.json")
    hoje = max(acervo)
    dias = [("2026-10-02", "%s (antes do 1º turno)", CINZA), ("2026-10-23", "%s (antes do 2º turno)", BRANCO),
            ("2026-10-26", "%s (depois do 2º turno)", VERMELHO), (hoje, "%s", LARANJA)]

    def grafico_curva(papel, gid, titulo, subtitulo, fmt_venc):
        curvas = [(curva(acervo, papel, d), rot, cor) for d, rot, cor in dias]
        vencs = sorted(set.intersection(*[set(c[1]) for (c, _, _) in curvas]))
        # o vencimento de menos de um ano fica de fora: a taxa dele é dominada
        # pela inflação dos meses que faltam e entorta a escala
        vencs = [v for v in vencs if v > "2027-12-31"]
        cats = [fmt_venc(v) for v in vencs]
        series = []
        for (d, c), rot, cor in curvas:
            series.append(serie_cat(rot % rotulo_dia(d), cor, [c[v] for v in vencs], 2, rotulo=True))
        (d_a, ca), _, _ = curvas[1]
        (d_b, cb), _, _ = curvas[-1]
        (d_c, cc), _, _ = curvas[2]
        dif = [serie_cat("%s menos %s" % (rotulo_dia(d_c), rotulo_dia(d_a)), VERMELHO,
                         [100 * (cc[v] - ca[v]) for v in vencs], 0, tipo="barra"),
               serie_cat("%s menos %s" % (rotulo_dia(d_b), rotulo_dia(d_a)), LARANJA,
                         [100 * (cb[v] - ca[v]) for v in vencs], 0, tipo="barra")]
        print("  %s: %s" % (papel, ", ".join("%s %+.0f pb" % (cats[i], 100 * (cb[v] - ca[v]))
                                             for i, v in enumerate(vencs))))
        return dict(id=gid, titulo=titulo, subtitulo=subtitulo, categorias=cats,
                    fonte="ANBIMA (taxas indicativas) e FtM", variantes=[
                        dict(rot="as curvas", unidade="%", eixo={"zero": False}, series=series),
                        dict(rot="diferença em pontos-base", unidade="pb", agrupadas=True, series=dif)])

    venc = lambda v: "%s/%s" % (MESES[int(v[5:7]) - 1], v[2:4])          # noqa: E731
    g_pre = grafico_curva("LTN", "br-curva-pre", "Curva de juros prefixados (LTN)",
                          "Taxa indicativa de cada vencimento, % ao ano", venc)
    g_real = grafico_curva("NTN-B", "br-curva-real", "Curva de juros reais (NTN-B)",
                           "Taxa indicativa de cada vencimento, % ao ano acima do IPCA", venc)
    print("  Ibovespa até %s (%s); dólar até %s (%s); ANBIMA até %s"
          % (max(ibov), br(ibov[max(ibov)], 0), max(dolar), br(dolar[max(dolar)], 4), hoje))
    return [reacao, g_ibov, g_dolar, g_pre, g_real]


# ================================================================ Brasil: Focus

OLINDA = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"


def focus(indicador, ini="2026-01-01"):
    filtro = "Indicador eq '%s' and Data ge '%s' and baseCalculo eq 0" % (indicador, ini)
    # a Olinda recusa "+" no lugar do espaço (400): vai com %20
    url = OLINDA + "?$filter=%s&$format=json&$select=Data,DataReferencia,Mediana" % urllib.parse.quote(filtro)
    out = {}
    for l in json.loads(baixar(url))["value"]:
        out.setdefault(l["DataReferencia"], {})[l["Data"]] = l["Mediana"]
    return out


def graficos_focus():
    ev = [dict(em=TURNO1, rot="1º turno"), dict(em=TURNO2, rot="2º turno")]
    cores = {"2026": BRANCO, "2027": LARANJA, "2028": CIANO}
    variantes = []
    for ind, rot, unidade, anos in (("IPCA", "IPCA", "%", ("2026", "2027", "2028")),
                                    ("Selic", "Selic no fim do ano", "%", ("2026", "2027", "2028")),
                                    ("PIB Total", "PIB", "%", ("2026", "2027")),
                                    ("Câmbio", "Dólar no fim do ano", "brl", ("2026", "2027"))):
        f = focus(ind)
        variantes.append(dict(rot=rot, unidade=unidade, eixo={"zero": False},
                              series=[serie(a, cores[a], f[a], 4 if unidade == "brl" else 2, rotulo=True)
                                      for a in anos]))
        ult = max(f[anos[0]])
        print("  Focus %s em %s: %s" % (ind, ult, ", ".join("%s %s" % (a, f[a][max(f[a])]) for a in anos)))
    return [dict(id="br-focus", titulo="Expectativas do mercado (Focus)",
                 subtitulo="Mediana das projeções para cada ano; IPCA e PIB em % no ano, Selic em % ao ano, "
                           "dólar em R$ por US$",
                 diario=True, buracoMax=6, fonte="Banco Central do Brasil (Focus)", eventos=ev,
                 variantes=variantes)]


# ================================================================ Brasil: Copom

def graficos_copom():
    doc = json_ftm_dados("dados/copom.json")
    g = doc["secoes"][0]["graficos"][0]
    comunicados = []
    for c in sorted(g["comunicados"], key=lambda x: x["data"]):
        if c["data"] < "2023-01-01":
            continue
        pars = [b["p"] for b in c.get("b", []) if b.get("p")]
        if pars:
            comunicados.append(dict(data=c["data"], paragrafos=pars,
                                    url="https://www.bcb.gov.br/publicacoes/comunicadoscopom"))
    comp = dict(id="copom-comunicados", tipo="comunicados", titulo="Comparador dos comunicados do Copom",
                subtitulo="Escolha dois comunicados: o que saiu do texto aparece riscado em vermelho, "
                          "o que entrou, em verde",
                fonte="Banco Central do Brasil", site="BC", comunicados=comunicados)
    selic = desde(sgs(432, "01/01/2016"), "2016-01-01")
    g_selic = dict(id="br-selic", titulo="Selic Meta", subtitulo="% ao ano", unidade="%", diario=True,
                   buracoMax=4000, fonte="Banco Central do Brasil",
                   series=[serie("Selic Meta", BRANCO, cf.degraus(selic), 2, rotulo=True)])
    print("  Copom: %d comunicados até %s; Selic %s" % (len(comunicados), comunicados[-1]["data"],
                                                         selic[max(selic)]))
    return [comp, g_selic]


# ================================================================ Brasil: crédito privado

def ida_resumo():
    """Quadro-resumo do IDA do último dia útil que a ANBIMA tiver."""
    dia = datetime.date.today()
    for _ in range(10):
        dia -= datetime.timedelta(days=1)
        if dia.weekday() >= 5:
            continue
        corpo = urllib.parse.urlencode({"Idioma": "PT", "tipo": "qr", "indice": "DI", "escolha": "2",
                                        "saida": "csv", "DataIniD": dia.strftime("%d/%m/%Y")}).encode()
        txt = baixar("https://www.anbima.com.br/informacoes/ida/IDA_down.asp", dados=corpo).decode("latin-1")
        linhas = [l.split(";") for l in txt.splitlines() if l.startswith("IDA")]
        if linhas:
            return dia.isoformat(), linhas
    raise RuntimeError("IDA: nenhum quadro-resumo nos últimos dias")


def cdi_acumulado(cdi, ini, fim):
    f = 1.0
    for k, v in cdi.items():
        if ini < k <= fim:
            f *= 1 + v / 100
    return 100 * (f - 1)


def graficos_credito():
    inad, inad_l = mensal(sgs(21083)), mensal(sgs(21086))
    taxa, spread = mensal(sgs(20718)), mensal(sgs(20787))
    conc = {k: v / 1000 for k, v in mensal(sgs(24440)).items()}
    selic = sgs(432, "01/01/2011")
    selic_m = {}
    for k in sorted(selic):
        selic_m[k[:7]] = selic[k]
    selic_m = {k: v for k, v in selic_m.items() if k >= "2011-03" and k <= max(taxa)}
    g1 = dict(id="br-credito-inadimplencia", titulo="Inadimplência do crédito às empresas",
              subtitulo="% da carteira de pessoas jurídicas com atraso acima de 90 dias", unidade="%",
              fonte="Banco Central do Brasil", series=[
                  serie("Total", BRANCO, inad, 2, rotulo=True),
                  serie("Recursos livres", LARANJA, inad_l, 2, rotulo=True)])
    g2 = dict(id="br-credito-taxa", titulo="Taxa de juros e spread do crédito livre às empresas",
              subtitulo="% ao ano; spread = taxa da operação menos o custo de captação do banco",
              unidade="%", fonte="Banco Central do Brasil", series=[
                  serie("Taxa média", BRANCO, taxa, 2, rotulo=True),
                  serie("Spread", LARANJA, spread, 2, rotulo=True),
                  serie("Selic Meta (fim do mês)", CINZA, selic_m, 2, rotulo=True)])
    g3 = dict(id="br-credito-concessoes", titulo="Concessões de crédito às empresas",
              subtitulo="R$ bilhões por mês, com ajuste sazonal", unidade="bi", fonte="Banco Central do Brasil",
              series=[serie("Concessões, pessoas jurídicas", AZUL, conc, 1, rotulo=True)])

    dia, linhas = ida_resumo()
    cdi = sgs(12, "01/01/%d" % (int(dia[:4]) - 3))
    d = datetime.date.fromisoformat(dia)
    ref = {"mês": d.replace(day=1) - datetime.timedelta(days=1), "ano": datetime.date(d.year - 1, 12, 31),
           "12 meses": d.replace(year=d.year - 1), "24 meses": d.replace(year=d.year - 2)}
    cdi_v = {k: cdi_acumulado(cdi, v.isoformat(), dia) for k, v in ref.items()}
    num = lambda t: float(t.replace(".", "").replace(",", "."))             # noqa: E731
    cel = lambda v: {"t": br(v, 2) + "%"}                                  # noqa: E731
    tabela = []
    for l in linhas:
        nome = l[0].replace("IDA - ", "IDA-").replace("Infraestrutura", "Infra").replace("GERAL", "Geral")
        tabela.append([{"t": nome, "forte": nome == "IDA-DI"}, cel(num(l[4])), cel(num(l[5])), cel(num(l[6])),
                       cel(num(l[7])), {"t": l[8]}])
    tabela.append([{"t": "CDI", "forte": True}, cel(cdi_v["mês"]), cel(cdi_v["ano"]), cel(cdi_v["12 meses"]),
                   cel(cdi_v["24 meses"]), {"t": "-"}])
    g4 = dict(id="br-ida", tipo="tabela", titulo="Retorno dos índices de debêntures (IDA) e do CDI",
              subtitulo="Retorno acumulado até %s, em %%; duration em dias úteis" % rotulo_dia(dia),
              fonte="ANBIMA, Banco Central do Brasil (CDI, SGS 12) e FtM",
              colunas=[{"rot": "Índice"}, {"rot": "No mês", "num": True}, {"rot": "No ano", "num": True},
                       {"rot": "12 meses", "num": True}, {"rot": "24 meses", "num": True},
                       {"rot": "Duration", "num": True}], linhas=tabela)
    print("  crédito PJ até %s; IDA de %s" % (max(inad), dia))
    return [g1, g2, g3, g4]


# ================================================================ montagem

# os blocos sem título continuam a seção de cima: o texto de cada um fica logo
# antes do gráfico dele
SECOES = [("Decisão do FOMC", graficos_fomc), ("", graficos_fomc_inflacao), ("", graficos_fomc_payroll),
          ("", graficos_fomc_desemprego), ("", graficos_fomc_participacao), ("", graficos_fomc_juros),
          ("Midterms", graficos_midterms),
          ("A venda das ações de IA", graficos_ia), ("IPO da Anthropic", graficos_anthropic),
          ("Eleição: bolsa, câmbio e juros", graficos_eleicao), ("Expectativas do Focus", graficos_focus),
          ("Decisão do Copom", graficos_copom), ("Crédito privado", graficos_credito)]


def main():
    secoes = []
    for titulo, f in SECOES:
        print(titulo + "…")
        secoes.append(dict(titulo=titulo, texto="", fontes=[], figuras=[], graficos=f()))
    doc = dict(atualizado=datetime.date.today().isoformat(), referencia=datetime.date.today().isoformat(),
               formato="artigo", grupo=GRUPO, assunto=ASSUNTO, marca="wealth",
               fonte="FRED, BLS, Tesouro dos EUA, BIS, Nasdaq, Anthropic (S-1/A), Ipeadata, ANBIMA e Banco Central",
               secoes=secoes)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado %s (%.0f KB)" % (SAIDA, os.path.getsize(SAIDA) / 1024))
    import aplicar_texto
    aplicar_texto.aplicar(NOME + ".md", NOME + ".json")


if __name__ == "__main__":
    main()

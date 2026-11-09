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
import re
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
    pmi = cf.graficos_atividade()[0]
    pmi["subtitulo"] = "Acima de 50 = expansão; faixas cinza = recessões (NBER)"
    _FOMC.update(graficos_ftm_dados_eua(), pmi=pmi)
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
    """PIB (contribuições), desemprego U-3/U-6, participação ajustada e construção de data
    centers, do ftm-dados."""
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
    return dict(pib=pib, u6=u6, participacao=participacao, datacenters=gs["construcao-datacenters-fabricas"])


# ================================================================ EUA: midterms

def graficos_midterms():
    g = copiar("midterms-2026.json", ["midterms-historia-aprovacao"])[0]
    # o texto começa pela Câmara: ela abre primeiro
    g["variantes"] = sorted(g["variantes"], key=lambda v: v["rot"] != "Câmara")
    return [g]


def graficos_midterms_resultado():
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
    # do bloco de crédito do FOMC fica só a dívida das empresas de IA
    return [g1, g3, g4] + [g for g in credito if g["id"] == "ia-divida"]


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
    sim = dict(gs["anthropic-simulador"], tipo="simulador")
    sim.pop("painel", None)
    return [receita, margem, sim]


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
    print("  Ibovespa até %s (%s); dólar até %s (%s); ANBIMA até %s"
          % (max(ibov), br(ibov[max(ibov)], 0), max(dolar), br(dolar[max(dolar)], 4), hoje))
    td = json_ftm_dados("dados/tesouro-direto.json")
    ntnb = [s for sec in td["secoes"] for g in sec["graficos"] if g["id"] == "td-ntnb-vencimentos"
            for s in g["series"] if s["nome"] == "2035"][0]
    g_2035 = dict(id="br-ntnb-2035", titulo="NTN-B 2035 em 2025 e 2026",
                  subtitulo="Tesouro IPCA+ com Juros Semestrais 2035, juro real em % a.a.; média entre a taxa de compra e "
                            "a de venda", unidade="%", diario=True, buracoMax=6, eixo={"zero": False},
                  fonte="Tesouro Nacional (Tesouro Direto) e FtM", eventos=ev,
                  series=[dict(nome="NTN-B 2035", cor=LARANJA, rotulo=True,
                               dados=[p for p in ntnb["dados"] if p[0] >= "2025-01-01"])])
    print("  NTN-B 2035 até %s: %s" % (ntnb["dados"][-1][0], ntnb["dados"][-1][1]))
    return [reacao, g_ibov, g_dolar, g_pre, g_2035]


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
    print("  Copom: %d comunicados até %s" % (len(comunicados), comunicados[-1]["data"]))
    return [comp]


# ================================================================ Brasil: IPCA (do ftm-dados)

def graficos_ipca_ftm_dados():
    doc = json_ftm_dados("dados/ipca.json")
    gs = {g["id"]: g for s in doc["secoes"] for g in s["graficos"]}
    # Focus: só as linhas (o app daqui não desenha velas)
    focus = dict(gs["ipca-projecoes-focus"])
    focus.pop("variantes", None)
    # as cartas abertas viram marcas no alto, no formato de evento deste app
    dist = dict(gs["ipca-distancia-meta"])
    dist["eventos"] = [dict(em=e["x"], rot="Carta") for e in dist.get("eventos", [])]
    dist["subtitulo"] = "IPCA em 12 meses menos a meta, em pontos percentuais; marcas no alto: cartas abertas do BC ao CMN"
    grupos = gs["servicos-industriais-alimentacao"]
    for g in (focus, dist, grupos):
        g["fonte"] = g.get("fonte") or "IBGE, Banco Central do Brasil e FtM"
    return dict(focus=focus, distancia=dist, grupos=grupos)


_IPCA = {}


def ipca_ftm_dados():
    if not _IPCA:
        _IPCA.update(graficos_ipca_ftm_dados())
    return _IPCA


def graficos_focus_ipca():
    return [ipca_ftm_dados()["focus"]]


def graficos_ipca_meta():
    return [ipca_ftm_dados()["distancia"]]


def graficos_ipca_grupos():
    return [ipca_ftm_dados()["grupos"]]


# ================================================================ Brasil: CAGED

def ipea(codigo):
    url = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='%s')" % codigo
    return {l["VALDATA"][:7]: float(l["VALVALOR"]) for l in json.loads(baixar(url))["value"]
            if l["VALVALOR"] is not None}


# Mês que o Ipeadata ainda não tem: o saldo do comunicado do Ministério do
# Trabalho (Novo Caged de setembro de 2026, divulgado em 04/11/2026). Sai
# daqui quando o Ipeadata trouxer o mês (o Ipeadata ganha).
CAGED_MANUAL = {"2026-09": 121305}


def graficos_caged():
    antigo, novo = ipea("CAGED12_SALDO12"), ipea("CAGED12_SALDON12")
    for m, v in CAGED_MANUAL.items():
        novo.setdefault(m, v)
    saldo = {m: v for m, v in antigo.items() if m < "2020-01"}
    saldo.update(novo)
    ks = sorted(saldo)
    doze = {ks[i]: sum(saldo[k] for k in ks[i - 11:i + 1]) / 1000 for i in range(11, len(ks))
            if cf.mes_mais(ks[i - 11], 11) == ks[i]}
    g1 = dict(id="br-caged-12m", titulo="Saldo de empregos formais (Caged) em 12 meses",
              subtitulo="Mil vagas, soma de 12 meses; Caged até 2019 e Novo Caged desde 2020", unidade="mil",
              fonte="Ministério do Trabalho (via Ipeadata; set/26 do comunicado do ministério) e FtM",
              eventos=[dict(em="2020-01", rot="Novo Caged")],
              series=[serie("Saldo em 12 meses", AZUL, {k: v for k, v in doze.items() if k >= "2003-01"}, 0, rotulo=True)])
    anos = sorted({m[:4] for m in saldo if m.endswith("-09")})
    cats = anos
    velho = {str(i): saldo[a + "-09"] / 1000 for i, a in enumerate(anos) if a < "2020"}
    novo_s = {str(i): saldo[a + "-09"] / 1000 for i, a in enumerate(anos) if a >= "2020"}
    g2 = dict(id="br-caged-setembro", titulo="Saldo de empregos formais (Caged) em setembro de cada ano",
              subtitulo="Mil vagas", unidade="mil", categorias=cats, valores=True,
              fonte="Ministério do Trabalho (via Ipeadata; set/26 do comunicado do ministério) e FtM",
              series=[dict(nome="Caged", cor=CINZA, tipo="barra",
                           dados=[[k, round(v, 1)] for k, v in sorted(velho.items(), key=lambda x: int(x[0]))]),
                      dict(nome="Novo Caged", cor=AZUL, tipo="barra",
                           dados=[[k, round(v, 1)] for k, v in sorted(novo_s.items(), key=lambda x: int(x[0]))])])
    print("  Caged: 12 meses até %s = %.0f mil; setembros %s" %
          (max(doze), doze[max(doze)], {a: round(saldo[a + "-09"] / 1000, 1) for a in anos[-8:]}))
    return [g1, g2]


# ================================================================ Brasil: fiscal

RTN_URL = ("https://www.tesourotransparente.gov.br/ckan/dataset/ab56485b-9c40-4efb-8563-9ce3e1973c4b/resource/"
           "527ccdb1-3059-42f3-bf23-b5e3ab4c6dc6/download/serieh")


def rtn_real():
    """A tabela 1.1-A do Resultado do Tesouro Nacional: governo central, mensal,
    em R$ milhões a preços do último mês (IPCA). {rótulo: {AAAA-MM: valor}}.
    O servidor do Tesouro devolve erro com User-Agent de navegador: vai sem."""
    aba = cf.xlsx_aba(baixar(RTN_URL), "1.1-A")
    cab = next(r for r in aba.values() if str(r.get("A", "")).strip() == "Discriminação")
    datas = {c: cf.data_excel(v) for c, v in cab.items() if c != "A" and cf.numero(v) is not None}
    out = {}
    for r in aba.values():
        rot = re.sub(r"\s+", " ", str(r.get("A", ""))).strip()
        if not rot:
            continue
        out[rot] = {datas[c]: cf.numero(v) for c, v in r.items() if c in datas and cf.numero(v) is not None}
    deflator = next(r for r in aba.values() if str(r.get("A", "")).startswith("R$ Milhões"))
    return out, str(deflator.get("A"))


def graficos_fiscal():
    rtn, base = rtn_real()
    achar = lambda prefixo: next(v for k, v in rtn.items() if k.startswith(prefixo))      # noqa: E731
    desp, liq = achar("4. DESPESA TOTAL"), achar("3. RECEITA LÍQUIDA")
    nao_adm, t_edu, t_rec = (achar("1.4 - Receitas Não Administradas"), achar("2.3 Transferência de Contribuição"),
                             achar("2.4 Transferências de Exploração"))
    # receita líquida sem as receitas não administradas pela Receita Federal
    # (dividendos, royalties, concessões e outras), e sem as transferências
    # a estados e municípios que saem delas (salário-educação e royalties)
    sem = {m: liq[m] - nao_adm[m] + t_edu.get(m, 0) + t_rec.get(m, 0) for m in liq}

    def cresc12(s):
        ks = sorted(s)
        soma = {ks[i]: sum(s[k] for k in ks[i - 11:i + 1]) for i in range(11, len(ks))}
        return {m: 100 * (v / soma[cf.mes_mais(m, -12)] - 1) for m, v in soma.items() if cf.mes_mais(m, -12) in soma}
    ini = "2010-01"
    series = [serie("Despesa primária total", VERMELHO, desde(cresc12(desp), ini), 1, rotulo=True),
              serie("Receita primária líquida", AZUL, desde(cresc12(liq), ini), 1, rotulo=True),
              serie("Receita líquida sem as receitas não administradas pela RFB", VERDE,
                    desde(cresc12(sem), ini), 1, rotulo=True)]
    ult = max(desp)
    print("  RTN até %s (%s): despesa %.1f%%, receita líquida %.1f%%, sem não administradas %.1f%%"
          % (ult, base, cresc12(desp)[ult], cresc12(liq)[ult], cresc12(sem)[ult]))
    mes = cf.rot_mes(ult)
    return [dict(id="br-fiscal-crescimento-real", titulo="Governo central: crescimento real da despesa e da receita primária",
                 subtitulo="Variação real dos valores acumulados em 12 meses sobre os 12 meses anteriores, em %%; "
                           "a preços de %s (IPCA)" % mes,
                 unidade="%", fonte="Tesouro Nacional (Resultado do Tesouro Nacional, tabela 1.1-A) e FtM",
                 series=series)]


# ================================================================ montagem

def graficos_fomc_todos():
    f = fomc()
    return [f[k] for k in ("comunicados", "pmi", "datacenters", "pce", "payroll", "u6", "participacao", "treasuries")]


def graficos_midterms_todos():
    return graficos_midterms() + graficos_midterms_resultado()


GERADORES = [graficos_fomc_todos, graficos_midterms_todos, graficos_ia, graficos_anthropic, graficos_eleicao,
             graficos_focus, graficos_focus_ipca, graficos_copom, graficos_ipca_meta, graficos_ipca_grupos,
             graficos_caged, graficos_fiscal]

# Um gráfico por bloco, com o comentário dele logo antes (pedido dele). Os
# blocos sem título continuam a seção de cima; a ordem casa com a do texto.
SECOES = [("Decisão do FOMC", ["fomc-comunicados"]), ("", ["ism-pmi"]), ("", ["construcao-datacenters-fabricas"]),
          ("", ["pce-nucleos"]), ("", ["payroll-setores"]), ("", ["eua-u3-u6"]), ("", ["eua-participacao"]),
          ("", ["treasuries-5-10-30"]),
          ("Midterms", ["midterms-historia-aprovacao"]), ("", ["midterms-resultado-camara"]),
          ("", ["midterms-resultado-senado"]), ("", []),
          ("A venda das ações de IA", ["ia-indices"]), ("", ["ia-setores-semana"]), ("", ["ia-vix"]), ("", ["ia-divida"]),
          ("IPO da Anthropic", ["anthropic-receita-trimestral"]), ("", ["anthropic-margens"]),
          ("", ["anthropic-simulador"]),
          ("Eleição: bolsa, câmbio e juros", ["eleicoes-reacao"]), ("", ["br-ibovespa"]), ("", ["br-dolar"]),
          ("", ["br-curva-pre"]), ("", ["br-ntnb-2035"]),
          ("Expectativas do Focus", ["br-focus"]), ("", ["ipca-projecoes-focus"]),
          ("Decisão do Copom", ["copom-comunicados"]), ("", ["ipca-distancia-meta"]),
          ("", ["servicos-industriais-alimentacao"]),
          ("Emprego formal", ["br-caged-12m"]), ("", ["br-caged-setembro"]),
          ("A principal questão para o próximo ano", ["br-fiscal-crescimento-real"])]


def main():
    graficos = {}
    for f in GERADORES:
        print(f.__name__ + "…")
        for g in f():
            graficos[g["id"]] = g
    usados = [i for _, ids in SECOES for i in ids]
    faltam = [i for i in usados if i not in graficos]
    if faltam:
        raise SystemExit("gráficos que o texto pede e ninguém gerou: %s" % ", ".join(faltam))
    secoes = [dict(titulo=titulo, texto="", fontes=[], figuras=[], graficos=[graficos[i] for i in ids])
              for titulo, ids in SECOES]
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

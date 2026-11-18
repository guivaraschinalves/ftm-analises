#!/usr/bin/env python3
"""
Migração na Europa: fluxos, estoque de nascidos no exterior, origens e idade,
para a UE-27, Alemanha, França, Itália e Espanha. Gera dados/migracao-europa.json.
Só biblioteca padrão. Rodado à mão. O texto vem de textos/migracao-europa.md.

Pedido dele em 18/11/2026, a partir do md "ftm-analises-migracao-europa-graficos"
(OpenBot). Os números saem da API do Eurostat, não do md; batem com ele.

DE ONDE VEM CADA COISA (API de disseminação do Eurostat, JSON-stat)

  - demo_pjan: população em 1º de janeiro (série histórica e 2024 para as taxas de fluxo).
  - migr_imm8 e migr_emi2: imigração e emigração anuais, totais (idade
    completa). Incluem o retorno de nativos e, na UE-27, a mudança entre países
    da UE.
  - migr_imm5prv e migr_emi3nxt: imigração por país de residência anterior e
    emigração por país de destino seguinte (2020–2024, critério uniforme
    pós-Brexit NEU27_2020_FOR para fluxos apenas com países fora da UE-27).
  - migr_pop3ctb: população em 1º/jan/2025 por país de nascimento (total,
    nascidos no exterior, na UE e fora dela) e por faixa de 5 anos.
  - migr_imm3ctb: imigração de 2024 por país de nascimento e faixa de 5 anos
    (para a idade, a "alcançada no ano", REACH: a única que a França publica).
    A França não abre os países de fora da UE; a UE-27 não abre país nenhum.
    A idade dos novos imigrantes da UE-27 não sai pronta: é a soma dos países
    que publicam a abertura por idade.
  - Idade média: ponto médio de cada faixa (2,5; 7,5; ...; 82,5) e 88,5 para
    85+, como no md.
  - Our World in Data (UN DESA, International Migrant Stock 2024):
    migrant-stock-share e migrant-stock-total (1990–2024), para Europa e
    América do Norte em % da população e em milhares de pessoas.
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
SAIDA = os.path.join(RAIZ, "dados", "migracao-europa.json")
API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
OWID = "https://ourworldindata.org/grapher/"
UA = {"User-Agent": "ftm-analises"}

AZUL, VERMELHO, VERDE = "#4F81BD", "#C0504D", "#9BBB59"
AZUL_CLARO, LARANJA, BRANCO = "#8EB4E3", "#F79646", "#FFFFFF"

TERR = [("EU27_2020", "UE-27"), ("DE", "Alemanha"), ("FR", "França"), ("IT", "Itália"), ("ES", "Espanha")]
UE = ["BE", "BG", "CZ", "DK", "DE", "EE", "IE", "EL", "ES", "FR", "HR", "IT", "CY", "LV", "LT", "LU", "HU", "MT",
      "NL", "AT", "PL", "PT", "RO", "SI", "SK", "FI", "SE"]
FAIXAS = ["Y_LT5", "Y5-9", "Y10-14", "Y15-19", "Y20-24", "Y25-29", "Y30-34", "Y35-39", "Y40-44", "Y45-49",
          "Y50-54", "Y55-59", "Y60-64", "Y65-69", "Y70-74", "Y75-79", "Y80-84", "Y_GE85"]
ROT_FAIXAS = ["0–4", "5–9", "10–14", "15–19", "20–24", "25–29", "30–34", "35–39", "40–44", "45–49",
              "50–54", "55–59", "60–64", "65–69", "70–74", "75–79", "80–84", "85+"]
MEIOS = [2.5 + 5 * i for i in range(17)] + [88.5]
AGREGADOS = {"TOTAL", "FOR", "NAT", "EU27_2020_FOR", "NEU27_2020_FOR", "UNK", "STLS", "EU28_FOR", "NEU28_FOR",
             "EU27_2007_FOR", "NEU27_2007_FOR", "EU25_FOR", "NEU25_FOR", "EU15_FOR", "NEU15_FOR", "EFTA_FOR",
             "EU27_2020_NAT", "EFTA", "CC5_13_FOR", "NEU27_2020_NAT"}
# nomes em português dos países que podem aparecer no topo
NOMES = {"UA": "Ucrânia", "SY": "Síria", "TR": "Turquia", "RO": "Romênia", "IN": "Índia", "BD": "Bangladesh",
         "AL": "Albânia", "MA": "Marrocos", "PK": "Paquistão", "EG": "Egito", "CO": "Colômbia", "VE": "Venezuela",
         "PE": "Peru", "AR": "Argentina", "IT": "Itália", "DE": "Alemanha", "BE": "Bélgica", "ES": "Espanha",
         "PT": "Portugal", "PL": "Polônia", "BG": "Bulgária", "AF": "Afeganistão", "CN": "China", "BR": "Brasil",
         "TN": "Tunísia", "DZ": "Argélia", "NG": "Nigéria", "GE": "Geórgia", "RU": "Rússia", "US": "EUA",
         "UK": "Reino Unido", "FR": "França", "NL": "Países Baixos", "AT": "Áustria", "HR": "Croácia",
         "HU": "Hungria", "GR": "Grécia", "EL": "Grécia", "IQ": "Iraque", "IR": "Irã", "PH": "Filipinas",
         "LK": "Sri Lanka", "SN": "Senegal", "HN": "Honduras", "CU": "Cuba", "UY": "Uruguai", "CL": "Chile",
         "EC": "Equador", "BO": "Bolívia", "DO": "República Dominicana", "NP": "Nepal", "MD": "Moldávia",
         "RS": "Sérvia", "XK": "Kosovo", "MK": "Macedônia do Norte", "BA": "Bósnia", "KO": "Kosovo",
         "IE": "Irlanda", "CZ": "Tchéquia", "SK": "Eslováquia", "LT": "Lituânia", "LV": "Letônia",
         "SE": "Suécia", "DK": "Dinamarca", "FI": "Finlândia", "LU": "Luxemburgo", "NO": "Noruega",
         "CH": "Suíça", "SI": "Eslovênia", "CY": "Chipre", "MT": "Malta", "EE": "Estônia"}


def baixar(url, headers=None, tentativas=4):
    """Baixa uma URL usando apenas biblioteca padrão, com retentativas."""
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:                               # noqa: BLE001
            ultimo = e
            time.sleep(2 * (i + 1))
    raise RuntimeError("não deu para baixar %s: %s" % (url, ultimo))


def eurostat(codigo, chaves, **filtros):
    """{tupla com os códigos das dimensões em `chaves`, nessa ordem: valor}, mais os rótulos."""
    pares = []
    for k, v in filtros.items():
        for x in (v if isinstance(v, list) else [v]):
            pares.append("%s=%s" % (k, x))
    r = json.loads(baixar(API + codigo + "?format=JSON&lang=EN&" + "&".join(pares), headers=UA))
    ids, tam = r["id"], r["size"]
    cats = [sorted(r["dimension"][d]["category"]["index"].items(), key=lambda kv: kv[1]) for d in ids]
    varia = [ids.index(c) for c in chaves]
    out = {}
    for pos, v in r["value"].items():
        pos, coord = int(pos), []
        for i in reversed(range(len(ids))):
            coord.append(pos % tam[i])
            pos //= tam[i]
        coord.reverse()
        chave = tuple(cats[i][coord[i]][0] for i in varia)
        out[chave if len(chave) > 1 else chave[0]] = v
    rotulos = {d: r["dimension"][d]["category"].get("label", {}) for d in ids}
    return out, rotulos


def br(v, casas=1):
    s = "{:,.{c}f}".format(v, c=casas)
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def conferir(condicao, msg):
    if not condicao:
        raise RuntimeError("conferência falhou: " + msg)


def owid(slug, coluna):
    """Baixa CSV do Our World in Data e retorna {(entity, year): float}."""
    url = OWID + slug + ".csv?v=1&csvType=full&useColumnShortNames=true"
    txt = baixar(url, headers=UA).decode("utf-8")
    out = {}
    for row in csv.DictReader(io.StringIO(txt)):
        v = row.get(coluna, "").strip()
        if v:
            out[(row["entity"], row["year"])] = float(v)
    return out


ANOS_EXTRA = ["2020", "2021", "2022", "2023", "2024"]


def main():
    geos = [g for g, _ in TERR]
    pop_t, _ = eurostat("demo_pjan", ["geo", "time"], geo=geos, age="TOTAL", sex="T")
    imi_t, _ = eurostat("migr_imm8", ["geo", "time"], geo=geos, age="TOTAL", sex="T", agedef="COMPLET")
    emi_t, _ = eurostat("migr_emi2", ["geo", "time"], geo=geos, age="TOTAL", sex="T", agedef="COMPLET")
    # fluxos por residência anterior / destino seguinte (2020–2024: corte uniforme pós-Brexit fora da UE-27)
    partes = ["TOTAL", "EU27_2020_FOR", "NEU27_2020_FOR", "UNK"]
    imm_prv, _ = eurostat("migr_imm5prv", ["geo", "partner", "time"], geo=geos, time=ANOS_EXTRA,
                          age="TOTAL", sex="T", agedef="COMPLET", partner=partes)
    emi_nxt, _ = eurostat("migr_emi3nxt", ["geo", "partner", "time"], geo=geos, time=ANOS_EXTRA,
                          age="TOTAL", sex="T", agedef="COMPLET", partner=partes)
    # estoque em 1º/jan/2025 por bloco de nascimento e idade (inclui o total da população)
    est, _ = eurostat("migr_pop3ctb", ["geo", "c_birth", "age"], geo=geos, time="2025", sex="T", age=["TOTAL"] + FAIXAS,
                      c_birth=["TOTAL", "FOR", "EU27_2020_FOR", "NEU27_2020_FOR"])
    # fluxo de 2024 por país de nascimento (todos) no total de idades; e por idade para os nascidos fora
    flu, rot = eurostat("migr_imm3ctb", ["geo", "c_birth"], geo=geos, time="2024", sex="T", age="TOTAL", agedef="COMPLET")
    # idade "alcançada no ano" (REACH): é a que a França publica, e a do md
    flu_idade, _ = eurostat("migr_imm3ctb", ["geo", "age"], geo=geos + [g for g in UE if g not in geos], time="2024",
                            sex="T", agedef="REACH", c_birth="FOR", age=FAIXAS)
    nomes_pais = rot.get("c_birth", {})

    anos_por_geo = {}
    for g in geos:
        ys = sorted({t for gg, t in pop_t if gg == g}
                    & {t for gg, t in imi_t if gg == g}
                    & {t for gg, t in emi_t if gg == g}, key=int)
        conferir(len(ys) >= 10 and ys[-1] == "2024", "%s série histórica insuficiente ou sem 2024" % g)
        conferir(len(ys) == int(ys[-1]) - int(ys[0]) + 1, "%s buraco inesperado na série histórica" % g)
        for y in ys:
            conferir(pop_t.get((g, y), 0) > 0 and imi_t.get((g, y), 0) > 0 and emi_t.get((g, y), 0) > 0,
                     "%s sem população ou fluxos em %s" % (g, y))
        conferir(abs(imi_t[(g, "2024")] - flu[(g, "TOTAL")]) <= 1,
                 "%s migr_imm8 2024 (%s) != migr_imm3ctb TOTAL (%s)" % (g, imi_t[(g, "2024")], flu[(g, "TOTAL")]))
        for y in ANOS_EXTRA:
            conferir(imm_prv.get((g, "TOTAL", y)) == imi_t[(g, y)],
                     "%s migr_imm5prv TOTAL %s != migr_imm8" % (g, y))
            conferir(emi_nxt.get((g, "TOTAL", y)) == emi_t[(g, y)],
                     "%s migr_emi3nxt TOTAL %s != migr_emi2" % (g, y))
            conferir(imm_prv.get((g, "NEU27_2020_FOR", y), 0) > 0 and emi_nxt.get((g, "NEU27_2020_FOR", y), 0) > 0,
                     "%s sem fluxo extra-UE em %s" % (g, y))
            soma_im = sum(imm_prv.get((g, p, y), 0) for p in ("EU27_2020_FOR", "NEU27_2020_FOR", "UNK"))
            soma_em = sum(emi_nxt.get((g, p, y), 0) for p in ("EU27_2020_FOR", "NEU27_2020_FOR", "UNK"))
            if g == "EU27_2020":
                conferir(soma_im <= imm_prv[(g, "TOTAL", y)] and soma_em <= emi_nxt[(g, "TOTAL", y)],
                         "%s parcelas extra/intra passam do TOTAL em %s" % (g, y))
            else:
                conferir(soma_im == imm_prv[(g, "TOTAL", y)] and soma_em == emi_nxt[(g, "TOTAL", y)],
                         "%s EU + fora UE + UNK != TOTAL em %s" % (g, y))
        anos_por_geo[g] = ys
        conferir(est[(g, "EU27_2020_FOR", "TOTAL")] + est[(g, "NEU27_2020_FOR", "TOTAL")] == est[(g, "FOR", "TOTAL")],
                 "%s estoque UE + fora UE != FOR" % g)
        conferir(sum(est[(g, "TOTAL", f)] for f in FAIXAS) == est[(g, "TOTAL", "TOTAL")],
                 "%s soma das faixas etárias != TOTAL" % g)
        conferir(sum(est[(g, "FOR", f)] for f in FAIXAS) == est[(g, "FOR", "TOTAL")],
                 "%s soma das faixas etárias (FOR) != FOR TOTAL" % g)
        conferir(flu.get((g, "EU27_2020_FOR"), 0) + flu.get((g, "NEU27_2020_FOR"), 0) == flu[(g, "FOR")],
                 "%s fluxo UE + fora UE != FOR" % g)

    # 1. fluxos em % da população e em milhares de pessoas (2024 e série histórica; total e fora da UE-27)
    cats = [n for _, n in TERR]
    im = {g: 100 * imi_t[(g, "2024")] / pop_t[(g, "2024")] for g in geos}
    em = {g: 100 * emi_t[(g, "2024")] / pop_t[(g, "2024")] for g in geos}
    im_ext = {g: 100 * imm_prv[(g, "NEU27_2020_FOR", "2024")] / pop_t[(g, "2024")] for g in geos}
    em_ext = {g: 100 * emi_nxt[(g, "NEU27_2020_FOR", "2024")] / pop_t[(g, "2024")] for g in geos}
    im_q = {g: imi_t[(g, "2024")] / 1000.0 for g in geos}
    em_q = {g: emi_t[(g, "2024")] / 1000.0 for g in geos}
    im_ext_q = {g: imm_prv[(g, "NEU27_2020_FOR", "2024")] / 1000.0 for g in geos}
    em_ext_q = {g: emi_nxt[(g, "NEU27_2020_FOR", "2024")] / 1000.0 for g in geos}
    for g, n in TERR:
        ys = anos_por_geo[g]
        print("  %s (%s–%s): imigração %.2f%% (%.0f mil; fora UE %.2f%%, %.0f mil), "
              "emigração %.2f%% (%.0f mil; fora UE %.2f%%, %.0f mil), "
              "saldo %+.2f p.p. (fora UE %+.2f p.p.)"
              % (n, ys[0], ys[-1], im[g], im_q[g], im_ext[g], im_ext_q[g],
                 em[g], em_q[g], em_ext[g], em_ext_q[g], im[g] - em[g], im_ext[g] - em_ext[g]))
    g_fluxos = dict(id="migracao-fluxos", titulo="Imigração e emigração, 2024",
                    subtitulo="Entradas e saídas no ano (em % da população em 1º/jan/2024 ou milhares de pessoas); "
                              "saldo = imigração menos emigração",
                    unidade="%", categorias=cats, agrupadas=True, barra=0.8,
                    fonte="Eurostat (migr_imm8, migr_emi2 e demo_pjan) e FtM",
                    variantes=[
                        dict(rot="Total (% pop.)", unidade="%",
                             fonte="Eurostat (migr_imm8, migr_emi2 e demo_pjan) e FtM",
                             series=[dict(nome="Imigração", cor=AZUL, tipo="barra", valores=True,
                                          dados=[[str(i), round(im[g], 2)] for i, g in enumerate(geos)]),
                                     dict(nome="Emigração", cor=VERMELHO, tipo="barra", valores=True,
                                          dados=[[str(i), round(em[g], 2)] for i, g in enumerate(geos)]),
                                     dict(nome="Saldo", cor=VERDE, tipo="barra", valores=True,
                                          dados=[[str(i), round(im[g] - em[g], 2)] for i, g in enumerate(geos)])]),
                        dict(rot="Fora da UE-27 (% pop.)", unidade="%",
                             fonte="Eurostat (migr_imm5prv, migr_emi3nxt e demo_pjan) e FtM",
                             series=[dict(nome="Imigração", cor=AZUL, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_ext[g], 2)] for i, g in enumerate(geos)]),
                                     dict(nome="Emigração", cor=VERMELHO, tipo="barra", valores=True,
                                          dados=[[str(i), round(em_ext[g], 2)] for i, g in enumerate(geos)]),
                                     dict(nome="Saldo", cor=VERDE, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_ext[g] - em_ext[g], 2)] for i, g in enumerate(geos)])]),
                        dict(rot="Total (mil)", unidade="mil",
                             fonte="Eurostat (migr_imm8 e migr_emi2) e FtM",
                             series=[dict(nome="Imigração", cor=AZUL, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_q[g], 1)] for i, g in enumerate(geos)]),
                                     dict(nome="Emigração", cor=VERMELHO, tipo="barra", valores=True,
                                          dados=[[str(i), round(em_q[g], 1)] for i, g in enumerate(geos)]),
                                     dict(nome="Saldo", cor=VERDE, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_q[g] - em_q[g], 1)] for i, g in enumerate(geos)])]),
                        dict(rot="Fora da UE-27 (mil)", unidade="mil",
                             fonte="Eurostat (migr_imm5prv e migr_emi3nxt) e FtM",
                             series=[dict(nome="Imigração", cor=AZUL, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_ext_q[g], 1)] for i, g in enumerate(geos)]),
                                     dict(nome="Emigração", cor=VERMELHO, tipo="barra", valores=True,
                                          dados=[[str(i), round(em_ext_q[g], 1)] for i, g in enumerate(geos)]),
                                     dict(nome="Saldo", cor=VERDE, tipo="barra", valores=True,
                                          dados=[[str(i), round(im_ext_q[g] - em_ext_q[g], 1)] for i, g in enumerate(geos)])]),
                    ])

    var_fluxos_tempo = []
    var_fluxos_tempo_qtd = []
    var_fluxos_fora = []
    var_fluxos_fora_qtd = []
    for g, n in TERR:
        ys = anos_por_geo[g]
        im_s = {y: 100 * imi_t[(g, y)] / pop_t[(g, y)] for y in ys}
        em_s = {y: 100 * emi_t[(g, y)] / pop_t[(g, y)] for y in ys}
        im_sq = {y: imi_t[(g, y)] / 1000.0 for y in ys}
        em_sq = {y: emi_t[(g, y)] / 1000.0 for y in ys}
        conferir(abs(im_s["2024"] - im[g]) < 1e-9 and abs(em_s["2024"] - em[g]) < 1e-9,
                 "%s 2024 histórico diverge do resumo" % g)
        var_fluxos_tempo.append(dict(rot=n, series=[
            dict(nome="Imigração", cor=AZUL, largura=4.5, rotulo=True,
                 dados=[["%s-01" % y, round(im_s[y], 2)] for y in ys]),
            dict(nome="Emigração", cor=VERMELHO, largura=4.5, rotulo=True,
                 dados=[["%s-01" % y, round(em_s[y], 2)] for y in ys]),
            dict(nome="Saldo", cor=VERDE, largura=5.5, rotulo=True,
                 dados=[["%s-01" % y, round(im_s[y] - em_s[y], 2)] for y in ys])]))
        var_fluxos_tempo_qtd.append(dict(rot=n, series=[
            dict(nome="Imigração", cor=AZUL, largura=4.5, rotulo=True,
                 dados=[["%s-01" % y, round(im_sq[y], 1)] for y in ys]),
            dict(nome="Emigração", cor=VERMELHO, largura=4.5, rotulo=True,
                 dados=[["%s-01" % y, round(em_sq[y], 1)] for y in ys]),
            dict(nome="Saldo", cor=VERDE, largura=5.5, rotulo=True,
                 dados=[["%s-01" % y, round(im_sq[y] - em_sq[y], 1)] for y in ys])]))

        im_es = {y: 100 * imm_prv[(g, "NEU27_2020_FOR", y)] / pop_t[(g, y)] for y in ANOS_EXTRA}
        em_es = {y: 100 * emi_nxt[(g, "NEU27_2020_FOR", y)] / pop_t[(g, y)] for y in ANOS_EXTRA}
        im_esq = {y: imm_prv[(g, "NEU27_2020_FOR", y)] / 1000.0 for y in ANOS_EXTRA}
        em_esq = {y: emi_nxt[(g, "NEU27_2020_FOR", y)] / 1000.0 for y in ANOS_EXTRA}
        conferir(abs(im_es["2024"] - im_ext[g]) < 1e-9 and abs(em_es["2024"] - em_ext[g]) < 1e-9,
                 "%s 2024 extra-UE histórico diverge do resumo" % g)
        var_fluxos_fora.append(dict(rot=n, series=[
            dict(nome="Imigração de fora da UE-27", cor=AZUL, largura=4.5, rotulo=True,
                 dados=[[str(i), round(im_es[y], 2)] for i, y in enumerate(ANOS_EXTRA)]),
            dict(nome="Emigração para fora da UE-27", cor=VERMELHO, largura=4.5, rotulo=True,
                 dados=[[str(i), round(em_es[y], 2)] for i, y in enumerate(ANOS_EXTRA)]),
            dict(nome="Saldo", cor=VERDE, largura=5.5, rotulo=True,
                 dados=[[str(i), round(im_es[y] - em_es[y], 2)] for i, y in enumerate(ANOS_EXTRA)])]))
        var_fluxos_fora_qtd.append(dict(rot=n, series=[
            dict(nome="Imigração de fora da UE-27", cor=AZUL, largura=4.5, rotulo=True,
                 dados=[[str(i), round(im_esq[y], 1)] for i, y in enumerate(ANOS_EXTRA)]),
            dict(nome="Emigração para fora da UE-27", cor=VERMELHO, largura=4.5, rotulo=True,
                 dados=[[str(i), round(em_esq[y], 1)] for i, y in enumerate(ANOS_EXTRA)]),
            dict(nome="Saldo", cor=VERDE, largura=5.5, rotulo=True,
                 dados=[[str(i), round(im_esq[y] - em_esq[y], 1)] for i, y in enumerate(ANOS_EXTRA)])]))
    g_fluxos_tempo = dict(id="migracao-fluxos-tempo",
                          titulo="Imigração e emigração em % da população ao longo do tempo",
                          subtitulo="Entradas e saídas anuais (inclui intra-UE), sobre a população em 1º de janeiro; "
                                    "saldo = imigração menos emigração, em pontos percentuais",
                          unidade="%", buracoMax=12,
                          fonte="Eurostat (migr_imm8, migr_emi2 e demo_pjan) e FtM",
                          variantes=var_fluxos_tempo)
    g_fluxos_tempo_qtd = dict(id="migracao-fluxos-tempo-qtd",
                              titulo="Imigração e emigração em milhares de pessoas ao longo do tempo",
                              subtitulo="Entradas e saídas anuais (inclui intra-UE); saldo = imigração menos emigração",
                              unidade="mil", buracoMax=12,
                              fonte="Eurostat (migr_imm8 e migr_emi2) e FtM",
                              variantes=var_fluxos_tempo_qtd)
    g_fluxos_fora = dict(id="migracao-fluxos-fora-ue-tempo",
                         titulo="Imigração e emigração de fora da UE-27 em % da população, 2020–2024",
                         subtitulo="Entradas vindas de fora da UE-27 e saídas para fora da UE-27 no ano, sobre a "
                                   "população em 1º de janeiro; saldo = entradas menos saídas, em pontos percentuais",
                         unidade="%", categorias=ANOS_EXTRA,
                         fonte="Eurostat (migr_imm5prv, migr_emi3nxt e demo_pjan) e FtM",
                         variantes=var_fluxos_fora)
    g_fluxos_fora_qtd = dict(id="migracao-fluxos-fora-ue-tempo-qtd",
                             titulo="Imigração e emigração de fora da UE-27 em milhares de pessoas, 2020–2024",
                             subtitulo="Entradas vindas de fora da UE-27 e saídas para fora da UE-27 no ano; "
                                       "saldo = entradas menos saídas",
                             unidade="mil", categorias=ANOS_EXTRA,
                             fonte="Eurostat (migr_imm5prv e migr_emi3nxt) e FtM",
                             variantes=var_fluxos_fora_qtd)

    # 2. estoque de nascidos no exterior (em % da população e em milhares de pessoas, 2025)
    pct = {b: {g: 100 * est[(g, b, "TOTAL")] / est[(g, "TOTAL", "TOTAL")] for g in geos}
           for b in ("FOR", "EU27_2020_FOR", "NEU27_2020_FOR")}
    est_q = {b: {g: est[(g, b, "TOTAL")] / 1000.0 for g in geos}
             for b in ("FOR", "EU27_2020_FOR", "NEU27_2020_FOR")}
    tot = "; ".join("%s %s%% (%s mi)" % (n, br(pct["FOR"][g]), br(est_q["FOR"][g] / 1000.0)) for g, n in TERR)
    g_estoque = dict(id="migracao-estoque", titulo="Nascidos no exterior, 1º de janeiro de 2025",
                     subtitulo="Residentes nascidos em outro país, por bloco de nascimento; total: %s" % tot,
                     unidade="%", categorias=cats, barra=0.6,
                     fonte="Eurostat (migr_pop3ctb) e FtM",
                     variantes=[
                         dict(rot="% da população", unidade="%",
                              series=[dict(nome="Nascidos em outro país da UE", cor=AZUL_CLARO, tipo="barra",
                                           dados=[[str(i), round(pct["EU27_2020_FOR"][g], 2)] for i, g in enumerate(geos)]),
                                      dict(nome="Nascidos fora da UE", cor=AZUL, tipo="barra",
                                           dados=[[str(i), round(pct["NEU27_2020_FOR"][g], 2)] for i, g in enumerate(geos)])]),
                         dict(rot="Milhares de pessoas", unidade="mil",
                              series=[dict(nome="Nascidos em outro país da UE", cor=AZUL_CLARO, tipo="barra",
                                           dados=[[str(i), round(est_q["EU27_2020_FOR"][g], 1)] for i, g in enumerate(geos)]),
                                      dict(nome="Nascidos fora da UE", cor=AZUL, tipo="barra",
                                           dados=[[str(i), round(est_q["NEU27_2020_FOR"][g], 1)] for i, g in enumerate(geos)])]),
                     ])

    # 2b. Europa x América do Norte, 1990–2024 (UN DESA 2024 via Our World in Data)
    anos_owid = ["1990", "1995", "2000", "2005", "2010", "2015", "2020", "2024"]
    owid_pct = owid("migrant-stock-share", "immigrant_share_of_dest_population_all")
    owid_tot = owid("migrant-stock-total", "immigrants_all")
    for ent in ("Europe", "North America", "European Union (27)"):
        for y in anos_owid:
            conferir((ent, y) in owid_pct and (ent, y) in owid_tot, "OWID sem dado para %s em %s" % (ent, y))
            conferir(0.0 < owid_pct[(ent, y)] < 50.0 and owid_tot[(ent, y)] > 0,
                     "OWID valor inválido para %s em %s" % (ent, y))
    for y in anos_owid:
        conferir(owid_tot[("Europe", y)] > owid_tot[("European Union (27)", y)],
                 "OWID Europe <= EU27 em %s" % y)
    conferir(abs(owid_tot[("Europe", "2024")] / (owid_pct[("Europe", "2024")] / 100.0) - 744.6e6) < 20e6,
             "OWID população implícita da Europa em 2024 fora da faixa esperada")
    print("  OWID 2024: Europa %.2f%% (%.0f mil); América do Norte %.2f%% (%.0f mil)"
          % (owid_pct[("Europe", "2024")], owid_tot[("Europe", "2024")] / 1000.0,
             owid_pct[("North America", "2024")], owid_tot[("North America", "2024")] / 1000.0))
    g_europa_an = dict(id="migracao-europa-america-norte",
                       titulo="População nascida no exterior: Europa e América do Norte, 1990–2024",
                       subtitulo="Imigrantes residentes nascidos em outro país (definição continental do Our World "
                                 "in Data: América do Norte inclui América Central e Caribe)",
                       unidade="%", categorias=anos_owid,
                       fonte="UN DESA (International Migrant Stock 2024, via Our World in Data)",
                       variantes=[
                           dict(rot="% da população", unidade="%",
                                series=[dict(nome="Europa", cor=AZUL, largura=5, rotulo=True,
                                             dados=[[str(i), round(owid_pct[("Europe", y)], 2)]
                                                    for i, y in enumerate(anos_owid)]),
                                        dict(nome="América do Norte", cor=VERMELHO, largura=5, rotulo=True,
                                             dados=[[str(i), round(owid_pct[("North America", y)], 2)]
                                                    for i, y in enumerate(anos_owid)])]),
                           dict(rot="Milhares de pessoas", unidade="mil",
                                series=[dict(nome="Europa", cor=AZUL, largura=5, rotulo=True,
                                             dados=[[str(i), round(owid_tot[("Europe", y)] / 1000.0, 1)]
                                                    for i, y in enumerate(anos_owid)]),
                                        dict(nome="América do Norte", cor=VERMELHO, largura=5, rotulo=True,
                                             dados=[[str(i), round(owid_tot[("North America", y)] / 1000.0, 1)]
                                                    for i, y in enumerate(anos_owid)])]),
                       ])

    # 3. de onde vêm os novos imigrantes nascidos no exterior (2024: % e milhares)
    variantes, variantes_qtd, fora, fora_qtd = [], [], {}, {}
    for g, n in TERR:
        total = flu[(g, "FOR")]
        n_fora = flu.get((g, "NEU27_2020_FOR"), 0)
        fora[n] = 100 * n_fora / total
        fora_qtd[n] = n_fora / 1000.0
        if g == "EU27_2020":    # a UE-27 não abre país nenhum: só UE contra fora da UE
            variantes.append(dict(rot=n + " (só UE x fora da UE)", itens=[
                ["Nascidos fora da UE", round(fora[n], 1), AZUL],
                ["Nascidos em outro país da UE", round(100 - fora[n], 1), AZUL_CLARO]]))
            variantes_qtd.append(dict(rot=n + " (só UE x fora da UE)", itens=[
                ["Nascidos fora da UE", round(n_fora / 1000.0, 1), AZUL],
                ["Nascidos em outro país da UE", round((total - n_fora) / 1000.0, 1), AZUL_CLARO]]))
            continue
        # só países (código de duas letras); os agregados regionais têm código maior
        paises = {c: v for (gg, c), v in flu.items()
                  if gg == g and len(c) == 2 and c not in AGREGADOS and c != g and v}
        if g == "FR":       # a França não abre os países de fora da UE
            paises = {c: v for c, v in paises.items() if c in UE}
        top = sorted(paises.items(), key=lambda kv: -kv[1])[:5]
        itens = [[NOMES.get(c, nomes_pais.get(c, c)), round(100 * v / total, 1), AZUL if c not in UE else AZUL_CLARO]
                 for c, v in top]
        itens_qtd = [[NOMES.get(c, nomes_pais.get(c, c)), round(v / 1000.0, 1), AZUL if c not in UE else AZUL_CLARO]
                     for c, v in top]
        rot_v = n + (" (só países da UE)" if g == "FR" else "")
        variantes.append(dict(rot=rot_v, itens=itens))
        variantes_qtd.append(dict(rot=rot_v, itens=itens_qtd))
        print("  %s: %s" % (n, ", ".join("%s %.1f%%" % (a, b) for a, b, _ in itens)))
    g_origens = dict(id="migracao-origens", tipo="ranking", unidade="%",
                     titulo="Os cinco principais países de nascimento dos novos imigrantes, 2024",
                     subtitulo="%% dos imigrantes nascidos no exterior que chegaram no ano; azul claro = país da UE; "
                               "nascidos fora da UE: %s" % "; ".join("%s %s%%" % (n, br(v)) for n, v in fora.items()),
                     fonte="Eurostat (migr_imm3ctb) e FtM", itens=variantes[0]["itens"], variantes=variantes)
    g_origens_qtd = dict(id="migracao-origens-qtd", tipo="ranking", unidade="mil",
                         titulo="Os cinco principais países de nascimento dos novos imigrantes, 2024 (em milhares)",
                         subtitulo="Milhares de imigrantes nascidos no exterior que chegaram no ano; azul claro = país "
                                   "da UE; nascidos fora da UE: %s"
                                   % "; ".join("%s %s mil" % (n, br(v, 0)) for n, v in fora_qtd.items()),
                         fonte="Eurostat (migr_imm3ctb) e FtM", itens=variantes_qtd[0]["itens"],
                         variantes=variantes_qtd)

    # 4. idade: residentes e estoque de 2025, novos imigrantes de 2024 (distribuição % e milhares)
    def dist(contagem):
        s = sum(contagem)
        return [100 * x / s for x in contagem]

    def media(d):
        return sum(m * p for m, p in zip(MEIOS, d)) / 100
    var_idade, var_idade_qtd, medias = [], [], {}
    for g, n in TERR:
        resid_n = [est[(g, "TOTAL", f)] for f in FAIXAS]
        estoq_n = [est[(g, "FOR", f)] for f in FAIXAS]
        resid = dist(resid_n)
        estoq = dist(estoq_n)
        if all((g, f) in flu_idade for f in FAIXAS):
            novos_n, base = [flu_idade[(g, f)] for f in FAIXAS], None
        else:              # a UE-27 não publica: soma dos países que publicam todas as faixas
            com = [p for p in UE if all((p, f) in flu_idade for f in FAIXAS)]
            conferir(len(com) >= 20, "UE-27 com poucos países publicando idade: %d" % len(com))
            novos_n = [sum(flu_idade[(p, f)] for p in com) for f in FAIXAS]
            base = com
        novos = dist(novos_n)
        for nome_dist, d in (("resid", resid), ("estoq", estoq), ("novos", novos)):
            conferir(abs(sum(d) - 100.0) < 1e-6, "%s %s não soma 100%% (%.6f)" % (g, nome_dist, sum(d)))
        medias[g] = (media(resid), media(estoq), media(novos))
        print("  %s: idade média residentes %.1f, estoque %.1f, novos %.1f%s"
              % (n, medias[g][0], medias[g][1], medias[g][2], "" if base is None else
                 " (novos: %d países)" % len(base)))
        var_idade.append(dict(rot=n, series=[
            dict(nome="População residente, 2025", cor=AZUL_CLARO, tipo="barra",
                 dados=[[str(i), round(v, 2)] for i, v in enumerate(resid)]),
            dict(nome="Nascidos no exterior, estoque de 2025", cor=LARANJA, largura=6, traco="pontilhado",
                 dados=[[str(i), round(v, 2)] for i, v in enumerate(estoq)]),
            dict(nome="Novos imigrantes nascidos no exterior, 2024", cor=BRANCO, largura=5,
                 dados=[[str(i), round(v, 2)] for i, v in enumerate(novos)])]))
        var_idade_qtd.append(dict(rot=n, series=[
            dict(nome="População residente, 2025", cor=AZUL_CLARO, tipo="barra",
                 dados=[[str(i), round(v / 1000.0, 1)] for i, v in enumerate(resid_n)]),
            dict(nome="Nascidos no exterior, estoque de 2025", cor=LARANJA, largura=6, traco="pontilhado",
                 dados=[[str(i), round(v / 1000.0, 1)] for i, v in enumerate(estoq_n)]),
            dict(nome="Novos imigrantes nascidos no exterior, 2024", cor=BRANCO, largura=5,
                 dados=[[str(i), round(v / 1000.0, 1)] for i, v in enumerate(novos_n)])]))
    g_idade = dict(id="migracao-idade", titulo="Distribuição por idade: residentes, imigrantes e novos imigrantes",
                   subtitulo="% de cada grupo em cada faixa de 5 anos; a UE-27 dos novos imigrantes soma os países "
                             "que publicam a idade",
                   unidade="%", categorias=ROT_FAIXAS, barra=0.8, eixo=dict(min=0, max=20),
                   fonte="Eurostat (migr_pop3ctb e migr_imm3ctb) e FtM", variantes=var_idade)
    g_idade_qtd = dict(id="migracao-idade-qtd",
                       titulo="População por idade: residentes, imigrantes e novos imigrantes (em milhares)",
                       subtitulo="Milhares de pessoas em cada faixa de 5 anos; a UE-27 dos novos imigrantes soma os "
                                 "países que publicam a idade",
                       unidade="mil", categorias=ROT_FAIXAS, barra=0.8,
                       fonte="Eurostat (migr_pop3ctb e migr_imm3ctb) e FtM", variantes=var_idade_qtd)
    g_media = dict(id="migracao-idade-media", titulo="Idade média: residentes, imigrantes e novos imigrantes",
                   subtitulo="Anos, pelo ponto médio das faixas de 5 anos; residentes e estoque em 1º/jan/2025, "
                             "novos imigrantes em 2024",
                   unidade="anos", categorias=cats, agrupadas=True, barra=0.8,
                   fonte="Eurostat (migr_pop3ctb e migr_imm3ctb) e FtM",
                   series=[dict(nome="População residente", cor=AZUL_CLARO, tipo="barra", valores=True,
                                dados=[[str(i), round(medias[g][0], 1)] for i, g in enumerate(geos)]),
                           dict(nome="Nascidos no exterior (estoque)", cor=LARANJA, tipo="barra", valores=True,
                                dados=[[str(i), round(medias[g][1], 1)] for i, g in enumerate(geos)]),
                           dict(nome="Novos imigrantes", cor=BRANCO, tipo="barra", valores=True,
                                dados=[[str(i), round(medias[g][2], 1)] for i, g in enumerate(geos)])])

    hoje = datetime.date.today().isoformat()
    doc = dict(assunto="Migração na Europa", grupo="Análises Variadas", fonte="Eurostat e FtM",
               referencia="2025-01", atualizado=hoje, formato="artigo",
               secoes=[dict(titulo="Quem chega e quem sai", texto="", fontes=[], figuras=[],
                            graficos=[g_fluxos, g_fluxos_tempo, g_fluxos_tempo_qtd, g_fluxos_fora, g_fluxos_fora_qtd]),
                       dict(titulo="Quantos nasceram fora", texto="", fontes=[], figuras=[],
                            graficos=[g_estoque, g_europa_an]),
                       dict(titulo="De onde vêm", texto="", fontes=[], figuras=[], graficos=[g_origens, g_origens_qtd]),
                       dict(titulo="A idade de quem chega", texto="", fontes=[], figuras=[],
                            graficos=[g_idade, g_idade_qtd, g_media])])
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado", SAIDA)
    sys.path.insert(0, os.path.dirname(__file__))
    import aplicar_texto
    if aplicar_texto.aplicar("migracao-europa.md", "migracao-europa.json"):
        raise RuntimeError("falha ao aplicar textos/migracao-europa.md")


if __name__ == "__main__":
    main()

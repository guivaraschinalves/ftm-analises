#!/usr/bin/env python3
"""
Monta dados/missao-global-miami.json, a página da Missão Global Miami. Por
enquanto, só a leitura do cenário brasileiro: a Selic com as recessões e com
os ciclos de alta e de corte.

Uso:
    python3 scripts/missao_miami.py

Só biblioteca padrão. Rodado à mão. O texto vem de textos/missao-global-miami.md
(aplicar_texto, no fim).

DE ONDE VEM CADA COISA

  - Selic: meta definida pelo Copom, SGS 432 (diária, desde 05/03/1999, quando
    o Copom passou a fixar a meta). A data é a de vigência, o dia seguinte à
    reunião.
  - Recessões: CODACE (Comitê de Datação de Ciclos Econômicos, FGV IBRE).
    A faixa vai do mês seguinte ao pico até o vale, como o FRED faz com o
    NBER. Até 2016 é a datação mensal (comunicados de 03/02/2010 e de
    30/10/2017); a recessão de 2020 só tem datação trimestral (pico no 4º tri
    de 2019, comunicado de 29/06/2020; vale no 2º tri de 2020, comunicado de
    02/02/2023), então vai de jan a jun/2020.
  - Ciclos: calculados aqui. Um ciclo de alta é a sequência de altas da meta
    sem nenhum corte no meio; o de corte, o contrário. Pausa curta não encerra
    o ciclo (a de abr a out/2014, na eleição, fica dentro do de 2013-15), mas
    um ano ou mais sem mudança, sim (os cortes de 2016-18 e de 2019-20 são
    dois ciclos). A faixa vai da vigência da primeira mudança à da última, e a
    duração é esse intervalo em meses.
"""
import datetime
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import cenario_fomc as cf                                     # noqa: E402
import cenario_novembro as cn                                 # noqa: E402

NOME = "missao-global-miami"
SAIDA = os.path.join(RAIZ, "dados", NOME + ".json")
AZUL, VERMELHO, VERDE = cf.AZUL, cf.VERMELHO, cf.VERDE
MESES = cf.MESES

# (primeiro mês da recessão, último mês), já no padrão do FRED: do mês seguinte
# ao pico até o vale. As anteriores a 1999 ficam fora do eixo da Selic meta.
RECESSOES = [("1980-11", "1983-02"), ("1987-03", "1988-10"), ("1989-07", "1991-12"), ("1995-01", "1995-09"),
             ("1997-11", "1999-02"), ("2001-01", "2001-09"), ("2002-11", "2003-06"), ("2008-08", "2009-01"),
             ("2014-04", "2016-12"), ("2020-01", "2020-06")]


def fim_mes(m):
    d = datetime.date(int(m[:4]), int(m[5:7]), 28) + datetime.timedelta(days=4)
    return (d.replace(day=1) - datetime.timedelta(days=1)).isoformat()


def rot_dia(d):
    return "%s/%s/%s" % (d[8:], d[5:7], d[:4])


def rot_mes(d):
    return "%s/%s" % (MESES[int(d[5:7]) - 1], d[2:4])


def meses_entre(a, b):
    da, db = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    return round((db - da).days / 30.4375)


def ciclos(selic):
    """[(sentido, primeira mudança, última mudança, taxa antes, taxa no fim, nº de mudanças)]."""
    ks = sorted(selic)
    mudancas = [(k, selic[ant], selic[k]) for ant, k in zip(ks, ks[1:]) if selic[k] != selic[ant]]
    out = []
    for d, de, para in mudancas:
        sentido = "alta" if para > de else "corte"
        parado = out and (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(out[-1]["fim"])).days >= 365
        if out and out[-1]["sentido"] == sentido and not parado:
            out[-1].update(fim=d, para=para, n=out[-1]["n"] + 1)
        else:
            out.append(dict(sentido=sentido, ini=d, fim=d, de=de, para=para, n=1))
    return out


# ================================================================ ciclo
# O item 1 do roteiro (o ciclo), na ordem pedida por ele em 11/11/2026:
# atividade (PMS e PMC), PIB, crédito, confiança e emprego. PIB e crédito são
# cópias dos cartões do ftm-dados (como estão no GitHub); o resto sai daqui.

BRANCO, AZUL_CLARO, AZUL_ESCURO, CINZA = cf.BRANCO, "#8EB4E3", cf.AZUL_ESCURO, "#8a8a86"
SIDRA_UA = {"User-Agent": "Mozilla/5.0 (ftm-analises)"}
FONTE_ATIV = "IBGE (Pesquisa Mensal de Serviços e Pesquisa Mensal de Comércio) e FtM"
FONTE_PNAD = "IBGE (PNAD Contínua) e FtM"
INICIO_ATIV = "2012-01"      # a PMS começa em 2011; a variação em 12 meses, em 2012


def sidra(caminho):
    """Linhas da API do SIDRA, sem o cabeçalho e sem célula vazia ("...", "-")."""
    out = []
    for l in json.loads(cf.baixar("https://apisidra.ibge.gov.br/values/" + caminho, headers=SIDRA_UA))[1:]:
        try:
            l["v"] = float(l["V"])
        except (TypeError, ValueError):
            continue
        out.append(l)
    if not out:
        raise RuntimeError("SIDRA %s: nenhum dado" % caminho)
    return out


def mes(p):
    return "%s-%s" % (p[:4], p[4:6])


def rot_m(m):
    return "%s/%s" % (MESES[int(m[5:7]) - 1], m[2:4])


def mes_menos(m, k):
    t = int(m[:4]) * 12 + int(m[5:7]) - 1 - k
    return "%d-%02d" % (t // 12, t % 12 + 1)


def desde(d, ini):
    return {k: v for k, v in d.items() if k >= ini}


def graficos_ftm_dados(arq):
    """{id: cartão} de um JSON do ftm-dados."""
    gs = {}

    def anda(secs):
        for s in secs:
            for g in s.get("graficos", []):
                gs[g["id"]] = g
            anda(s.get("subsecoes", []))
    anda(cn.json_ftm_dados(arq)["secoes"])
    return gs


def sem_trimestral(g):
    """O app daqui não tem eixo trimestral: "AAAA-Qn" vira o mês em que o
    trimestre termina, e a linha liga de 3 em 3 meses."""
    g = json.loads(json.dumps(g))
    if not g.pop("trimestral", False):
        return g
    for grupo in [g] + g.get("variantes", []):
        for s in grupo.get("series", []):
            s["dados"] = [["%s-%02d" % (k[:4], 3 * int(k[-1])), v] for k, v in s["dados"]]
    g["buracoMax"] = 3
    return g


def direita(g):
    """Série no eixo da direita formata o número (rótulo e caixa do mouse)
    pela unidade dele; e o app daqui lê o unidade2 no gráfico, não no recorte."""
    for grupo in [g] + g.get("variantes", []):
        u2 = grupo.get("unidade2") or g.get("unidade2")
        if u2:
            g.setdefault("unidade2", u2)
        for s in grupo.get("series", []):
            if s.get("dir"):
                s["unidade"] = u2
    return g


def graficos_atividade():
    """Volume de serviços (PMS) e de vendas no varejo (PMC): variação em 12
    meses dos dois num gráfico; o nível (com ajuste sazonal) em outro, com os
    dois juntos ou cada um."""
    def tab(caminho):
        d = {}
        for l in sidra(caminho):
            d.setdefault(l["D2C"], {})[mes(l["D3C"])] = l["v"]
        return d
    pms = tab("t/5906/n1/all/v/7168,11626/p/all/c11046/56726")
    pmc = tab("t/8880/n1/all/v/7170,11711/p/all/c11046/56734")
    nomes = (("Serviços (PMS)", pms, "7168", "11626", AZUL), ("Varejo (PMC)", pmc, "7170", "11711", VERMELHO))
    for nome, d, nivel, doze, _ in nomes:
        ult, rec = max(d[nivel]), max(d[nivel], key=d[nivel].get)
        print("  %s: %s nível %.1f (recorde %s %.1f); 12 meses %.1f%%"
              % (nome, ult, d[nivel][ult], rec, d[nivel][rec], d[doze][max(d[doze])]))
    g12 = dict(id="atividade-12m", titulo="Volume de serviços e de vendas no varejo em 12 meses",
               subtitulo="Variação do volume acumulado em 12 meses sobre os 12 meses anteriores, em %",
               unidade="pct1", fonte=FONTE_ATIV,
               series=[cf.serie(n, c, desde(d[dz], INICIO_ATIV), 1, largura=5, rotulo=True)
                       for n, d, _, dz, c in nomes])

    def sozinho(nome, sa, cor):
        rec = max(sa, key=sa.get)
        linha = {m: v for m, v in ((m, None) for m in sa)}
        return dict(rot=nome, series=[
            cf.serie("Volume", cor, sa, 1, largura=5, rotulo=True),
            cf.serie("Fevereiro de 2020", AZUL_CLARO, {m: sa["2020-02"] for m in linha}, 1, traco="pontilhado",
                     largura=3, rotulo=True),
            cf.serie("Recorde (%s)" % rot_m(rec), CINZA, {m: sa[rec] for m in linha}, 1, traco="pontilhado",
                     largura=3, rotulo=True)])
    niveis = {n: desde(d[nv], "2011-01") for n, d, nv, _, _ in nomes}
    g_nivel = dict(id="atividade-nivel", titulo="Volume de serviços e de vendas no varejo",
                   subtitulo="Índice com ajuste sazonal, 2022 = 100; sozinhos, com fevereiro de 2020 (antes da "
                             "pandemia) e o recorde pontilhados",
                   unidade="ind", eixo={"zero": False}, fonte=FONTE_ATIV, variantes=[
                       dict(rot="Os dois", series=[cf.serie(n, c, niveis[n], 1, largura=5, rotulo=True)
                                                   for n, _, _, _, c in nomes]),
                       sozinho("Serviços (PMS)", niveis["Serviços (PMS)"], AZUL),
                       sozinho("Varejo (PMC)", niveis["Varejo (PMC)"], VERMELHO)])
    return [g12, g_nivel]


IDS_PIB = ["pib-familias-4tri", "pib-participacao"]
IDS_CREDITO = ["credito-concessoes-pf-pj", "credito-inadimplencia", "credito-servico-divida",
               "credito-endividamento", "credito-juros-selic", "credito-direcionado-livre", "credito-gap-bis"]
# outros cartões do ftm-dados que fecham o roteiro do ciclo: a inflação implícita
# dos serviços (volume × preço) e os serviços subjacentes, a ponte para a inflação
IDS_OUTROS = [("dados/pms.json", ["pms-inflacao-implicita"]), ("dados/ipca.json", ["ex3-servicos"])]
# o ftm-dados não põe fonte em alguns cartões
FONTES_COPIA = {"credito-inadimplencia": "Banco Central (SGS 21082, 21083 e 21084)",
                "credito-servico-divida": "Banco Central (SGS 29033, 29034 e 29036)",
                "credito-endividamento": "Banco Central (SGS 29037 e 29038)",
                "credito-juros-selic": "Banco Central (SGS 432 e 29033)",
                "ex3-servicos": "IBGE e Banco Central (SGS 13522, 433 e 29683)"}
# cores trocadas na cópia (paleta para daltonismo: ciano × verde não)
CORES_COPIA = {"ex3-servicos": {"IPCA": "#8a8a86", "EX3": AZUL}}
UNIDADES_COPIA = {"x2": "x"}       # unidades do ftm-dados que o app daqui chama por outro nome


OLINDA_TRI = ("https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
              "ExpectativasMercadoTrimestrais?$filter=Indicador%20eq%20'PIB%20Total'%20and%20baseCalculo%20eq%200"
              "&$orderby=Data%20desc&$top=40&$format=json")
OLINDA_ANO = ("https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
              "ExpectativasMercadoAnuais?$filter=Indicador%20eq%20'PIB%20Total'%20and%20baseCalculo%20eq%200"
              "&$orderby=Data%20desc&$top=10&$format=json")


def focus_pib_4tri():
    """PIB acumulado em 4 trimestres pela mediana do Focus, do último trimestre
    do IBGE até o 4º trimestre do ano seguinte. O Focus dá cada trimestre
    contra o mesmo trimestre do ano anterior; isso vira nível em cima do índice
    encadeado do IBGE (sem ajuste sazonal) e daí sai o acumulado em 4
    trimestres, que no 4º trimestre tem de bater com a mediana anual (a do
    boletim). Devolve ({"AAAA-MM": %}, data do Focus); o mês é o do fim do
    trimestre, como em sem_trimestral, e o primeiro ponto é o último oficial
    (para a linha pontilhada sair dele)."""
    nivel = {"%s-%02d" % (l["D3C"][:4], 3 * int(l["D3C"][4:])): l["v"]
             for l in sidra("t/1620/n1/all/v/583/p/all/c11255/90707")}
    oficial = max(nivel)
    tri = json.loads(cf.baixar(OLINDA_TRI))["value"]
    data = tri[0]["Data"]
    for x in sorted((x for x in tri if x["Data"] == data), key=lambda x: x["DataReferencia"].split("/")[::-1]):
        t, a = x["DataReferencia"].split("/")
        m = "%s-%02d" % (a, 3 * int(t))
        if m > oficial:
            nivel[m] = nivel["%d-%02d" % (int(a) - 1, 3 * int(t))] * (1 + x["Mediana"] / 100)
    ks = sorted(nivel)
    fim = "%d-12" % (int(oficial[:4]) + 1)
    acum = {ks[i]: 100 * (sum(nivel[j] for j in ks[i - 3:i + 1]) / sum(nivel[j] for j in ks[i - 7:i - 3]) - 1)
            for i in range(7, len(ks)) if oficial <= ks[i] <= fim}
    anual = {x["DataReferencia"]: x["Mediana"] for x in json.loads(cf.baixar(OLINDA_ANO))["value"]
             if x["Data"] == data}
    for k, v in acum.items():
        if k[5:] == "12" and k > oficial and abs(v - anual[k[:4]]) > 0.1:
            raise RuntimeError("Focus de %s: o trimestral dá %.2f%% em %s; o anual, %.2f%%"
                               % (data, v, k[:4], anual[k[:4]]))
    print("  Focus do PIB (%s): %s" % (data, ", ".join("%s %.2f%%" % kv for kv in sorted(acum.items()))))
    return acum, data


def com_focus(g):
    """Cartão do PIB em 4 trimestres com a mediana do Focus pontilhada."""
    acum, data = focus_pib_4tri()
    pib = next(s for s in g["series"] if s["nome"] == "PIB")
    if pib["dados"][-1][0] != min(acum):
        raise RuntimeError("PIB do ftm-dados até %s, o do SIDRA até %s" % (pib["dados"][-1][0], min(acum)))
    g["series"].insert(1, cf.serie("PIB, mediana do Focus", pib["cor"], acum, 1, traco="pontilhado",
                                   largura=3, rotulo=True))
    d = datetime.date.fromisoformat(data)
    g["subtitulo"] += "; pontilhado = mediana do Focus para o PIB (%d/%s)" % (d.day, MESES[d.month - 1].lower())
    g["fonte"] = "IBGE (Contas Nacionais Trimestrais), Banco Central (Focus) e FtM"
    return g


def graficos_pib_credito():
    out = []
    for arq, ids in [("dados/pib.json", IDS_PIB), ("dados/credito.json", IDS_CREDITO)] + IDS_OUTROS:
        gs = graficos_ftm_dados(arq)
        for i in ids:
            g = direita(sem_trimestral(gs[i]))
            g.pop("nota", None)
            if i == "pib-familias-4tri":
                g = com_focus(g)
            if i == "credito-endividamento":       # só o total, sem a linha "exceto habitacional"
                g["series"] = [x for x in g["series"] if x["nome"] == "Endividamento das famílias"]
            g["fonte"] = g.get("fonte") or FONTES_COPIA[i]
            g["unidade"] = UNIDADES_COPIA.get(g.get("unidade"), g.get("unidade"))
            for grupo in [g] + g.get("variantes", []):
                for x in grupo.get("series", []):
                    for trecho, cor in CORES_COPIA.get(i, {}).items():
                        if x["nome"].startswith(trecho) or trecho in x["nome"]:
                            x["cor"] = cor
            # o número em cima da barra: no ftm-dados é "valores" na série; aqui,
            # no gráfico, e só com "agrupadas" (com uma série de barras, dá no mesmo)
            if any(x.get("valores") for x in g.get("series", [])):
                g.update(agrupadas=True, valores=True)
            ult = max(k for grupo in [g] + g.get("variantes", []) for s in grupo.get("series", [])
                      for k, _ in s["dados"])
            print("  %-28s até %s" % (i, ult if not g.get("categorias") else g["categorias"][int(ult)]))
            out.append(g)
    return out


def graficos_cartao():
    """Cartão de crédito das pessoas físicas (recursos livres, SGS): saldo em
    12 meses descontado o IPCA (rotativo, cartão total e todo o crédito livre
    às famílias) e inadimplência (atraso acima de 90 dias). O rotativo é a
    parte cara: a fatura que não foi paga inteira."""
    def m(c):
        return cn.mensal(cn.sgs(c, "01/03/2011"))
    ipca = cn.mensal(cn.sgs(433, "01/01/2011"))
    ix, f = {}, 1.0
    for k in sorted(ipca):
        f *= 1 + ipca[k] / 100
        ix[k] = f

    def real12(d):
        return {k: 100 * ((v / ix[k]) / (d[a] / ix[a]) - 1) for k, v in d.items()
                for a in [mes_menos(k, 12)] if a in d and k in ix}
    saldo = [("Cartão rotativo", 20587, VERMELHO), ("Cartão de crédito total", 20590, AZUL),
             ("Crédito livre às famílias", 20570, CINZA)]
    inad = [("Cartão rotativo", 21127, VERMELHO), ("Cartão de crédito total", 21129, AZUL),
            ("Crédito livre às famílias", 21112, CINZA)]
    s12 = {n: real12(m(c)) for n, c, _ in saldo}
    ina = {n: m(c) for n, c, _ in inad}
    for n, _, _ in saldo:
        u = max(s12[n])
        print("  %-26s saldo real em 12 meses %s %.1f%%; inadimplência %.1f%%" % (n, u, s12[n][u], ina[n][max(ina[n])]))
    g_saldo = dict(id="credito-cartao-saldo", titulo="Saldo do cartão de crédito das famílias",
                   subtitulo="Variação do saldo em 12 meses, descontado o IPCA, em %; recursos livres",
                   unidade="pct1", fonte="Banco Central (SGS 20587, 20590 e 20570; IPCA: SGS 433) e FtM",
                   series=[cf.serie(n, c, s12[n], 1, largura=5, rotulo=True) for n, _, c in saldo])
    g_inad = dict(id="credito-cartao-inadimplencia", titulo="Inadimplência do cartão de crédito das famílias",
                  subtitulo="Atrasos acima de 90 dias, em % do saldo; recursos livres", unidade="pct1",
                  fonte="Banco Central (SGS 21127, 21129 e 21112)", variantes=[
                      dict(rot="Rotativo", series=[cf.serie(inad[0][0], VERMELHO, ina[inad[0][0]], 2, largura=5,
                                                            rotulo=True)]),
                      dict(rot="Cartão total e crédito livre", series=[
                          cf.serie(n, c, ina[n], 2, largura=5, rotulo=True) for n, _, c in inad[1:]])])
    return [g_saldo, g_inad]


FGV_COLUNAS = {1: "ICE", 2: "ISA-E", 3: "IE-E", 4: "ICST", 5: "IE-CST", 6: "ISA-CST", 8: "ICC", 9: "ISA-C",
               10: "IE-C"}


def fgv_confianca():
    """Os índices de confiança da FGV, com ajuste sazonal, da exportação do
    FGV Dados que ele sobe no ftm-dados (dados/xgvxConsulta*.xls, a mais nova
    pelo nome). Ele confirmou em 13/11/2026 que pode publicar. Colunas pela
    legenda da planilha: 1 ICE, 2 ISA-E, 3 IE-E, 4 ICST, 5 IE-CST, 6 ISA-CST,
    7 NUCI da construção (fora), 8 ICC, 9 ISA do consumidor, 10 IE do consumidor."""
    import subprocess
    import xls
    subprocess.run(["git", "-C", cn.FTM_DADOS, "fetch", "-q", "origin"], check=True)
    nomes = subprocess.run(["git", "-C", cn.FTM_DADOS, "ls-tree", "--name-only", "origin/main", "dados/"],
                           check=True, capture_output=True, text=True).stdout.split("\n")
    arq = sorted(n for n in nomes if "xgvxConsulta" in n)[-1]
    corpo = subprocess.run(["git", "-C", cn.FTM_DADOS, "show", "origin/main:" + arq], check=True,
                           capture_output=True).stdout
    cel = list(xls.abas(corpo).values())[0]
    # confere a legenda: as colunas mudam se ele exportar outras séries
    legenda = {int(float(cel[(r, 0)])): str(cel.get((r, 1), "")) for r in range(11, 22)
               if str(cel.get((r, 0), "")).strip().replace(".0", "").isdigit()}
    for col, sigla in FGV_COLUNAS.items():
        nome = legenda.get(col, "")
        esperado = {"ICE": "ICE ", "ISA-E": "ISA-E", "IE-E": "IE-E", "ICST": "ICST", "IE-CST": "IE-CST",
                    "ISA-CST": "ISA-CST", "ICC": "Confiança do Consumidor com", "ISA-C": "Situação Presente",
                    "IE-C": "Expectativas com"}[sigla]
        if esperado not in nome:
            raise RuntimeError("planilha da FGV: coluna %d não é %s (%s)" % (col, sigla, nome))
    ser = {sigla: {} for sigla in FGV_COLUNAS.values()}
    for (r, k), v in cel.items():
        if k in FGV_COLUNAS:
            d = str(cel.get((r, 0), ""))
            if len(d) == 7 and d[2] == "/":
                try:
                    ser[FGV_COLUNAS[k]]["%s-%s" % (d[3:], d[:2])] = float(v)
                except (TypeError, ValueError):
                    pass
    return arq, ser


def graficos_confianca():
    """Índices de confiança da FGV (com ajuste sazonal): empresarial (ICE, que
    junta indústria, serviços, comércio e construção pelo valor adicionado),
    consumidor (ICC) e construção (ICST), cada um com a situação atual e as
    expectativas. Padronizados: média 100 e desvio-padrão 10 entre jul/2010 e
    jun/2015 (100 é a média daquele período, não um ponto neutro)."""
    arq, s = fgv_confianca()
    grupos = [("Empresarial", "ICE", "ISA-E", "IE-E"), ("Consumidor", "ICC", "ISA-C", "IE-C"),
              ("Construção", "ICST", "ISA-CST", "IE-CST")]
    variantes = []
    for rot, ic, isa, ie in grupos:
        u = max(s[ic])
        print("  FGV %s (%s): %s %.1f; situação atual %.1f; expectativas %.1f (%s)"
              % (rot, ic, u, s[ic][u], s[isa][u], s[ie][u], arq))
        variantes.append(dict(rot=rot, series=[
            cf.serie("Confiança (%s)" % ic, BRANCO, s[ic], 1, largura=5, rotulo=True),
            cf.serie("Situação atual", AZUL, s[isa], 1, largura=3, rotulo=True),
            cf.serie("Expectativas", VERMELHO, s[ie], 1, largura=3, rotulo=True),
            cf.serie("Média de 2010 a 2015 (100)", CINZA, {m: 100 for m in s[ic]}, 0, traco="pontilhado",
                     largura=3)]))
    return [dict(id="confianca", titulo="Índices de confiança da FGV", unidade="ind", eixo={"zero": False},
                 subtitulo="Com ajuste sazonal; padronizados com média 100 e desvio-padrão 10 entre jul/2010 e "
                           "jun/2015 (cada 10 pontos = um desvio-padrão)",
                 fonte="FGV IBRE (Sondagens), via FGV Dados", variantes=variantes)]


SERASA_PAGINA = "https://www.serasaexperian.com.br/conteudos/indicadores-economicos/"
SERASA_UA = {"User-Agent": "Mozilla/5.0 (ftm-analises)"}


def xlsx_celulas(corpo, aba):
    """{(linha, coluna): texto} de uma aba de .xlsx (linha e coluna a partir de 1)."""
    import io
    import re
    import zipfile
    import xml.etree.ElementTree as ET
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    z = zipfile.ZipFile(io.BytesIO(corpo))
    sst = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
            sst.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    alvo = {r.get("Id"): r.get("Target") for r in rels}
    rid = next(sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
               for sh in wb.find("m:sheets", ns) if sh.get("name") == aba)
    caminho = "xl/" + alvo[rid].lstrip("/").replace("xl/", "")
    fora = {}
    for c in ET.fromstring(z.read(caminho)).iter("{%s}c" % ns["m"]):
        ref, v = c.get("r"), c.find("m:v", ns)
        if v is None:
            continue
        letras = re.match(r"[A-Z]+", ref).group(0)
        col = 0
        for ch in letras:
            col = col * 26 + ord(ch) - 64
        fora[(int(ref[len(letras):]), col)] = sst[int(v.text)] if c.get("t") == "s" else v.text
    return fora


def graficos_recuperacoes():
    """Recuperações judiciais requeridas (Serasa Experian), mensal. A Serasa só
    abre os dois anos mais recentes (desde jan/2024): série mais longa é paga.
    A planilha muda de nome a cada mês (falencias-e-recuperacoes-<mês><ano>.xlsx)
    e é achada pelo link na página de indicadores. Abas "Total de Processos"
    (pedidos) e "Total de CNPJs Setor" (empresas envolvidas, por setor)."""
    import re
    pagina = cf.baixar(SERASA_PAGINA, headers=SERASA_UA).decode("utf-8", "replace")
    links = sorted(set(re.findall(r'/content/dam/[^"\' ]*falencias-e-recuperacoes-[^"\' ]*\.xlsx', pagina)))
    if not links:
        raise RuntimeError("Serasa: link da planilha de falências e recuperações não encontrado")
    url = "https://www.serasaexperian.com.br" + links[-1]
    corpo = cf.baixar(url, headers=SERASA_UA)

    def mes_excel(v):
        d = datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(v)))
        return d.strftime("%Y-%m")
    proc = xlsx_celulas(corpo, "Total de Processos")
    rj, fal = {}, {}
    for r in range(5, 200):
        if (r, 1) in proc and (r, 4) in proc and str(proc[(r, 1)]).replace(".", "").isdigit():
            m = mes_excel(proc[(r, 1)])
            rj[m] = float(proc[(r, 4)])
            if (r, 2) in proc:
                fal[m] = float(proc[(r, 2)])
    setor = xlsx_celulas(corpo, "Total de CNPJs Setor")
    # colunas das recuperações judiciais requeridas: 12 comércio, 13 indústria, 14 serviços,
    # 15 agropecuária, 16 total (conferido pelo cabeçalho)
    cab = {c: str(setor.get((5, c), "")).strip() for c in range(12, 17)}
    if cab != {12: "Comércio", 13: "Indústria", 14: "Serviços", 15: "Agropecuária", 16: "Total"} or \
            "Recuperações Judiciais" not in str(setor.get((3, 12), "")):
        raise RuntimeError("Serasa: cabeçalho da aba por setor mudou: %s" % cab)
    por_setor = {c: {} for c in range(12, 17)}
    for r in range(6, 200):
        if (r, 1) in setor and (r, 16) in setor and str(setor[(r, 1)]).replace(".", "").isdigit():
            m = mes_excel(setor[(r, 1)])
            for c in por_setor:
                por_setor[c][m] = float(setor.get((r, c), 0))
    for m, tot in por_setor[16].items():
        soma = sum(por_setor[c][m] for c in range(12, 16))
        if abs(soma - tot) > 0.5:
            raise RuntimeError("Serasa: setores não somam o total em %s (%s contra %s)" % (m, soma, tot))
    ks = sorted(rj)
    mm3 = {ks[i]: sum(rj[ks[j]] for j in range(i - 2, i + 1)) / 3 for i in range(2, len(ks))}
    u = ks[-1]
    ant = "%d-%s" % (int(u[:4]) - 1, u[5:])
    ano = [m for m in ks if m[:4] == u[:4]]
    ano_ant = ["%d-%s" % (int(m[:4]) - 1, m[5:]) for m in ano]
    s_ano, s_ant = sum(rj[m] for m in ano), sum(rj.get(m, 0) for m in ano_ant)
    print("  recuperações judiciais (Serasa, %s): %s %d pedidos (%s %d); no ano %d contra %d; planilha %s"
          % (links[-1].rsplit("/", 1)[-1], u, rj[u], ant, rj.get(ant, 0), s_ano, s_ant, url.rsplit("/", 1)[-1]))
    cores = {12: AZUL, 13: VERMELHO, 14: VERDE, 15: AZUL_CLARO}
    nomes = {12: "Comércio", 13: "Indústria", 14: "Serviços", 15: "Agropecuária"}
    return [dict(id="recuperacoes-judiciais", titulo="Recuperações judiciais requeridas",
                 subtitulo="Pedidos de recuperação judicial por mês; a Serasa abre só os dados desde jan/2024",
                 unidade="n", fonte="Serasa Experian (Indicador de Falências e Recuperações) e FtM", variantes=[
                     dict(rot="Pedidos", series=[
                         cf.serie("Pedidos no mês", AZUL, rj, 0, tipo="barra", rotulo=True),
                         cf.serie("Média de 3 meses", BRANCO, mm3, 1, largura=4, rotulo=True)]),
                     dict(rot="Empresas por setor", series=[
                         cf.serie(nomes[c], cores[c], por_setor[c], 0, tipo="barra") for c in range(12, 16)]
                         + [cf.serie("Total de empresas (CNPJs)", BRANCO, por_setor[16], 0, largura=4, rotulo=True)]),
                     dict(rot="Falências requeridas", series=[
                         cf.serie("Falências requeridas no mês", VERMELHO, fal, 0, tipo="barra", rotulo=True)])])]


def trimestres(d):
    """Série da PNAD por trimestre móvel ("AAAA-MM") → trimestres civis ("AAAA-Qn"):
    os trimestres móveis que terminam em mar, jun, set e dez."""
    return {"%s-Q%d" % (m[:4], int(m[5:7]) // 3): v for m, v in d.items() if m[5:7] in ("03", "06", "09", "12")}


def acum4(d):
    """Variação em 4 trimestres sobre os 4 anteriores, em %."""
    def janela(q):
        a, n, qs = int(q[:4]), int(q[-1]), []
        for _ in range(4):
            qs.append("%d-Q%d" % (a, n))
            n -= 1
            if n == 0:
                a, n = a - 1, 4
        return qs
    out = {}
    for q in d:
        j, j0 = janela(q), janela("%d-%s" % (int(q[:4]) - 1, q[5:]))
        if all(x in d for x in j + j0):
            out[q] = 100 * (sum(d[x] for x in j) / sum(d[x] for x in j0) - 1)
    return out


def graficos_trabalho_ponte():
    """A ponte entre o ciclo e a inflação: o emprego reage à atividade com
    atraso (IBC-Br × pessoas ocupadas) e o salário real cresce acima da
    produtividade (PIB real ÷ ocupados), o que encarece o trabalho por unidade
    produzida."""
    ocup = {mes(l["D3C"]): l["v"] for l in sidra("t/6320/n1/all/v/4090/p/all/c11913/96165")}
    ocup_var = {mes(l["D3C"]): l["v"] for l in sidra("t/6320/n1/all/v/8435/p/all/c11913/96165")}
    rend = {mes(l["D3C"]): l["v"] for l in sidra("t/6390/n1/all/v/5933/p/all")}
    pib = {"%s-Q%d" % (l["D3C"][:4], int(l["D3C"][4:])): l["v"]
           for l in sidra("t/1620/n1/all/v/583/p/all/c11255/90707")}
    oq, rq = trimestres(ocup), trimestres(rend)
    prod = {q: pib[q] / oq[q] for q in pib if q in oq}
    v_prod, v_rend = acum4(prod), acum4(rq)
    fim_tri = lambda d: {"%s-%02d" % (q[:4], 3 * int(q[-1])): v for q, v in d.items()}   # noqa: E731
    qp, qr = max(v_prod), max(v_rend)
    print("  produtividade em 4 tri: %s %.1f%%; rendimento real: %s %.1f%% (%s %.1f%%)"
          % (qp, v_prod[qp], qr, v_rend[qr], qp, v_rend[qp]))
    g_prod = dict(id="rendimento-produtividade", titulo="Rendimento médio real e produtividade do trabalho",
                  subtitulo="Variação acumulada em 4 trimestres sobre os 4 anteriores, em %; produtividade = PIB "
                            "real ÷ pessoas ocupadas; rendimento = rendimento médio real habitual (PNAD)",
                  unidade="pct1", buracoMax=3, fonte="IBGE (Contas Nacionais Trimestrais e PNAD Contínua) e FtM",
                  series=[cf.serie("Rendimento médio real", VERMELHO, fim_tri(v_rend), 1, largura=5, rotulo=True),
                          cf.serie("Produtividade do trabalho", AZUL, fim_tri(v_prod), 1, largura=5, rotulo=True)])
    ibc = cn.mensal(cn.sgs(24363, "01/01/2011"))
    ibc_var = {}
    for m in sorted(ibc):
        a = [cf.mes_mais(m, -k) for k in range(3)]
        b = [cf.mes_mais(x, -12) for x in a]
        if all(x in ibc for x in a + b):
            ibc_var[m] = 100 * (sum(ibc[x] for x in a) / sum(ibc[x] for x in b) - 1)
    ibc_var = {m: v for m, v in ibc_var.items() if m >= min(ocup_var)}
    um, uo = max(ibc_var), max(ocup_var)
    print("  IBC-Br trimestre móvel: %s %.1f%%; ocupação: %s %.1f%%" % (um, ibc_var[um], uo, ocup_var[uo]))
    g_ae = dict(id="atividade-emprego", titulo="Atividade e emprego",
                subtitulo="Trimestre móvel terminado no mês contra o mesmo trimestre do ano anterior, em %; "
                          "atividade = IBC-Br, a prévia do PIB do Banco Central; emprego = pessoas ocupadas (PNAD)",
                unidade="pct1", fonte="Banco Central (SGS 24363), IBGE (PNAD Contínua) e FtM",
                series=[cf.serie("Atividade (IBC-Br)", BRANCO, ibc_var, 1, largura=5, rotulo=True),
                        cf.serie("Pessoas ocupadas", VERDE, ocup_var, 1, largura=5, rotulo=True)])
    return [g_ae, g_prod]


def graficos_emprego():
    """Taxa de desemprego e taxa de participação (PNAD, trimestre móvel) e o
    Caged de setembro de cada ano (o do Relatório de Novembro)."""
    taxa = {mes(l["D3C"]): l["v"] for l in sidra("t/6381/n1/all/v/4099/p/all")}
    pop = {}
    for l in sidra("t/6318/n1/all/v/1641/p/all/c629/32385,32386"):
        pop.setdefault(l["D4C"], {})[mes(l["D3C"])] = l["v"]
    part = {m: 100 * v / pop["32385"][m] for m, v in pop["32386"].items() if m in pop["32385"]}
    # confere com a taxa trimestral que o IBGE publica (tabela 6461)
    pub = {"%s-%02d" % (l["D3C"][:4], 3 * int(l["D3C"][4:])): l["v"] for l in sidra("t/6461/n1/all/v/4096/p/all")}
    erro = max(abs(part[m] - v) for m, v in pub.items() if m in part)
    if erro > 0.15:
        raise RuntimeError("taxa de participação longe da publicada (%.2f p.p.)" % erro)
    ut, up = max(taxa), max(part)
    print("  desemprego %s %.1f%% (mínimo %s %.1f%%); participação %s %.1f%% (máximo %s %.1f%%); "
          "diferença para a trimestral publicada até %.2f p.p."
          % (ut, taxa[ut], min(taxa, key=taxa.get), min(taxa.values()), up, part[up],
             max(part, key=part.get), max(part.values()), erro))
    g_taxa = dict(id="desemprego", titulo="Taxa de desemprego",
                  subtitulo="Desocupados em % da força de trabalho, trimestre móvel terminado no mês, sem ajuste "
                            "sazonal", unidade="pct1", fonte=FONTE_PNAD,
                  series=[cf.serie("Taxa de desemprego", AZUL, taxa, 1, largura=5, rotulo=True)])
    g_part = dict(id="participacao", titulo="Taxa de participação na força de trabalho",
                  subtitulo="Pessoas na força de trabalho (ocupadas ou procurando trabalho) em % das pessoas de 14 "
                            "anos ou mais, trimestre móvel terminado no mês, sem ajuste sazonal",
                  unidade="pct1", eixo={"zero": False}, fonte=FONTE_PNAD,
                  series=[cf.serie("Taxa de participação", AZUL, part, 1, largura=5, rotulo=True)])
    return [g_taxa, g_part, cn.graficos_caged()[1]]


# um gráfico por seção (cada seção anda inteira quando ele muda a ordem); o
# título só na primeira de cada grupo
CICLO = [("Atividade", "atividade-12m"), ("", "atividade-nivel"), ("", "pms-inflacao-implicita"),
         ("PIB", "pib-familias-4tri"), ("", "pib-participacao"),
         ("Crédito", "credito-concessoes-pf-pj"), ("", "credito-inadimplencia"), ("", "credito-servico-divida"),
         ("", "credito-endividamento"), ("", "credito-cartao-saldo"), ("", "credito-cartao-inadimplencia"),
         ("", "credito-juros-selic"), ("", "credito-direcionado-livre"), ("", "credito-gap-bis"),
         ("Confiança", "confianca"),
         ("Emprego", "atividade-emprego"), ("", "desemprego"), ("", "participacao"), ("", "br-caged-setembro"),
         ("", "rendimento-produtividade"), ("", "ex3-servicos"),
         ("Recuperações judiciais", "recuperacoes-judiciais")]


def main():
    selic = cn.sgs(432, "05/03/1999")
    ult = max(selic)
    print("Selic meta: %d dias, %s a %s (%.2f%%)" % (len(selic), min(selic), ult, selic[ult]))
    serie = cf.serie("Selic meta", AZUL, selic, 2, rotulo=True)

    rec = [dict(de=a + "-01", ate=fim_mes(b)) for a, b in RECESSOES if fim_mes(b) >= min(selic)]
    g_rec = dict(id="selic-recessoes", titulo="Selic e recessões",
                 subtitulo="Meta da Selic, % ao ano, desde mar/1999; faixas cinza = recessões datadas pela "
                           "CODACE (FGV)",
                 unidade="%", diario=True, periodoPadrao="tudo", buracoMax=8, sombras=rec,
                 fonte="Banco Central (SGS 432) e CODACE/FGV (datação mensal; 2020 pela trimestral)",
                 series=[serie])

    cs = ciclos(selic)
    sombras = []
    for k, c in enumerate(cs):
        meses = meses_entre(c["ini"], c["fim"])
        c["meses"] = meses
        em_curso = k == len(cs) - 1
        nome = "Alta" if c["sentido"] == "alta" else "Corte"
        dica = "%s: %s a %s, %d %s, %s p.p.%s" % (
            nome, rot_mes(c["ini"]), rot_mes(c["fim"]), meses, "mês" if meses == 1 else "meses",
            cf.br(c["para"] - c["de"], 2, True), " (em curso)" if em_curso else "")
        sombras.append(dict(de=c["ini"], ate=c["fim"], cor=VERMELHO if c["sentido"] == "alta" else VERDE,
                            rot=str(meses), dica=dica))
        print("  %-5s %s a %s: %2d meses, %5.2f → %5.2f (%d mudanças)"
              % (c["sentido"], c["ini"], c["fim"], meses, c["de"], c["para"], c["n"]))
    for s in ("alta", "corte"):
        feitos = [c["meses"] for c in cs[:-1] if c["sentido"] == s]
        print("  %s: %d ciclos encerrados, média de %.1f meses (%d a %d)"
              % (s, len(feitos), sum(feitos) / len(feitos), min(feitos), max(feitos)))
    g_ciclos = dict(id="selic-ciclos", titulo="Selic: ciclos de alta e de corte",
                    subtitulo="Meta da Selic, % ao ano; faixas vermelhas = ciclos de alta, verdes = ciclos de "
                              "corte, da primeira à última mudança; o número é a duração em meses",
                    unidade="%", diario=True, periodoPadrao="tudo", buracoMax=8, sombras=sombras,
                    fonte="Banco Central (SGS 432) e FtM",
                    series=[dict(serie)])

    secoes = [dict(titulo="Selic", texto="", fontes=[], figuras=[], graficos=[g_rec]),
              dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_ciclos])]
    ciclo = {g["id"]: g for f in (graficos_atividade, graficos_pib_credito, graficos_cartao, graficos_confianca,
                       graficos_emprego, graficos_trabalho_ponte, graficos_recuperacoes)
             for g in f()}
    for titulo, gid in CICLO:
        secoes.append(dict(titulo=titulo, texto="", fontes=[], figuras=[], graficos=[ciclo[gid]]))
    hoje = datetime.date.today().isoformat()
    doc = dict(atualizado=hoje, referencia=hoje, formato="artigo", assunto="Missão Global Miami",
               # a ordem dos gráficos é escolhida na página (botões Subir/Descer e
               # arrastar) e gravada neste arquivo; o app aplica ao abrir
               reordenar="dados/ordens/missao-global-miami.json",
               fonte="Banco Central, CODACE/FGV, IBGE, CNI, CNC, Fecomercio SP e Ministério do Trabalho",
               secoes=secoes)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado %s (%.0f KB)" % (SAIDA, os.path.getsize(SAIDA) / 1024))
    import aplicar_texto
    aplicar_texto.aplicar(NOME + ".md", NOME + ".json")
    # o texto casa as seções sem título pela posição: se o .md não tiver uma
    # seção por gráfico, na ordem de CICLO, gráfico some ou sai repetido
    with open(SAIDA, encoding="utf-8") as f:
        ids = [g["id"] for s in json.load(f)["secoes"] for g in s["graficos"]]
    esperado = ["selic-recessoes", "selic-ciclos"] + [gid for _, gid in CICLO]
    if ids != esperado:
        raise RuntimeError("textos/%s.md fora do lugar: o JSON saiu com %s; tinha de ser %s"
                           % (NOME, ids, esperado))


if __name__ == "__main__":
    main()

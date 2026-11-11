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
# Atividade, confiança e mercado de trabalho: os gráficos que ainda não
# existiam em nenhum dos sites. O resto do ciclo (PMS, PIB, crédito, Caged)
# está no ftm-dados e entra aqui quando ele pedir.

BRANCO, AZUL_CLARO, AZUL_ESCURO, CINZA = cf.BRANCO, "#8EB4E3", cf.AZUL_ESCURO, "#8a8a86"
SIDRA_UA = {"User-Agent": "Mozilla/5.0 (ftm-analises)"}
FONTE_PMC = "IBGE (Pesquisa Mensal de Comércio) e FtM"
FONTE_PNAD = "IBGE (PNAD Contínua) e FtM"


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


def graficos_varejo():
    """PMC: volume com ajuste sazonal (varejo e ampliado) e as variações, no
    molde da PMS do ftm-dados, sem a inflação implícita."""
    d = {}
    for tab, nome, cod in ((8880, "Varejo", "56734"), (8881, "Varejo ampliado", "56736")):
        for l in sidra("t/%d/n1/all/v/7170,11708,11709,11711/p/all/c11046/%s" % (tab, cod)):
            d.setdefault((nome, l["D2C"]), {})[mes(l["D3C"])] = l["v"]
    variantes = []
    for nome in ("Varejo", "Varejo ampliado"):
        sa = d[(nome, "7170")]
        rec = max(sa, key=sa.get)
        linha = lambda v: {m: v for m in sa}                               # noqa: E731
        variantes.append(dict(rot=nome, subtitulo="Índice com ajuste sazonal, 2022 = 100; pontilhado: fevereiro "
                                                  "de 2020, antes da pandemia, e o recorde (%s)" % rot_m(rec),
                              series=[cf.serie("Volume de vendas", BRANCO, sa, 1, largura=5, rotulo=True),
                                      cf.serie("Fevereiro de 2020", AZUL_CLARO, linha(sa["2020-02"]), 1,
                                               traco="pontilhado", largura=3, rotulo=True),
                                      cf.serie("Recorde (%s)" % rot_m(rec), VERMELHO, linha(sa[rec]), 1,
                                               traco="pontilhado", largura=3, rotulo=True)]))
        ult = max(sa)
        print("  %s: %s %.1f, recorde %s %.1f (%.1f%% abaixo); 12 meses %.1f%%"
              % (nome, ult, sa[ult], rec, sa[rec], 100 * (sa[ult] / sa[rec] - 1), d[(nome, "11711")][ult]))
    # o app daqui não usa o subtítulo do recorte: o geral vale para os dois
    g_vol = dict(id="pmc-volume", titulo="Volume de vendas no varejo", unidade="ind", fonte=FONTE_PMC,
                 subtitulo="Índice com ajuste sazonal, 2022 = 100; pontilhado: fevereiro de 2020, antes da "
                           "pandemia, e o recorde; o ampliado soma veículos, material de construção e atacado "
                           "de alimentos",
                 eixo={"zero": False}, variantes=variantes)

    # 3 meses anualizado: média dos últimos 3 meses sobre a dos 3 anteriores,
    # anualizada, com ajuste sazonal (como na PMS)
    sa = d[("Varejo", "7170")]
    ks = sorted(sa)
    media3 = lambda i: sum(sa[ks[j]] for j in range(i - 2, i + 1)) / 3     # noqa: E731
    ritmo = {ks[i]: 100 * ((media3(i) / media3(i - 3)) ** 4 - 1) for i in range(5, len(ks))}
    # desde 2022: com a pandemia (de −40% a +80%) o resto vira uma linha reta
    ritmo = {m: v for m, v in ritmo.items() if m >= "2022-01"}
    doze = {m: v for m, v in d[("Varejo", "11711")].items() if m >= "2022-01"}
    g_var = dict(id="pmc-variacoes", titulo="Volume de vendas no varejo: variações",
                 subtitulo="Em %; varejo, e o ampliado em 12 meses; no mês e em 3 meses anualizado, com ajuste "
                           "sazonal",
                 unidade="%", fonte=FONTE_PMC, variantes=[
                     dict(rot="No mês", subtitulo="Varejo, variação sobre o mês anterior, com ajuste sazonal, em %",
                          series=[cf.serie("Variação no mês", AZUL, d[("Varejo", "11708")], 1, tipo="barra",
                                           rotulo=True)]),
                     dict(rot="Sobre o mesmo mês do ano anterior", subtitulo="Varejo, variação interanual, em %",
                          series=[cf.serie("Variação interanual", AZUL, d[("Varejo", "11709")], 1, tipo="barra",
                                           rotulo=True)]),
                     dict(rot="Em 12 meses", subtitulo="Variação em 12 meses sobre os 12 anteriores, em %",
                          series=[cf.serie("Varejo", AZUL, d[("Varejo", "11711")], 1, largura=5, rotulo=True),
                                  cf.serie("Varejo ampliado", VERMELHO, d[("Varejo ampliado", "11711")], 1,
                                           largura=5, rotulo=True)]),
                     dict(rot="3 meses, anualizado", subtitulo="Varejo, com ajuste sazonal, em %",
                          series=[cf.serie("3 meses, anualizado", VERMELHO, ritmo, 1, largura=3, rotulo=True),
                                  cf.serie("Variação em 12 meses", AZUL, doze, 1, largura=5, rotulo=True)])])
    print("  varejo: 3 meses anualizado %.1f%% em %s" % (ritmo[max(ritmo)], max(ritmo)))
    return [g_vol, g_var]


def graficos_confianca():
    """ICEI (CNI, geral: o Ipeadata não tem o dessazonalizado), ICEC ajustado
    (CNC) e ICC (Fecomercio SP), do Ipeadata."""
    indices = [("Indústria (ICEI)", "CNI12_ICEIGER12", 50, "Índice de Confiança do Empresário Industrial, da CNI, "
                "geral; de 0 a 100, acima de 50 = confiança"),
               ("Comércio (ICEC)", "CNC12_ICECAJ12", 100, "Índice de Confiança do Empresário do Comércio, da CNC, "
                "com ajuste sazonal; de 0 a 200, acima de 100 = confiança"),
               ("Consumidor (ICC)", "FCESP12_IIC12", 100, "Índice de Confiança do Consumidor, da Fecomercio SP; "
                "de 0 a 200, acima de 100 = otimismo")]
    variantes = []
    for rot, cod, neutro, sub in indices:
        s = cn.ipea(cod)
        ult = max(s)
        print("  %s: %s %.1f (12 meses antes %.1f)" % (rot, ult, s[ult], s.get(cf.mes_mais(ult, -12), float("nan"))))
        variantes.append(dict(rot=rot, subtitulo=sub, series=[
            cf.serie(rot, AZUL, s, 1, largura=5, rotulo=True),
            cf.serie("Neutro (%d)" % neutro, CINZA, {m: neutro for m in s}, 0, traco="pontilhado", largura=3)]))
    return [dict(id="confianca", titulo="Índices de confiança", unidade="ind", eixo={"zero": False},
                 subtitulo="Indústria (CNI, geral): de 0 a 100, neutro = 50; comércio (CNC, com ajuste sazonal) e "
                           "consumidor (Fecomercio SP): de 0 a 200, neutro = 100",
                 fonte="CNI, CNC e Fecomercio SP (via Ipeadata)", variantes=variantes)]


def trimestres(d):
    """Série da PNAD por trimestre móvel ("AAAA-MM") → trimestres civis ("AAAA-Qn"):
    os trimestres móveis que terminam em mar, jun, set e dez."""
    return {"%s-Q%d" % (m[:4], int(m[5:7]) // 3): v for m, v in d.items() if m[5:7] in ("03", "06", "09", "12")}


def menos4(q):
    return "%d-%s" % (int(q[:4]) - 1, q[5:])


def acum4(d, media=False):
    """Variação em 4 trimestres sobre os 4 anteriores, em %."""
    def janela(q):
        a, n = int(q[:4]), int(q[-1])
        qs = []
        for _ in range(4):
            qs.append("%d-Q%d" % (a, n))
            n -= 1
            if n == 0:
                a, n = a - 1, 4
        return qs
    out = {}
    for q in d:
        j, j0 = janela(q), janela(menos4(q))
        if all(x in d for x in j + j0):
            out[q] = 100 * (sum(d[x] for x in j) / sum(d[x] for x in j0) - 1)
    return out


def graficos_trabalho():
    """Desemprego (PNAD) e Caged; rendimento real e produtividade; atividade e emprego."""
    taxa = {mes(l["D3C"]): l["v"] for l in sidra("t/6381/n1/all/v/4099/p/all")}
    ocup = {mes(l["D3C"]): l["v"] for l in sidra("t/6320/n1/all/v/4090/p/all/c11913/96165")}
    ocup_var = {mes(l["D3C"]): l["v"] for l in sidra("t/6320/n1/all/v/8435/p/all/c11913/96165")}
    rend = {mes(l["D3C"]): l["v"] for l in sidra("t/6390/n1/all/v/5933/p/all")}
    pib = {"%s-Q%d" % (l["D3C"][:4], int(l["D3C"][4:])): l["v"]
           for l in sidra("t/1620/n1/all/v/583/p/all/c11255/90707")}

    # desemprego e Caged
    ut = max(taxa)
    minimo = min(taxa, key=taxa.get)
    caged = cn.graficos_caged()[0]
    print("  desemprego: %s %.1f%% (mínimo da série: %s %.1f%%; 12 meses antes %.1f%%)"
          % (ut, taxa[ut], minimo, taxa[minimo], taxa[cf.mes_mais(ut, -12)]))
    g_desemp = dict(id="desemprego-caged", titulo="Desemprego e emprego formal",
                    subtitulo="Taxa de desemprego da PNAD, em % da força de trabalho, trimestre móvel, sem ajuste "
                              "sazonal; saldo do Caged em 12 meses, em mil vagas",
                    fonte="IBGE (PNAD Contínua) e Ministério do Trabalho (Caged, via Ipeadata)", variantes=[
                        dict(rot="Taxa de desemprego (PNAD)", unidade="pct1",
                             subtitulo="Desocupados em % da força de trabalho, trimestre móvel terminado no mês, "
                                       "sem ajuste sazonal",
                             series=[cf.serie("Taxa de desemprego", AZUL, taxa, 1, largura=5, rotulo=True)]),
                        dict(rot="Saldo do Caged em 12 meses", unidade="mil", subtitulo=caged["subtitulo"],
                             eventos=caged.get("eventos"), series=caged["series"])])

    # rendimento médio real e produtividade (PIB real por pessoa ocupada)
    oq, rq = trimestres(ocup), trimestres(rend)
    prod = {q: pib[q] / oq[q] for q in pib if q in oq}
    v_prod, v_rend = acum4(prod), acum4(rq)
    # o app daqui não tem eixo trimestral: o trimestre vai no mês em que termina
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

    # atividade e emprego: IBC-Br e ocupação, trimestre móvel contra o mesmo do ano anterior
    ibc = cn.mensal(cn.sgs(24363, "01/01/2011"))
    ks = sorted(ibc)
    ibc_var = {}
    for m in ks:
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
    return [g_desemp, g_prod, g_ae]


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
              dict(titulo="", texto="", fontes=[], figuras=[], graficos=[g_ciclos]),
              dict(titulo="Objetivos do Banco Central", texto="", fontes=[], figuras=[], graficos=[])]
    ciclo = {g["id"]: g for f in (graficos_varejo, graficos_confianca, graficos_trabalho) for g in f()}
    for titulo, gid in [("Varejo", "pmc-volume"), ("", "pmc-variacoes"), ("Confiança", "confianca"),
                        ("Mercado de trabalho", "desemprego-caged"), ("", "rendimento-produtividade"),
                        ("", "atividade-emprego")]:
        secoes.append(dict(titulo=titulo, texto="", fontes=[], figuras=[], graficos=[ciclo[gid]]))
    hoje = datetime.date.today().isoformat()
    doc = dict(atualizado=hoje, referencia=hoje, formato="artigo", assunto="Missão Global Miami",
               fonte="Banco Central, CODACE/FGV, IBGE, CNI, CNC, Fecomercio SP e Ministério do Trabalho",
               secoes=secoes)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado %s (%.0f KB)" % (SAIDA, os.path.getsize(SAIDA) / 1024))
    import aplicar_texto
    aplicar_texto.aplicar(NOME + ".md", NOME + ".json")


if __name__ == "__main__":
    main()

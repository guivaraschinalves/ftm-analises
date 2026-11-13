#!/usr/bin/env python3
"""
Receita administrada pela Receita Federal e despesa do governo central (com os
juros) em % do PIB, por ano, para a parte Brasil da Missão Global Miami
(chamado pelo missao_miami.py). Só biblioteca padrão.

  - Receita e despesa: Resultado do Tesouro Nacional (RTN), série histórica
    mensal em valores correntes, aba 1.1 (o leitor é o do ftm-dados,
    scripts/rtn.py). Juros nominais: linha 9 do RTN (vem do Banco Central),
    com o sinal trocado para entrar como gasto.
  - PIB: SGS 4382 (acumulado em 12 meses, R$ milhões). O ano é a soma de jan a
    dez sobre o PIB do ano; o último ponto é a soma dos 12 meses até o último
    mês publicado sobre o PIB desses 12 meses.
  - IR por contribuinte: o RTN só dá o total do Imposto de Renda. A divisão
    usa a arrecadação da Receita Federal por estado (dados abertos,
    arrecadacao-estado.csv, desde 2000): pessoa física = IRPF + IR retido sobre
    rendimentos do trabalho; pessoa jurídica = IRPJ; e o resto do retido na
    fonte (capital, remessas ao exterior e outros) à parte. A proporção de
    cada parte na arrecadação bruta é aplicada ao total do RTN, para a soma
    continuar batendo com a receita administrada.
"""
import csv
import io
import os
import sys

import cenario_fomc as cf
import cenario_novembro as cn

sys.path.insert(0, os.path.join(os.path.expanduser("~"), "projetos", "ftm-dados", "scripts"))
import rtn  # noqa: E402

AZUL, VERMELHO, VERDE = "#4F81BD", "#C0504D", "#9BBB59"
AZUL_ESCURO, AZUL_CLARO, VINHO, AMARELO = "#1F497D", "#8EB4E3", "#632523", "#FFFF00"
CINZA, CINZA_CLARO, CINZA_ESCURO = "#8a8a86", "#D0D0CC", "#5c5c59"
BRANCO = cf.BRANCO
RFB_CSV = "https://www.gov.br/receitafederal/dados/arrecadacao-estado.csv"
MESES_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro",
            "Novembro", "Dezembro"]
FONTE = "Tesouro Nacional (RTN), Banco Central (SGS 4382, PIB) e FtM"


def linha(tab, inicio):
    rot = next((k for k in tab if k.startswith(inicio)), None)
    if rot is None:
        raise RuntimeError("RTN: linha %r não encontrada" % inicio)
    return tab[rot]


def janelas(ultimo):
    """[(rótulo, rótulo longo, último mês da janela)]: um por ano fechado e o
    último ponto em 12 meses."""
    a_ult, m_ult = int(ultimo[:4]), int(ultimo[5:7])
    out = [(str(a), str(a), "%d-12" % a) for a in range(1997, a_ult if m_ult < 12 else a_ult + 1)]
    if m_ult < 12:
        out.append((str(a_ult), "%d (12 meses até %s)" % (a_ult, cf.rot_mes(ultimo)), ultimo))
    return out


def soma12(d, fim):
    a, m = int(fim[:4]), int(fim[5:7])
    ks = []
    for _ in range(12):
        ks.append("%d-%02d" % (a, m))
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    if not all(k in d for k in ks):
        return None
    return sum(d[k] for k in ks)


def numero(v):
    """A planilha mistura formatos: em 2001 e 2002 a vírgula separa o milhar
    ("35,322,043"); nos outros anos ela é a casa decimal ("211106,48")."""
    import re
    v = (v or "").strip()
    if not v:
        return None
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+", v):
        return float(v.replace(",", ""))
    return float(v.replace(".", "").replace(",", "."))


def ir_receita():
    """{"AAAA-MM": {"pf": R$, "pj": R$, "outros": R$}} da arrecadação bruta."""
    corpo = cf.baixar(RFB_CSV, headers={"User-Agent": "Mozilla/5.0 (ftm-analises)"})
    txt = corpo.decode("utf-8") if corpo[:3] == b"\xef\xbb\xbf" else corpo.decode("latin-1")
    grupos = {"pf": ["IRPF", "IRRF - RENDIMENTOS DO TRABALHO"],
              "pj": ["IRPJ - ENTIDADES FINANCEIRAS", "IRPJ - DEMAIS EMPRESAS"],
              "outros": ["IRRF - RENDIMENTOS DO CAPITAL", "IRRF - REMESSAS P/ EXTERIOR", "IRRF - OUTROS RENDIMENTOS"]}
    out = {}
    for l in csv.DictReader(io.StringIO(txt.lstrip("﻿")), delimiter=";"):
        mes = l["Mês"].strip().capitalize()
        if mes not in MESES_PT:
            continue
        k = "%s-%02d" % (l["Ano"].strip(), MESES_PT.index(mes) + 1)
        d = out.setdefault(k, {"pf": 0.0, "pj": 0.0, "outros": 0.0})
        for g, cols in grupos.items():
            for c in cols:
                v = numero(l.get(c))
                if v is not None:
                    d[g] += v
    if not out:
        raise RuntimeError("Receita Federal: arrecadação por estado vazia")
    return out


def graficos():
    tab, unidade = rtn.tabela("1.1")
    if "Correntes" not in unidade:
        raise RuntimeError("RTN: aba 1.1 não está em valores correntes (%s)" % unidade)
    pib = cn.mensal(cn.sgs(4382, "01/01/1997"))

    # ---------- receita administrada pela RFB ----------
    rec = [("ii", "1.1.01", "Imposto sobre a importação", CINZA), ("ipi", "1.1.02", "IPI", AMARELO),
           ("ir", "1.1.03", "Imposto de renda", AZUL), ("iof", "1.1.04", "IOF", CINZA_CLARO),
           ("cofins", "1.1.05", "Cofins", VERMELHO), ("pis", "1.1.06", "PIS/Pasep", VINHO),
           ("csll", "1.1.07", "CSLL", VERDE), ("cpmf", "1.1.08", "CPMF", CINZA_ESCURO),
           ("cide", "1.1.09", "Cide-Combustíveis", CINZA_ESCURO), ("outras", "1.1.10", "Outras", CINZA_ESCURO)]
    m = {k: linha(tab, p) for k, p, _, _ in rec}
    total = linha(tab, "1.1 - Receita Administrada")
    ult = max(k for k in total if k in pib)
    jan = janelas(ult)
    ir = ir_receita()

    def pct(d, fim):
        s = soma12(d, fim)
        return None if s is None else 100 * s / pib[fim]
    # CPMF, Cide e outras numa camada só: a sétima cor já foi
    m["resto"] = {k: m["cpmf"][k] + m["cide"][k] + m["outras"][k] for k in m["outras"]}
    ordem = [("ir", "Imposto de renda", AZUL), ("cofins", "Cofins", VERMELHO), ("csll", "CSLL", VERDE),
             ("pis", "PIS/Pasep", VINHO), ("ii", "Imposto sobre a importação", CINZA), ("ipi", "IPI", AMARELO),
             ("iof", "IOF", CINZA_CLARO), ("resto", "CPMF, Cide e outras", CINZA_ESCURO)]

    idx_all = [(i, r, fim) for i, (r, _, fim) in enumerate(jan)]
    cats = [r for r, _, _ in jan]
    longas = [l for _, l, _ in jan]

    def serie_barra(nome, cor, valores):
        return dict(nome=nome, cor=cor, tipo="barra", dados=[[str(i), round(v, 2)] for i, v in valores if v is not None])
    tot = [(i, pct(total, fim)) for i, _, fim in idx_all]
    s_total = dict(nome="Total administrado pela RFB", cor=BRANCO, largura=5, rotulo=True,
                   dados=[[str(i), round(v, 2)] for i, v in tot if v is not None])
    v_total = [serie_barra(n, c, [(i, pct(m[k], fim)) for i, _, fim in idx_all]) for k, n, c in ordem] + [s_total]
    # IR dividido (desde 2000): a proporção da arrecadação bruta aplicada ao IR do RTN
    jan_ir = [(i, r, fim) for i, r, fim in idx_all if soma12({k: 1 for k in ir}, fim)]
    i0 = jan_ir[0][0]
    partes = {"pf": [], "pj": [], "outros": []}
    for i, r, fim in jan_ir:
        g = {p: soma12({k: v[p] for k, v in ir.items()}, fim) for p in partes}
        s = sum(g.values())
        tot_ir = pct(m["ir"], fim)
        for p in partes:
            partes[p].append((i - i0, tot_ir * g[p] / s))
    camadas_ir = [serie_barra("IR pessoa física", AZUL, partes["pf"]),
                  serie_barra("IR pessoa jurídica", AZUL_ESCURO, partes["pj"]),
                  serie_barra("IR retido: capital e outros", AZUL_CLARO, partes["outros"])]
    outras = [serie_barra(n, c, [(i - i0, pct(m[k], fim)) for i, _, fim in jan_ir]) for k, n, c in ordem[1:]]
    s_total_ir = dict(s_total, dados=[[str(i - i0), round(v, 2)] for i, v in tot if v is not None and i >= i0])
    u = tot[-1][1]
    pf_u, pj_u = partes["pf"][-1][1], partes["pj"][-1][1]
    print("  receita RFB %s: %.1f%% do PIB; IR PF %.1f%%, PJ %.1f%%, outros %.1f%%"
          % (longas[-1], u, pf_u, pj_u, partes["outros"][-1][1]))
    g_rec = dict(id="receita-rfb-pib", titulo="Receita do governo central administrada pela Receita Federal",
                 subtitulo="Em %% do PIB, por ano; %s: %s%% do PIB; no IR dividido, pessoa física = IRPF + IR "
                           "retido sobre salários; retido: capital, remessas ao exterior e outros" % (longas[-1], cf.br(u, 1)),
                 unidade="%", barra=1, fonte=FONTE + "; IR por contribuinte: Receita Federal (arrecadação por estado)",
                 variantes=[
                     dict(rot="Por tributo", categorias=cats, categoriasLongas=longas, series=v_total),
                     dict(rot="Com o IR dividido (desde 2000)", categorias=cats[i0:], categoriasLongas=longas[i0:],
                          series=camadas_ir + outras + [s_total_ir])])

    # ---------- despesa total + juros ----------
    juros = {k: -v for k, v in linha(tab, "9. JUROS NOMINAIS").items()}
    desp = [("4.1 ", "Benefícios previdenciários", VERMELHO),
            ("4.4 ", "Executivo (programação financeira)", AZUL),
            ("4.2 ", "Pessoal e encargos sociais", VERDE), ("4.3 ", "Outras despesas obrigatórias", AZUL_ESCURO)]
    d = {p: linha(tab, p) for p, _, _ in desp}
    ult_d = max(k for k in juros if k in pib and all(k in v for v in d.values()))
    jd = janelas(ult_d)
    cats_d, longas_d = [r for r, _, _ in jd], [l for _, l, _ in jd]
    series = [serie_barra(n, c, [(i, pct(d[p], fim)) for i, (_, _, fim) in enumerate(jd)]) for p, n, c in desp]
    series.append(serie_barra("Juros nominais", AZUL_CLARO, [(i, pct(juros, fim)) for i, (_, _, fim) in enumerate(jd)]))
    soma = {k: sum(v[k] for v in d.values()) + juros[k] for k in juros if all(k in v for v in d.values())}
    tot_d = [(i, pct(soma, fim)) for i, (_, _, fim) in enumerate(jd)]
    series.append(dict(nome="Despesa total + juros", cor=BRANCO, largura=5, rotulo=True,
                       dados=[[str(i), round(v, 2)] for i, v in tot_d if v is not None]))
    # confere: a soma dos quatro grupos é a despesa total do RTN
    dt = linha(tab, "4. DESPESA TOTAL")
    erro = max(abs(sum(v[k] for v in d.values()) - dt[k]) for k in dt if all(k in v for v in d.values()))
    if erro > 1:
        raise RuntimeError("RTN: os grupos não somam a despesa total (R$ %.1f mi)" % erro)
    print("  despesa + juros %s: %.1f%% do PIB (juros %.1f%%)"
          % (longas_d[-1], tot_d[-1][1], series[4]["dados"][-1][1]))
    g_desp = dict(id="despesa-juros-pib", titulo="Despesa total do governo central e juros da dívida",
                  subtitulo="Em %% do PIB, por ano; %s: %s%% do PIB, dos quais %s%% de juros"
                            % (longas_d[-1], cf.br(tot_d[-1][1], 1), cf.br(series[4]["dados"][-1][1], 1)),
                  unidade="%", barra=1, categorias=cats_d, categoriasLongas=longas_d, fonte=FONTE, series=series)
    return [g_rec, g_desp]

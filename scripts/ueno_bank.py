#!/usr/bin/env python3
"""
Ueno Bank: a resolução de novembro de 2026 contada pelos números que o banco
mandava ao Banco Central do Paraguai.

Fonte: "Tablas Boletín Bancos" da Superintendencia de Bancos do BCP (planilha
de set/2026, mensal desde jan/2016, por entidade). O site do BCP fica atrás de
um desafio do Cloudflare, então a planilha é baixada à mão e o caminho vai como
argumento:

    python3 scripts/ueno_bank.py "~/projetos/ftm-dados/dados/1.1 Tablas Boletín Bancos Set26 1.xlsx"

Grava dados/ueno-bank.json.

Como ler a planilha:
  - formato longo: Fecha (serial do Excel, último dia do mês), Codigo Entidad,
    conta e valor. Valores em milhões de guaranis; "Codigo Moneda" 6900 é
    moeda nacional e 6200 estrangeira já convertida, e as duas se somam.
  - Ueno Bank é a entidade 1046 (desde dez/2023). O Visión Banco (1039)
    some em mai/2024: em jun/2024 os depósitos do Ueno saltam de ₲ 3,3 para
    ₲ 9,2 trilhões, a fusão.
  - 1000 é o sistema, mas só na aba Ratios; nas outras o sistema é a soma das
    entidades.
  - C1 = capital principal (nível 1) / AYCP, mínimo 8%; C2 = (nível 1 +
    nível 2) / AYCP, mínimo 12% (o BCP pode subir até 14%). A resolução foi
    por "índice de solvência abaixo de 50% do mínimo", isto é, C2 abaixo de 6%.
"""
import collections
import datetime
import io
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAIDA = os.path.join(RAIZ, "dados", "ueno-bank.json")
UENO, VISION, SISTEMA = "1046", "1039", "1000"
INICIO = "2023-12"      # primeiro mês do Ueno como banco
FUSAO = "2024-06"       # primeiro mês com o Visión Banco dentro
FONTE = "BCP (Superintendencia de Bancos) e FtM"

AZUL, VERMELHO, VERDE, ROXO, CIANO, LARANJA = "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6", "#F79646"
BRANCO, AMARELO, CINZA, AREIA = "#FFFFFF", "#FFFF00", "#95A5A6", "#D9B382"

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def ler_aba(conteudo, nome):
    """Linhas da aba como dicionários pelo cabeçalho da primeira linha."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    textos = [("".join(t.text or "" for t in si.iter(NS + "t"))) for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    aba = next(a for a in ET.fromstring(z.read("xl/workbook.xml")).iter(NS + "sheet") if a.get("name") == nome)
    alvo = rels[aba.get(RNS + "id")].lstrip("/")
    alvo = alvo if alvo.startswith("xl/") else "xl/" + alvo
    linhas = {}
    for c in ET.fromstring(z.read(alvo)).iter(NS + "c"):
        v = c.find(NS + "v")
        if v is None or v.text is None:
            continue
        ref = c.get("r")
        col = re.match(r"[A-Z]+", ref).group(0)
        linhas.setdefault(int(ref[len(col):]), {})[col] = textos[int(v.text)] if c.get("t") == "s" else v.text
    rs = [linhas[r] for r in sorted(linhas)]
    cab = rs[0]
    return [{cab[k]: l.get(k, "") for k in cab} for l in rs[1:]]


def mes(serial):
    return (datetime.date(1899, 12, 30) + datetime.timedelta(int(float(serial)))).isoformat()[:7]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def virg(x, casas=1):
    return f"{x:.{casas}f}".replace(".", ",")


def serie(nome, cor, dados, casas=2, **extra):
    return dict(nome=nome, cor=cor, dados=[[m, round(v, casas)] for m, v in sorted(dados.items()) if v is not None], **extra)


def main():
    caminho = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else
                                 "~/projetos/ftm-dados/dados/1.1 Tablas Boletín Bancos Set26 1.xlsx")
    b = open(caminho, "rb").read()

    # ---------- Ratios: capital, AYCP, inadimplência
    R = collections.defaultdict(dict)
    for r in ler_aba(b, "Ratios"):
        R[(r["Codigo Entidad"], r["Sub_Rubro"])][mes(r["Fecha"])] = num(r["Total"])
    ult = max(R[(UENO, "ACTIVOS Y CONTINGENTES PONDERADOS")])

    def rat(ent, chave, desde=INICIO, escala=100):
        return {m: v * escala for m, v in R[(ent, chave)].items() if m >= desde}

    T1, T12 = "Relación entre TIER 1/ACPR", "Relación entre TIER 1 + TIER 2/ACPR"
    # O sistema (1000) falta em alguns meses (jun/2026): preenche com a soma dos bancos, que bate com
    # o publicado em todos os meses menos fev/2024 (0,8 p.p.); onde há número oficial, fica ele
    CAP1, CAP2, AYCP = ("Capital Principal (Nivel 1)", "Capital Complementario (Nivel 2) (limitado al 100% del Capital Nivel 1)",
                        "ACTIVOS Y CONTINGENTES PONDERADOS")
    bancos = {e for e, k in R if e != SISTEMA}
    for m in {m for e in bancos for m in R[(e, AYCP)]}:
        a_ = sum(R[(e, AYCP)].get(m, 0) for e in bancos)
        c1 = sum(R[(e, CAP1)].get(m, 0) for e in bancos)
        c2 = sum(R[(e, CAP2)].get(m, 0) for e in bancos)
        if a_:
            for chave, v in ((T1, c1 / a_), (T12, (c1 + c2) / a_)):
                pub = R[(SISTEMA, chave)].get(m)
                if pub is not None and abs(pub - v) > 0.002:
                    print(f"  aviso: {chave} {m} publicado {pub:.4f}, soma {v:.4f}")
                if pub is None:
                    R[(SISTEMA, chave)][m] = v
    meses = sorted(m for m in R[(UENO, T1)] if m >= INICIO)
    capital = dict(
        id="ueno-capital", titulo="Ueno Bank: capital sobre ativos ponderados por risco",
        subtitulo=("Capital próprio para cada 100 de risco assumido, em %. O C1 conta só o capital de melhor qualidade; "
                   "o C2 soma dívidas que absorvem perdas. Abaixo de 6%, a resolução é obrigatória"),
        unidade="pct1", fonte=FONTE,
        series=[serie("C2 do Ueno", LARANJA, rat(UENO, T12), 1, rotulo=True),
                serie("C1 do Ueno", AZUL, rat(UENO, T1), 1, rotulo=True),
                serie("C2 do sistema", BRANCO, rat(SISTEMA, T12), 1),
                serie("Mínimo do C2 (12%)", AMARELO, {m: 12.0 for m in meses}, 1, traco="pontilhado"),
                serie("Mínimo do C1 (8%)", CINZA, {m: 8.0 for m in meses}, 1, traco="pontilhado"),
                serie("Resolução (metade do mínimo do C2)", VERMELHO, {m: 6.0 for m in meses}, 1, traco="pontilhado")],
    )

    def indice(d, base=FUSAO):
        return {m: 100 * v / d[base] for m, v in d.items() if m >= base}
    aycp_u = rat(UENO, "ACTIVOS Y CONTINGENTES PONDERADOS", escala=1)
    aycp_s = rat(SISTEMA, "ACTIVOS Y CONTINGENTES PONDERADOS", escala=1)
    cap1_u = rat(UENO, "Capital Principal (Nivel 1)", escala=1)
    crescimento = dict(
        id="ueno-crescimento", titulo="Ueno Bank: ativos ponderados por risco e capital principal",
        subtitulo=("Jun/2024 = 100 (fusão com o Visión Banco). Laranja: o risco que o banco carrega; azul: o capital que o cobre. "
                   "Laranja acima da azul, banco mais frágil"),
        unidade="n", fonte=FONTE,
        series=[serie("Ativos ponderados do Ueno", LARANJA, indice(aycp_u), 1, rotulo=True),
                serie("Capital principal do Ueno", AZUL, indice(cap1_u), 1, rotulo=True),
                serie("Ativos ponderados do sistema", BRANCO, indice(aycp_s), 1, rotulo=True)],
    )
    alav_u = rat(UENO, "Activos y Contingentes/ Patrimonio Neto (veces)", escala=1)
    alav_s = rat(SISTEMA, "Activos y Contingentes/ Patrimonio Neto (veces)", escala=1)

    MORA = "Cartera Vencida/Cartera Total - Morosidad"
    # ---------- categorias de risco
    K = collections.defaultdict(float)
    for r in ler_aba(b, "Categoría Creditos"):
        K[(mes(r["Fecha"]), r["Codigo Entidad"], r["Codigo Tipo Riesgo"])] += num(r["Total"])

    def fatia_cat(ent, cats):
        out = {}
        for m in meses:
            if ent == SISTEMA:
                tot = sum(v for (mm, e, c), v in K.items() if mm == m)
                parte = sum(v for (mm, e, c), v in K.items() if mm == m and c in cats)
            else:
                tot = sum(v for (mm, e, c), v in K.items() if mm == m and e == ent)
                parte = sum(v for (mm, e, c), v in K.items() if mm == m and e == ent and c in cats)
            if tot:
                out[m] = 100 * parte / tot
        return out
    qualidade = dict(
        id="ueno-qualidade", titulo="Ueno Bank: inadimplência e carteira classificada fora da categoria 1",
        subtitulo=("Em % da carteira. Inadimplência é o crédito já vencido; a classificação, de 1 (menor risco) a 6, "
                   "mostra o problema antes do vencimento"),
        unidade="pct1", fonte=FONTE,
        variantes=[
            dict(rot="Inadimplência (carteira vencida)", unidade="pct1",
                 series=[serie("Ueno", LARANJA, rat(UENO, MORA), 2, rotulo=True),
                         serie("Sistema", BRANCO, rat(SISTEMA, MORA), 2, rotulo=True)]),
            dict(rot="Em observação (categorias 1a e 1b)", unidade="pct1",
                 series=[serie("Ueno", LARANJA, fatia_cat(UENO, {"1a", "1b"}), 1, rotulo=True),
                         serie("Sistema", BRANCO, fatia_cat(SISTEMA, {"1a", "1b"}), 1, rotulo=True)]),
            dict(rot="Categorias 2 a 6", unidade="pct1",
                 series=[serie("Ueno", LARANJA, fatia_cat(UENO, {"2", "3", "4", "5", "6"}), 1, rotulo=True),
                         serie("Sistema", BRANCO, fatia_cat(SISTEMA, {"2", "3", "4", "5", "6"}), 1, rotulo=True)]),
        ],
    )

    # ---------- carteira por setor
    S = collections.defaultdict(float)
    for r in ler_aba(b, "Credito Sector"):
        S[(mes(r["Fecha"]), r["Codigo Entidad"], r["Actividad_Destino_vs2"].strip())] += num(r["CARTERA VIGENTE"]) + num(r["CARTERA VENCIDA"])
    setores = sorted({k[2] for k in S})
    tot_u = sum(v for (m, e, s), v in S.items() if m == ult and e == UENO)
    tot_s = sum(v for (m, e, s), v in S.items() if m == ult)
    pares = sorted(((100 * S.get((ult, UENO, s), 0) / tot_u, 100 * sum(v for (m, e, ss), v in S.items() if m == ult and ss == s) / tot_s, s)
                    for s in setores), reverse=True)
    nomes_setor = {"SERVICIOS": "Serviços", "CONSUMO": "Consumo", "VIVIENDA": "Habitação", "ACTIVIDADES INMOBILIARIAS": "Imobiliário",
                   "COMERCIO AL POR MAYOR": "Atacado", "COMERCIO AL POR MENOR": "Varejo", "GANADERIA": "Pecuária",
                   "SECTOR FINANCIERO": "Setor financeiro", "INDUSTRIA": "Indústria", "CONSTRUCCION": "Construção",
                   "AGRICULTURA": "Agricultura", "OTROS": "Outros", "ADMINISTRACION PUBLICA": "Administração pública"}
    setor = dict(
        id="ueno-setor", titulo="Ueno Bank: crédito por setor",
        subtitulo=(f"Em % da carteira de cada um, {ult[5:]}/{ult[:4]}: a quem o banco empresta. O Ueno concentrava "
                   f"{pares[0][0]:.0f}% em serviços, setor que pesa {pares[0][1]:.0f}% no sistema"),
        unidade="pct1", fonte=FONTE, categorias=[nomes_setor.get(s, s.title()) for _, _, s in pares], barra=0.8, agrupadas=True,
        series=[serie("Ueno", LARANJA, {str(i): u for i, (u, _, _) in enumerate(pares)}, 1, tipo="barra"),
                serie("Sistema", BRANCO, {str(i): t for i, (_, t, _) in enumerate(pares)}, 1, tipo="barra")],
    )
    serv_u = {m: v / 1e6 for (m, e, s), v in S.items() if e == UENO and s == "SERVICIOS"}
    serv_f = {m: 100 * S[(m, UENO, "SERVICIOS")] / sum(v for (mm, e, s), v in S.items() if mm == m and s == "SERVICIOS")
              for m in serv_u}
    servicos = dict(
        id="ueno-servicos", titulo="Ueno Bank: crédito ao setor de serviços",
        subtitulo=(f"Crédito a empresas de serviços, o setor em que o Ueno mais cresceu: de ₲ {virg(serv_u[FUSAO])} tri em jun/2024 "
                   f"para ₲ {virg(serv_u[ult])} tri, {serv_f[ult]:.0f}% de todo o crédito a serviços do país"),
        unidade="gs-tri", fonte=FONTE,
        variantes=[
            dict(rot="Trilhões de guaranis", unidade="gs-tri", series=[serie("Ueno", LARANJA, serv_u, 2, tipo="barra", rotulo=True)]),
            dict(rot="% de todo o crédito a serviços do sistema", unidade="pct1",
                 series=[serie("Ueno", LARANJA, serv_f, 1, rotulo=True)]),
        ],
    )

    # ---------- depósitos por tipo e fatias no sistema
    C = collections.defaultdict(float)
    for r in ler_aba(b, "Carteras"):
        C[(mes(r["Fecha"]), r["Codigo Entidad"], r["Codigo Cuenta"])] += num(r["Importe"])
    tipos = [("Cta. Cte.", "Conta corrente", AZUL), ("A la Vista", "À vista", CIANO), ("Plazo Fijo", "Prazo fixo", VERDE),
             ("CDA", "CDA", LARANJA), ("Intereses Devengados", "Juros a pagar", ROXO)]
    total_tipo = lambda m, conta: sum(v for (mm, e, c), v in C.items() if mm == m and c == conta)
    dep_abs = [serie(nome, cor, {m: C.get((m, UENO, conta), 0) / 1e6 for m in meses}, 2, tipo="barra")
               for conta, nome, cor in tipos]
    dep_tot_u = {m: sum(C.get((m, UENO, c), 0) for c, _, _ in tipos) for m in meses}
    dep_tot_s = {m: sum(total_tipo(m, c) for c, _, _ in tipos) for m in meses}
    dep_abs.append(serie("Total", BRANCO, {m: v / 1e6 for m, v in dep_tot_u.items()}, 2, rotulo=True))
    dep_pct = [serie(nome, cor, {m: 100 * C.get((m, UENO, conta), 0) / total_tipo(m, conta) for m in meses if total_tipo(m, conta)}, 1)
               for conta, nome, cor in tipos]
    dep_pct.append(serie("Total", BRANCO, {m: 100 * dep_tot_u[m] / dep_tot_s[m] for m in meses}, 1, rotulo=True))
    depositos = dict(
        id="ueno-depositos", titulo="Ueno Bank: depósitos por tipo",
        subtitulo=("Saldo no fim do mês. Conta corrente e à vista são de saque livre; prazo fixo e CDA, aplicações com prazo. "
                   "O salto de jun/2024 é o Visión Banco"),
        unidade="gs-tri", fonte=FONTE, barra=1,
        variantes=[dict(rot="Trilhões de guaranis", unidade="gs-tri", series=dep_abs),
                   dict(rot="% do total de cada tipo no sistema", unidade="pct1", series=dep_pct)],
    )

    T = collections.defaultdict(float)
    for r in ler_aba(b, "TC"):
        T[(mes(r["Fecha"]), r["Codigo Entidad"], r["Clasificación"])] += num(r["Total"])
    Ch = collections.defaultdict(float)
    for r in ler_aba(b, "Canales & Person"):
        d = r["Descripción"].lower().replace("á", "a").strip()
        Ch[(mes(r["Fecha"]), r["Codigo Entidad"], d)] += num(r["Total"])

    def fatia(D, chave):
        out = {}
        for m in meses:
            t = sum(v for (mm, e, c), v in D.items() if mm == m and c == chave)
            if t:
                out[m] = 100 * D.get((m, UENO, chave), 0) / t
        return out
    cart = {m: sum(C.get((m, UENO, c), 0) for c in ("Cartera Vigente", "Cartera Vencida")) for m in meses}
    cart_s = {m: sum(total_tipo(m, c) for c in ("Cartera Vigente", "Cartera Vencida")) for m in meses}
    fatia_dep = 100 * dep_tot_u[ult] / dep_tot_s[ult]
    fatia_cart = 100 * cart[ult] / cart_s[ult]
    fatia_tc = fatia(T, "Cantidad")[ult]
    fatia_cnb = fatia(Ch, "corresponsal no bancario")[ult]
    fatias = dict(
        id="ueno-fatias", titulo="Ueno Bank: participação no sistema bancário",
        subtitulo=(f"Em % do total dos bancos do Paraguai. Pequeno em dinheiro ({fatia_dep:.0f}% dos depósitos, "
                   f"{fatia_cart:.0f}% do crédito), enorme em alcance: {fatia_tc:.0f}% dos cartões de crédito e "
                   f"{fatia_cnb:.0f}% dos correspondentes"),
        unidade="pct1", fonte=FONTE,
        variantes=[dict(rot=nome, unidade="pct1", series=[serie(nome, cor, dados, 1, rotulo=True)]) for nome, cor, dados in [
            ("Depósitos", AZUL, {m: 100 * dep_tot_u[m] / dep_tot_s[m] for m in meses}),
            ("Carteira de crédito", LARANJA, {m: 100 * cart[m] / cart_s[m] for m in meses}),
            ("Cartões de crédito (quantidade)", ROXO, fatia(T, "Cantidad")),
            ("Cartões de crédito (saldo devedor)", CIANO, fatia(T, "Saldo")),
            ("Correspondentes não bancários", AMARELO, fatia(Ch, "corresponsal no bancario"))]],
    )
    cnb_u = {m: Ch.get((m, UENO, "corresponsal no bancario"), 0) for m in meses}
    cnb_o = {m: sum(v for (mm, e, c), v in Ch.items() if mm == m and c == "corresponsal no bancario" and e != UENO) for m in meses}
    correspondentes = dict(
        id="ueno-correspondentes", titulo="Correspondentes não bancários: Ueno e demais bancos",
        subtitulo=("Pontos no fim do mês: mercearias, farmácias e lojas que recebem depósitos e pagam saques e contas em nome "
                   "do banco. É como ele chega a quem usa dinheiro vivo"),
        unidade="n", fonte=FONTE,
        series=[serie("Ueno", LARANJA, cnb_u, 0, rotulo=True), serie("Demais bancos", BRANCO, cnb_o, 0, rotulo=True)],
    )

    doc = dict(
        atualizado=datetime.date.today().isoformat(), referencia=ult, formato="artigo", fonte=FONTE,
        assunto="Ueno Bank", grupo="Análises Variadas",
        secoes=[dict(titulo="", graficos=[fatias, capital, crescimento, qualidade, setor, servicos, depositos, correspondentes])],
    )
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    u = lambda d: d.get(ult)
    print(f"gravado {os.path.relpath(SAIDA, RAIZ)}, até {ult}")
    print(f"  C1 {rat(UENO, T1)[ult]:.1f}% C2 {rat(UENO, T12)[ult]:.1f}% (sistema {rat(SISTEMA, T12)[ult]:.1f}%); "
          f"alavancagem {u(alav_u):.1f}x (sistema {u(alav_s):.1f}x); AYCP x{aycp_u[ult]/aycp_u[FUSAO]:.2f} desde a fusão "
          f"(sistema x{aycp_s[ult]/aycp_s[FUSAO]:.2f})")
    print(f"  serviços: ₲ {serv_u[ult]:.2f} tri ({serv_f[ult]:.1f}% do setor no sistema), contra ₲ {serv_u[FUSAO]:.2f} tri em {FUSAO}")


if __name__ == "__main__":
    main()

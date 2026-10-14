#!/usr/bin/env python3
"""
Monta dados/oferta-diesel.xlsx — de onde vem o diesel que o Brasil queima:
quanto sai das refinarias daqui, quanto vem de fora, e para onde vai a
demanda.

Uso:
    ~/.venvs/dados-economicos/bin/python scripts/oferta_diesel.py

Precisa de openpyxl. NÃO entra na Action. Tudo vem dos dados abertos da ANP,
mensais, em metros cúbicos, atualizados até o mês anterior.

ÓLEO DIESEL E BIODIESEL SÃO PRODUTOS DIFERENTES, e a planilha nunca soma um
no outro:

  - **Óleo diesel A** é o mineral, o que sai da refinaria ou vem importado.
  - **Biodiesel (B100)** é feito de óleo vegetal e gordura animal, é outro
    produto e é todo nacional.
  - **Óleo diesel B** é o que a distribuidora vende: diesel A com biodiesel
    misturado na proporção que a lei manda (B15 desde agosto de 2025).

O biodiesel entra aqui por uma razão só: sem ele as duas pontas não fecham.
A ANP mede VENDAS em diesel B e mede PRODUÇÃO e IMPORTAÇÃO em diesel A. Em
2025 foram 69,5 milhões de m³ vendidos contra 63,7 milhões de m³ de oferta de
diesel A — o buraco de 5,8 milhões não existe, é biodiesel (9,8 milhões
naquele ano). Por isso cada coluna diz qual dos três produtos está medindo.

O QUE É CADA CONTA

    oferta de diesel A   = produção nacional + importação − exportação
    % importado          = importação ÷ oferta de diesel A
    diesel A nas vendas  = vendas de diesel B − biodiesel misturado

A "produção nacional" é de todas as refinarias do país, não só as da
Petrobras: entram Mataripe (Acelen), Manguinhos (Refit), Riograndense, 3R
Potiguar e as demais. Os produtores que não são refinaria aparecem num
arquivo à parte da ANP e reportam zero diesel — a conta os inclui mesmo
assim, para o dia em que deixarem de reportar zero.

O QUE O NÚMERO NÃO É

  - "Vendas" é o que as DISTRIBUIDORAS venderam, não o consumo do país:
    produtor que vende direto a grande consumidor não passa por aí. É essa a
    maior parte da diferença entre a oferta e as vendas, junto com estoque.
  - Não há dado de estoque nesta planilha, então o resíduo entre oferta e
    vendas não é interpretável como variação de estoque.
  - O biodiesel misturado só existe na série da ANP a partir de 2017. Antes
    disso a coluna fica vazia, e "diesel A nas vendas" também — a mistura
    existia (B5 desde 2010), mas o volume não está publicado nesse arquivo.

QUEM IMPORTA

A série volumétrica de comércio exterior não diz quem trouxe a carga. Quem diz
é o Relatório de Desembaraços, que a ANP monta do Siscomex e publica por
empresa, e que começa em janeiro de 2020 — antes disso não há dado por agente.
Ele vem em quilos; a conversão para m³ usa 0,84 t/m³, que é o mesmo fator que a
própria ANP aplica (a densidade implícita entre os dois arquivos dá 0,840 em
quase todos os meses, o que mostra que a série volumétrica é este arquivo
dividido por 0,84).

Duas ressalvas, ambas na coluna de cobertura e no LEIA-ME:

  - O relatório nomeia o IMPORTADOR DE REGISTRO, não o dono final da carga.
    Trading que importa por conta de distribuidora aparece como trading.
  - Alguns meses saem incompletos e são completados depois. A coluna
    "cobertura" é o desembaraçado dividido pelo volumétrico do mesmo mês: onde
    ela foge de 100%, a abertura por agente daquele mês não fecha com o total.
"""
import csv
import datetime
import os
import sys
import urllib.request

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DADOS = os.path.join(RAIZ, "dados")
SAIDA = os.path.join(RAIZ, "oferta-diesel.xlsx")
CACHE = os.path.join(DADOS, ".cache-anp-oferta")

BASE = "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/"
ARQUIVOS = {
    "vendas": "vdpb/vendas-derivados-petroleo-e-etanol/vendas-combustiveis-m3-1990-2025.csv",
    "tipos": "vdpb/vct/vendas-oleo-diesel-tipo-m3-2013-2025.csv",
    "refinarias": "pppd/producao-derivados-petroleo-por-refinaria-m3-1990-2025.csv",
    "outros": "pppd/producao-derivados-outros-produtores-m3-2001-2025.csv",
    "comercio": "ie/derivados/importacoes-exportacoes-derivados-2000-2025.csv",
    "biodiesel": "vdpb/vendas-de-biodiesel/vendas-biodiesel-b100-m3.csv",
}
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                           " (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}

# Quem importou cada carga. Um .xlsx por ano, o primeiro de 2020.
DIESEL = "ÓLEO DIESEL"
MESES = {m: i for i, m in enumerate(
    "JAN FEV MAR ABR MAI JUN JUL AGO SET OUT NOV DEZ".split(), start=1)}


def baixar(nome):
    os.makedirs(CACHE, exist_ok=True)
    alvo = os.path.join(CACHE, os.path.basename(ARQUIVOS[nome]))
    if not os.path.exists(alvo) or os.path.getsize(alvo) < 1000:
        print("  baixando %s…" % os.path.basename(alvo))
        req = urllib.request.Request(BASE + ARQUIVOS[nome], headers=NAVEGADOR)
        with urllib.request.urlopen(req, timeout=300) as r, open(alvo, "wb") as f:
            f.write(r.read())
    return alvo


def num(s):
    s = (s or "").strip().strip('"')
    if not s or s == "-":
        return 0.0
    return float(s.replace(".", "").replace(",", "."))


def mes_de(ano, mes):
    """(ano, "JAN") → "2026-01"; aceita também "Janeiro"."""
    m = mes.strip().upper()[:3]
    if m not in MESES:
        raise ValueError("mês desconhecido: %r" % mes)
    return "%s-%02d" % (ano, MESES[m])


def linhas(nome):
    with open(baixar(nome), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            yield r


def soma_mensal(nome, coluna, **filtros):
    """{"AAAA-MM": soma} das linhas que casam com os filtros."""
    fora = {}
    for r in linhas(nome):
        if any(r.get(k, "").strip().upper() != v for k, v in filtros.items()):
            continue
        k = mes_de(r["ANO"], r["MÊS"])
        fora[k] = fora.get(k, 0.0) + num(r[coluna])
    return fora


def biodiesel_mensal():
    """O B100 vendido às distribuidoras, que é o que de fato foi misturado.
    Este arquivo tem o mês noutro formato ("08/2026") e é separado por
    vírgula, diferente de todos os outros da ANP."""
    fora = {}
    with open(baixar("biodiesel"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=","):
            mes, ano = r["Mês/Ano"].split("/")
            k = "%s-%02d" % (ano, int(mes))
            fora[k] = fora.get(k, 0.0) + num(r["Vendas de Biodiesel"])
    return fora


def rolagem(serie, meses_ordenados, janela=12):
    """Soma móvel de 12 meses, só quando os 12 existem."""
    fora, pos = {}, {m: i for i, m in enumerate(meses_ordenados)}
    for m in meses_ordenados:
        i = pos[m]
        if i + 1 < janela:
            continue
        bloco = [serie.get(x) for x in meses_ordenados[i + 1 - janela:i + 1]]
        if all(v is not None for v in bloco):
            fora[m] = sum(bloco)
    return fora


def montar():
    print("ANP, dados abertos…")
    vendas = soma_mensal("vendas", "VENDAS", PRODUTO=DIESEL)
    refin = soma_mensal("refinarias", "PRODUÇÃO", PRODUTO=DIESEL)
    outros = soma_mensal("outros", "PRODUÇÃO", PRODUTO=DIESEL)
    imp = soma_mensal("comercio", "IMPORTADO / EXPORTADO", PRODUTO=DIESEL,
                      **{"OPERAÇÃO COMERCIAL": "IMPORTAÇÃO"})
    exp = soma_mensal("comercio", "IMPORTADO / EXPORTADO", PRODUTO=DIESEL,
                      **{"OPERAÇÃO COMERCIAL": "EXPORTAÇÃO"})
    bio = biodiesel_mensal()
    for nome, s in (("vendas (diesel B)", vendas), ("produção refinarias", refin),
                    ("outros produtores", outros), ("importação", imp),
                    ("exportação", exp), ("biodiesel misturado", bio)):
        if s:
            d = sorted(s)
            print("  %-22s %4d meses, de %s a %s" % (nome, len(s), d[0], d[-1]))
        else:
            print("  %-22s vazio" % nome)
    if max(outros.values(), default=0) > 0:
        print("  (produtores que não são refinaria passaram a produzir diesel)")
    return vendas, refin, outros, imp, exp, bio


def mensal(vendas, refin, outros, imp, exp, bio):
    meses = sorted(set(vendas) | set(refin) | set(imp) | set(exp))
    # o balanço só faz sentido onde existe a série de comércio exterior
    meses = [m for m in meses if m >= min(set(imp) | set(exp))]
    producao = {m: refin.get(m, 0.0) + outros.get(m, 0.0) for m in meses}
    oferta = {m: producao[m] + imp.get(m, 0.0) - exp.get(m, 0.0) for m in meses}
    r_prod = rolagem(producao, meses)
    r_imp = rolagem(imp, meses)
    r_oferta = rolagem(oferta, meses)
    r_vendas = rolagem(vendas, meses)
    fora = []
    for m in meses:
        o = oferta[m]
        v = vendas.get(m)
        b = bio.get(m)
        fora.append((
            m, producao[m], imp.get(m, 0.0), exp.get(m, 0.0), o,
            imp.get(m, 0.0) / o if o else None,
            v, b, (v - b) if (v is not None and b is not None) else None,
            r_prod.get(m), r_imp.get(m), r_oferta.get(m), r_vendas.get(m),
            (r_imp[m] / r_oferta[m]) if m in r_imp and r_oferta.get(m) else None,
        ))
    return fora


def anual(vendas, refin, outros, imp, exp, bio):
    anos = sorted({m[:4] for m in set(vendas) | set(refin) | set(imp)})
    def soma(s, a):
        return sum(v for m, v in s.items() if m[:4] == a)
    def meses_com(s, a):
        return len({m for m in s if m[:4] == a})
    fora = []
    for a in anos:
        p = soma(refin, a) + soma(outros, a)
        i, e, v, b = soma(imp, a), soma(exp, a), soma(vendas, a), soma(bio, a)
        o = p + i - e
        if not (p or i or v):
            continue
        fora.append((a, meses_com(vendas, a) or meses_com(refin, a),
                     p, i, e, o, i / o if o else None,
                     v or None, b or None, (v - b) if (v and b) else None))
    return fora


def por_tipo():
    """Vendas de diesel B por tipo de enxofre, mensal, desde 2013."""
    acc, tipos = {}, set()
    for r in linhas("tipos"):
        p = r["PRODUTO"].strip()
        if "DIESEL" not in p.upper():
            continue
        tipos.add(p)
        k = mes_de(r["ANO"], r["MÊS"])
        acc.setdefault(k, {}).setdefault(p, 0.0)
        acc[k][p] += num(r["VENDAS"])
    ordem = sorted(tipos, key=lambda t: (-sum(d.get(t, 0) for d in acc.values()), t))
    return ordem, [[m] + [acc[m].get(t) for t in ordem] + [sum(acc[m].values())]
                   for m in sorted(acc)]


def por_refinaria():
    """Produção de diesel por refinaria, mensal."""
    acc, refs = {}, set()
    for r in linhas("refinarias"):
        if r["PRODUTO"].strip().upper() != DIESEL:
            continue
        nome = r["REFINARIA"].strip()
        refs.add(nome)
        k = mes_de(r["ANO"], r["MÊS"])
        acc.setdefault(k, {}).setdefault(nome, 0.0)
        acc[k][nome] += num(r["PRODUÇÃO"])
    ordem = sorted(refs, key=lambda t: (-sum(d.get(t, 0) for d in acc.values()), t))
    return ordem, [[m] + [acc[m].get(t) for t in ordem] + [sum(acc[m].values())]
                   for m in sorted(acc)]


# Tudo o que lê o Relatório de Desembaraços e classifica o importador vive em
# anp_desembaracos.py, compartilhado com oferta_gasolina.py: o download, o
# layout que muda de ano para ano, a classificação por tipo de agente, o
# calendário de quem era dono de cada refinaria e o perfil do fornecimento.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anp_desembaracos as ad

CLASSES = ad.CLASSES
nome_legivel = ad.nome_legivel


def desembaracos():
    """{"AAAA-MM": {importador: m³}} de diesel."""
    return ad.por_importador(ad.NCM_DIESEL, CACHE)


def producao_por_grupo():
    """{(mês, "petrobras"|"outras", região): m³} de diesel.

    Região é sempre "Brasil" por ora: a T.1 da FGV aloca o fornecimento ao
    MERCADO ATENDIDO e não à localização da planta, e essa fonte ainda não
    está identificada. Ver o LEIA-ME."""
    fora = {}
    for arq, col, grupo in (("refinarias", "REFINARIA", None),
                            ("outros", "PRODUTOR", "outras")):
        for r in linhas(arq):
            if r["PRODUTO"].strip().upper() != DIESEL:
                continue
            m = mes_de(r["ANO"], r["MÊS"])
            g = grupo or ad.dono(r[col], int(r["ANO"]),
                                 MESES[r["MÊS"].strip().upper()[:3]])
            k = (m, g, "Brasil")
            fora[k] = fora.get(k, 0.0) + num(r["PRODUÇÃO"])
    return fora


def importacao_por_classe(desemb):
    """{(mês, classe do importador, região): m³}."""
    fora = {}
    for m, d in desemb.items():
        for quem, v in d.items():
            k = (m, ad.classe(quem), "Brasil")
            fora[k] = fora.get(k, 0.0) + v
    return fora


def por_agente(desemb, imp):
    """Importação de diesel por tipo de agente, mensal, com a cobertura do mês."""
    linhas_ = []
    for m in sorted(desemb):
        d = desemb[m]
        soma = {c: 0.0 for c in CLASSES}
        for quem, v in d.items():
            soma[ad.classe(quem)] += v
        total = sum(soma.values())
        volumetrico = imp.get(m)
        linhas_.append([m] + [soma[c] for c in CLASSES] + [total,
                       (total / volumetrico) if volumetrico else None])
    return linhas_


def por_empresa(desemb, teto=20):
    """As maiores importadoras de diesel em coluna; o resto some em 'outras'."""
    acc = {}
    for d in desemb.values():
        for quem, v in d.items():
            acc[quem] = acc.get(quem, 0.0) + v
    ordem = sorted(acc, key=lambda q: (-acc[q], q))[:teto]
    resto = set(acc) - set(ordem)
    linhas_ = []
    for m in sorted(desemb):
        d = desemb[m]
        linhas_.append([m] + [d.get(q) for q in ordem]
                       + [sum(d.get(q, 0.0) for q in resto) or None,
                          sum(d.values())])
    return ordem, linhas_


def escrever(mes, ano, tipos, tipos_linhas, refs, refs_linhas,
             agente_linhas, emp, emp_linhas, perfil12, perfil1, hoje):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import precos_combustiveis as pc

    wb = Workbook()
    wb.remove(wb.active)
    leia = wb.create_sheet("LEIA-ME")
    for linha in [
        ["De onde vem o diesel que o Brasil queima"],
        ["Gerado em", hoje.strftime("%d/%m/%Y")],
        ["Fonte", "ANP, dados abertos (mensais, em metros cúbicos)"],
        [],
        ["Aba", "O que é"],
        ["Balanço anual", "Produção, importação, exportação e vendas por ano"],
        ["Balanço mensal", "O mesmo mês a mês, com soma móvel de 12 meses ao lado"],
        ["Vendas por tipo", "Diesel B por teor de enxofre (S-10, S-500…), desde 2013"],
        ["Produção por refinaria", "Quem produz o diesel, mês a mês"],
        ["Importação por agente", "Quem traz o diesel de fora, por tipo de agente, "
                                  "desde 2020"],
        ["Importação por empresa", "As 20 maiores importadoras em coluna, desde 2020"],
        ["Perfil do fornecimento", "Quanto do fornecimento veio de cada agente, em "
                                   "janela de 12 meses"],
        ["Perfil mensal", "O mesmo mês a mês, mais ruidoso e sem janela"],
        [],
        ["ÓLEO DIESEL E BIODIESEL SÃO PRODUTOS DIFERENTES, e esta planilha nunca soma "
         "um no outro."],
        ["Óleo diesel A", "O mineral: o que sai da refinaria ou vem importado."],
        ["Biodiesel (B100)", "Feito de óleo vegetal e gordura animal. Outro produto, "
                             "e todo nacional."],
        ["Óleo diesel B", "O que a distribuidora vende: diesel A com biodiesel "
                          "misturado na proporção que a lei manda (B15 desde 8/2025)."],
        [],
        ["O biodiesel entra aqui por uma razão só: sem ele as duas pontas não fecham. "
         "A ANP mede VENDAS em diesel B e mede"],
        ["PRODUÇÃO e IMPORTAÇÃO em diesel A. Em 2025 foram 69,5 milhões de m³ vendidos "
         "contra 63,7 milhões de oferta de diesel A"],
        ["— o buraco de 5,8 milhões não existe, é biodiesel (9,8 milhões naquele ano). "
         "Cada coluna diz qual produto está medindo."],
        [],
        ["As contas:"],
        ["oferta de diesel A", "= produção nacional + importação − exportação"],
        ["% importado", "= importação ÷ oferta de diesel A"],
        ["diesel A nas vendas", "= vendas de diesel B − biodiesel misturado"],
        [],
        ["A produção nacional é de TODAS as refinarias do país, não só as da Petrobras: "
         "entram Mataripe (Acelen), Manguinhos"],
        ["(Refit), Riograndense, 3R Potiguar e as demais. Produtores que não são "
         "refinaria reportam zero diesel à ANP; a conta"],
        ["os inclui mesmo assim, para o dia em que deixarem de reportar zero."],
        [],
        ["ATENÇÃO — 'vendas' é o que as DISTRIBUIDORAS venderam, não o consumo do país."],
        ["Produtor que vende direto a grande consumidor não passa por aí. É essa a maior "
         "parte da diferença entre a oferta e as"],
        ["vendas, junto com estoque. Não há dado de estoque aqui, então o resíduo entre "
         "as duas não é variação de estoque."],
        [],
        ["O biodiesel misturado só existe na série da ANP a partir de 2017. Antes disso "
         "a coluna fica vazia, e 'diesel A nas"],
        ["vendas' também — a mistura existia (B5 desde 2010), mas o volume não está "
         "publicado nesse arquivo."],
        [],
        ["QUEM IMPORTA"],
        ["A série volumétrica de comércio exterior não diz quem trouxe a carga. Quem "
         "diz é o Relatório de Desembaraços, que a"],
        ["ANP monta do Siscomex e publica por empresa. Ele começa em JANEIRO DE 2020 — "
         "antes disso não existe dado por agente."],
        ["Vem em quilos; a conversão para m³ usa 0,84 t/m³, o mesmo fator que a própria "
         "ANP aplica para montar o volumétrico."],
        [],
        ["importador de registro", "O relatório nomeia quem registrou a importação, não "
                                   "o dono final da carga. Trading que"],
        ["", "importa por conta de distribuidora aparece como trading."],
        ["cobertura", "= desembaraçado ÷ importação volumétrica do mesmo mês. Alguns "
                      "meses saem incompletos e"],
        ["", "são completados depois; onde a cobertura foge de 100%, a abertura por "
             "agente daquele mês não"],
        ["", "fecha com o total e não deve ser lida como participação."],
        ["classificação", "O tipo de agente é nosso, feito da razão social mais a "
                          "estrutura societária conhecida. O"],
        ["", "braço trading de um grupo (Vibra Trading, Royal FIC Comercial) vai com o "
             "grupo, não com as"],
        ["", "tradings independentes. A aba por empresa traz o dado cru, sem "
             "classificação."],
        [],
        ["A soma móvel de 12 meses existe porque o diesel tem sazonalidade forte "
         "(safra, chuva, feriado). Mês contra mês do"],
        ["ano anterior também serve; mês contra mês anterior, não."],
    ]:
        leia.append(linha)
    leia["A1"].font = Font(bold=True, size=14)
    leia["A5"].font = leia["B5"].font = Font(bold=True)
    for lin in leia.iter_rows(min_col=1, max_col=1):
        t = lin[0].value or ""
        if t.startswith(("ÓLEO DIESEL E BIODIESEL", "ATENÇÃO", "As contas:",
                         "QUEM IMPORTA")):
            lin[0].font = Font(bold=True)
    for col, larg in zip("AB", (24, 106)):
        leia.column_dimensions[col].width = larg

    m3 = "#,##0"
    pc.aba(wb, "Balanço anual",
           ["ano", "meses", "produção nacional (diesel A)", "importação (diesel A)",
            "exportação (diesel A)", "oferta de diesel A", "% importado",
            "vendas (diesel B)", "biodiesel misturado", "diesel A nas vendas"],
           ano, larguras=[7, 8, 27, 22, 22, 20, 12, 20, 22, 22],
           formato={3: m3, 4: m3, 5: m3, 6: m3, 7: "0.0%", 8: m3, 9: m3, 10: m3})

    pc.aba(wb, "Balanço mensal",
           ["mês", "produção nacional", "importação", "exportação",
            "oferta de diesel A", "% importado", "vendas (diesel B)",
            "biodiesel misturado", "diesel A nas vendas",
            "produção 12m", "importação 12m", "oferta 12m", "vendas 12m",
            "% importado 12m"],
           mes, larguras=[9, 19, 14, 14, 20, 12, 19, 21, 21, 15, 15, 15, 15, 17],
           formato={2: m3, 3: m3, 4: m3, 5: m3, 6: "0.0%", 7: m3, 8: m3, 9: m3,
                    10: m3, 11: m3, 12: m3, 13: m3, 14: "0.0%"})

    pc.aba(wb, "Vendas por tipo", ["mês"] + tipos + ["total"], tipos_linhas,
           larguras=[9] + [20] * (len(tipos) + 1),
           formato={i: m3 for i in range(2, len(tipos) + 3)})

    pc.aba(wb, "Produção por refinaria", ["mês"] + refs + ["total"], refs_linhas,
           larguras=[9] + [15] * (len(refs) + 1),
           formato={i: m3 for i in range(2, len(refs) + 3)})

    pc.aba(wb, "Importação por agente",
           ["mês"] + CLASSES + ["total desembaraçado", "cobertura"], agente_linhas,
           larguras=[9] + [21] * len(CLASSES) + [20, 11],
           formato={**{i: m3 for i in range(2, len(CLASSES) + 3)},
                    len(CLASSES) + 3: "0.0%"})

    pc.aba(wb, "Importação por empresa",
           ["mês"] + [nome_legivel(e) for e in emp] + ["outras", "total"],
           emp_linhas,
           larguras=[9] + [26] * (len(emp) + 2),
           formato={i: m3 for i in range(2, len(emp) + 4)})

    cab_perfil = ["mês", "âmbito", "Refinarias e Centrais Petroquímicas",
                  "Petrobras", "Outras", "Importações", "Tradings",
                  "Distribuidores", "volume no período (m³)"]
    larg_perfil = [9, 9, 32, 12, 12, 13, 12, 15, 21]
    fmt_perfil = {i: "0.0" for i in range(3, 9)}
    fmt_perfil[9] = m3
    pc.aba(wb, "Perfil do fornecimento", cab_perfil, perfil12,
           larguras=larg_perfil, formato=fmt_perfil)
    pc.aba(wb, "Perfil mensal", cab_perfil, perfil1,
           larguras=larg_perfil, formato=fmt_perfil)

    wb.save(SAIDA)


def main():
    hoje = datetime.date.today()
    dados = montar()
    mes = mensal(*dados)
    ano = anual(*dados)
    print("Vendas por tipo…")
    tipos, tipos_linhas = por_tipo()
    print("  %d tipos, %d meses" % (len(tipos), len(tipos_linhas)))
    print("Produção por refinaria…")
    refs, refs_linhas = por_refinaria()
    print("  %d refinarias, %d meses" % (len(refs), len(refs_linhas)))
    print("Importação por agente…")
    desemb = desembaracos()
    agente_linhas = por_agente(desemb, dados[3])
    emp, emp_linhas = por_empresa(desemb)
    print("  %d meses, de %s a %s" % (len(desemb), min(desemb), max(desemb)))
    ruins = [l[0] for l in agente_linhas if l[-1] and abs(l[-1] - 1) > 0.05]
    if ruins:
        print("  cobertura fora de ±5%% em: %s" % ", ".join(ruins))

    print("\nbalanço do diesel A, por ano (mil m³):")
    print("  %4s %4s %10s %10s %9s %10s %7s %10s" %
          ("ano", "mes", "produção", "import", "export", "oferta", "%imp", "vendas B"))
    for a, n, p, i, e, o, pc_, v, b, da in ano[-12:]:
        print("  %4s %4d %10.0f %10.0f %9.0f %10.0f %6.1f%% %10s"
              % (a, n, p / 1e3, i / 1e3, e / 1e3, o / 1e3, 100 * (pc_ or 0),
                 "%.0f" % (v / 1e3) if v else "-"))

    print("Perfil do fornecimento…")
    prod_g = producao_por_grupo()
    imp_c = importacao_por_classe(desemb)
    meses_perfil = sorted({m for m, _, _ in prod_g} | {m for m, _, _ in imp_c})
    meses_perfil = [m for m in meses_perfil if m >= min(desemb)]
    perfil12 = ad.perfil(prod_g, imp_c, meses_perfil, janela=12)
    perfil1 = ad.perfil(prod_g, imp_c, meses_perfil, janela=1)
    print("  %d pontos em janela de 12 meses, de %s a %s"
          % (len(perfil12), perfil12[0][0], perfil12[-1][0]))

    escrever(mes, ano, tipos, tipos_linhas, refs, refs_linhas,
             agente_linhas, emp, emp_linhas, perfil12, perfil1, hoje)
    print("\ngravado %s (%.0f KB)"
          % (os.path.relpath(SAIDA, RAIZ), os.path.getsize(SAIDA) / 1024))


if __name__ == "__main__":
    main()

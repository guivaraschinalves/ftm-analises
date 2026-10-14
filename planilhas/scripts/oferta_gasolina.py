#!/usr/bin/env python3
"""
Monta dados/oferta-gasolina.xlsx — de onde vem a gasolina que o Brasil queima:
quanto sai das refinarias daqui, quanto vem de fora, quem traz, e para onde vai
a demanda.

Uso:
    ~/.venvs/dados-economicos/bin/python scripts/oferta_gasolina.py

Precisa de openpyxl. NÃO entra na Action. Gêmeo de oferta_diesel.py, com as
diferenças que a gasolina impõe e que estão explicadas abaixo.

GASOLINA A, ETANOL ANIDRO E GASOLINA C SÃO COISAS DIFERENTES, e a planilha
nunca soma uma na outra:

  - **Gasolina A** é a mineral, o que sai da refinaria ou vem importado.
  - **Etanol anidro** é o etanol sem água que se mistura à gasolina A. É outro
    produto, e é todo nacional.
  - **Gasolina C** é o que a distribuidora vende: gasolina A com anidro
    misturado no percentual que a lei manda (E32 desde agosto de 2026).

TRÊS FONTES DE PRODUÇÃO, NÃO UMA

No diesel basta somar refinarias e "outros produtores". Na gasolina há uma
terceira fonte que importa: as **centrais petroquímicas** (as três unidades da
Braskem) produzem gasolina A como subproduto — cerca de 22 mil barris por dia,
algo em torno de 4% da produção nacional, estável há vinte anos. No diesel elas
reportam zero, e é por isso que oferta_diesel.py as ignora. Aqui elas entram em
coluna própria.

A PONTE ENTRE AS DUAS PONTAS É O PERCENTUAL LEGAL, NÃO UM VOLUME MEDIDO

Esta é a diferença grande em relação ao diesel, e é uma piora. A ANP mede
VENDAS em gasolina C e mede PRODUÇÃO e IMPORTAÇÃO em gasolina A — igual ao
diesel. Mas no diesel ela publica o volume de biodiesel efetivamente vendido às
distribuidoras, que é o que de fato foi misturado. **No caso do anidro não
existe série equivalente nos dados abertos.** O que a ANP publica sobre anidro
é meta de contratação e de estoque por safra, não volume mensal misturado.

Então a coluna "gasolina A nas vendas" aqui é derivada do PERCENTUAL
OBRIGATÓRIO, dia a dia, pela cronologia oficial do MAPA e pelas resoluções do
CNPE. É parâmetro legal, não medição. Duas consequências:

  - A gasolina premium continua em 25% de anidro mesmo quando a comum está em
    30% ou 32%. Como a premium é fatia pequena do mercado, o teor efetivo fica
    um pouco abaixo do mandatório, e portanto a "gasolina A nas vendas" fica um
    pouco subestimada.
  - Onde o percentual mudou no meio do mês, a coluna "teor de anidro" é a média
    do mês ponderada por dias, não o percentual do dia 1º.

O QUE É CADA CONTA

    produção nacional     = refinarias + centrais petroquímicas + outros
    oferta de gasolina A  = produção nacional + importação − exportação
    % importado           = importação ÷ oferta de gasolina A
    gasolina A nas vendas = vendas de gasolina C × (1 − teor de anidro)

QUEM IMPORTA

A série volumétrica de comércio exterior não diz quem trouxe a carga. Quem diz
é o Relatório de Desembaraços, que a ANP monta do Siscomex e publica por
empresa, e que começa em janeiro de 2020 — antes disso não há dado por agente.
Ele vem em quilos; a conversão para m³ usa 0,74 t/m³, que é o mesmo fator que a
própria ANP aplica (a densidade implícita entre os dois arquivos dá 0,740 em
praticamente todos os meses, o que mostra que a série volumétrica é este
arquivo dividido por 0,74).

Duas ressalvas, ambas na coluna de cobertura e no LEIA-ME:

  - O relatório nomeia o IMPORTADOR DE REGISTRO, não o dono final da carga.
    Trading que importa por conta de distribuidora aparece como trading.
  - Alguns meses saem incompletos e são completados depois. A coluna
    "cobertura" é o desembaraçado dividido pelo volumétrico do mesmo mês: onde
    ela foge de 100%, a abertura por agente daquele mês não fecha com o total.

O QUE O NÚMERO NÃO É

  - "Vendas" é o que as DISTRIBUIDORAS venderam, não o consumo do país.
  - Não há dado de estoque aqui, então o resíduo entre oferta e vendas não é
    interpretável como variação de estoque.
  - Gasolina de aviação é outro produto e não entra em nenhuma conta.
"""
import csv
import datetime
import os
import sys
import urllib.request

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DADOS = os.path.join(RAIZ, "dados")
SAIDA = os.path.join(RAIZ, "oferta-gasolina.xlsx")
CACHE = os.path.join(DADOS, ".cache-anp-oferta")   # o mesmo do diesel

BASE = "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/"
ARQUIVOS = {
    "vendas": "vdpb/vendas-derivados-petroleo-e-etanol/vendas-combustiveis-m3-1990-2025.csv",
    "refinarias": "pppd/producao-derivados-petroleo-por-refinaria-m3-1990-2025.csv",
    "petroquimicas": "pppd/producao-derivados-centrais-petroquimicas-m3-2001-2025.csv",
    "outros": "pppd/producao-derivados-outros-produtores-m3-2001-2025.csv",
    "comercio": "ie/derivados/importacoes-exportacoes-derivados-2000-2025.csv",
}
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                           " (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}

GASOLINA_A = "GASOLINA A"
GASOLINA_C = "GASOLINA C"
MESES = {m: i for i, m in enumerate(
    "JAN FEV MAR ABR MAI JUN JUL AGO SET OUT NOV DEZ".split(), start=1)}

# Percentual obrigatório de etanol anidro na gasolina C comum, com a data em
# que passou a valer. Fonte: "Cronologia da mistura carburante (etanol anidro)
# na gasolina no Brasil", MAPA/Agroenergia, e as resoluções do CNPE para E30 e
# E32. A gasolina premium seguiu em 25% desde 2015 e não está aqui.
MISTURA = [
    (datetime.date(2000, 8, 20), 0.20),   # Decreto 3.552/00
    (datetime.date(2001, 5, 31), 0.22),   # Decreto 3.824/01
    (datetime.date(2002, 1, 10), 0.24),   # Portaria MAPA 589/01
    (datetime.date(2002, 7, 1), 0.25),    # Portaria MAPA 266/02
    (datetime.date(2003, 2, 1), 0.20),    # Portaria MAPA 17/03
    (datetime.date(2003, 6, 1), 0.25),    # Portaria MAPA 554/03
    (datetime.date(2005, 10, 14), 0.20),  # Portaria MAPA 429/05
    (datetime.date(2006, 11, 20), 0.23),  # Portaria MAPA 278/06
    (datetime.date(2007, 7, 1), 0.25),    # Portaria MAPA 143/07
    (datetime.date(2010, 2, 1), 0.20),    # Portaria MAPA 7/10
    (datetime.date(2010, 5, 2), 0.25),
    (datetime.date(2011, 10, 1), 0.20),   # Portaria MAPA 678/11
    (datetime.date(2013, 5, 1), 0.25),    # Portaria MAPA 105/13
    (datetime.date(2015, 3, 16), 0.27),   # Portaria MAPA 75/15
    (datetime.date(2025, 8, 1), 0.30),    # Resolução CNPE 9/2025
    (datetime.date(2026, 8, 1), 0.32),    # Resolução CNPE 9/2026, temporária
]


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
    m = mes.strip().upper()[:3]
    if m not in MESES:
        raise ValueError("mês desconhecido: %r" % mes)
    return "%s-%02d" % (ano, MESES[m])


def linhas(nome):
    with open(baixar(nome), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            yield r


def soma_mensal(nome, coluna, **filtros):
    fora = {}
    for r in linhas(nome):
        if any(r.get(k, "").strip().upper() != v for k, v in filtros.items()):
            continue
        k = mes_de(r["ANO"], r["MÊS"])
        fora[k] = fora.get(k, 0.0) + num(r[coluna])
    return fora


def teor_do_mes(chave):
    """Teor obrigatório médio do mês "AAAA-MM", ponderado por dias corridos.
    Devolve None antes do primeiro percentual da tabela."""
    ano, mes = int(chave[:4]), int(chave[5:])
    dia = datetime.date(ano, mes, 1)
    fim = (datetime.date(ano + (mes == 12), mes % 12 + 1, 1))
    soma, dias = 0.0, 0
    while dia < fim:
        vigente = None
        for desde, pct in MISTURA:
            if desde <= dia:
                vigente = pct
        if vigente is None:
            return None
        soma += vigente
        dias += 1
        dia += datetime.timedelta(days=1)
    return soma / dias


def rolagem(serie, meses_ordenados, janela=12):
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
    vendas = soma_mensal("vendas", "VENDAS", PRODUTO=GASOLINA_C)
    refin = soma_mensal("refinarias", "PRODUÇÃO", PRODUTO=GASOLINA_A)
    petroq = soma_mensal("petroquimicas", "PRODUÇÃO", PRODUTO=GASOLINA_A)
    outros = soma_mensal("outros", "PRODUÇÃO", PRODUTO=GASOLINA_A)
    imp = soma_mensal("comercio", "IMPORTADO / EXPORTADO", PRODUTO=GASOLINA_A,
                      **{"OPERAÇÃO COMERCIAL": "IMPORTAÇÃO"})
    exp = soma_mensal("comercio", "IMPORTADO / EXPORTADO", PRODUTO=GASOLINA_A,
                      **{"OPERAÇÃO COMERCIAL": "EXPORTAÇÃO"})
    for nome, s in (("vendas (gasolina C)", vendas), ("produção refinarias", refin),
                    ("centrais petroquímicas", petroq), ("outros produtores", outros),
                    ("importação", imp), ("exportação", exp)):
        if s:
            d = sorted(s)
            print("  %-24s %4d meses, de %s a %s" % (nome, len(s), d[0], d[-1]))
        else:
            print("  %-24s vazio" % nome)
    return vendas, refin, petroq, outros, imp, exp


def mensal(vendas, refin, petroq, outros, imp, exp):
    meses = sorted(set(vendas) | set(refin) | set(imp) | set(exp))
    meses = [m for m in meses if m >= min(set(imp) | set(exp))]
    producao = {m: refin.get(m, 0.0) + petroq.get(m, 0.0) + outros.get(m, 0.0)
                for m in meses}
    oferta = {m: producao[m] + imp.get(m, 0.0) - exp.get(m, 0.0) for m in meses}
    r_prod = rolagem(producao, meses)
    r_imp = rolagem(imp, meses)
    r_oferta = rolagem(oferta, meses)
    r_vendas = rolagem(vendas, meses)
    fora = []
    for m in meses:
        o = oferta[m]
        v = vendas.get(m)
        t = teor_do_mes(m)
        fora.append((
            m, refin.get(m, 0.0), petroq.get(m, 0.0), outros.get(m, 0.0),
            producao[m], imp.get(m, 0.0), exp.get(m, 0.0), o,
            imp.get(m, 0.0) / o if o else None,
            t, v, (v * (1 - t)) if (v is not None and t is not None) else None,
            r_prod.get(m), r_imp.get(m), r_oferta.get(m), r_vendas.get(m),
            (r_imp[m] / r_oferta[m]) if m in r_imp and r_oferta.get(m) else None,
        ))
    return fora


def anual(vendas, refin, petroq, outros, imp, exp):
    anos = sorted({m[:4] for m in set(vendas) | set(refin) | set(imp)})
    def soma(s, a):
        return sum(v for m, v in s.items() if m[:4] == a)
    def meses_com(s, a):
        return len({m for m in s if m[:4] == a})
    fora = []
    for a in anos:
        p = soma(refin, a) + soma(petroq, a) + soma(outros, a)
        i, e, v = soma(imp, a), soma(exp, a), soma(vendas, a)
        o = p + i - e
        if not (p or i or v):
            continue
        # o teor do ano é ponderado pelas vendas de cada mês, não média simples
        pares = [(teor_do_mes(m), vendas[m]) for m in vendas if m[:4] == a]
        pares = [(t, w) for t, w in pares if t is not None]
        teor = sum(t * w for t, w in pares) / sum(w for t, w in pares) if pares else None
        fora.append((a, meses_com(vendas, a) or meses_com(refin, a),
                     p, i, e, o, i / o if o else None, teor,
                     v or None, (v * (1 - teor)) if (v and teor) else None))
    return fora


def por_refinaria():
    """Produção de gasolina A por planta, mensal. Junta refinarias, centrais
    petroquímicas e outros produtores, com a origem no nome da coluna."""
    acc, plantas = {}, set()
    for arq, col, marca in (("refinarias", "REFINARIA", ""),
                            ("petroquimicas", "CENTRAL PETROQUÍMICA", " (petroq.)"),
                            ("outros", "PRODUTOR", " (outros)")):
        for r in linhas(arq):
            if r["PRODUTO"].strip().upper() != GASOLINA_A:
                continue
            nome = r[col].strip() + marca
            plantas.add(nome)
            k = mes_de(r["ANO"], r["MÊS"])
            acc.setdefault(k, {}).setdefault(nome, 0.0)
            acc[k][nome] += num(r["PRODUÇÃO"])
    ordem = sorted(plantas, key=lambda t: (-sum(d.get(t, 0) for d in acc.values()), t))
    return ordem, [[m] + [acc[m].get(t) for t in ordem] + [sum(acc[m].values())]
                   for m in sorted(acc)]


# Tudo o que lê o Relatório de Desembaraços e classifica o importador vive em
# anp_desembaracos.py, compartilhado com oferta_diesel.py: o download, o
# layout que muda de ano para ano, a classificação por tipo de agente, o mapa
# CNPJ→UF e o perfil do fornecimento no formato da FGV.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anp_desembaracos as ad

CLASSES = ad.CLASSES
nome_legivel = ad.nome_legivel


def desembaracos():
    """{"AAAA-MM": {importador: m³}} de gasolina A."""
    return ad.por_importador(ad.NCM_GASOLINA, CACHE)


def por_agente(desemb, imp):
    linhas_ = []
    for m in sorted(desemb):
        soma = {c: 0.0 for c in CLASSES}
        for quem, v in desemb[m].items():
            soma[ad.classe(quem)] += v
        total = sum(soma.values())
        volumetrico = imp.get(m)
        linhas_.append([m] + [soma[c] for c in CLASSES] + [total,
                       (total / volumetrico) if volumetrico else None])
    return linhas_


def nome_legivel(razao):
    """ATEM'S DISTRIBUIDORA → Atem's Distribuidora."""
    bonito = razao.title()
    return bonito.replace("'S", "'s")


def por_empresa(desemb, teto=20):
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


def producao_por_grupo():
    """{(mês, "petrobras"|"outras", região): m³} de gasolina A.

    Por ora a região é sempre "Brasil". O recorte por região esbarra numa
    questão de método ainda em aberto: a tabela T.1 da FGV aloca o
    fornecimento ao MERCADO ATENDIDO, não à localização da planta — no
    Centro-Oeste não há refinaria nenhuma e ainda assim a Petrobras aparece
    com 95%. Alocar por UF da planta responde outra pergunta, e por isso não
    está aqui. Quando aparecer a fonte de vendas por produtor e destino, basta
    trocar "Brasil" pela região."""
    fora = {}
    for arq, col, grupo in (("refinarias", "REFINARIA", None),
                            ("petroquimicas", "CENTRAL PETROQUÍMICA", "outras"),
                            ("outros", "PRODUTOR", "outras")):
        for r in linhas(arq):
            if r["PRODUTO"].strip().upper() != GASOLINA_A:
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


def escrever(mes, ano, plantas, plantas_linhas, agente_linhas, emp, emp_linhas,
             perfil12, perfil1, hoje):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import precos_combustiveis as pc

    wb = Workbook()
    wb.remove(wb.active)
    leia = wb.create_sheet("LEIA-ME")
    for linha in [
        ["De onde vem a gasolina que o Brasil queima"],
        ["Gerado em", hoje.strftime("%d/%m/%Y")],
        ["Fonte", "ANP, dados abertos (mensais, em metros cúbicos)"],
        [],
        ["Aba", "O que é"],
        ["Balanço anual", "Produção, importação, exportação e vendas por ano"],
        ["Balanço mensal", "O mesmo mês a mês, com soma móvel de 12 meses ao lado"],
        ["Produção por planta", "Quem produz a gasolina A, mês a mês"],
        ["Importação por agente", "Quem traz a gasolina de fora, por tipo de agente, "
                                  "desde 2020"],
        ["Importação por empresa", "As 20 maiores importadoras em coluna, desde 2020"],
        ["Perfil do fornecimento", "Quanto do fornecimento veio de cada agente, em "
                                   "janela de 12 meses"],
        ["Perfil mensal", "O mesmo mês a mês, mais ruidoso e sem janela"],
        [],
        ["GASOLINA A, ETANOL ANIDRO E GASOLINA C SÃO COISAS DIFERENTES, e esta planilha "
         "nunca soma uma na outra."],
        ["Gasolina A", "A mineral: o que sai da refinaria ou vem importado."],
        ["Etanol anidro", "Etanol sem água, misturado à gasolina A. Outro produto, e "
                          "todo nacional."],
        ["Gasolina C", "O que a distribuidora vende: gasolina A com anidro no "
                       "percentual que a lei manda (E32 desde 8/2026)."],
        [],
        ["TRÊS FONTES DE PRODUÇÃO, NÃO UMA"],
        ["No diesel basta somar refinarias e 'outros produtores'. Na gasolina há uma "
         "terceira fonte que importa: as centrais"],
        ["petroquímicas (as três unidades da Braskem) produzem gasolina A como "
         "subproduto, cerca de 4% da produção nacional,"],
        ["estável há vinte anos. No diesel elas reportam zero, e é por isso que a "
         "planilha do diesel as ignora. Aqui têm coluna."],
        [],
        ["As contas:"],
        ["produção nacional", "= refinarias + centrais petroquímicas + outros produtores"],
        ["oferta de gasolina A", "= produção nacional + importação − exportação"],
        ["% importado", "= importação ÷ oferta de gasolina A"],
        ["gasolina A nas vendas", "= vendas de gasolina C × (1 − teor de anidro)"],
        [],
        ["ATENÇÃO — 'gasolina A nas vendas' é DERIVADA DO PERCENTUAL LEGAL, não de um "
         "volume medido."],
        ["No diesel a ANP publica o biodiesel efetivamente vendido às distribuidoras. "
         "Para o etanol anidro não existe série"],
        ["equivalente nos dados abertos: o que a ANP publica é meta de contratação e de "
         "estoque por safra, não volume mensal"],
        ["misturado. Então o teor vem da cronologia oficial do MAPA e das resoluções do "
         "CNPE, dia a dia. Duas consequências:"],
        ["", "a gasolina premium seguiu em 25% de anidro mesmo com a comum em 30% ou "
             "32%; como a premium é fatia pequena,"],
        ["", "o teor efetivo fica um pouco abaixo do mandatório e a 'gasolina A nas "
             "vendas' fica um pouco subestimada."],
        ["", "Onde o percentual mudou no meio do mês, 'teor de anidro' é a média do mês "
             "ponderada por dias, não o do dia 1º."],
        [],
        ["QUEM IMPORTA"],
        ["A série volumétrica de comércio exterior não diz quem trouxe a carga. Quem "
         "diz é o Relatório de Desembaraços, que a"],
        ["ANP monta do Siscomex e publica por empresa. Ele começa em JANEIRO DE 2020 — "
         "antes disso não existe dado por agente."],
        ["Vem em quilos; a conversão para m³ usa 0,74 t/m³, o mesmo fator que a própria "
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
                          "estrutura societária conhecida. A aba"],
        ["", "por empresa traz o dado cru, sem classificação."],
        [],
        ["ATENÇÃO — 'vendas' é o que as DISTRIBUIDORAS venderam, não o consumo do país."],
        ["Não há dado de estoque aqui, então o resíduo entre oferta e vendas não é "
         "variação de estoque. Gasolina de aviação é"],
        ["outro produto e não entra em nenhuma conta."],
        [],
        ["A soma móvel de 12 meses existe porque a gasolina tem sazonalidade (férias, "
         "safra, preço relativo do etanol hidratado,"],
        ["que concorre com ela no tanque do flex). Mês contra mês do ano anterior "
         "também serve; mês contra mês anterior, não."],
    ]:
        leia.append(linha)
    leia["A1"].font = Font(bold=True, size=14)
    leia["A5"].font = leia["B5"].font = Font(bold=True)
    for lin in leia.iter_rows(min_col=1, max_col=1):
        t = lin[0].value or ""
        if t.startswith(("GASOLINA A, ETANOL", "ATENÇÃO", "As contas:", "QUEM IMPORTA",
                         "TRÊS FONTES")):
            lin[0].font = Font(bold=True)
    for col, larg in zip("AB", (24, 106)):
        leia.column_dimensions[col].width = larg

    m3 = "#,##0"
    pc.aba(wb, "Balanço anual",
           ["ano", "meses", "produção nacional (gasolina A)", "importação (gasolina A)",
            "exportação (gasolina A)", "oferta de gasolina A", "% importado",
            "teor de anidro", "vendas (gasolina C)", "gasolina A nas vendas"],
           ano, larguras=[7, 8, 29, 24, 24, 21, 12, 15, 21, 22],
           formato={3: m3, 4: m3, 5: m3, 6: m3, 7: "0.0%", 8: "0.0%", 9: m3, 10: m3})

    pc.aba(wb, "Balanço mensal",
           ["mês", "refinarias", "centrais petroquímicas", "outros produtores",
            "produção nacional", "importação", "exportação", "oferta de gasolina A",
            "% importado", "teor de anidro", "vendas (gasolina C)",
            "gasolina A nas vendas",
            "produção 12m", "importação 12m", "oferta 12m", "vendas 12m",
            "% importado 12m"],
           mes, larguras=[9, 13, 22, 18, 18, 13, 13, 21, 12, 14, 20, 21,
                          15, 15, 15, 15, 17],
           formato={2: m3, 3: m3, 4: m3, 5: m3, 6: m3, 7: m3, 8: m3, 9: "0.0%",
                    10: "0.0%", 11: m3, 12: m3, 13: m3, 14: m3, 15: m3, 16: m3,
                    17: "0.0%"})

    pc.aba(wb, "Produção por planta", ["mês"] + plantas + ["total"], plantas_linhas,
           larguras=[9] + [19] * (len(plantas) + 1),
           formato={i: m3 for i in range(2, len(plantas) + 3)})

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
    print("Produção por planta…")
    plantas, plantas_linhas = por_refinaria()
    print("  %d plantas, %d meses" % (len(plantas), len(plantas_linhas)))
    print("Importação por agente…")
    desemb = desembaracos()
    agente_linhas = por_agente(desemb, dados[4])
    emp, emp_linhas = por_empresa(desemb)
    print("  %d meses, de %s a %s" % (len(desemb), min(desemb), max(desemb)))
    ruins = [l[0] for l in agente_linhas if l[-1] and abs(l[-1] - 1) > 0.05]
    if ruins:
        print("  cobertura fora de ±5%% em: %s" % ", ".join(ruins))

    print("\nbalanço da gasolina A, por ano (mil m³):")
    print("  %4s %4s %10s %10s %9s %10s %7s %7s %10s" %
          ("ano", "mes", "produção", "import", "export", "oferta", "%imp", "anidro",
           "vendas C"))
    for a, n, p, i, e, o, pc_, t, v, ga in ano[-12:]:
        print("  %4s %4d %10.0f %10.0f %9.0f %10.0f %6.1f%% %6.1f%% %10s"
              % (a, n, p / 1e3, i / 1e3, e / 1e3, o / 1e3, 100 * (pc_ or 0),
                 100 * (t or 0), "%.0f" % (v / 1e3) if v else "-"))

    print("Perfil do fornecimento…")
    prod_g = producao_por_grupo()
    imp_c = importacao_por_classe(desemb)
    meses_perfil = sorted({m for m, _, _ in prod_g} | {m for m, _, _ in imp_c})
    meses_perfil = [m for m in meses_perfil if m >= min(desemb)]
    perfil12 = ad.perfil(prod_g, imp_c, meses_perfil, janela=12)
    perfil1 = ad.perfil(prod_g, imp_c, meses_perfil, janela=1)
    print("  %d pontos em janela de 12 meses, de %s a %s"
          % (len(perfil12), perfil12[0][0], perfil12[-1][0]))

    escrever(mes, ano, plantas, plantas_linhas, agente_linhas, emp, emp_linhas,
             perfil12, perfil1, hoje)
    print("\ngravado %s (%.0f KB)"
          % (os.path.relpath(SAIDA, RAIZ), os.path.getsize(SAIDA) / 1024))


if __name__ == "__main__":
    main()

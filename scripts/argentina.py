#!/usr/bin/env python3
"""
Argentina: risco país, dólar blue, dólar oficial e brecha cambial (diários),
reservas internacionais (bruta, ativos e passivos, líquida) e inflação.
Gera dados/argentina.json. Só biblioteca padrão. Rodado à mão. Página
própria: argentina.html (fora do índice).

Pedido dele em 26/11/2026. Todo gráfico mostra a série inteira com a marca
da posse de Milei (10/12/2023; nas séries mensais, dez/2023). O recorte só
desde a posse saiu a pedido dele.

DE ONDE VEM CADA COISA (Ámbito, mercados.ambito.com, histórico geral)

  - riesgopais/historico-general: risco país (EMBI do JP Morgan) em pontos
    básicos, desde dez/1998. Datas "dd-mm-aaaa".
  - dolar/informal/historico-general: dólar blue, compra e venda, desde
    jan/2002. Datas "dd/mm/aaaa".
  - dolar/oficial/historico-general: dólar oficial do Ámbito (varejo, média
    dos bancos; não é o atacado da Com. A 3500), desde abr/2002. Fica o
    Ámbito por decisão dele (26/11/2026), mesmo com dias que destoam do BCRA
    (ex.: 23/04/2025, 1.333,24 no Ámbito contra 1.174,51 do BCRA, que dá
    brecha de −9,2% nesse dia).
  - Usa-se a venda nas duas cotações.

ARMADILHA DO ÁMBITO: a lista vem do mais novo para o mais velho e às vezes
repete a data (cotação carimbada com o dia da publicação, não do fechamento;
ex.: em 24/11/2026 aparecem 1.700 e 1.675, e o 1.675 é o fechamento de
23/11). Fica a primeira ocorrência de cada data, que é a última publicada e
bate com o "valor_cierre_ant" do próprio Ámbito. O dia que some fica buraco.

BRECHA = blue (venda) ÷ oficial (venda) − 1, em %, e blue − oficial em pesos,
só nos dias com as duas cotações.

RESERVAS
  - Bruta, diária: BCRA, API de Estadísticas v4.0, variável 1 ("Reservas
    internacionales"), US$ milhões, desde 1996. Cifras provisórias.
  - Ativos e passivos, mensal (fim de mês): a planilha de Reservas
    Internacionais e Liquidez em Moeda Estrangeira que o BCRA entrega ao FMI
    (padrão SDDS), lida da API SDMX do FMI (IMF.STA/IRFCL, ARG, setor S1X =
    autoridade monetária). Ativo: IRFCL65 (ativos de reserva oficiais).
    Passivos: a seção II, drenos predeterminados de curto prazo (vencem em
    até 12 meses), em três partes:
      depósitos, empréstimos e títulos em moeda estrangeira = IRFCL78 (ou,
        quando falta, IRFCL79 + IRFCL80 saídas + IRFCL80 entradas); aqui
        entram os depósitos dos bancos no BCRA (encaixes) e empréstimos;
      swaps e futuros, posição vendida = IRFCL1T (o swap com a China a
        partir de dez/2022);
      outros drenos = IRFCL85 (inclui os repos, IRFCL48T; até nov/2022 o
        BCRA lançava aqui também o swap com a China).
  - Reserva líquida = ativos de reserva + drenos (que vêm negativos), só do
    BCRA. Os vencimentos do Tesouro (setor S1311) ficam de fora.

INFLAÇÃO
  - INDEC, IPC nacional base dez/2016 = 100 (serie_ipc_divisiones.csv,
    código 0, região Nacional). Mensal e em 12 meses recalculadas do índice.
    A série nacional começa em dez/2016; a série longa do BCRA (desde 1943)
    emenda índices de outra cobertura, os números de 2007 a 2015 e um
    substituto no apagão estatístico de 2015/16, e por isso não entra.

BASE MONETÁRIA E M2 (mensal, fim de mês, desde jan/1990)
  - BCRA, API v4.0, séries históricas mensais em milhares de pesos:
    1606 base monetária = 1608 moeda em poder do público + 1609 moeda nos
    bancos + 1610 contas correntes dos bancos no BCRA (reservas bancárias);
    1611/1612 M1 total/em moeda local; 1617/1618 M2 total/em moeda local.
    M1 em moeda estrangeira = 1611 − 1612; poupança (cajas de ahorro) em
    moeda local = 1618 − 1612; em moeda estrangeira = (1617 − 1618) − (1611 −
    1612). Os depósitos em dólar já vêm convertidos em pesos pelo BCRA.
  - Em dólares: dividido pelo câmbio de referência do BCRA (Com. A 3500,
    variável 5, último dia útil do mês) a partir de mar/2002, quando a série
    começa; antes, pelo câmbio oficial de fim de mês do FMI (IMF.STA/ER,
    XDC_USD, EOP_RT), que cobre 1990 a fev/2002.
  - Variação em 12 meses a partir de jan/1992: em 1990 e 1991, saindo da
    hiperinflação, passa de 1.000% e achata o resto da série.

ATIVOS DO BCRA (mensal, fim de mês, desde jan/1990)
  - Balanço do BCRA, planilha balbcrhis.xls do próprio BCRA (Cuadro I-2,
    aba "B.C.R.A."), lida pelo rótulo do código de cada coluna (bcra2...):
    ativos externos líquidos (activos externos netos, total), crédito ao
    setor oficial (sector oficial, total) e créditos a entidades financeiras
    em moeda nacional; a soma é o total das fontes da base monetária.
  - Valores convertidos a milhares de pesos atuais com as colunas
    "Unidades monetarias originales representadas" e "Equivalencia" (nota
    da aba Observaciones). O câmbio de valuação da própria
    planilha não serve antes de 2002 (vem na unidade antiga): em dólares usa
    o mesmo câmbio da base e do M2, e a coluna "1 u$s =" fica como
    conferência a partir de abr/2002.

BALANÇO DE PAGAMENTOS (trimestral, BPM6, desde 1992)
  - INDEC é quem compila o BP. As aberturas (rendas primária e secundária,
    ativos e passivos de ID e carteira) vêm do FMI (IMF.STA/BOP, ARG, que
    recebe o BP do INDEC), porque a API de séries do governo argentino
    (apis.datos.gob.ar, conjunto 160.2 do INDEC, desde 2006) deixa algumas
    vazias; os totais do INDEC conferem os do FMI.
  - Sinais como no FtM Dados (scripts/bp.py), em que entrada de dinheiro é
    positiva: conta financeira = −(financeira total − ativos de reserva);
    reservas = −(ativos de reserva); ID no exterior = −ativos; ID no país =
    passivos; carteira no exterior = −ativos; carteira no país = passivos;
    outros + derivativos = −(outros investimentos líquidos + derivativos).
    Conta corrente + capital + financeira + reservas + erros e omissões = 0.
  - Cada trimestre vai datado no último mês (mar, jun, set, dez); a soma de
    4 trimestres é o equivalente ao acumulado em 12 meses do Brasil.
  - Começa em 1992, o início do BP trimestral do INDEC (o FMI tem desde
    1976, mas antes de 1992 são estimativas anuais repartidas).

ATIVIDADE (PIB trimestral e EMAE mensal, INDEC)
  - PIB: planilhas do INDEC sh_oferta_demanda_MM_AA.xls (cuadro 1, linha
    B1b, milhões de pesos de 2004, série original) e
    sh_oferta_demanda_desest_MM_AA.xls (aba "desestacionalizado n", PIB);
    MM_AA é o mês de publicação, e o script pega a mais nova que existir.
    Variação acumulada em 4 trimestres = soma dos 4 últimos trimestres sobre
    a dos 4 anteriores (série original); variação trimestral = trimestre
    contra o anterior na série dessazonalizada.
  - EMAE: sh_emae_mensual_base2004.xls (aba "Tabla"): índice original,
    dessazonalizado e variações publicadas. "Acumulado no trimestre" = média
    dos 3 meses dessazonalizados contra a média do trimestre anterior, a
    medida comparável à variação trimestral do PIB dessazonalizado.
  - Contribuições por setor: o INDEC só abre o EMAE por setor na série
    original (sh_emae_actividad_base2004.xls, aba "Tabla Letras", índices
    2004 = 100), então elas são da variação anual mensal (mês contra o
    mesmo mês do ano anterior), no gráfico "EMAE: variação anual". Peso de cada setor = valor
    adicionado de 2004 a preços de 2004 (PIB, cuadro 4, coluna "Total" de
    2004; impostos = as três linhas de impostos). A soma ponderada dos
    índices reproduz o EMAE publicado (erro médio de 0,06%); a contribuição
    é peso × (índice do mês − índice do mesmo mês do ano anterior) ÷ soma
    ponderada do mesmo mês do ano anterior. Setores agrupados em 7:
    agro e pesca (A, B), mineração (C), indústria (D), construção (F),
    comércio (G), demais serviços (E, H a O) e impostos líquidos de
    subsídios. O serviço doméstico (P, 0,6% do PIB de 2004) não tem índice
    mensal e fica de fora, como no próprio EMAE.
  - Índice por atividade (pedido dele em 26/11/2026, como o gráfico
    "Actividad económica por sectores"): o INDEC não dessazonaliza o EMAE
    por setor, então, por escolha dele, cada setor vai em média móvel de 12
    meses da série original, com base nov/2023 = 100 (BASE_ATIVIDADE).
    Agro (A), indústria (D), comércio (G), energia e mineração (C + E,
    somados pelos pesos de 2004) e construção (F); o EMAE total, com o mesmo
    tratamento, vai de referência.
  - Se o EMAE trimestral acompanhar o PIB (diferença média ≤ TOL_EMAE_PIB
    p.p. em todos os trimestres com os dois), o trimestre que o EMAE já
    fechou e o PIB ainda não vai meio sombreado no gráfico do PIB trimestral.

BRASIL, PARA COMPARAR (variação em 12 meses no mesmo gráfico da Argentina)
  - BCB, SGS: 1788 base monetária restrita (saldo de fim de período) =
    1786 papel-moeda emitido + 1787 reservas bancárias; 27810 M2 (conceito
    atual, saldo de fim de período) = 27791 M1 + 1835 depósitos de poupança +
    27809 títulos privados em poder do público.
  - A base vem em unidade monetária corrente: a variação em 12 meses só
    começa em jul/1995, um ano depois do real. O M2 no conceito atual começa
    em dez/2001, então a variação começa em dez/2002.

CONFERÊNCIAS QUE ABORTAM (segunda fonte: api.argentinadatos.com)
  - Risco país: mesmo dia nas duas fontes, diferença ≤ 1% em pelo menos 99%
    dos dias em comum, e o último ponto igual.
  - Blue e oficial: média mensal das duas fontes, nos mesmos dias, a partir
    de 2014, com diferença ≤ 0,5 peso + TOL_MES[nome]. O ArgentinaDatos
    guarda uma foto por dia corrido (às vezes com um dia de atraso) e
    arredonda para peso inteiro por anos (daí o meio peso), por isso a
    conferência é pela média do mês, não dia a dia. O oficial tem tolerância
    maior porque o do Ámbito é a média dos bancos e o do ArgentinaDatos é o
    Banco Nación (em 2024 ficam a uns 3%).
  - O último fechamento do Ámbito tem de aparecer no ArgentinaDatos em até
    2 dias corridos (≤ 0,5%).
  - Oficial do Ámbito × BCRA (variável 4) dia a dia desde jun/2010: mediana
    ≤ 0,1% e no máximo 1% dos dias acima de 1% (os poucos dias fora ficam
    impressos no log; a série usada continua a do Ámbito).
  - Brecha recalculada a partir da série gravada (arredondada) contra a de
    precisão cheia: ≤ 0,05 p.p.
  - Reserva bruta do FMI (IRFCL65) contra o último dia do mês do BCRA desde
    2002: ≤ 0,5%, salvo ago a nov/2009 (a alocação de DEG de 2009 entra
    antes no FMI; ≤ 6%) e jan/2002 e dez/2003 (≤ 2,5%).
  - As três partes dos drenos somam o total da seção II (IRFCLDT2): ≤ US$ 2
    milhões em todo mês.
  - Base monetária = soma dos três componentes; M1 e M2 totais = moeda local
    + estrangeira (cc e cajas de ahorro, 1613 a 1616, 1619 a 1622): ≤ 1 mil
    pesos em todo mês desde 1990.
  - Base monetária do BCRA contra a do FMI (MFS_CBS, S121_L_MB_CBS, desde
    2017): ≤ 0,01%.
  - Câmbio do FMI contra o de referência do BCRA (variável 5, último dia
    útil do mês) desde abr/2002: ≤ TOL_CAMBIO (3%; o FMI usa outra cotação
    oficial e chega a 2,3% de distância; a mediana fica perto de zero).
  - Balanço do BCRA: ativos externos + setor oficial + crédito a bancos =
    total das fontes, e essa soma − absorção = base monetária (≤ 1 mil pesos;
    exceções da própria planilha em TOTAL_ERRADO e ABSORCAO_ERRADA, e o total
    usado é sempre a soma das três contas); essa base contra a série 1606 da API do BCRA (≤ 0,01%); câmbio
    de valuação contra o câmbio usado na base e no M2, desde abr/2002 (≤ 3,5%, TOL_VALUACAO; mar/2002, o primeiro mês do câmbio de referência, fica de fora).
  - BP: conta corrente = bens + serviços + rendas; conta corrente + capital
    − financeira + erros e omissões = 0; financeira = ID + carteira +
    derivativos + outros + reservas (≤ US$ 1 milhão em todo trimestre desde
    1992). Totais do FMI contra o INDEC (conta corrente, bens, serviços,
    capital, financeira, ID, carteira, outros, derivativos, reservas e erros e
    omissões) desde 2006: ≤ US$ 0,5 milhão (a conta capital de 2016 difere
    US$ 1 a 2 milhões, revisão do INDEC: ≤ US$ 3 milhões).
  - PIB: a coluna "Total" de cada ano é a média dos 4 trimestres (≤ 0,01%);
    variação trimestral refeita da série dessazonalizada contra a publicada
    (aba "desestacionalizado v", ≤ 0,001 p.p.). EMAE: variação anual e
    mensal refeitas contra as publicadas na planilha (≤ 0,001 p.p.).
  - Contribuições do EMAE: a soma das contribuições contra a variação anual
    publicada do EMAE, mês a mês desde 2005: ≤ TOL_CONTRIB p.p.; a
    soma dos pesos de 2004 (setores + impostos + P) = PIB de 2004.
  - Brasil: base = papel-moeda emitido + reservas bancárias e M2 = M1 +
    poupança + títulos privados (≤ R$ 2 mil em todo mês); base do BCB contra
    a do FMI (MFS_MA, NDMBM_MAI): ≤ 0,01%.
  - IPC: variação mensal e em 12 meses refeitas do índice contra as
    publicadas pelo INDEC (≤ 0,051 p.p., o INDEC publica com uma casa) e
    contra as variáveis 27 e 28 da API do BCRA a partir de jun/2017 (≤ 0,051
    p.p.; antes disso o BCRA usa o IPC GBA).
"""
import datetime
import json
import os
import statistics
import sys
import time
import urllib.request

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SAIDA = os.path.join(RAIZ, "dados", "argentina.json")
AMBITO = "https://mercados.ambito.com//%s/historico-general/01-01-1990/%s"
ARGDATOS = "https://api.argentinadatos.com/v1/%s"
UA = {"User-Agent": "Mozilla/5.0 (ftm-analises)"}
BCRA = "https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/%d?desde=%s&hasta=%s&limit=3000&offset=%d"
FMI = ("https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IRFCL/+/ARG.*.S1X.M"
       "?attributes=dsd&measures=all")
FMI_ER = ("https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/ER/+/ARG.XDC_USD.EOP_RT.M"
          "?attributes=dsd&measures=all")
FMI_CBS = ("https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/MFS_CBS/+/ARG.S121_L_MB_CBS.*.M"
           "?attributes=dsd&measures=all")
SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.%d/dados?formato=json&dataInicial=01/01/1990&dataFinal=%s"
FMI_MA_BR = ("https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/MFS_MA/+/BRA.NDMBM_MAI.*.M"
             "?attributes=dsd&measures=all")
INICIO_YOY_BR_BASE = "1995-07"
INICIO_YOY_BR_M2 = "2002-12"
BALBCR = "https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/balbcrhis.xls"
# meses em que a própria planilha não fecha (conferido à mão em 26/11/2026):
# em 2014 a célula do total diverge da soma das três contas, mas a soma menos
# a absorção dá a base exata (o total publicado é que está errado); em
# nov/2009 a absorção difere em 4,1 bi de pesos. Trocar se o BCRA corrigir.
TOTAL_ERRADO = {"2014-01", "2014-02", "2014-09", "2014-10", "2014-11", "2014-12"}
ABSORCAO_ERRADA = {"2009-11"}
MESES_ES = {"Ene.": 1, "Feb.": 2, "Mar.": 3, "Abr.": 4, "May.": 5, "Jun.": 6, "Jul.": 7, "Ago.": 8,
            "Sep.": 9, "Set.": 9, "Oct.": 10, "Nov.": 11, "Dic.": 12}
FMI_BOP = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/BOP/+/ARG.*.*.*.Q?attributes=dsd&measures=all"
INDEC_BOP = "https://apis.datos.gob.ar/series/api/series/?ids=%s&format=json&limit=1000&metadata=none"
# código do INDEC (conjunto 160.2) -> chave do FMI (entrada|indicador), em US$ milhões
INDEC_X_FMI = {"160.2_TL_CUENNTE_0_T_22": "NETCD_T|CAB", "160.2_CTA_CORNES_0_T_46": "NETCD_T|G",
               "160.2_CTA_CORIOS_0_T_49": "NETCD_T|S", "160.2_TL_CUENTAL_0_T_20": "NETCD_T|KAB",
               "160.2_TL_CUENERA_0_T_23": "NNAFANIL_T|FAB", "160.2_CTA_FINCTA_0_T_41": "NNAFANIL_T|D_F",
               "160.2_CTA_FINERA_0_T_41": "NNAFANIL_T|P_F", "160.2_CTA_FINION_0_T_38": "NNAFANIL_T|O_F",
               "160.2_CTA_FINROS_0_T_36": "NNAFANIL_T|F_F7", "160.2_AVOS_RERVA_0_T_15": "A_T|R_F",
               "160.2_ERES_OMTOS_0_T_23": "NETCD_T|EO"}
INICIO_BP = "1992-03"
INDEC_FTP = "https://www.indec.gob.ar/ftp/cuadros/economia/"
TOL_EMAE_PIB = 0.25
TOL_CONTRIB = 0.6
# nomes dos setores do EMAE (letras da CIIU no INDEC) no gráfico estático
NOMES_SETOR = {"A": "Agropecuária e silvicultura", "B": "Pesca", "C": "Minas e pedreiras",
               "D": "Indústria manufatureira", "E": "Eletricidade, gás e água", "F": "Construção",
               "G": "Comércio e reparações", "H": "Hotéis e restaurantes", "I": "Transporte e comunicações",
               "J": "Intermediação financeira", "K": "Atividades imobiliárias e empresariais",
               "L": "Administração pública e defesa", "M": "Ensino", "N": "Saúde e serviços sociais",
               "O": "Outros serviços comunitários e pessoais", "T": "Impostos líquidos de subsídios"}
BASE_ATIVIDADE = "2023-11"
SETORES_ATIVIDADE = [("Agro", ["A"], "#4F81BD"), ("Indústria", ["D"], "#C0504D"), ("Comércio", ["G"], "#9BBB59"),
                     ("Energia e mineração", ["C", "E"], "#8EB4E3"), ("Construção", ["F"], "#1F497D")]
GRUPOS_EMAE = [("Agro e pesca", ["A", "B"], "#4F81BD"), ("Mineração", ["C"], "#C0504D"),
               ("Indústria", ["D"], "#9BBB59"), ("Construção", ["F"], "#1F497D"),
               ("Comércio", ["G"], "#8EB4E3"), ("Demais serviços", ["E", "H", "I", "J", "K", "L", "M", "N", "O"],
                                                "#632523"),
               ("Impostos líquidos de subsídios", ["T"], "#FFFF00")]
INICIO_MON = "1990-01"
INICIO_YOY = "1992-01"
TOL_CAMBIO = 0.03
# valuação do balanço × câmbio de fim de mês: até 3,1% em 2002 e 2003, logo
# depois da desvalorização (a data de valuação nem sempre é o último dia útil)
TOL_VALUACAO = 0.035
INDEC = "https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_divisiones.csv"
ESPESSURA = 1.95                         # 1,5 × 1,3: +50% e depois mais +30% (pedidos dele em 26/11/2026)
POSSE = datetime.date(2023, 12, 10)
INICIO_OFICIAL_BCRA = datetime.date(2010, 6, 1)
# de jan a mai/2017 o BCRA (variáveis 27 e 28) traz o IPC GBA: o nacional só
# saiu depois, retroativo a jan/2017
INICIO_BCRA_IPC = "2017-06"
POSSE_MES = "2023-12"
# meses em que a reserva bruta do FMI pode se afastar da do BCRA (ver acima)
TOL_BRUTA = {"2009-08": 0.06, "2009-09": 0.06, "2009-10": 0.06, "2009-11": 0.06,
             "2002-01": 0.025, "2003-12": 0.025}
TOL_MES = {"blue": 0.03, "oficial": 0.04}   # na média mensal, além de 0,5 peso de arredondamento
INICIO_CONF = "2014-01"

BRANCO, AZUL, VERMELHO, VERDE, AZUL_ESC = "#FFFFFF", "#4F81BD", "#C0504D", "#9BBB59", "#1F497D"
AZUL_CLARO = "#8EB4E3"


def baixar(url, tentativas=4):
    for k in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if k == tentativas - 1:
                raise RuntimeError("falhou %s: %s" % (url, e))
            time.sleep(3 * (k + 1))


def num_ar(txt):
    """'1.067,00' -> 1067.0"""
    return float(txt.replace(".", "").replace(",", "."))


def ambito(caminho, sep):
    hoje = datetime.date.today().strftime("%d-%m-%Y")
    linhas = baixar(AMBITO % (caminho, hoje))
    if not linhas or linhas[0][0] != "Fecha":
        raise RuntimeError("Ámbito %s: cabeçalho inesperado %r" % (caminho, linhas[:1]))
    col = linhas[0].index("Venta") if "Venta" in linhas[0] else linhas[0].index("Puntos")
    out, repetidas = {}, 0
    for r in linhas[1:]:
        d = datetime.datetime.strptime(r[0], "%d" + sep + "%m" + sep + "%Y").date()
        if d in out:
            repetidas += 1
            continue
        out[d] = num_ar(r[col])
    # o dia de hoje é cotação intradia, não fechamento
    out.pop(datetime.date.today(), None)
    if len(out) < 4000:
        raise RuntimeError("Ámbito %s: só %d dias" % (caminho, len(out)))
    print("Ámbito %-15s %d dias (%d datas repetidas descartadas), %s a %s"
          % (caminho, len(out), repetidas, min(out), max(out)))
    return out


def argdatos(caminho, campo):
    return {datetime.date.fromisoformat(r["fecha"]): float(r[campo]) for r in baixar(ARGDATOS % caminho)}


def conferir_risco(a, b):
    comuns = [d for d in a if d in b]
    ruins = [(d, a[d], b[d]) for d in comuns if abs(b[d] / a[d] - 1) > 0.01]
    print("risco país: %d dias em comum, %d com diferença > 1%%" % (len(comuns), len(ruins)))
    if len(comuns) < 5000 or len(ruins) > 0.01 * len(comuns):
        raise RuntimeError("risco país não bate com o ArgentinaDatos: %r" % ruins[:10])
    ult = max(a)
    if ult in b and b[ult] != a[ult]:
        raise RuntimeError("risco país: último ponto %s difere (%s × %s)" % (ult, a[ult], b[ult]))


def conferir_cambio(nome, a, b):
    m = {}
    for d, v in a.items():
        if d in b and d.strftime("%Y-%m") >= INICIO_CONF:
            m.setdefault(d.strftime("%Y-%m"), []).append((v, b[d]))
    ruins = []
    for k, pares in m.items():
        xa = statistics.mean(x for x, _ in pares)
        xb = statistics.mean(y for _, y in pares)
        ruins.append(((abs(xb - xa) - 0.5) / xa, k))
    ruins.sort(reverse=True)
    print("%s: %d meses conferidos desde %s, maior diferença além do arredondamento %.2f%% (%s)"
          % (nome, len(m), INICIO_CONF, ruins[0][0] * 100, ruins[0][1]))
    if len(m) < 100 or ruins[0][0] > TOL_MES[nome]:
        raise RuntimeError("%s: média mensal não bate: %r" % (nome, ruins[:5]))
    ult = max(a)
    ok = [d for d in b if 0 <= (d - ult).days <= 2 and abs(b[d] / a[ult] - 1) <= 0.005]
    if not ok:
        raise RuntimeError("%s: último fechamento %s (%s) não aparece no ArgentinaDatos" % (nome, ult, a[ult]))


def conferir_oficial_bcra(amb):
    v4 = bcra(4, INICIO_OFICIAL_BCRA.isoformat())
    hoje = datetime.date.today()
    v4 = {d: x for d, x in v4.items() if d < hoje}
    com = [d for d in amb if d in v4]
    difs = sorted(((abs(amb[d] / v4[d] - 1), d) for d in com), reverse=True)
    med = statistics.median(x for x, _ in difs)
    fora = [(str(d), amb[d], v4[d]) for x, d in difs if x > 0.01]
    print("oficial Ámbito × BCRA (var. 4): %d dias, mediana %.3f%%, %d dias acima de 1%%; maiores: %r"
          % (len(com), med * 100, len(fora), fora[:3]))
    if len(com) < 3000 or med > 0.001 or len(fora) > 0.01 * len(com):
        raise RuntimeError("oficial do Ámbito não bate com o BCRA")


def serie(nome, s, casas, **extra):
    if "largura" in extra:                  # linhas 50% mais grossas (pedido dele em 26/11/2026)
        extra["largura"] = round(extra["largura"] * ESPESSURA, 2)
    chave = lambda d: d if isinstance(d, str) else d.isoformat()
    return dict(nome=nome, dados=[[chave(d), round(s[d], casas)] for d in sorted(s)], **extra)


def recortes(series, mensal, rot_extra="", unidade=None):
    """A série inteira com a marca da posse de Milei. (O recorte "desde a posse"
    saiu a pedido dele em 26/11/2026; a marca na série inteira fica.)"""
    desde = POSSE_MES if mensal else POSSE.isoformat()
    a = dict(rot=rot_extra or "Série inteira", series=series, eventos=[dict(em=desde, rot="Posse de Milei")])
    if unidade:
        a["unidade"] = unidade
    return [a]


def eixo_em(g, rot, eixo):
    """Fixa o eixo numa opção do cartão (pelo rótulo) ou no cartão todo (rot=None)."""
    if rot is None:
        g["eixo"] = eixo
        return g
    achou = [v for v in g.get("variantes", []) if v["rot"] == rot]
    if not achou:
        raise RuntimeError("%s: opção %r não existe" % (g["id"], rot))
    for v in achou:
        v["eixo"] = eixo
    return g


def achatar(g):
    """Cartão com um recorte só não precisa de botões: as séries sobem para o gráfico."""
    if len(g.get("variantes", [])) == 1:
        v = g.pop("variantes")[0]
        v.pop("rot", None)
        g.update(v)
    return g


def bcra(var, desde="1996-01-01"):
    hoje = datetime.date.today().isoformat()
    out, off = {}, 0
    while True:
        d = baixar(BCRA % (var, desde, hoje, off))
        det = d["results"][0]["detalle"]
        for x in det:
            out[datetime.date.fromisoformat(x["fecha"])] = float(x["valor"])
        if len(det) < 3000:
            break
        off += 3000
    if not out:
        raise RuntimeError("BCRA %d: vazio" % var)
    print("BCRA %-4d %d pontos, %s a %s" % (var, len(out), min(out), max(out)))
    return out


def irfcl():
    """{indicador: {"aaaa-mm": US$ milhões}} da planilha de liquidez (S1X)."""
    d = baixar(FMI)
    st = d["data"]["structures"][0]
    dims = st["dimensions"]["series"]
    pos = [x["id"] for x in dims].index("INDICATOR")
    per = [o["value"] for o in st["dimensions"]["observation"][0]["values"]]
    tab = {}
    for k, s in d["data"]["dataSets"][0]["series"].items():
        ind = dims[pos]["values"][int(k.split(":")[pos])]["id"]
        for i, o in s["observations"].items():
            if o[0] not in (None, "NaN"):
                tab.setdefault(ind, {})[per[int(i)].replace("-M", "-")] = float(o[0]) / 1e6
    print("FMI IRFCL: %d indicadores, ativos de reserva de %s a %s"
          % (len(tab), min(tab["IRFCLDT1_IRFCL65_USD"]), max(tab["IRFCLDT1_IRFCL65_USD"])))
    return tab


def reservas_mensais(tab, bruta_dia):
    ativo = tab["IRFCLDT1_IRFCL65_USD"]
    total = tab["IRFCLDT2_USD"]
    swaps = tab.get("IRFCLDT2_IRFCL1T_SHP_USD", {})
    outros = tab.get("IRFCLDT2_IRFCL85_USD", {})
    dep = {}
    for m in total:
        if m in tab.get("IRFCLDT2_IRFCL78_USD", {}):
            dep[m] = tab["IRFCLDT2_IRFCL78_USD"][m]
        else:
            dep[m] = sum(tab.get(k, {}).get(m, 0.0) for k in
                         ("IRFCLDT2_IRFCL79_FO_USD", "IRFCLDT2_IRFCL80_FO_USD", "IRFCLDT2_IRFCL80_IN_USD"))
    meses = sorted(m for m in total if m in ativo)
    for m in meses:
        soma = dep[m] + swaps.get(m, 0.0) + outros.get(m, 0.0)
        if abs(soma - total[m]) > 2:
            raise RuntimeError("drenos de %s não somam o total: %.0f × %.0f" % (m, soma, total[m]))
    # conferência: ativo do FMI × último dia do mês do BCRA
    fim = {}
    for d, v in bruta_dia.items():
        k = d.strftime("%Y-%m")
        if k not in fim or d > fim[k][0]:
            fim[k] = (d, v)
    pior = (0, None)
    for m, v in ativo.items():
        if m < "2002-01" or m not in fim:
            continue
        dif = abs(fim[m][1] / v - 1)
        if dif > TOL_BRUTA.get(m, 0.005):
            raise RuntimeError("reserva bruta de %s: FMI %.0f × BCRA %.0f" % (m, v, fim[m][1]))
        if m not in TOL_BRUTA:
            pior = max(pior, (dif, m))
    print("reserva bruta FMI × BCRA: maior diferença fora das exceções %.3f%% (%s)" % (pior[0] * 100, pior[1]))
    liq = {m: ativo[m] + total[m] for m in meses}
    return meses, ativo, dep, swaps, outros, liq


def sdmx_mensal(url):
    """Série única mensal do FMI: {"aaaa-mm": valor}."""
    d = baixar(url)
    st = d["data"]["structures"][0]
    per = [o["value"] for o in st["dimensions"]["observation"][0]["values"]]
    series = list(d["data"]["dataSets"][0]["series"].values())
    if len(series) != 1:
        raise RuntimeError("FMI: esperava 1 série, vieram %d (%s)" % (len(series), url))
    return {per[int(i)].replace("-M", "-"): float(o[0]) for i, o in series[0]["observations"].items()
            if o[0] not in (None, "NaN")}


def mais(m, k):
    t = int(m[:4]) * 12 + int(m[5:]) - 1 + k
    return "%04d-%02d" % (t // 12, t % 12 + 1)


def monetario():
    v = {}
    for n in list(range(1606, 1634)):
        if n in (1607, 1623, 1624) or n >= 1625:
            continue
        v[n] = {d.strftime("%Y-%m"): x for d, x in bcra(n, "1940-01-01").items()}
    meses = [m for m in sorted(v[1606]) if m >= INICIO_MON]
    for m in meses:
        g = lambda n: v[n].get(m, 0.0)
        for nome, a, b in (("base", g(1606), g(1608) + g(1609) + g(1610)),
                           ("M1 local", g(1612), g(1608) + g(1613) + g(1614)),
                           ("M1 estrangeira", g(1611) - g(1612), g(1615) + g(1616)),
                           ("M2 local", g(1618), g(1612) + g(1619) + g(1620)),
                           ("M2 estrangeira", g(1617) - g(1618), g(1615) + g(1616) + g(1621) + g(1622))):
            if abs(a - b) > 1:
                raise RuntimeError("%s de %s não fecha: %.0f × %.0f" % (nome, m, a, b))
    print("identidades da base, M1 e M2: %d meses, de %s a %s" % (len(meses), meses[0], meses[-1]))
    cbs = sdmx_mensal(FMI_CBS)
    pior = max(abs(cbs[m] / 1000 / v[1606][m] - 1) for m in cbs if m in v[1606])
    print("base monetária BCRA × FMI (MFS): %d meses, maior diferença %.4f%%"
          % (len([m for m in cbs if m in v[1606]]), pior * 100))
    if pior > 0.0001:
        raise RuntimeError("base monetária não bate com o FMI")
    cambio = sdmx_mensal(FMI_ER)
    ref = {}
    for d, x in bcra(5, "2002-03-01").items():
        k = d.strftime("%Y-%m")
        if k not in ref or d > ref[k][0]:
            ref[k] = (d, x)
    difs = sorted(((abs(ref[m][1] / cambio[m] - 1), m) for m in cambio if m in ref and m >= "2002-04"), reverse=True)
    print("câmbio FMI × BCRA (var. 5): %d meses, maior diferença %.3f%% (%s)" % (len(difs), difs[0][0] * 100, difs[0][1]))
    if difs[0][0] > TOL_CAMBIO:
        raise RuntimeError("câmbio do FMI não bate com o BCRA: %r" % difs[:5])
    print("câmbio FMI × BCRA: mediana %.3f%%" % (statistics.median(x for x, _ in difs) * 100))
    cambio = {m: x for m, x in cambio.items() if m < "2002-03"}
    cambio.update({m: x for m, (_, x) in ref.items()})
    falta = [m for m in meses if m not in cambio]
    if falta:
        print("meses sem câmbio do FMI (ficam buraco em dólares):", falta)
    return v, meses, cambio


def balanco_bcra(base_api, cambio):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from xls import abas
    with urllib.request.urlopen(urllib.request.Request(BALBCR, headers=UA), timeout=120) as r:
        c = abas(r.read())["B.C.R.A."]
    cols = sorted({k for _, k in c})
    linhas = sorted({r for r, _ in c})
    # cada coluna tem um código (bcra2, bcra6...) numa linha do cabeçalho
    cod = {}
    for k in cols:
        for r in linhas[:40]:
            v = c.get((r, k))
            if isinstance(v, str) and v.strip().startswith("bcra"):
                cod[v.strip()] = k
    precisa = {"externos": "bcra2", "oficial": "bcra6", "bancos": "bcra17", "absorcao": "bcra19",
               "base": "bcra29", "cambio": "bcra34"}
    falta = [v for v in precisa.values() if v not in cod]
    if falta:
        raise RuntimeError("balbcrhis: códigos não achados %r" % falta)
    # a coluna do total das fontes não tem código: é a de rótulo "Total" logo antes de "Fuentes de absorción"
    k_total = cod["bcra19"] - 1
    # externos: o código bcra2 é "Oro y divisas"; o total de ativos externos é a coluna anterior
    k_ext = cod["bcra2"] - 1
    k_uni, k_eq = 4, 5
    # o leitor devolve RK inteiro como int: vale como número também
    num = lambda v: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    out = {n: {} for n in ("externos", "oficial", "bancos", "total", "absorcao", "base", "cambio")}
    for r in linhas:
        ano, mes = c.get((r, 0)), c.get((r, 1))
        # o rótulo do mês às vezes traz marca ("Ene. *", "Ene. ")
        mes = mes.split()[0] if isinstance(mes, str) and mes.split() else mes
        if num(ano) is None or mes not in MESES_ES:
            continue
        m = "%04d-%02d" % (int(ano), MESES_ES[mes])
        if m < INICIO_MON or num(c.get((r, k_total))) is None:
            continue
        fator = c[(r, k_uni)] * c[(r, k_eq)] / 1000      # -> milhares de pesos atuais
        for n, k in (("externos", k_ext), ("oficial", cod["bcra6"]), ("bancos", cod["bcra17"]),
                     ("total", k_total), ("absorcao", cod["bcra19"]), ("base", cod["bcra29"])):
            v = num(c.get((r, k)))
            out[n][m] = (v or 0.0) * fator
        if num(c.get((r, cod["bcra34"]))):
            out["cambio"][m] = c[(r, cod["bcra34"])]
    meses = sorted(out["total"])
    todos = [mais(meses[0], k) for k in range(len(meses) + 24) if mais(meses[0], k) <= meses[-1]]
    if [m for m in todos if m not in out["total"]]:
        raise RuntimeError("balbcrhis: meses faltando %r" % [m for m in todos if m not in out["total"]])
    for m in meses:
        soma = out["externos"][m] + out["oficial"][m] + out["bancos"][m]
        ok_total = abs(soma - out["total"][m]) <= 1 or m in TOTAL_ERRADO
        ok_base = abs(soma - out["absorcao"][m] - out["base"][m]) <= 1 or m in ABSORCAO_ERRADA
        if not (ok_total and ok_base):
            raise RuntimeError("balanço do BCRA de %s não fecha: soma %.0f, total %.0f, base %.0f"
                               % (m, soma, out["total"][m], out["base"][m]))
        out["total"][m] = soma            # o total é a soma das três contas
    # dez/2007: a base do balanço fica 0,30% acima da série 1606 (revisão); os demais meses batem exatamente
    pior = max((abs(out["base"][m] / base_api[m] - 1), m) for m in meses if m in base_api and m != "2007-12")
    if abs(out["base"]["2007-12"] / base_api["2007-12"] - 1) > 0.005:
        raise RuntimeError("base de dez/2007 do balanço passou de 0,5% da API")
    print("balanço do BCRA: %d meses (%s a %s); base contra a API, maior diferença %.4f%% (%s)"
          % (len(meses), meses[0], meses[-1], pior[0] * 100, pior[1]))
    if pior[0] > 0.0001:
        raise RuntimeError("base do balanço não bate com a API do BCRA")
    # a coluna de valuação só vale como conferência a partir de mar/2002 (antes vem na unidade antiga)
    difc = max((abs(out["cambio"][m] / cambio[m] - 1), m) for m in out["cambio"] if m in cambio and m >= "2002-04")
    print("câmbio de valuação × câmbio da base: maior diferença %.3f%% (%s)" % (difc[0] * 100, difc[1]))
    if difc[0] > TOL_VALUACAO:
        raise RuntimeError("câmbio de valuação do balanço não bate")
    return meses, out


def bp():
    """BP trimestral em US$ milhões, chave = último mês do trimestre."""
    d = baixar(FMI_BOP)
    st = d["data"]["structures"][0]
    dims = st["dimensions"]["series"]
    nomes = [x["id"] for x in dims]
    pe, pi = nomes.index("BOP_ACCOUNTING_ENTRY"), nomes.index("INDICATOR")
    per = [o["value"] for o in st["dimensions"]["observation"][0]["values"]]
    t = {}
    for k, s_ in d["data"]["dataSets"][0]["series"].items():
        idx = [int(i) for i in k.split(":")]
        chave = dims[pe]["values"][idx[pe]]["id"] + "|" + dims[pi]["values"][idx[pi]]["id"]
        for i, o in s_["observations"].items():
            if o[0] in (None, "NaN"):
                continue
            a, q = per[int(i)].split("-Q")
            t.setdefault(chave, {})["%s-%02d" % (a, int(q) * 3)] = float(o[0]) / 1e6
    g = lambda c: t.get(c, {})
    cc = g("NETCD_T|CAB")
    trims = [m for m in sorted(cc) if m >= INICIO_BP]
    v = lambda c, m: g(c).get(m, 0.0)
    for m in trims:
        e1 = cc[m] - sum(v("NETCD_T|" + c, m) for c in ("G", "S", "IN1", "IN2"))
        e2 = cc[m] + v("NETCD_T|KAB", m) - v("NNAFANIL_T|FAB", m) + v("NETCD_T|EO", m)
        e3 = v("NNAFANIL_T|FAB", m) - sum(v(c, m) for c in ("NNAFANIL_T|D_F", "NNAFANIL_T|P_F", "NNAFANIL_T|F_F7",
                                                             "NNAFANIL_T|O_F", "A_T|R_F"))
        e4 = v("NNAFANIL_T|D_F", m) - v("A_NFA_T|D_F", m) + v("L_NIL_T|D_F", m)
        e5 = v("NNAFANIL_T|P_F", m) - v("A_NFA_T|P_F", m) + v("L_NIL_T|P_F", m)
        if max(abs(e1), abs(e2), abs(e3), abs(e4), abs(e5)) > 1:
            raise RuntimeError("BP de %s não fecha: %r" % (m, (e1, e2, e3, e4, e5)))
    print("BP (FMI): %d trimestres, %s a %s; identidades fecham" % (len(trims), trims[0], trims[-1]))
    # INDEC
    ids = list(INDEC_X_FMI)
    r = baixar(INDEC_BOP % ",".join(ids))
    pior, n = (0, None), 0
    for linha in r["data"]:
        a, mm = linha[0][:4], int(linha[0][5:7])
        m = "%s-%02d" % (a, mm + 2)                 # o INDEC data o trimestre no primeiro mês
        for i, x in zip(ids, linha[1:]):
            if x is None:
                continue
            dif = abs(x - v(INDEC_X_FMI[i], m))
            if i == "160.2_TL_CUENTAL_0_T_20" and m[:4] == "2016":
                if dif > 3:
                    raise RuntimeError("conta capital de %s: INDEC × FMI passou de US$ 3 milhões" % m)
                continue                            # revisão do INDEC em 2016: US$ 1 a 2 milhões
            n += 1
            pior = max(pior, (dif, "%s %s" % (i, m)))
    print("BP INDEC × FMI: %d valores, maior diferença US$ %.3f milhões (%s)" % (n, pior[0], pior[1]))
    if n < 800 or pior[0] > 0.5:
        raise RuntimeError("BP do FMI não bate com o INDEC")
    sel = lambda c, sinal=1: {m: sinal * v(c, m) for m in trims}
    out = dict(
        cc=sel("NETCD_T|CAB"), bens=sel("NETCD_T|G"), serv=sel("NETCD_T|S"), r1=sel("NETCD_T|IN1"),
        r2=sel("NETCD_T|IN2"), ck=sel("NETCD_T|KAB"), eo=sel("NETCD_T|EO"), res=sel("A_T|R_F", -1),
        id_ext=sel("A_NFA_T|D_F", -1), id_pais=sel("L_NIL_T|D_F"), cart_ext=sel("A_NFA_T|P_F", -1),
        cart_pais=sel("L_NIL_T|P_F"),
        outros={m: -(v("NNAFANIL_T|O_F", m) + v("NNAFANIL_T|F_F7", m)) for m in trims})
    out["cf"] = {m: -(v("NNAFANIL_T|FAB", m) - v("A_T|R_F", m)) for m in trims}
    for m in trims:
        if abs(out["cc"][m] + out["ck"][m] + out["cf"][m] + out["res"][m] + out["eo"][m]) > 1:
            raise RuntimeError("BP com sinais do FtM não fecha em %s" % m)
    return trims, out


def xls_indec(nome):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from xls import abas
    with urllib.request.urlopen(urllib.request.Request(INDEC_FTP + nome, headers=UA), timeout=120) as r:
        dados = r.read()
    if dados[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise RuntimeError("INDEC: %s não é .xls" % nome)
    return abas(dados)


def xls_indec_recente(prefixo):
    """A planilha publicada mais recente: prefixo_MM_AA.xls, do mês atual para trás."""
    hoje = datetime.date.today()
    for k in range(0, 15):
        t = hoje.year * 12 + hoje.month - 1 - k
        nome = "%s_%02d_%02d.xls" % (prefixo, t % 12 + 1, (t // 12) % 100)
        try:
            a = xls_indec(nome)
            print("INDEC: %s" % nome)
            return a
        except Exception:                      # noqa: BLE001
            continue
    raise RuntimeError("INDEC: nenhuma planilha %s nos últimos 15 meses" % prefixo)


def pib_emae():
    num_ = lambda v: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    ano_ = lambda v: int(str(v)[:4]) if v is not None and str(v)[:4].isdigit() else (int(v) if num_(v) else None)
    # PIB original (cuadro 1)
    livro_pib = xls_indec_recente("sh_oferta_demanda")
    c = livro_pib["cuadro 1"]
    cols = sorted({k for _, k in c})
    linha = [r for r in sorted({r for r, _ in c}) if str(c.get((r, 0)) or "").strip() == "B1b"][0]
    lin_ano = [r for r in range(0, 8) if any(ano_(c.get((r, k))) for k in cols[2:6])][0]
    lin_tri = lin_ano + 1
    orig, ano, totais = {}, None, {}
    for k in cols:
        if ano_(c.get((lin_ano, k))):
            ano = ano_(c.get((lin_ano, k)))
        rot, v = str(c.get((lin_tri, k)) or ""), num_(c.get((linha, k)))
        if ano is None or v is None:
            continue
        if "trimestre" in rot:
            orig["%04d-%02d" % (ano, int(rot[0]) * 3)] = v
        elif rot.strip().startswith("Total"):
            totais[ano] = v
    for a, tot in totais.items():
        qs = [orig.get("%04d-%02d" % (a, 3 * q)) for q in range(1, 5)]
        if None not in qs and abs(statistics.mean(qs) / tot - 1) > 0.0001:
            raise RuntimeError("PIB de %d: total não é a média dos trimestres" % a)
    # PIB dessazonalizado
    d = xls_indec_recente("sh_oferta_demanda_desest")
    Q = {"I": 3, "II": 6, "III": 9, "IV": 12}

    def tabela(aba):
        out, ano = {}, None
        for r in sorted({r for r, _ in aba}):
            if ano_(aba.get((r, 0))):
                ano = ano_(aba.get((r, 0)))
            tq = str(aba.get((r, 1)) or "").strip()
            if tq in Q and ano and num_(aba.get((r, 2))) is not None:
                out["%04d-%02d" % (ano, Q[tq])] = num_(aba.get((r, 2)))
        return out
    des = tabela(d["desestacionalizado n"])
    pub_qq = tabela(d["desestacionalizado v"])
    qq = {m: (des[m] / des[mais(m, -3)] - 1) * 100 for m in des if mais(m, -3) in des}
    pior = max(abs(qq[m] - pub_qq[m]) for m in qq if m in pub_qq)
    if pior > 0.001 or len(qq) < 80:
        raise RuntimeError("PIB: variação trimestral não bate com a publicada (%.4f)" % pior)
    a4 = {}
    for m in orig:
        ult = [mais(m, -3 * k) for k in range(4)]
        ant = [mais(m, -3 * k) for k in range(4, 8)]
        if all(x in orig for x in ult + ant):
            a4[m] = (sum(orig[x] for x in ult) / sum(orig[x] for x in ant) - 1) * 100
    print("PIB: original %s a %s, dessazonalizado %s a %s; trimestral × publicada %.5f p.p."
          % (min(orig), max(orig), min(des), max(des), pior))
    # EMAE
    e = xls_indec("sh_emae_mensual_base2004.xls")["Tabla"]
    MES = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
           "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}
    eo, ed, pub_a, pub_m, ano = {}, {}, {}, {}, None
    for r in sorted({r for r, _ in e}):
        if ano_(e.get((r, 0))):
            ano = ano_(e.get((r, 0)))
        mes = str(e.get((r, 1)) or "").strip()
        if mes in MES and ano and num_(e.get((r, 2))) is not None:
            m = "%04d-%02d" % (ano, MES[mes])
            eo[m], ed[m] = num_(e[(r, 2)]), num_(e[(r, 4)])
            if num_(e.get((r, 3))) is not None and ano > 2004:
                pub_a[m] = num_(e[(r, 3)])
            if num_(e.get((r, 5))) is not None:
                pub_m[m] = num_(e[(r, 5)])
    ea = {m: (eo[m] / eo[mais(m, -12)] - 1) * 100 for m in eo if mais(m, -12) in eo}
    em = {m: (ed[m] / ed[mais(m, -1)] - 1) * 100 for m in ed if mais(m, -1) in ed}
    p1 = max(abs(ea[m] - pub_a[m]) for m in ea if m in pub_a)
    p2 = max(abs(em[m] - pub_m[m]) for m in em if m in pub_m)
    if p1 > 0.001 or p2 > 0.001:
        raise RuntimeError("EMAE: variações não batem com as publicadas (%.4f, %.4f)" % (p1, p2))
    tri = {}
    for m in ed:
        if int(m[5:]) % 3 == 0 and all(mais(m, -k) in ed for k in range(6)):
            atual = statistics.mean(ed[mais(m, -k)] for k in range(3))
            antes = statistics.mean(ed[mais(m, -k)] for k in range(3, 6))
            tri[m] = (atual / antes - 1) * 100
    # contribuições por setor (variação anual do trimestre, série original)
    c4 = livro_pib["cuadro 4"]
    c4cols = sorted({k for _, k in c4})
    k2004 = [k for k in c4cols if str(c4.get((lin_tri, k)) or "").strip().startswith("Total")][0]
    peso, imp = {}, 0.0
    for r in sorted({r for r, _ in c4}):
        cod = str(c4.get((r, 0)) or "").strip()
        v = num_(c4.get((r, k2004)))
        if v is None:
            continue
        if len(cod) == 1 and cod.isalpha():
            peso[cod] = v
        elif cod in ("D214 - D31", "D211", "D212"):
            imp += v
        elif cod == "B1b" and "Producto" in str(c4.get((r, 1))):
            pib2004 = v
    peso["T"] = imp
    if abs(sum(peso.values()) / pib2004 - 1) > 1e-6:
        raise RuntimeError("pesos de 2004 não somam o PIB de 2004")
    la = xls_indec("sh_emae_actividad_base2004.xls")["Tabla Letras"]
    cab = {k: str(la.get((2, k)) or "") for k in sorted({k for _, k in la})}
    col = {}
    for k, t in cab.items():
        t = t.strip()
        if t.startswith("Impuestos"):
            col["T"] = k
        elif len(t) > 2 and t[1:4].strip().startswith("-") and t[0].isalpha():
            col[t[0]] = k
    letras = sorted(set(NOMES_SETOR) | {l for g in GRUPOS_EMAE for l in g[1]} | {l for g in SETORES_ATIVIDADE for l in g[1]})
    if any(l not in col or l not in peso for l in letras):
        raise RuntimeError("EMAE por setor: faltam colunas %r" % [l for l in letras if l not in col])
    setor, ano = {}, None
    for r in sorted({r for r, _ in la}):
        if ano_(la.get((r, 0))):
            ano = ano_(la.get((r, 0)))
        mes = str(la.get((r, 1)) or "").strip()
        if mes in MES and ano and num_(la.get((r, col["A"]))) is not None:
            setor["%04d-%02d" % (ano, MES[mes])] = {l: num_(la[(r, col[l])]) for l in letras}
    contrib = {}
    for m in setor:
        if mais(m, -12) not in setor:
            continue
        qa, qb = setor[m], setor[mais(m, -12)]
        den = sum(peso[l] * qb[l] for l in letras)
        contrib[m] = {g[0]: sum(peso[l] * (qa[l] - qb[l]) for l in g[1]) / den * 100 for g in GRUPOS_EMAE}
    difs_c = sorted(((abs(sum(contrib[m].values()) - pub_a[m]), m) for m in contrib if m in pub_a), reverse=True)
    print("EMAE por setor: %d meses; soma das contribuições × variação anual publicada: maior diferença "
          "%.3f p.p. (%s), mediana %.3f" % (len(contrib), difs_c[0][0], difs_c[0][1],
                                          statistics.median(x for x, _ in difs_c)))
    difc = difs_c[0]
    if difc[0] > TOL_CONTRIB:
        raise RuntimeError("contribuições do EMAE não somam a variação anual")
    pib_a = {m: (orig[m] / orig[mais(m, -12)] - 1) * 100 for m in orig if mais(m, -12) in orig}
    comuns = [m for m in tri if m in qq]
    dif = statistics.mean(abs(tri[m] - qq[m]) for m in comuns)
    rec = [m for m in comuns][-8:]
    dif_rec = statistics.mean(abs(tri[m] - qq[m]) for m in rec)
    print("EMAE: %s a %s; anual e mensal × publicadas %.5f e %.5f p.p.; trimestre EMAE × PIB: %d trimestres, "
          "diferença média %.3f p.p. (últimos 8: %.3f), correlação %.4f"
          % (min(eo), max(eo), p1, p2, len(comuns), dif, dif_rec,
             statistics.correlation([tri[m] for m in comuns], [qq[m] for m in comuns])))
    # gráfico estático do último mês: incidência e variação anual de cada setor
    lv = xls_indec("sh_emae_actividad_base2004.xls")["Tabla Var Letras"]
    var_pub, ano = {}, None
    for r in sorted({r for r, _ in lv}):
        if ano_(lv.get((r, 0))):
            ano = ano_(lv.get((r, 0)))
        mes = str(lv.get((r, 1)) or "").strip()
        if mes in MES and ano and num_(lv.get((r, col["A"]))) is not None:
            var_pub["%04d-%02d" % (ano, MES[mes])] = {l: num_(lv[(r, col[l])]) for l in NOMES_SETOR}
    mu = max(m for m in contrib if m in var_pub)
    prev = setor[mais(mu, -12)]
    den_u = sum(peso[l] * prev[l] for l in letras)
    inc_u = {l: peso[l] * (setor[mu][l] - prev[l]) / den_u * 100 for l in NOMES_SETOR}
    var_u = {l: (setor[mu][l] / prev[l] - 1) * 100 for l in NOMES_SETOR}
    pv = max(abs(var_u[l] - var_pub[mu][l]) for l in NOMES_SETOR)
    print("EMAE %s por setor: variação refeita × publicada %.5f p.p.; soma das incidências %.3f contra %.3f "
          "publicado" % (mu, pv, sum(inc_u.values()), pub_a[mu]))
    if pv > 0.001 or abs(sum(inc_u.values()) - pub_a[mu]) > TOL_CONTRIB:
        raise RuntimeError("EMAE por setor do último mês não confere")
    estatico = dict(mes=mu, total=pub_a[mu], inc=inc_u, var=var_u)
    # índice por atividade: média de 12 meses, base BASE_ATIVIDADE = 100
    def mm12(s_):
        return {m: statistics.mean(s_[mais(m, -k)] for k in range(12)) for m in s_
                if all(mais(m, -k) in s_ for k in range(12))}
    ativ = {}
    for nome, ls, _ in SETORES_ATIVIDADE:
        bruto = {m: sum(peso[l] * v[l] for l in ls) for m, v in setor.items()}
        media = mm12(bruto)
        ativ[nome] = {m: x / media[BASE_ATIVIDADE] * 100 for m, x in media.items()}
    media_t = mm12(eo)
    ativ["EMAE total"] = {m: x / media_t[BASE_ATIVIDADE] * 100 for m, x in media_t.items()}
    ult = max(ativ["EMAE total"])
    print("atividade por setor (média de 12 meses, %s = 100), %s: %s" % (
        BASE_ATIVIDADE, ult, ", ".join("%s %.1f" % (k, v[ult]) for k, v in ativ.items())))
    return orig, des, qq, a4, eo, ed, ea, em, tri, dif, contrib, ativ, estatico


def sgs(cod):
    hoje = datetime.date.today().strftime("%d/%m/%Y")
    d = baixar(SGS % (cod, hoje))
    out = {}
    for x in d:
        if x["valor"] not in (None, ""):
            dd, mm, aa = x["data"].split("/")
            out["%s-%s" % (aa, mm)] = float(x["valor"])
    if not out:
        raise RuntimeError("SGS %d vazio" % cod)
    print("BCB SGS %-5d %d meses, %s a %s" % (cod, len(out), min(out), max(out)))
    return out


def brasil():
    base, pme, resb = sgs(1788), sgs(1786), sgs(1787)
    m2, m1, poup, tit = sgs(27810), sgs(27791), sgs(1835), sgs(27809)
    for m in base:
        if m >= "1995-01" and abs(base[m] - pme.get(m, 0) - resb.get(m, 0)) > 2:
            raise RuntimeError("base do Brasil de %s não fecha: %.0f" % (m, base[m] - pme.get(m, 0) - resb.get(m, 0)))
    comuns_m2 = [m for m in m2 if m in m1 and m in poup and m in tit]
    if len(comuns_m2) < len(m2) - 1:      # o M1 do conceito atual começa um mês depois (jan/2002)
        raise RuntimeError("M2 do Brasil: faltam componentes em %d meses" % (len(m2) - len(comuns_m2)))
    for m in comuns_m2:
        if abs(m2[m] - m1[m] - poup[m] - tit[m]) > 2:
            raise RuntimeError("M2 do Brasil de %s não fecha: %.0f" % (m, m2[m] - m1[m] - poup[m] - tit[m]))
    fmi = sdmx_mensal(FMI_MA_BR)
    comuns = [m for m in fmi if m in base and m >= "1995-01"]
    pior = max(abs(fmi[m] / 1000 / base[m] - 1) for m in comuns)
    print("base do Brasil BCB × FMI: %d meses, maior diferença %.4f%%" % (len(comuns), pior * 100))
    if len(comuns) < 300 or pior > 0.0001:
        raise RuntimeError("base do Brasil não bate com o FMI")
    yoy_ = lambda s_, ini: {m: (s_[m] / s_[mais(m, -12)] - 1) * 100 for m in s_
                            if m >= ini and mais(m, -12) in s_}
    return yoy_(base, INICIO_YOY_BR_BASE), yoy_(m2, INICIO_YOY_BR_M2)


def ipc():
    with urllib.request.urlopen(urllib.request.Request(INDEC, headers=UA), timeout=120) as r:
        linhas = r.read().decode("latin-1").splitlines()
    cab = linhas[0].split(";")
    ic = {c: cab.index(c) for c in ("Codigo", "Periodo", "Indice_IPC", "v_m_IPC", "v_i_a_IPC", "Region")}
    ind, vm_pub, via_pub = {}, {}, {}
    for l in linhas[1:]:
        c = l.split(";")
        if len(c) < len(cab) or c[ic["Codigo"]] != "0" or c[ic["Region"]] != "Nacional":
            continue
        m = c[ic["Periodo"]][:4] + "-" + c[ic["Periodo"]][4:6]
        ind[m] = num_ar(c[ic["Indice_IPC"]]) if "," in c[ic["Indice_IPC"]] else float(c[ic["Indice_IPC"]])
        for col, dest in (("v_m_IPC", vm_pub), ("v_i_a_IPC", via_pub)):
            if c[ic[col]] not in ("NA", ""):
                dest[m] = float(c[ic[col]].replace(",", "."))
    meses = sorted(ind)
    if meses[0] != "2016-12" or len(meses) < 100:
        raise RuntimeError("IPC INDEC: série inesperada %s a %s" % (meses[0], meses[-1]))
    def menos(m, k):
        t = int(m[:4]) * 12 + int(m[5:]) - 1 - k
        return "%04d-%02d" % (t // 12, t % 12 + 1)
    vm = {m: (ind[m] / ind[menos(m, 1)] - 1) * 100 for m in meses if menos(m, 1) in ind}
    via = {m: (ind[m] / ind[menos(m, 12)] - 1) * 100 for m in meses if menos(m, 12) in ind}
    for nome, calc, pub in (("mensal", vm, vm_pub), ("12 meses", via, via_pub)):
        if set(calc) != set(pub):
            raise RuntimeError("IPC %s: meses diferentes do publicado" % nome)
        pior = max(abs(calc[m] - pub[m]) for m in calc)
        print("IPC %s refeito × INDEC: maior diferença %.3f p.p." % (nome, pior))
        if pior > 0.051:
            raise RuntimeError("IPC %s não bate com o INDEC" % nome)
    for var, nome, calc in ((27, "mensal", vm), (28, "12 meses", via)):
        b = {d.strftime("%Y-%m"): v for d, v in bcra(var, "2016-01-01").items()}
        comuns = [m for m in calc if m in b and m >= INICIO_BCRA_IPC]
        pior = max(abs(calc[m] - b[m]) for m in comuns)
        print("IPC %s × BCRA (var. %d): %d meses, maior diferença %.3f p.p." % (nome, var, len(comuns), pior))
        if len(comuns) < len([m for m in calc if m >= INICIO_BCRA_IPC]) - 1 or pior > 0.051:
            raise RuntimeError("IPC %s não bate com o BCRA" % nome)
    return vm, via


def main():
    risco = ambito("riesgopais", "-")
    blue = ambito("dolar/informal", "/")
    oficial = ambito("dolar/oficial", "/")

    conferir_risco(risco, argdatos("finanzas/indices/riesgo-pais", "valor"))
    conferir_cambio("blue", blue, argdatos("cotizaciones/dolares/blue", "venta"))
    conferir_cambio("oficial", oficial, argdatos("cotizaciones/dolares/oficial", "venta"))
    conferir_oficial_bcra(oficial)

    dias = sorted(d for d in blue if d in oficial)
    brecha = {d: (blue[d] / oficial[d] - 1) * 100 for d in dias}
    dif = {d: blue[d] - oficial[d] for d in dias}
    for d in dias:
        b2 = (round(blue[d], 2) / round(oficial[d], 2) - 1) * 100
        if abs(b2 - brecha[d]) > 0.05:
            raise RuntimeError("brecha de %s não fecha: %s × %s" % (d, b2, brecha[d]))

    u = max(risco)
    print("último risco país: %s = %.0f pontos" % (u, risco[u]))
    u = dias[-1]
    print("último câmbio: %s, blue %.2f, oficial %.2f, brecha %.2f%% (%.2f pesos)"
          % (u, blue[u], oficial[u], brecha[u], dif[u]))
    pico = max(dias, key=lambda d: brecha[d])
    print("maior brecha: %s = %.1f%%" % (pico, brecha[pico]))

    bruta = bcra(1)
    meses, ativo, dep, swaps, outros, liq = reservas_mensais(irfcl(), bruta)
    vm, via = ipc()
    mon, meses_mon, cambio = monetario()
    br_base, br_m2 = brasil()
    meses_bal, bal = balanco_bcra({m: mon[1606][m] for m in meses_mon}, cambio)
    trims, bpq = bp()
    (pib_o, pib_d, pib_qq, pib_a4, emae_o, emae_d, emae_a, emae_m, emae_tri, dif_emae,
     emae_contrib, emae_ativ, emae_est) = pib_emae()
    u = max(bruta)
    print("última reserva bruta (BCRA): %s = US$ %.0f milhões" % (u, bruta[u]))
    m = meses[-1]
    print("último mês da planilha: %s, bruta %.0f, depósitos etc. %.0f, swaps %.0f, outros %.0f, líquida %.0f"
          % (m, ativo[m], dep[m], swaps.get(m, 0), outros.get(m, 0), liq[m]))
    print("líquida em %s (posse): %.0f" % ("2023-12", liq["2023-12"]))
    m = max(vm)
    print("IPC %s: mensal %.2f%%, 12 meses %.2f%%" % (m, vm[m], via[m]))

    g_risco = dict(
        id="argentina-risco-pais", titulo="Risco país da Argentina",
        subtitulo="Spread do EMBI da Argentina sobre os títulos do Tesouro americano, em pontos básicos; diário",
        unidade="int", diario=True, buracoMax=8, fonte="Ámbito (JP Morgan)",
        variantes=recortes([serie("Risco país", risco, 0, cor=BRANCO, largura=3, rotulo=True)], False),
    )
    g_cambio = dict(
        id="argentina-dolar-blue-oficial", titulo="Dólar blue e dólar oficial na Argentina",
        subtitulo="Pesos por dólar, cotação de venda; diário",
        unidade="n2", diario=True, buracoMax=8, fonte="Ámbito",
        variantes=recortes([serie("Dólar blue", blue, 2, cor=BRANCO, largura=3, rotulo=True),
                            serie("Dólar oficial", oficial, 2, cor=AZUL, largura=2.5, rotulo=True)], False),
    )
    g_brecha = dict(
        id="argentina-brecha-cambial", titulo="Brecha cambial na Argentina: dólar blue sobre o dólar oficial",
        subtitulo="Quanto o dólar blue supera o oficial, em % ou em pesos; cotação de venda; diário",
        diario=True, buracoMax=8, fonte="Ámbito e FtM", unidade="pct1",
        variantes=recortes([serie("Brecha (%)", brecha, 2, cor=BRANCO, largura=3, rotulo=True)], False, "em %", "pct1")
        + recortes([serie("Brecha (pesos)", dif, 2, cor=BRANCO, largura=3, rotulo=True)], False, "em pesos", "n2"),
    )
    bi = lambda d: {k: v / 1000 for k, v in d.items()}
    g_bruta = dict(
        id="argentina-reservas-brutas", titulo="Reservas internacionais brutas do BCRA",
        subtitulo="US$ bilhões; diário; cifras provisórias", unidade="usd-bi", diario=True, buracoMax=8,
        fonte="BCRA (Principales variables)",
        eixo=dict(min=0, max=80),
        variantes=recortes([serie("Reservas brutas", bi(bruta), 3, cor=AZUL, largura=1, rotulo=True, area=True,
                                  opacidadeArea=0.85)], False),
    )
    g_comp = dict(
        id="argentina-reservas-ativos-passivos", titulo="Reservas do BCRA: ativos e passivos de curto prazo",
        subtitulo="US$ bilhões, fim de mês; passivos: saídas de moeda estrangeira já contratadas que vencem em até 12 meses",
        unidade="usd-bi", fonte="BCRA (Reservas Internacionais e Liquidez em Moeda Estrangeira, via FMI) e FtM",
        variantes=recortes([
            serie("Reservas brutas", {m: ativo[m] / 1000 for m in meses}, 3, cor=AZUL, tipo="barra"),
            serie("Depósitos, empréstimos e títulos", {m: dep[m] / 1000 for m in meses}, 3, cor=VERMELHO, tipo="barra"),
            serie("Swaps de moeda", {m: swaps[m] / 1000 for m in meses if m in swaps}, 3, cor=VERDE, tipo="barra"),
            serie("Outros (até nov/22, inclui o swap com a China)", {m: outros[m] / 1000 for m in meses if m in outros},
                  3, cor=AZUL_ESC, tipo="barra"),
            serie("Reservas líquidas", {m: liq[m] / 1000 for m in meses}, 3, cor=BRANCO, largura=3, rotulo=True),
        ], True),
    )
    g_liq = dict(
        id="argentina-reservas-liquidas", titulo="Reservas internacionais líquidas do BCRA",
        subtitulo="Reservas brutas menos os passivos de curto prazo do BCRA em moeda estrangeira; US$ bilhões, fim de mês",
        unidade="usd-bi", fonte="BCRA (Reservas Internacionais e Liquidez em Moeda Estrangeira, via FMI) e FtM",
        variantes=recortes([
            serie("Reservas líquidas positivas", {m: max(liq[m], 0) / 1000 for m in meses}, 3, cor=AZUL, largura=1,
                  area=True, opacidadeArea=0.85, rotulo=liq[meses[-1]] >= 0),
            serie("Reservas líquidas negativas", {m: min(liq[m], 0) / 1000 for m in meses}, 3, cor=VERMELHO,
                  largura=1, area=True, opacidadeArea=0.85, rotulo=liq[meses[-1]] < 0)], True),
    )
    g_ipc_m = dict(
        id="argentina-inflacao-mensal", titulo="Inflação mensal na Argentina",
        subtitulo="IPC nacional, variação % em relação ao mês anterior", unidade="pct1",
        fonte="INDEC (IPC) e FtM",
        variantes=recortes([serie("Inflação mensal", vm, 1, cor=AZUL, tipo="barra", rotulo=True)], True),
    )
    g_ipc_a = dict(
        id="argentina-inflacao-12m", titulo="Inflação em 12 meses na Argentina",
        subtitulo="IPC nacional, variação % acumulada em 12 meses", unidade="pct1",
        fonte="INDEC (IPC) e FtM",
        variantes=recortes([serie("Inflação em 12 meses", via, 1, cor=BRANCO, largura=3, rotulo=True)], True),
    )

    def quatro(series_fn, unidade_pesos="n2"):
        return (recortes(series_fn("pesos"), True, "em pesos", unidade_pesos)
                + recortes(series_fn("usd"), True, "em dólares", "usd-bi"))

    def conv(serie_mil, moeda):
        """milhares de pesos -> trilhões de pesos ou bilhões de dólares"""
        if moeda == "pesos":
            return {m: x / 1e9 for m, x in serie_mil.items()}
        return {m: x / cambio[m] / 1e6 for m, x in serie_mil.items() if m in cambio}

    sel = lambda n: {m: mon[n][m] for m in meses_mon}
    bm, pub, bancos, resb = sel(1606), sel(1608), sel(1609), sel(1610)
    m1l, m1t, m2l, m2t = sel(1612), sel(1611), sel(1618), sel(1617)
    m1e = {m: m1t[m] - m1l[m] for m in meses_mon}
    poup = {m: m2t[m] - m1t[m] for m in meses_mon}
    poupl = {m: m2l[m] - m1l[m] for m in meses_mon}
    poupe = {m: (m2t[m] - m2l[m]) - m1e[m] for m in meses_mon}
    m2e = {m: m2t[m] - m2l[m] for m in meses_mon}
    g_bm = dict(
        id="argentina-base-monetaria", titulo="Base monetária na Argentina e seus componentes",
        subtitulo="Fim de mês; trilhões de pesos ou US$ bilhões pelo câmbio oficial de fim de mês",
        unidade="n2", fonte="BCRA, FMI (câmbio) e FtM",
        variantes=quatro(lambda moeda: [
            serie("Moeda em poder do público", conv(pub, moeda), 4, cor=VERDE, tipo="barra"),
            serie("Moeda nos bancos", conv(bancos, moeda), 4, cor=VERMELHO, tipo="barra"),
            serie("Reservas bancárias no BCRA", conv(resb, moeda), 4, cor=AZUL_CLARO, tipo="barra"),
            serie("Base monetária", conv(bm, moeda), 4, cor=BRANCO, largura=3, rotulo=True)]),
    )
    yoy = lambda s_: {m: (s_[m] / s_[mais(m, -12)] - 1) * 100 for m in s_ if m >= INICIO_YOY and mais(m, -12) in s_}
    g_bm_a = dict(
        id="argentina-base-monetaria-12m", titulo="Base monetária: variação em 12 meses, Argentina e Brasil",
        subtitulo="Variação % do saldo de fim de mês em moeda local sobre o mesmo mês do ano anterior",
        unidade="pct1", fonte="BCRA, BCB e FtM",
        variantes=recortes([serie("Argentina", yoy(bm), 2, cor=BRANCO, largura=3, rotulo=True),
                            serie("Brasil", br_base, 2, cor=VERDE, largura=2.5, rotulo=True)], True),
    )
    g_m2 = dict(
        id="argentina-m2-m1-poupanca", titulo="Agregado monetário M2 na Argentina: M1 e depósitos de poupança",
        subtitulo="M2 = M1 + depósitos de poupança (cajas de ahorro), em pesos e em moeda estrangeira; fim de mês; trilhões de pesos ou US$ bilhões",
        unidade="n2", fonte="BCRA, FMI (câmbio) e FtM",
        variantes=quatro(lambda moeda: [
            serie("M1", conv(m1t, moeda), 4, cor=VERMELHO, tipo="barra"),
            serie("Depósitos de poupança", conv(poup, moeda), 4, cor=VERDE, tipo="barra"),
            serie("M2", conv(m2t, moeda), 4, cor=BRANCO, largura=3, rotulo=True)]),
    )
    g_m2_moeda = dict(
        id="argentina-m2-por-moeda", titulo="Agregado monetário M2 na Argentina: moeda nacional e estrangeira",
        subtitulo="Depósitos em dólar convertidos pelo câmbio oficial; fim de mês; trilhões de pesos ou US$ bilhões",
        unidade="n2", fonte="BCRA, FMI (câmbio) e FtM",
        variantes=quatro(lambda moeda: [
            serie("M2 em moeda nacional", conv(m2l, moeda), 4, cor=AZUL, tipo="barra"),
            serie("M2 em moeda estrangeira", conv(m2e, moeda), 4, cor=VERDE, tipo="barra"),
            serie("M2 total", conv(m2t, moeda), 4, cor=BRANCO, largura=3, rotulo=True)]),
    )
    g_m2_4 = dict(
        id="argentina-m2-componentes", titulo="Agregado monetário M2 na Argentina: componentes por moeda",
        subtitulo="M1 e depósitos de poupança, em moeda nacional e estrangeira; fim de mês; trilhões de pesos ou US$ bilhões",
        unidade="n2", fonte="BCRA, FMI (câmbio) e FtM",
        variantes=quatro(lambda moeda: [
            serie("M1 em moeda nacional", conv(m1l, moeda), 4, cor=AZUL, tipo="barra"),
            serie("M1 em moeda estrangeira", conv(m1e, moeda), 4, cor=VERMELHO, tipo="barra"),
            serie("Poupança em moeda nacional", conv(poupl, moeda), 4, cor=AZUL_ESC, tipo="barra"),
            serie("Poupança em moeda estrangeira", conv(poupe, moeda), 4, cor=VERDE, tipo="barra"),
            serie("M2 total", conv(m2t, moeda), 4, cor=BRANCO, largura=3, rotulo=True)]),
    )
    g_m2_a = dict(
        id="argentina-m2-12m", titulo="Agregado monetário M2: variação em 12 meses, Argentina e Brasil",
        subtitulo="Variação % do saldo de fim de mês em moeda local sobre o mesmo mês do ano anterior",
        unidade="pct1", fonte="BCRA, BCB e FtM",
        variantes=recortes([serie("Argentina: M2 total", yoy(m2t), 2, cor=BRANCO, largura=3, rotulo=True),
                            serie("Argentina: M2 em moeda nacional", yoy(m2l), 2, cor=AZUL, largura=2.5, rotulo=True),
                            serie("Brasil: M2", br_m2, 2, cor=VERDE, largura=2.5, rotulo=True)], True),
    )
    g_m2_pct = dict(
        id="argentina-m2-pct-estrangeira", titulo="Parcela do M2 em moeda estrangeira na Argentina",
        subtitulo="% do M2 total; fim de mês", unidade="pct1", fonte="BCRA e FtM",
        variantes=recortes([serie("M2 em moeda estrangeira", {m: m2e[m] / m2t[m] * 100 for m in meses_mon}, 2,
                                  cor=AZUL, tipo="barra", rotulo=True)], True),
    )
    conv_bal = conv          # mesmo câmbio da base e do M2
    g_ativos = dict(
        id="argentina-ativos-bcra", titulo="Ativos do BCRA: fontes da base monetária",
        subtitulo="Fim de mês; trilhões de pesos ou US$ bilhões pelo câmbio oficial de fim de mês",
        unidade="n2", fonte="BCRA (balanço, Cuadro I-2), FMI (câmbio) e FtM",
        variantes=quatro(lambda moeda: [
            serie("Ativos externos líquidos", conv_bal(bal["externos"], moeda), 4, cor=AZUL, tipo="barra"),
            serie("Crédito ao setor oficial", conv_bal(bal["oficial"], moeda), 4, cor=VERMELHO, tipo="barra"),
            serie("Créditos a entidades financeiras em moeda nacional", conv_bal(bal["bancos"], moeda), 4,
                  cor=VERDE, tipo="barra"),
            serie("Ativos do BCRA", conv_bal(bal["total"], moeda), 4, cor=BRANCO, largura=3, rotulo=True)]),
    )
    g_ativos_a = dict(
        id="argentina-ativos-bcra-12m", titulo="Ativos do BCRA: variação em 12 meses",
        subtitulo="Variação % do total das fontes da base monetária em pesos sobre o mesmo mês do ano anterior",
        unidade="pct1", fonte="BCRA (balanço, Cuadro I-2) e FtM",
        variantes=recortes([serie("Ativos do BCRA", yoy(bal["total"]), 2, cor=VERDE, largura=3, rotulo=True)], True),
    )
    mb_ = meses_bal[-1]
    print("ativos do BCRA %s: %.2f tri de pesos (US$ %.1f bi), externos %.2f, oficial %.2f, bancos %.2f; 12m %.1f%%"
          % (mb_, bal["total"][mb_] / 1e9, bal["total"][mb_] / cambio[mb_] / 1e6, bal["externos"][mb_] / 1e9,
             bal["oficial"][mb_] / 1e9, bal["bancos"][mb_] / 1e9, yoy(bal["total"])[mb_]))

    def acum4(s_):
        return {m: sum(s_[mais(m, -3 * k)] for k in range(4)) for m in s_
                if all(mais(m, -3 * k) in s_ for k in range(4))}

    def bp_var(series_fn):
        """4 recortes: acumulado em 4 trimestres e trimestral, série inteira e desde Milei."""
        return (recortes(series_fn(acum4), True, "acumulado em 4 trimestres", "usd-bi")
                + recortes(series_fn(lambda s_: dict(s_)), True, "trimestral", "usd-bi"))

    bi_ = lambda s_: {m: x / 1000 for m, x in s_.items()}
    sub_bp = "US$ bilhões; trimestres datados no último mês"
    g_bp = dict(
        id="argentina-bp", titulo="Balanço de pagamentos da Argentina", subtitulo=sub_bp,
        unidade="usd-bi", barra=3, buracoMax=3, fonte="INDEC (via FMI) e FtM",
        variantes=bp_var(lambda f: [
            serie("Conta Corrente", bi_(f(bpq["cc"])), 3, cor=AZUL, tipo="barra"),
            serie("Conta Capital", bi_(f(bpq["ck"])), 3, cor="#FFFF00", tipo="barra"),
            serie("Conta Financeira", bi_(f(bpq["cf"])), 3, cor=VERDE, tipo="barra"),
            serie("Reservas Intern.", bi_(f(bpq["res"])), 3, cor="#F79646", tipo="barra", contorno=True),
            serie("Erros e Omissões", bi_(f(bpq["eo"])), 3, cor=VERMELHO, tipo="barra")]),
    )
    g_cc = dict(
        id="argentina-bp-cc", titulo="Conta corrente da Argentina", subtitulo=sub_bp,
        unidade="usd-bi", barra=3, buracoMax=3, fonte="INDEC (via FMI) e FtM",
        variantes=bp_var(lambda f: [
            serie("Balança Comercial", bi_(f(bpq["bens"])), 3, cor=AZUL, tipo="barra"),
            serie("Serviços", bi_(f(bpq["serv"])), 3, cor=VERMELHO, tipo="barra"),
            serie("Renda Primária", bi_(f(bpq["r1"])), 3, cor=VERDE, tipo="barra"),
            serie("Renda Secundária", bi_(f(bpq["r2"])), 3, cor=AZUL_ESC, tipo="barra"),
            serie("Saldo Conta Corrente", bi_(f(bpq["cc"])), 3, cor=BRANCO, largura=3, rotulo=True)]),
    )
    g_cf = dict(
        id="argentina-bp-cf", titulo="Conta financeira da Argentina",
        subtitulo=sub_bp + "; entrada de recursos é positiva, como no Brasil", unidade="usd-bi", barra=3,
        buracoMax=3, fonte="INDEC (via FMI) e FtM",
        variantes=bp_var(lambda f: [
            serie("ID no Exterior", bi_(f(bpq["id_ext"])), 3, cor=AZUL, tipo="barra"),
            serie("ID no País", bi_(f(bpq["id_pais"])), 3, cor=VERMELHO, tipo="barra"),
            serie("Carteira no Exterior", bi_(f(bpq["cart_ext"])), 3, cor=VERDE, tipo="barra"),
            serie("Carteira no País", bi_(f(bpq["cart_pais"])), 3, cor=AZUL_ESC, tipo="barra"),
            serie("Outros + Derivativos", bi_(f(bpq["outros"])), 3, cor="#4BACC6", tipo="barra"),
            serie("Saldo Conta Financeira", bi_(f(bpq["cf"])), 3, cor=BRANCO, largura=3, rotulo=True)]),
    )
    eixo_em(g_cf, None, dict(max=60))
    tq = trims[-1]
    a4 = {k: acum4(x)[tq] / 1000 for k, x in bpq.items()}
    print("BP %s, 4 trimestres (US$ bi): CC %.1f, KA %.1f, CF %.1f, reservas %.1f, E&O %.1f; bens %.1f, serv %.1f, "
          "r1 %.1f, r2 %.1f" % (tq, a4["cc"], a4["ck"], a4["cf"], a4["res"], a4["eo"], a4["bens"], a4["serv"],
                               a4["r1"], a4["r2"]))

    # atividade
    previa = {m: x for m, x in emae_tri.items() if m > max(pib_qq)}
    usa_previa = dif_emae <= TOL_EMAE_PIB and bool(previa)
    tri_nome = lambda m: "%dº tri/%s" % (int(m[5:]) // 3, m[:4])
    series_qq = [serie("PIB, variação trimestral", pib_qq, 2, cor=AZUL, tipo="barra")]
    if usa_previa:
        series_qq.append(serie("Prévia pelo EMAE (%s)" % ", ".join(tri_nome(m) for m in sorted(previa)), previa, 2,
                               cor=AZUL, tipo="barra", opacidade=0.4))
    g_pib = dict(
        id="argentina-pib", titulo="PIB real da Argentina: variação acumulada em 4 trimestres",
        subtitulo="Variação % real dos 4 últimos trimestres sobre os 4 anteriores; série original; "
                  "trimestres datados no último mês",
        unidade="pct1", barra=3, buracoMax=3, fonte="INDEC (cuentas nacionales) e FtM",
        variantes=recortes([serie("PIB, acumulado em 4 trimestres", pib_a4, 2, cor=AZUL, tipo="barra")], True),
    )
    g_pib_t = dict(
        id="argentina-pib-trimestral", titulo="PIB real da Argentina: variação trimestral",
        subtitulo="Variação % real sobre o trimestre anterior; dessazonalizado; trimestres datados no último mês",
        unidade="pct1", barra=3, buracoMax=3, fonte="INDEC (cuentas nacionales e EMAE) e FtM",
        variantes=recortes(series_qq, True),
    )
    g_emae_i = dict(
        id="argentina-emae-indice", titulo="EMAE: estimador mensal de atividade econômica da Argentina",
        subtitulo="Índice, 2004 = 100; dessazonalizado", unidade="ind", fonte="INDEC (EMAE)",
        variantes=recortes([serie("Dessazonalizado", emae_d, 2, cor=BRANCO, largura=3, rotulo=True)], True),
    )
    g_emae_s = dict(
        id="argentina-emae-atividade", titulo="EMAE por atividade econômica",
        subtitulo="Índice, nov/2023 = 100; média móvel de 12 meses da série original (o INDEC não dessazonaliza "
                  "os setores)",
        unidade="ind", fonte="INDEC (EMAE) e FtM", eixo=dict(zero=False),
        variantes=recortes([serie(nome, emae_ativ[nome], 2, cor=cor, largura=2.5, rotulo=True)
                            for nome, _, cor in SETORES_ATIVIDADE]
                           + [serie("EMAE total", emae_ativ["EMAE total"], 2, cor=BRANCO, largura=3, rotulo=True)],
                           True),
    )
    g_emae_a = dict(
        id="argentina-emae-12m", titulo="EMAE: variação anual",
        subtitulo="Variação % sobre o mesmo mês do ano anterior; série original", unidade="pct1",
        fonte="INDEC (EMAE) e FtM",
        variantes=recortes([serie("EMAE", emae_a, 2, cor=BRANCO, largura=3, rotulo=True)], True),
    )
    g_emae_c = dict(
        id="argentina-emae-contribuicoes", titulo="EMAE: contribuições por setor para a variação anual",
        subtitulo="Pontos percentuais da variação sobre o mesmo mês do ano anterior; série original",
        unidade="pct1", barra=1, fonte="INDEC (EMAE e cuentas nacionales) e FtM",
        variantes=recortes([serie(nome, {m: v[nome] for m, v in emae_contrib.items()}, 2, cor=cor, tipo="barra")
                            for nome, _, cor in GRUPOS_EMAE]
                           + [serie("EMAE", emae_a, 2, cor=BRANCO, largura=3, rotulo=True)], True),
    )
    MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
                "outubro", "novembro", "dezembro"]
    mu = emae_est["mes"]
    ordem = sorted(NOMES_SETOR, key=lambda l: -emae_est["inc"][l])
    g_emae_inc = dict(
        id="argentina-emae-setores-mes", tipo="ranking",
        titulo="EMAE por setor: variação anual e incidência, %s de %s" % (MESES_PT[int(mu[5:]) - 1], mu[:4]),
        subtitulo="Incidência: pontos percentuais da variação do EMAE; variação: % sobre o mesmo mês do ano anterior",
        unidade="pp", unidade2="pct1", limite=15, fonte="INDEC (EMAE e cuentas nacionales) e FtM",
        legendaPar=[["Incidência (p.p.)", AZUL], ["Variação (%)", "#8a8a86"]],
        itens=[["EMAE, nível geral", round(emae_est["total"], 2), BRANCO, True, None]]
        + [[NOMES_SETOR[l], round(emae_est["inc"][l], 2), AZUL, False, round(emae_est["var"][l], 1)] for l in ordem],
    )
    g_emae_m = dict(
        id="argentina-emae-mensal", titulo="EMAE: variação mensal",
        subtitulo="Variação % sobre o mês anterior; série dessazonalizada", unidade="pct1",
        fonte="INDEC (EMAE) e FtM",
        variantes=recortes([serie("EMAE", emae_m, 2, cor=AZUL, tipo="barra", rotulo=True)], True),
    )
    g_emae_t = dict(
        id="argentina-emae-trimestre", titulo="EMAE no trimestre e PIB trimestral",
        subtitulo="Variação % do trimestre contra o anterior, dessazonalizado; EMAE pela média dos 3 meses; "
                  "trimestres datados no último mês",
        unidade="pct1", barra=3, buracoMax=3, fonte="INDEC (EMAE e cuentas nacionales) e FtM",
        variantes=recortes([serie("EMAE, média do trimestre", emae_tri, 2, cor=AZUL, tipo="barra"),
                            serie("PIB", pib_qq, 2, cor=BRANCO, largura=3, rotulo=True)], True),
    )
    mq, me = max(pib_qq), max(emae_o)
    print("PIB %s: trimestral %.2f%%, 4 trimestres %.2f%% | EMAE %s: índice %.2f, anual %.2f%%, mensal %.2f%% | "
          "prévia %s (diferença média %.3f p.p.): %r" % (mq, pib_qq[mq], pib_a4[max(pib_a4)], me, emae_o[me],
                                                         emae_a[me], emae_m[me], "sim" if usa_previa else "não",
                                                         dif_emae, {k: round(v, 2) for k, v in previa.items()}))

    eixo_em(g_bm, "em pesos", dict(max=50))
    for g_ in (g_m2, g_m2_moeda, g_m2_4):
        eixo_em(g_, "em dólares", dict(max=120))

    m = meses_mon[-1]
    print("monetário %s: base %.2f tri, M2 %.2f tri (US$ %.1f bi), %% em moeda estrangeira %.1f%%, "
          "base 12m %.1f%%, M2 12m %.1f%%" % (m, bm[m] / 1e9, m2t[m] / 1e9, m2t[m] / cambio[m] / 1e6,
                                               m2e[m] / m2t[m] * 100, yoy(bm)[m], yoy(m2t)[m]))
    mb = max(br_base)
    print("Brasil %s: base 12m %.1f%%, M2 12m %.1f%%" % (mb, br_base[mb], br_m2[max(br_m2)]))

    ref = max(max(risco), dias[-1], max(bruta))
    doc = dict(assunto="Argentina", grupo="Análises Variadas", fonte="Ámbito, BCRA, BCB, FMI, INDEC e FtM",
               referencia=ref.strftime("%Y-%m"), atualizado=datetime.date.today().isoformat(), formato="artigo",
               secoes=[dict(titulo="Risco país", texto="", fontes=[], figuras=[], graficos=[g_risco]),
                       dict(titulo="Câmbio", texto="", fontes=[], figuras=[], graficos=[g_cambio, g_brecha]),
                       dict(titulo="Reservas internacionais", texto="", fontes=[], figuras=[],
                            graficos=[g_bruta, g_comp, g_liq]),
                       dict(titulo="Inflação", texto="", fontes=[], figuras=[], graficos=[g_ipc_m, g_ipc_a]),
                       dict(titulo="Atividade", texto="", fontes=[], figuras=[],
                            graficos=[g_pib, g_pib_t, g_emae_i, g_emae_s, g_emae_a, g_emae_c, g_emae_inc, g_emae_m, g_emae_t]),
                       dict(titulo="Contas externas", texto="", fontes=[], figuras=[], graficos=[g_bp, g_cc, g_cf]),
                       dict(titulo="Ativos do BCRA", texto="", fontes=[], figuras=[], graficos=[g_ativos, g_ativos_a]),
                       dict(titulo="Base monetária", texto="", fontes=[], figuras=[], graficos=[g_bm, g_bm_a]),
                       dict(titulo="M2", texto="", fontes=[], figuras=[],
                            graficos=[g_m2, g_m2_moeda, g_m2_4, g_m2_a, g_m2_pct])])
    for sec in doc["secoes"]:
        sec["graficos"] = [achatar(g) for g in sec["graficos"]]
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado", SAIDA)


if __name__ == "__main__":
    sys.exit(main())

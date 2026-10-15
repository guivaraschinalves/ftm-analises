#!/usr/bin/env python3
"""
Quanto as subvenções de 2026 valem para a Petrobras.

É a tabela T.3 de "Impacto da defasagem da gasolina no IPCA e reflexos de sua
subvenção nos resultados da Petrobras" (Francisco Pessoa Faria, Blog do IBRE),
refeita com dado observado no lugar de projeção e estendida ao diesel.

O QUE MUDA EM RELAÇÃO AO ARTIGO

  Ele escreveu em maio de 2026, quando a subvenção da gasolina tinha acabado
  de sair, e por isso projetou: produção e importação do biênio 2024-2025
  distribuídas nos sete meses restantes do ano, PPI estimado com os dados até
  22 de maio. Aqui tudo isso é observado, mês a mês, pela ANP.

  E o diesel entra. No artigo ele não existe, porque a subvenção do diesel
  (MP 1.363, de 30/5/2026, e MP 1.391, de 11/9/2026) veio depois e porque a
  tabela de preços de diesel da Petrobras não estava à mão.

A CONTA, QUE É A DELE

  ganho mensal     = produção × subvenção por litro
  prejuízo         = (PPI − preço cobrado) × importação × meses
  produção × preço = produção × preço cobrado

  O ganho é a parte robusta: não depende de preço nenhum, só do volume e do
  valor legal da subvenção, que é o mesmo para S-10 e S-500. O prejuízo
  depende do PPI e do preço, e os dois são médias.

O QUE A CONTA NÃO É

  Não é resultado contábil da empresa. Ignora custo de produção, tributo,
  hedge, estoque e o preço de exportação. Mede uma coisa só: a diferença
  entre vender ao preço de tabela e vender ao preço com subvenção, no volume
  que a empresa de fato produziu e importou.

  E não desconta o que a subvenção custa ao Tesouro, que é o outro lado.
"""
import datetime
import os
import sys

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anp_desembaracos as ad
import defasagem as df
import oferta_diesel as od
import oferta_gasolina as og
import precos_combustiveis as pc

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAIDA = os.path.join(RAIZ, "subvencao-petrobras.xlsx")

# O importador, como ele aparece na razão social do Relatório de Desembaraços.
IMPORTADOR = "PETROLEO BRASILEIRO"

# Quantos dias um ponto de entrega continua valendo depois da última vigência
# publicada. Um ano é folgado para quem está ativo e corta quem saiu da tabela.
VALIDADE = 365

# Um bloco por aba. `produto` é o nome na tabela da Petrobras; `aba_ppi` é a
# aba do arquivo da ANP; `modulo` é quem sabe a produção daquele derivado.
PRODUTOS = [
    {
        "nome": "Gasolina A",
        "produto": "Gasolina A",
        "aba_ppi": "Gasolina R$ semanal",
        "pdf": "Gasolina",
        "modulo": og,
        "ncm": ad.NCM_GASOLINA,
        "medidas": "MP 1.358, de 25/5/2026",
    },
    {
        "nome": "Diesel S-10",
        "produto": "Diesel S-10",
        "aba_ppi": "Diesel R$ semanal",
        "pdf": "Diesel",
        "modulo": od,
        "ncm": ad.NCM_DIESEL,
        "medidas": "MP 1.363, de 30/5/2026, e MP 1.391, de 11/9/2026",
    },
]


def mes_de(d):
    return d.strftime("%Y-%m")


def precos_mensais(linhas, produto):
    """{mês: (preço de tabela, preço com subvenção ou None)} em R$/l.

    Média simples dos pontos de entrega EXA que tinham preço vigente no dia 15
    do mês. É a modalidade do portão da refinaria, a mesma que o defasagem.py
    usa, e o dia 15 evita que um reajuste do fim do mês mande na média."""
    pontos = sorted({l[5] for l in linhas
                     if l[1] == produto and l[4] == df.MODALIDADE})
    escadas = {p: df.escadas_de(linhas, "Petrobras", p, produto=produto)
               for p in pontos}
    # O último dia em que cada ponto apareceu na tabela. A escada carrega o
    # último preço para sempre, e sem este corte Manaus, que a Petrobras
    # parou de publicar em 2022, continuaria entrando na média de 2026 com o
    # preço de 2022 e sem subvenção — e puxaria a subvenção média para baixo.
    ultimo = {p: max((d for d, _v in tab + sub), default=None)
              for p, (tab, sub) in escadas.items()}
    primeira = min((d for tab, sub in escadas.values() for d, _v in tab + sub),
                   default=None)
    if primeira is None:
        return {}
    fora, hoje = {}, datetime.date.today()
    ano, mes = primeira.year, primeira.month
    while (ano, mes) <= (hoje.year, hoje.month):
        dia = datetime.date(ano, mes, 15)
        cheios, liquidos = [], []
        for ponto, (tab, sub) in escadas.items():
            if ultimo[ponto] is None or (dia - ultimo[ponto]).days > VALIDADE:
                continue
            v = df.preco_em(tab, dia)
            if v is None:
                continue
            cheios.append(v)
            s = df.preco_em(sub, dia)
            liquidos.append(s if s is not None else v)
        if cheios:
            liquido = sum(liquidos) / len(liquidos)
            cheio = sum(cheios) / len(cheios)
            fora["%04d-%02d" % (ano, mes)] = (
                cheio, liquido if abs(cheio - liquido) > 1e-9 else None)
        mes += 1
        if mes == 13:
            ano, mes = ano + 1, 1
    return fora


def ppi_mensal(caminho, aba, minimo=3):
    """{mês: R$/l} — média das semanas, média dos pontos de entrega."""
    acc = {}
    for _ini, fim, valores in df.ler_ppi(caminho, aba):
        if valores:
            acc.setdefault(mes_de(fim), []).append(
                sum(valores.values()) / len(valores))
    return {m: sum(v) / len(v) for m, v in acc.items() if len(v) >= minimo}


def producao_petrobras(modulo):
    """{mês: m³} do que a Petrobras refinou."""
    fora = {}
    for (mes, grupo, _reg), v in modulo.producao_por_grupo().items():
        if grupo == "petrobras":
            fora[mes] = fora.get(mes, 0.0) + v
    return fora


def importacao_petrobras(ncm, cache):
    """{mês: m³} do que a Petrobras importou."""
    fora = {}
    for mes, imps in ad.por_importador(ncm, cache).items():
        for razao, v in imps.items():
            if IMPORTADOR in ad.sem_acento(razao).upper():
                fora[mes] = fora.get(mes, 0.0) + v
    return fora


def janela(precos, prod, imp, ppi):
    """(primeiro mês com subvenção, último mês com volume) ou None.

    O começo é o primeiro mês em que a tabela traz coluna subvencionada; o fim
    é o último mês com produção publicada, que é sempre o dado mais atrasado
    da conta."""
    com_subv = sorted(m for m, (_c, liq) in precos.items() if liq is not None)
    if not com_subv or not prod:
        return None
    fim = max(m for m in prod if m in precos and m in ppi and m in imp)
    return (com_subv[0], fim) if com_subv[0] <= fim else None


def media(d, ini, fim):
    sel = [v for m, v in d.items() if ini <= m <= fim]
    return sum(sel) / len(sel) if sel else None


def calcular(bloco):
    """A T.3 de um produto: (linhas da tabela, detalhe mensal, nota)."""
    caminho = pc.pdf_de(bloco["pdf"])
    if not caminho:
        return None, [], "sem tabela de preços da Petrobras para %s" % bloco["nome"]
    linhas = pc.ler_petrobras(caminho)
    precos = precos_mensais(linhas, bloco["produto"])
    ppi = ppi_mensal(df.baixar_ppi(), bloco["aba_ppi"])
    prod = producao_petrobras(bloco["modulo"])
    imp = importacao_petrobras(bloco["ncm"], bloco["modulo"].CACHE)

    jan = janela(precos, prod, imp, ppi)
    if not jan:
        return None, [], "sem mês com subvenção e volume ao mesmo tempo"
    ini, fim = jan
    meses = [m for m in sorted(prod) if ini <= m <= fim]
    n = len(meses)

    p_prod = media(prod, ini, fim) / 1000.0          # m³ -> mil m³
    p_imp = media(imp, ini, fim) / 1000.0
    cheio = sum(precos[m][0] for m in meses) / n
    liquido = sum(precos[m][1] if precos[m][1] is not None else precos[m][0]
                  for m in meses) / n
    paridade = sum(ppi[m] for m in meses) / n
    subvencao = cheio - liquido

    # Mil m³ são 10^6 litros, então mil m³ × R$/l já sai em R$ milhões.
    def milhoes(mil_m3, reais_litro):
        return mil_m3 * reais_litro

    # A ORIENTAÇÃO DAS COLUNAS É A DO ARTIGO, e é contraintuitiva. A subvenção
    # é paga ao produtor com a condição de ser descontada do preço cobrado:
    # a empresa SOBE a tabela e a distribuidora paga como antes. Então o preço
    # com subvenção é o que a distribuidora paga, que é o patamar de ANTES, e
    # o preço de tabela é o que a Petrobras recebe, que é o DEPOIS.
    tabela = [
        ("Produção mensal da Petrobras", "mil m³", p_prod, p_prod),
        ("Importação mensal da Petrobras", "mil m³", p_imp, p_imp),
        ("Preço recebido pela Petrobras", "R$/l", liquido, cheio),
        ("Preço de Paridade de Importação", "R$/l", paridade, paridade),
        ("Prejuízo com importações no período", "R$ milhões",
         milhoes(p_imp, paridade - liquido) * n,
         milhoes(p_imp, paridade - cheio) * n),
        ("Produção × preço (mensal)", "R$ milhões",
         milhoes(p_prod, liquido), milhoes(p_prod, cheio)),
        ("Ganho mensal da subvenção", "R$ milhões", None,
         milhoes(p_prod, subvencao)),
        ("Ganho no período", "R$ milhões", None,
         milhoes(p_prod, subvencao) * n),
    ]
    detalhe = [(m, prod.get(m, 0) / 1000.0, imp.get(m, 0) / 1000.0,
                precos[m][0], precos[m][1], ppi.get(m),
                prod.get(m, 0) / 1000.0
                * (precos[m][0] - (precos[m][1] or precos[m][0])))
               for m in meses]
    nota = ("%d meses, de %s a %s. Subvenção média de R$ %.4f/l."
            % (n, ini, fim, subvencao))
    return tabela, detalhe, nota


def escrever(resultados, hoje):
    wb = openpyxl.Workbook()
    neg = Font(bold=True)

    ws = wb.active
    ws.title = "LEIA-ME"
    for t, bold in [
        ("Quanto as subvenções de 2026 valem para a Petrobras", True),
        ("Gerado em %s" % hoje.strftime("%d/%m/%Y"), False),
        ("", False),
        ("É a tabela T.3 do artigo de Francisco Pessoa Faria no Blog do IBRE "
         "(FGV), refeita com dado observado", False),
        ("no lugar de projeção e estendida ao diesel, que no artigo não "
         "existe.", False),
        ("", False),
        ("O QUE MUDA EM RELAÇÃO AO ARTIGO", True),
        ("Ele escreveu em maio de 2026, quando a subvenção da gasolina tinha "
         "acabado de sair, e por isso projetou:", False),
        ("produção e importação do biênio 2024-2025 distribuídas nos sete "
         "meses restantes do ano, e PPI estimado", False),
        ("com os dados até 22 de maio. Aqui tudo é observado, mês a mês, pela "
         "ANP.", False),
        ("", False),
        ("A CONTA", True),
        ("ganho mensal     = produção × subvenção por litro", False),
        ("prejuízo         = (PPI − preço cobrado) × importação × meses", False),
        ("produção × preço = produção × preço cobrado", False),
        ("", False),
        ("O ganho é a parte robusta: não depende de preço nenhum, só do "
         "volume e do valor legal da subvenção,", False),
        ("que é o mesmo para S-10 e S-500. O prejuízo depende do PPI e do "
         "preço cobrado, e os dois são médias.", False),
        ("", False),
        ("DE ONDE VEM CADA NÚMERO", True),
        ("Produção | ANP, produção por refinaria, somando só as plantas que "
         "eram da Petrobras naquele mês.", False),
        ("Importação | ANP, Relatório de Desembaraços, linhas em que o "
         "importador é a própria Petrobras.", False),
        ("Preço cobrado | tabela da Petrobras, modalidade EXA (no duto dentro "
         "da refinaria), sem tributos, média", False),
        ("   simples dos pontos de entrega com preço vigente no dia 15 de cada "
         "mês.", False),
        ("PPI | preço de paridade de importação da ANP, média das semanas e "
         "dos pontos de entrega.", False),
        ("", False),
        ("O TETO, QUE É A RESSALVA MAIS IMPORTANTE", True),
        ("A linha do ganho supõe que a subvenção é paga sobre TODO o volume "
         "produzido. É a suposição do artigo,", False),
        ("e na gasolina ela passa despercebida: R$ 882 milhões por mês cabe "
         "no orçamento. No diesel ela quebra.", False),
        ("", False),
        ("Pela nossa conta o diesel renderia R$ 14 bilhões em três meses, só "
         "para a Petrobras. Três coisas dizem", False),
        ("que isso é muito:", False),
        ("  1. A subvenção é do diesel A RODOVIÁRIO, e o denominador aqui é a "
         "produção total de diesel, que", False),
        ("     inclui marítimo, não rodoviário e outros usos.", False),
        ("  2. Os créditos extraordinários de 2026 para subvenção de "
         "combustíveis somam cerca de R$ 17 bilhões", False),
        ("     (MP 1.388 com R$ 3,15 bi, MP 1.389 com R$ 6,6 bi, MP 1.395 com "
         "R$ 7,52 bi), e a fatia do diesel", False),
        ("     rodoviário fica perto de R$ 9 bilhões — para todas as empresas "
         "e um período maior.", False),
        ("  3. Desde a MP 1.391 o valor por litro é definido por ato do "
         "Ministro da Fazenda, em janelas de 30", False),
        ("     dias renováveis. Não é R$ 2,12 correndo sem parar.", False),
        ("", False),
        ("O FUNDO DA QUESTÃO: são duas coisas diferentes. O DESCONTO que a "
         "Petrobras dá no preço à distribuidora", False),
        ("está na tabela dela e é o que esta planilha mede. O que o TESOURO "
         "devolve a ela não está em lugar", False),
        ("nenhum público. A T.3 supõe que os dois são iguais; se o Tesouro "
         "ressarce menos que o desconto, a", False),
        ("diferença não é ganho, é prejuízo.", False),
        ("", False),
        ("Leia a linha do ganho como TETO: quanto a medida valeria se "
         "alcançasse tudo. O que de fato foi pago", False),
        ("sai no resultado da empresa e na execução orçamentária, não aqui.", False),
        ("", False),
        ("E O DESCONTO NEM SEMPRE É A SUBVENÇÃO", True),
        ("A diferença entre as duas colunas de preço é o desconto que a "
         "empresa de fato aplicou. Quando ela mexe", False),
        ("na tabela no mesmo dia em que a subvenção entra, os dois deixam de "
         "coincidir. Na gasolina coincidem:", False),
        ("a média sai em R$ 0,4400, que é o valor legal. No diesel a média "
         "sai acima de R$ 1,12 porque em 2/6/2026", False),
        ("a Petrobras subiu a tabela junto.", False),
        ("", False),
        ("O QUE ISTO NÃO É", True),
        ("Não é resultado contábil. Ignora custo de produção, tributo, hedge, "
         "estoque e preço de exportação.", False),
        ("Mede uma coisa só: a diferença entre vender ao preço de tabela e "
         "vender ao preço com subvenção, no", False),
        ("volume que a empresa de fato produziu e importou.", False),
        ("E não desconta o que a subvenção custa ao Tesouro, que é o outro "
         "lado da mesma moeda.", False),
        ("", False),
        ("ATENÇÃO AO DIESEL", True),
        ("O PPI da ANP para diesel é de Diesel A S10, então a linha do "
         "prejuízo com importações compara o S-10", False),
        ("com o PPI do S-10. Já a produção e a importação são de diesel "
         "TOTAL, porque nem a ANP nem o Relatório", False),
        ("de Desembaraços separam por teor de enxofre. Como a subvenção é a "
         "mesma para S-10 e S-500 (R$ 1,12 e", False),
        ("depois R$ 2,12 por litro nas duas), a linha do ganho não sofre com "
         "isso; a do prejuízo sofre um pouco,", False),
        ("porque o S-500 é 28% das vendas e custa alguns centavos menos.", False),
        ("", False),
        ("Fontes: ANP (produção, desembaraços, PPI) e tabelas de preços da "
         "Petrobras (Resolução ANP 795/2019).", False),
    ]:
        ws.append([t])
        if bold:
            ws.cell(ws.max_row, 1).font = neg
    ws.column_dimensions["A"].width = 105

    for bloco, tabela, detalhe, nota in resultados:
        ws = wb.create_sheet(bloco["nome"])
        ws.append(["Impacto da subvenção sobre os resultados da Petrobras — %s"
                   % bloco["nome"]])
        ws.cell(ws.max_row, 1).font = neg
        ws.append([bloco["medidas"]])
        ws.append([nota])
        ws.append([])
        inicio = ws.max_row + 1
        ws.append(["", "", "Antes da subvenção", "Após a subvenção"])
        for c in ws[inicio]:
            c.font = neg
            c.alignment = Alignment(wrap_text=True, vertical="top")
        for rotulo, unidade, antes, depois in tabela:
            ws.append([rotulo, unidade, antes, depois])
        for linha in ws.iter_rows(min_row=inicio + 1, min_col=3, max_col=4):
            for c in linha:
                if isinstance(c.value, float):
                    c.number_format = "#,##0.000" if abs(c.value) < 10 else "#,##0"
        for col, larg in zip("ABCD", (38, 12, 20, 20)):
            ws.column_dimensions[col].width = larg

        base = ws.max_row + 3
        ws.cell(base, 1, "Mês a mês, que é de onde saem as médias").font = neg
        cab = ["mês", "produção Petrobras (mil m³)",
               "importação Petrobras (mil m³)", "preço de tabela R$/l",
               "preço com subvenção R$/l", "PPI R$/l",
               "ganho do mês (R$ milhões)"]
        topo = base + 2
        for i, nome in enumerate(cab, start=1):
            c = ws.cell(topo, i, nome)
            c.font = neg
            c.alignment = Alignment(wrap_text=True, vertical="top")
        for l in detalhe:
            ws.append(list(l))
        for linha in ws.iter_rows(min_row=topo + 1):
            for c in linha:
                if isinstance(c.value, float):
                    c.number_format = "#,##0.000" if abs(c.value) < 10 else "#,##0"
        for i, larg in enumerate((10, 16, 16, 14, 16, 11, 15), start=1):
            ws.column_dimensions[get_column_letter(i)].width = larg

    wb.save(SAIDA)


def main():
    hoje = datetime.date.today()
    resultados = []
    for bloco in PRODUTOS:
        print("%s…" % bloco["nome"])
        tabela, detalhe, nota = calcular(bloco)
        if not tabela:
            print("  pulado: %s" % nota, file=sys.stderr)
            continue
        print("  %s" % nota)
        for rotulo, unidade, antes, depois in tabela:
            print("    %-36s %-11s %12s %12s"
                  % (rotulo, unidade,
                     "%.3f" % antes if antes is not None else "—",
                     "%.3f" % depois if depois is not None else "—"))
        resultados.append((bloco, tabela, detalhe, nota))
    if not resultados:
        raise SystemExit("nada a escrever")
    escrever(resultados, hoje)
    print("\nescrito: %s" % SAIDA)


if __name__ == "__main__":
    main()

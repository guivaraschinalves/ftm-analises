#!/usr/bin/env python3
"""
A composição do preço dos combustíveis: quanto do preço na bomba é o
combustível que sai da refinaria, quanto é biocombustível, quanto é imposto e
quanto fica com a distribuidora e o posto.

Módulo de precos_combustiveis.py — não roda sozinho. Para conferir o leitor
sem gerar a planilha:

    ~/.venvs/dados-economicos/bin/python scripts/composicao_anp.py --testar

DUAS SÉRIES, porque a ANP publica a mesma conta em dois lugares, com recortes
que não se encontram:

  1. **Semanal, só Brasil** — a "Síntese Semanal do Comportamento dos Preços
     dos Combustíveis", um PDF por semana. A composição está num gráfico de
     barra empilhada por produto; os valores em R$ vêm ao lado de cada faixa.
  2. **Mensal, Brasil e as cinco regiões** — as planilhas de "Composição e
     estruturas de formação dos preços". Uma por produto e por mês, cada uma
     com UMA semana de referência. É a única com corte regional.

Quem quer região não tem semana, e quem quer semana não tem região: a
diferença não é de metodologia, é do que a ANP escolheu publicar em cada
lugar. A fonte dos números é a mesma nos dois — o Relatório do Mercado de
Derivados de Petróleo do MME.

O ACERVO. Os dois acervos ficam versionados em dados/:

    dados/anp-composicao-semanal.csv
    dados/anp-composicao-semanal-edicoes.txt   (as edições já abertas)
    dados/anp-composicao-regioes.csv

e cada rodada baixa só o que falta. Sem isso, refazer a planilha custaria
260 MB de PDF — são ~380 edições de meio megabyte. Os PDFs vão para um
diretório temporário e são apagados ao fim. A lista de edições existe porque
o painel de composição só aparece da semana de 20/4/2024 em diante: sem
registrar que as antigas já foram abertas, toda rodada baixaria as 256 edições
de 2019 a 2024 que não rendem uma linha.

O QUE OS NÚMEROS NÃO SÃO

  - O componente de refinaria aqui é **livre de tributos**: os federais e os
    estaduais são linhas à parte. A série de produtores e importadores que já
    está na planilha ("ANP semanal") **inclui PIS/Cofins e CIDE**. São
    recortes diferentes do mesmo preço e não se comparam direto.
  - Na gasolina, o componente não é o preço de um litro de gasolina A: é a
    parcela de gasolina A (70%) num litro de gasolina C. O mesmo vale para o
    etanol anidro (30%) e, no diesel, para a mistura com biodiesel — cuja
    proporção mudou várias vezes no período.
  - As margens são **brutas e por resíduo**: é o que sobra do preço ao
    consumidor depois dos outros itens, então carregam frete, custo
    operacional e lucro, de distribuidora e de posto juntos.
  - GLP é em R$ por botijão de 13 kg, não por litro.
"""
import csv
import datetime
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.request

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DADOS = os.path.join(RAIZ, "dados")
ACERVO_SEMANAL = os.path.join(DADOS, "anp-composicao-semanal.csv")
ACERVO_REGIOES = os.path.join(DADOS, "anp-composicao-regioes.csv")
# As edições já abertas, inclusive as que não têm painel de composição — sem
# essa lista, toda rodada baixaria de novo as ~250 edições antigas que não
# rendem uma linha.
VISTAS_SEMANAL = os.path.join(DADOS, "anp-composicao-semanal-edicoes.txt")

PAGINA_SINTESE = ("https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/"
                  "precos/sintese-semanal-do-comportamento-dos-precos-dos-combustiveis")
PAGINA_CEFP = ("https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/"
               "precos/composicao-e-estruturas-de-formacao-dos-precos")
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                           " (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}

REGIOES = ["Brasil", "Sudeste", "Sul", "Centro-Oeste", "Norte", "Nordeste"]

# A ordem em que os itens entram no preço, da refinaria ao posto. É a ordem das
# colunas na aba larga e a ordem de empilhamento de um gráfico de área.
ITENS = [
    "Gasolina A", "Etanol anidro", "Diesel A", "Biodiesel", "GLP do produtor",
    "Tributos federais", "Tributos estaduais",
    "Margem de distribuição e revenda", "Margem de distribuição e transporte",
    "Margem de distribuição", "Custo de transporte", "Margem de revenda",
]
TOTAL = "Preço ao consumidor"

# Rótulo publicado → nome aqui. Os dois lados da casa escrevem a mesma coisa de
# jeitos diferentes ("Tributo Estadual" na Síntese, "Tributos Estaduais 4" na
# planilha), e o nome muda de ano para ano; o que não casar com nenhum padrão
# sai com "?" na frente, para aparecer na conferência em vez de sumir.
PADROES = [
    (r"(Pre.o (do )?Produtor de )?Gasolina A", "Gasolina A"),
    (r"(Pre.o do )?Etanol Anidro", "Etanol anidro"),
    (r"(Pre.o Produtor )?Diesel A", "Diesel A"),
    (r"(Pre.o do )?[Bb]iodiesel", "Biodiesel"),
    (r"(Pre.o (do )?Produtor (de )?)?GLP", "GLP do produtor"),
    (r"Tributos? Federa", "Tributos federais"),
    (r"Tributos? Estadua", "Tributos estaduais"),
    # "Margem Bruta" na planilha, "Margens Estimadas" na Síntese, e a chamada
    # da nota de pé de página pode vir colada no meio ("Distribuição3 +").
    (r"Marge(m|ns) (Bruta|Estimada)s? (de )?Distribui..o\s*\d?\s*\+\s*(Custos? )?Transporte",
     "Margem de distribuição e transporte"),
    (r"Marge(m|ns) (Bruta|Estimada)s? (de )?Distribui..o\s*\d?\s*\+\s*Revenda",
     "Margem de distribuição e revenda"),
    (r"Marge(m|ns) (Bruta|Estimada)s? (de )?Revenda", "Margem de revenda"),
    (r"Marge(m|ns) (Bruta|Estimada)s? (de )?Distribui..o\s*\d?\s*$", "Margem de distribuição"),
    (r"Custos? de Transporte", "Custo de transporte"),
    (r"Pre.o (ao|de) (Consumidor|Revenda)", TOTAL),
]


def canonico(bruto):
    s = re.sub(r"\s+", " ", bruto).strip()
    s = re.sub(r"\s*\(\w{2}\)\s*$", "", s)        # "Etanol Anidro (SP)", "Biodiesel (BR)"
    s = re.sub(r"\s*\d\s*$", "", s)               # a chamada de nota de pé de página
    for padrao, nome in PADROES:
        if re.match(padrao, s):
            return nome
    return "?" + s


# O nome da aba na planilha mensal → o mesmo nome que a Síntese usa, para que
# as duas séries entrem na planilha com a mesma grafia.
PRODUTOS = {"GASOLINA C": "Gasolina C", "DIESEL S10": "Diesel B S10",
            "DIESEL S500": "Diesel B S500", "GLP": "GLP P-13"}


def produto_do_rotulo(bruto, reserva=""):
    """Qual combustível é este, pelo nome do item de refinaria. Em 2024 o
    rótulo do diesel não trazia o teor de enxofre ('Diesel A', e só); então a
    graduação sai do título da página, que é o `reserva`."""
    s = re.sub(r"\s+", " ", bruto)
    if re.search(r"(?i)gasolina a", s):
        return "Gasolina C"
    if re.search(r"(?i)diesel", s):
        for onde in (s, reserva):
            if re.search(r"(?i)s-?500", onde):
                return "Diesel B S500"
            if re.search(r"(?i)s-?10", onde):
                return "Diesel B S10"
        return "Diesel B"
    if re.search(r"(?i)glp", s):
        return "GLP P-13"
    return None


def pagina(url):
    req = urllib.request.Request(url, headers=NAVEGADOR)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "replace")


def baixar(url, destino, tentativas=3):
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=NAVEGADOR)
            with urllib.request.urlopen(req, timeout=120) as r, open(destino, "wb") as f:
                f.write(r.read())
            return True
        except Exception as e:
            ultimo = e
            time.sleep(1.0 * 2 ** i)
    print("  não baixou %s: %s" % (os.path.basename(destino), ultimo), file=sys.stderr)
    return False


def ler_acervo(caminho, cabecalho):
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        linhas = list(csv.reader(f))
    if not linhas or linhas[0] != cabecalho:
        raise SystemExit("%s tem cabeçalho diferente do esperado — apague e refaça"
                         % os.path.relpath(caminho, RAIZ))
    return linhas[1:]


def ler_lista(caminho):
    if not os.path.exists(caminho):
        return set()
    with open(caminho, encoding="utf-8") as f:
        return {l.strip() for l in f if l.strip()}


def gravar_lista(caminho, nomes):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("".join(n + "\n" for n in sorted(nomes)))


def gravar_acervo(caminho, cabecalho, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cabecalho)
        w.writerows(sorted(linhas))


# ------------------------------------------------- semanal (Síntese, só Brasil)
#
# A composição vive num gráfico, não numa tabela: uma barra empilhada por
# produto, com o preço ao consumidor em cima e, ao lado de cada faixa, o valor
# em "R$ x,xx" à esquerda e o nome do item à direita. Não há coordenada fixa
# para apoiar o leitor — em 2024 o painel ficava no pé da página e em 2026 no
# topo, com escalas diferentes. O que vale é a geometria RELATIVA: acha-se a
# coluna de valores (a mais à esquerda que casa "R$" + número), e os rótulos
# são o que está à direita dela, dentro de uma faixa estreita — o suficiente
# para não invadir a coluna de "Maiores variações de preços", que fica bem
# mais longe. Depois é um para um, de cima para baixo; o valor de cima, que
# não tem rótulo, é o preço ao consumidor.

CAB_SEMANAL = ["produto", "semana_fim", "item", "valor", "total", "edicao"]
SEMANA = re.compile(r"Semana de\s*(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})")
NUMERO = re.compile(r"^[\d.]{1,7},\d{2}$")
MOEDA = re.compile(r"^R\$([\d.]{1,7},\d{2})$")
# Vão horizontal que separa um pedaço de texto do seguinte.
VAO = 6
# Altura do painel, a contar do título. Cabem seis faixas com folga.
ALTURA_PAINEL = 125
# Largura da coluna de valores, e até onde vai a de rótulos — as duas medidas
# a partir da esquerda da coluna de valores.
COLUNA_VALOR = 25
COLUNA_ROTULO = 165


def dia(s):
    d, m, a = s.split("/")
    return datetime.date(int(a), int(m), int(d))


def _linhas_de_caracteres(pg, topo, base):
    """{y: [caracteres]} da faixa, um grupo por linha de texto."""
    fora = {}
    for ch in pg.chars:
        if not topo <= ch["top"] < base:
            continue
        k = next((t for t in fora if abs(t - ch["top"]) <= 3), ch["top"])
        fora.setdefault(k, []).append(ch)
    return fora


def _corridas(chars):
    """Os pedaços de uma linha, cortados onde o vão horizontal é grande."""
    chars = sorted(chars, key=lambda ch: ch["x0"])
    fora, atual = [], [chars[0]]
    for ch in chars[1:]:
        if ch["x0"] - atual[-1]["x1"] > VAO:
            fora.append(atual)
            atual = [ch]
        else:
            atual.append(ch)
    fora.append(atual)
    return fora


def _painel(pg, titulo):
    """(total, [(rótulo, valor)]) do painel, ou None se a página não tem um."""
    todos = pg.extract_words()
    # O painel acaba onde começa o título da tabela de capitais, que às vezes
    # cabe dentro da altura padrão — e aí entraria como se fosse um rótulo.
    base = titulo["bottom"] + ALTURA_PAINEL
    for w in todos:
        if w["text"].startswith("Preços") and titulo["bottom"] + 20 < w["top"] < base:
            base = w["top"]
    dentro = sorted((w for w in todos if titulo["bottom"] <= w["top"] < base),
                    key=lambda w: (w["top"], w["x0"]))

    # Os valores saem do PDF de três jeitos diferentes — "R$ 2,06" numa
    # palavra só, em duas ("R$" + "2,06") e, em alguns diesel, caractere por
    # caractere, porque o rótulo do gráfico posiciona cada dígito. Por isso o
    # leitor não usa palavra nenhuma aqui: remonta cada linha a partir dos
    # caracteres, corta onde há vão horizontal e testa cada pedaço contra
    # "R$ x,xx". O vão também é o que separa esta coluna da de capitais.
    achados = []
    for y, chars in _linhas_de_caracteres(pg, titulo["bottom"], base).items():
        for corrida in _corridas(chars):
            moeda = MOEDA.match("".join(c["text"] for c in corrida).replace(" ", ""))
            if moeda:
                achados.append((corrida[0]["x0"], y, moeda.group(1)))
    if not achados:
        return None
    esquerda = min(x for x, _t, _v in achados)
    valores = [v for _x, _t, v in sorted((a for a in achados
                                          if a[0] <= esquerda + COLUNA_VALOR),
                                         key=lambda a: a[1])]

    linhas = {}
    for w in dentro:
        if (w["x0"] < esquerda + COLUNA_VALOR + 5
                or w["x1"] > esquerda + COLUNA_ROTULO
                or w["text"] in ("R$", "|", "Brasil")   # "Brasil" é o subtítulo
                or NUMERO.match(w["text"]) or MOEDA.match(w["text"])):
            continue
        k = next((t for t in linhas if abs(t - w["top"]) <= 4), w["top"])
        linhas.setdefault(k, []).append(w["text"])
    rotulos = [" ".join(linhas[k]) for k in sorted(linhas)]
    if not rotulos or len(valores) != len(rotulos) + 1:
        return None
    num = lambda s: float(s.replace(".", "").replace(",", "."))
    return num(valores[0]), [(rotulos[i], num(valores[i + 1])) for i in range(len(rotulos))]


def ler_sintese(caminho):
    """[(produto, semana_fim, item, valor, total)] de uma edição da Síntese.

    A semana sai do cabeçalho da PRÓPRIA página do painel, não da capa: a
    edição 40/2024 trazia na capa a semana de abril e nas dez páginas de
    dentro a de setembro, e ler a capa datava a edição inteira seis meses
    atrás — em cima de uma semana que já existia."""
    import pdfplumber
    fora = []
    with pdfplumber.open(caminho) as pdf:
        for pg in pdf.pages:
            # O título do painel, e não só a palavra: as edições de 2019 falam
            # de "composição do preço do combustível" no texto corrido e a
            # página de notas explica a conta, nenhuma das duas com painel.
            cabeca = pg.extract_text() or ""
            if "omposição do preço médio de revenda" not in cabeca:
                continue
            semana = SEMANA.search(cabeca.replace("\n", " "))
            if not semana:
                print("  %s pág %d: painel sem semana no cabeçalho"
                      % (os.path.basename(caminho), pg.page_number), file=sys.stderr)
                continue
            fim = dia(semana.group(2))
            titulo = next((w for w in pg.extract_words()
                           if w["text"].startswith("Composi")), None)
            achado = _painel(pg, titulo) if titulo else None
            if not achado:
                continue
            total, itens = achado
            prod = next((p for p in (produto_do_rotulo(r, cabeca[:200])
                                     for r, _ in itens) if p), None)
            if not prod:
                continue
            for rotulo, v in itens:
                fora.append((prod, fim, canonico(rotulo), v, total))
    return fora


def links_sintese(html):
    """{nome: url} das edições. A chave carrega a pasta do ano, e não só o
    nome do arquivo, porque a ANP repete o nome de um ano para o outro:
    'sintese-precos-n24.pdf' existe em 2021, 2024, 2025 e 2026 — chavear pelo
    nome puro juntaria quatro edições numa e deixaria três sem baixar."""
    fora = {}
    for u in re.findall(r'href="([^"]+\.pdf)"', html):
        if "sintese" not in u.lower() and "precos-n" not in u.lower():
            continue
        if u.startswith("/"):
            u = "https://www.gov.br" + u
        if not u.startswith("https://www.gov.br/anp/"):
            continue                              # o anp.gov.br antigo responde 404
        fora.setdefault(nome_de(u, "/arq-sintese-semanal/"), u)
    return fora


def nome_de(url, marco):
    """O trecho da URL depois de `marco`, como nome de arquivo."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", url.split(marco)[-1])


def semanal(atualizar=True):
    """O acervo semanal, atualizado com as edições que ainda não estavam nele."""
    acervo = ler_acervo(ACERVO_SEMANAL, CAB_SEMANAL)
    if atualizar:
        try:
            links = links_sintese(pagina(PAGINA_SINTESE))
        except Exception as e:
            print("  a página da Síntese não respondeu (%s) — fica o acervo" % e,
                  file=sys.stderr)
            links = {}
        vistas = ler_lista(VISTAS_SEMANAL)
        novas = {k: v for k, v in links.items() if k not in vistas}
        if novas:
            print("  %d edições novas da Síntese (%d já vistas)"
                  % (len(novas), len(vistas)))
            pasta = tempfile.mkdtemp(prefix="anp-sintese-")
            try:
                for nome, url in sorted(novas.items()):
                    alvo = os.path.join(pasta, nome)
                    if not baixar(url, alvo):
                        continue
                    lidas = ler_sintese(alvo)
                    for prod, fim, item, v, total in lidas:
                        acervo.append([prod, fim.isoformat(), item,
                                       "%.5g" % v, "%.5g" % total, nome])
                    vistas.add(nome)
                    os.remove(alvo)
            finally:
                shutil.rmtree(pasta, ignore_errors=True)
            gravar_acervo(ACERVO_SEMANAL, CAB_SEMANAL, acervo)
            gravar_lista(VISTAS_SEMANAL, vistas)
    serie, repetidas, divergentes = _sem_repetidas(
        [(p, f, i, float(v), float(t), e) for p, f, i, v, t, e in acervo])
    if repetidas:
        print("  %d semanas vieram em mais de uma edição; ficou uma de cada: %s"
              % (len(repetidas), ", ".join("%s %s" % r for r in repetidas[:4])))
    if divergentes:
        print("  ATENÇÃO: a mesma semana com valores diferentes em duas edições: %s"
              % (divergentes,), file=sys.stderr)
    return serie


def _sem_repetidas(linhas):
    """A ANP republica o mesmo arquivo com outro número de edição — a 02/2026
    está listada também em 2025, e a 21/2026 é uma segunda cópia da 15. Nesses
    casos a semana aparece duas vezes e fica a edição arquivada no ano da
    própria semana, que é a que a ANP lista hoje. Quase sempre as duas trazem
    o mesmo número; na semana de 4 a 10/1/2026 a segunda publicação corrigiu o
    etanol anidro da gasolina de R$ 1,01 para R$ 0,99 (o preço ao consumidor
    não mudou, a diferença foi para a margem). Quando os valores divergem o
    aviso sobe, porque aí não é republicação, é revisão."""
    por_item, repetidas, divergentes = {}, set(), set()
    for l in linhas:
        por_item.setdefault(l[:3], []).append(l)
    for (prod, fim, _item), iguais in por_item.items():
        if len(iguais) > 1:
            repetidas.add((prod, fim))
            if max(i[3] for i in iguais) - min(i[3] for i in iguais) > 0.005:
                divergentes.add((prod, fim))
    escolha = lambda l: (not l[5].startswith(l[1][:4]), l[5])
    return ([min(iguais, key=escolha) for iguais in por_item.values()],
            sorted(repetidas), sorted(divergentes))


# ------------------------------------- mensal por região (planilhas da ANP/MME)

CAB_REGIOES = ["produto", "mes", "semana_ini", "semana_fim", "regiao", "item",
               "valor", "participacao", "unidade", "arquivo"]
MESES = ("janeiro fevereiro março abril maio junho julho agosto setembro "
         "outubro novembro dezembro").split()
DATA_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
# Em agosto/2020 a ANP publicou o arquivo de setembro com o cabeçalho de
# agosto — mesma semana de referência nos dois, valores diferentes. Sem uma
# data confiável, o de setembro fica fora, e o aviso aparece na conferência.
REF_DUPLICADA = re.compile(r"202009-composicao")


def ler_planilha(caminho):
    """[(produto, mês, semana_ini, semana_fim, região, item, valor, part., unidade)]."""
    import openpyxl
    ws = openpyxl.load_workbook(caminho, data_only=True).worksheets[0]
    grade = [list(r) for r in ws.iter_rows(values_only=True)]
    texto = [c.strip() for r in grade for c in r if isinstance(c, str)]

    ih = next((i for i, r in enumerate(grade)
               if any(isinstance(c, str) and c.strip().startswith("Valor") for c in r)), None)
    if ih is None:
        raise ValueError("não achei a linha de cabeçalho")
    ref = " ".join(c for c in grade[ih] if isinstance(c, str) and "Ref" in c)
    datas = DATA_BR.findall(ref)
    if len(datas) != 2:
        raise ValueError("semana de referência ilegível: %r" % ref)
    ini, fim = (datetime.date(int(a), int(m), int(d)) for d, m, a in datas)
    if fim < ini:
        # Fevereiro/2024 saiu com "Ref.: 26/02/2024 a 03/02/2024" — o fim é um
        # erro de digitação. A semana da ANP é sempre de domingo a sábado.
        fim = ini + datetime.timedelta(days=6)
    rotulo = next((t for t in texto
                   if re.match(r"(?i)^(%s)/\d{4}$" % "|".join(MESES), t)), None)
    if not rotulo:
        raise ValueError("não achei o mês de referência")
    nome_mes, ano = rotulo.split("/")
    mes = "%s-%02d" % (ano, MESES.index(nome_mes.lower()) + 1)
    unidade = "R$/13kg" if "13K" in ref.upper() or any(
        isinstance(c, str) and "13K" in c.upper() for c in grade[ih]) else "R$/litro"

    coluna, atual = {}, None
    for j, c in enumerate(grade[ih - 1]):
        if isinstance(c, str) and c.strip() in REGIOES:
            atual = c.strip()
        if atual and isinstance(grade[ih][j], str) and grade[ih][j].strip().startswith("Valor"):
            coluna[atual] = j
    faltam = [r for r in REGIOES if r not in coluna]
    if faltam:
        raise ValueError("faltou a coluna de %s" % ", ".join(faltam))

    produto = PRODUTOS.get(ws.title.strip().upper())
    if not produto:
        raise ValueError("aba de produto desconhecida: %r" % ws.title)

    fora = []
    for linha in grade[ih + 1:]:
        texto_linha = [c for c in linha if isinstance(c, str) and c.strip()]
        if not texto_linha or texto_linha[0].strip().startswith(
                ("Fonte", "(", "Obs", "Nota", "*")):
            continue
        item = canonico(texto_linha[0])
        for regiao, j in coluna.items():
            v = linha[j]
            p = linha[j + 1] if j + 1 < len(linha) else None
            if isinstance(v, (int, float)):
                fora.append((produto, mes, ini, fim, regiao, item, float(v),
                             float(p) if isinstance(p, (int, float)) else None, unidade))
    return fora


def links_cefp(html):
    fora = {}
    for u in re.findall(r'href="(https://www\.gov\.br/anp/[^"]*/cefp/[^"]+\.xlsx?)"', html):
        fora.setdefault(nome_de(u, "/cefp/"), u)    # a pasta do ano entra no nome
    return fora


def por_regiao(atualizar=True):
    """O acervo mensal por região, atualizado com os arquivos que faltavam."""
    acervo = ler_acervo(ACERVO_REGIOES, CAB_REGIOES)
    if atualizar:
        try:
            links = links_cefp(pagina(PAGINA_CEFP))
        except Exception as e:
            print("  a página de composição não respondeu (%s) — fica o acervo" % e,
                  file=sys.stderr)
            links = {}
        tem = {l[9] for l in acervo}
        novas = {k: v for k, v in links.items()
                 if k not in tem and not REF_DUPLICADA.search(k)}
        if novas:
            print("  %d planilhas novas de composição (acervo tem %d)"
                  % (len(novas), len(tem)))
            pasta = tempfile.mkdtemp(prefix="anp-cefp-")
            try:
                for nome, url in sorted(novas.items()):
                    alvo = os.path.join(pasta, nome)
                    if not baixar(url, alvo):
                        continue
                    try:
                        lidas = ler_planilha(alvo)
                    except Exception as e:
                        print("  %s: %s" % (nome, e), file=sys.stderr)
                        continue
                    for prod, mes, ini, fim, reg, item, v, p, un in lidas:
                        acervo.append([prod, mes, ini.isoformat(), fim.isoformat(), reg,
                                       item, "%.6g" % v,
                                       "" if p is None else "%.6g" % p, un, nome])
                    os.remove(alvo)
            finally:
                shutil.rmtree(pasta, ignore_errors=True)
            gravar_acervo(ACERVO_REGIOES, CAB_REGIOES, acervo)
    fora = []
    for prod, mes, ini, fim, reg, item, v, p, un, arq in acervo:
        fora.append((prod, mes, ini, fim, reg, item, float(v),
                     float(p) if p else None, un, arq))
    return fora


# ---------------------------------------------------------------- conferência

def conferir(sem, reg):
    """As duas contas que têm de fechar, e o que elas dizem quando não fecham."""
    problemas = []

    # 1. Os componentes somam o preço ao consumidor? É a identidade da conta:
    #    a margem é resíduo, então o resto só pode fechar.
    for nome, grupos in (("semanal", _agrupar(sem, lambda l: (l[0], l[1]))),
                         ("regiões", _agrupar(reg, lambda l: (l[0], l[3], l[4])))):
        fora = 0
        for chave, itens in grupos.items():
            total = itens.get(TOTAL)
            soma = sum(v for i, v in itens.items() if i != TOTAL)
            if total and abs(soma - total) > max(0.03, 0.005 * total):
                fora += 1
                if fora <= 3:
                    problemas.append("  %s: %s soma %.2f mas o preço é %.2f"
                                     % (nome, chave, soma, total))
        print("  %s: %d grupos, %d fora da soma" % (nome, len(grupos), fora))

    # 2. Cada edição da Síntese traz um painel por produto. Semana com menos
    #    produto que a maioria é edição que o leitor não leu inteira.
    produtos = {}
    for p, fim, _i, _v, _t, _e in sem:
        produtos.setdefault(fim, set()).add(p)
    if produtos:
        normal = max(len(v) for v in produtos.values())
        curtas = sorted(k for k, v in produtos.items() if len(v) < normal)
        if curtas:
            problemas.append("  semanas com menos de %d produtos: %s"
                             % (normal, curtas[:6]))

    # 3. Algum rótulo novo que o canônico não reconheceu?
    novos = sorted({l[2] for l in sem if l[2].startswith("?")}
                   | {l[5] for l in reg if l[5].startswith("?")})
    if novos:
        problemas.append("  rótulos não reconhecidos: %s" % novos[:8])
    return problemas


def _agrupar(linhas, chave):
    fora = {}
    for l in linhas:
        item, valor = (l[2], l[3]) if len(l) == 6 else (l[5], l[6])
        fora.setdefault(chave(l), {})[item] = valor
    return fora


def main():
    print("Composição semanal (Síntese, Brasil)…")
    sem = semanal()
    print("Composição mensal por região…")
    reg = por_regiao()
    for nome, linhas, i_prod, i_sem in (("semanal", sem, 0, 1), ("regiões", reg, 0, 3)):
        por_prod = {}
        for l in linhas:
            a = por_prod.setdefault(l[i_prod], [l[i_sem], l[i_sem], 0])
            a[0], a[1] = min(a[0], l[i_sem]), max(a[1], l[i_sem])
            a[2] += 1
        print(" %s:" % nome)
        for p, (d0, d1, n) in sorted(por_prod.items()):
            print("   %-14s %5d linhas, de %s a %s" % (p, n, d0, d1))
    for p in conferir(sem, reg):
        print(p, file=sys.stderr)


if __name__ == "__main__":
    if "--testar" in sys.argv:
        main()
    else:
        raise SystemExit(__doc__.strip().splitlines()[0])

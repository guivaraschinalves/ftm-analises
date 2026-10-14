#!/usr/bin/env python3
"""
Preço de bomba de etanol hidratado e gasolina C, e a regra dos 70%.

Módulo compartilhado por precos_combustiveis.py e defasagem.py. Não roda
sozinho (mas `python scripts/precos_revenda.py` imprime um resumo, para
conferir).

DE ONDE VEM

Do Levantamento de Preços da ANP, a pesquisa semanal em postos revendedores.
É dado POR POSTO: cada linha é uma coleta, com UF, município, produto, data e
o valor de venda ao consumidor. A ANP publica em zips semestrais desde 2004.
Aqui eles são baixados uma vez, agregados em médias semanais e guardados num
CSV pequeno — os zips somam centenas de MB e não ficam no repositório.

A média é simples, não ponderada: a ANP não publica o volume vendido por
posto, então não há como ponderar. Isso significa que um município com muitos
postos pesa mais do que o seu consumo justificaria.

QUAL PRODUTO

  - "GASOLINA" na pesquisa é a gasolina C comum, que é o que sai da bomba.
    "GASOLINA ADITIVADA" é outro produto e fica de fora, senão a comparação
    pega um preço que o motorista do carro flex não usa de referência.
  - "ETANOL" é o hidratado, o que se abastece puro.

A REGRA DOS 70%

Regra de bolso do motorista de carro flex: o etanol compensa quando custa até
70% do preço da gasolina, porque rende menos por litro. A planilha traz a
razão e duas leituras dela:

  - **regra dos 70%**: o limiar fixo, do jeito que se usa no dia a dia.
  - **limiar técnico**: o mesmo cálculo levando em conta que a gasolina C não
    é gasolina pura — ela já tem etanol anidro dentro, e quanto mais tem,
    menos energia entrega por litro, o que EMPURRA o limiar para cima. Com
    27% de anidro dá cerca de 76%; com os 32% de agosto de 2026, cerca de
    77%. Ou seja: a regra dos 70% é conservadora, e ficou mais conservadora
    ainda depois do E30 e do E32.

O limiar técnico supõe que o etanol hidratado entrega 70% da energia da
gasolina A por litro. É a razão usualmente citada; quem preferir outra troca
a constante ENERGIA_ETANOL.
"""
import csv
import datetime
import io
import os
import sys
import zipfile

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DADOS = os.path.join(RAIZ, "dados")
CACHE = os.path.join(DADOS, ".cache-anp-revenda")
AGREGADO = os.path.join(CACHE, "revenda-semanal.csv")

# O nome do arquivo muda ao longo da série: .csv até 2021, .zip de 2022 em
# diante, e o 1º semestre de 2022 tem nome próprio.
BASE = ("https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/"
        "arquivos/shpc/dsas/ca/%s")


def nomes_possiveis(ano, semestre):
    if (ano, semestre) == (2022, 1):
        return ["precos-semestrais-ca.zip"]
    return ["ca-%d-%02d.zip" % (ano, semestre), "ca-%d-%02d.csv" % (ano, semestre)]
PRIMEIRO_ANO = 2004
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                           " (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}

# O semestre corrente só vira arquivo fechado depois que acaba. Até lá o que
# existe são os arquivos mensais e o das últimas quatro semanas — com nomes
# que a ANP troca de um mês para outro, daí a lista de tentativas.
MENSAL = ("https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/"
          "arquivos/shpc/dsan/%d/%s")
PADROES_MENSAIS = (
    "%(m)s-dados-abertos-precos-%(a)d-%(m)s-gasolina-etanol.csv",
    "%(m)s-dados-abertos-precos-gasolina-etanol.csv",
    "precos-gasolina-etanol-%(m)s.csv",
)
ULTIMAS_4 = ("https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/"
             "arquivos/shpc/qus/ultimas-4-semanas-gasolina-etanol.csv")

ENERGIA_ETANOL = 0.70        # energia do hidratado por litro, ante a gasolina A
REGRA_DE_OURO = 0.70         # o limiar fixo da regra de bolso
PRODUTOS = {"GASOLINA": "gasolina", "ETANOL": "etanol"}
# A região sai da UF, não da coluna "Regiao - Sigla" do arquivo: o cabeçalho
# vem com BOM e, lido em latin-1, o nome daquela coluna chega corrompido. Além
# disso a sigla "SE" é ambígua — é Sudeste na coluna de região e Sergipe na de
# estado. Derivar da UF evita os dois problemas.
REGIAO_DA_UF = {}
for _reg, _ufs in (("Norte", "AC AM AP PA RO RR TO"),
                   ("Nordeste", "AL BA CE MA PB PE PI RN SE"),
                   ("Centro-Oeste", "DF GO MS MT"),
                   ("Sudeste", "ES MG RJ SP"),
                   ("Sul", "PR RS SC")):
    for _uf in _ufs.split():
        REGIAO_DA_UF[_uf] = _reg


def sabado(data):
    """A data de coleta cai no sábado que fecha a semana, que é a convenção
    que as outras planilhas do repositório já usam para "semana".

    Devolve None para o que não é data: o arquivo das últimas semanas traz
    algumas linhas com os campos deslocados, e um CEP cai nesta coluna."""
    try:
        d = datetime.date(int(data[6:10]), int(data[3:5]), int(data[0:2]))
    except (ValueError, TypeError):
        return None
    return (d + datetime.timedelta(days=(5 - d.weekday()) % 7)).isoformat()


def baixar(ano, semestre):
    import urllib.request
    os.makedirs(CACHE, exist_ok=True)
    for nome in nomes_possiveis(ano, semestre):
        alvo = os.path.join(CACHE, "%d-%02d%s" % (ano, semestre,
                                                  os.path.splitext(nome)[1]))
        if os.path.exists(alvo) and os.path.getsize(alvo) > 100000:
            return alvo
        try:
            req = urllib.request.Request(BASE % nome, headers=NAVEGADOR)
            with urllib.request.urlopen(req, timeout=600) as r:
                conteudo = r.read()
        except Exception:
            continue
        if len(conteudo) < 100000:
            continue
        with open(alvo, "wb") as f:
            f.write(conteudo)
        return alvo
    return None


def registros(arq):
    """As linhas de um semestre, venha ele zipado ou não."""
    if arq.endswith(".zip"):
        z = zipfile.ZipFile(arq)
        with z.open(z.namelist()[0]) as fh:
            for r in csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1",
                                                     newline=""), delimiter=";"):
                yield r
        z.close()
    else:
        with open(arq, encoding="latin-1", newline="") as fh:
            for r in csv.DictReader(fh, delimiter=";"):
                yield r


def baixar_recentes(ano):
    """Mensais do ano mais o arquivo das últimas quatro semanas."""
    import urllib.request
    os.makedirs(CACHE, exist_ok=True)
    fora = []
    for mes in range(1, 13):
        alvo = os.path.join(CACHE, "mensal-%d-%02d.csv" % (ano, mes))
        if os.path.exists(alvo) and os.path.getsize(alvo) > 100000:
            fora.append(alvo)
            continue
        for padrao in PADROES_MENSAIS:
            url = MENSAL % (ano, padrao % {"a": ano, "m": "%02d" % mes})
            try:
                req = urllib.request.Request(url, headers=NAVEGADOR)
                with urllib.request.urlopen(req, timeout=300) as r:
                    conteudo = r.read()
            except Exception:
                continue
            if len(conteudo) < 100000:
                continue
            with open(alvo, "wb") as f:
                f.write(conteudo)
            fora.append(alvo)
            break
    alvo = os.path.join(CACHE, "ultimas-4-semanas.csv")
    try:
        req = urllib.request.Request(ULTIMAS_4, headers=NAVEGADOR)
        with urllib.request.urlopen(req, timeout=300) as r:
            conteudo = r.read()
        if len(conteudo) > 100000:
            with open(alvo, "wb") as f:
                f.write(conteudo)
            fora.append(alvo)
    except Exception:
        pass
    return fora


def agregar(forcar=False):
    """Média semanal do preço de venda, por UF, por região e para o Brasil.

    Guarda o resultado em CSV: reprocessar os zips leva minutos, ler o CSV
    leva um instante."""
    if os.path.exists(AGREGADO) and not forcar:
        return ler_agregado()
    soma = {}
    hoje = datetime.date.today()
    for ano in range(PRIMEIRO_ANO, hoje.year + 1):
        for semestre in (1, 2):
            arq = baixar(ano, semestre)
            if not arq:
                continue
            print("  lendo %s…" % os.path.basename(arq))
            for r in registros(arq):
                p = PRODUTOS.get((r.get("Produto") or "").strip().upper())
                if not p:
                    continue
                try:
                    v = float((r.get("Valor de Venda") or "").replace(",", "."))
                except (ValueError, AttributeError):
                    continue
                if v <= 0:
                    continue
                data = r.get("Data da Coleta") or ""
                if len(data) < 10:
                    continue
                sem = sabado(data)
                if not sem:
                    continue
                uf = (r.get("Estado - Sigla") or "").strip().upper()
                reg = REGIAO_DA_UF.get(uf)
                if not reg:
                    continue
                for ambito in ("Brasil", reg, uf):
                    a = soma.setdefault((sem, ambito, p), [0.0, 0])
                    a[0] += v
                    a[1] += 1
    # O semestral é a fonte boa; mensais e últimas-4-semanas entram só para as
    # semanas que ele ainda não cobre, e entre si são deduplicados por coleta
    # (data + posto + produto), porque uma semana pode cair em dois meses.
    cobertas = {sem for (sem, _, _) in soma}
    cru = {}
    for arq in baixar_recentes(hoje.year):
        print("  lendo %s…" % os.path.basename(arq))
        for r in registros(arq):
            p = PRODUTOS.get((r.get("Produto") or "").strip().upper())
            if not p:
                continue
            sem = sabado(r.get("Data da Coleta") or "")
            if not sem or sem in cobertas:
                continue
            try:
                v = float((r.get("Valor de Venda") or "").replace(",", "."))
            except (ValueError, AttributeError):
                continue
            if v <= 0:
                continue
            uf = (r.get("Estado - Sigla") or "").strip().upper()
            reg = REGIAO_DA_UF.get(uf)
            if not reg:
                continue
            cru[(r.get("Data da Coleta"),
                 (r.get("CNPJ da Revenda") or "").strip(), p)] = (v, uf, reg, sem)
    for (_, _, p), (v, uf, reg, sem) in cru.items():
        for ambito in ("Brasil", reg, uf):
            a = soma.setdefault((sem, ambito, p), [0.0, 0])
            a[0] += v
            a[1] += 1

    os.makedirs(CACHE, exist_ok=True)
    with open(AGREGADO, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["semana", "ambito", "produto", "preco_medio", "coletas"])
        for (sem, amb, p), (s, n) in sorted(soma.items()):
            w.writerow([sem, amb, p, "%.4f" % (s / n), n])
    print("  gravado %s" % os.path.relpath(AGREGADO, RAIZ))
    return ler_agregado()


def ler_agregado():
    fora = {}
    with open(AGREGADO, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            fora[(r["semana"], r["ambito"], r["produto"])] = (
                float(r["preco_medio"]), int(r["coletas"]))
    return fora


def limiar_tecnico(teor_anidro):
    """Até quanto do preço da gasolina C o etanol pode custar e ainda compensar.

    A gasolina C tem `teor_anidro` de etanol dentro, então entrega
    (1 − 0,30·teor) da energia da gasolina A por litro. O limiar é a energia
    do hidratado dividida por essa."""
    if teor_anidro is None:
        return None
    return ENERGIA_ETANOL / (1 - (1 - ENERGIA_ETANOL) * teor_anidro)


def teor_padrao(mes):
    """O percentual obrigatório de anidro naquele mês. Vem do calendário que
    oferta_gasolina.py já mantém (cronologia do MAPA + resoluções do CNPE),
    para não existir a mesma tabela em dois lugares."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import oferta_gasolina
    return oferta_gasolina.teor_do_mes(mes)


def serie(teor_do_mes=teor_padrao):
    """[semana, âmbito, etanol, gasolina, razão, limiar técnico, compensa?]."""
    dados = agregar()
    chaves = {(s, a) for (s, a, _) in dados}
    fora = []
    for sem, amb in sorted(chaves):
        e = dados.get((sem, amb, "etanol"))
        g = dados.get((sem, amb, "gasolina"))
        if not e or not g or not g[0]:
            continue
        razao = 100.0 * e[0] / g[0]
        teor = teor_do_mes(sem[:7]) if teor_do_mes else None
        lim = limiar_tecnico(teor)
        fora.append([sem, amb, e[0], g[0], razao,
                     100.0 * REGRA_DE_OURO,
                     (100.0 * lim) if lim else None,
                     "sim" if razao <= 100.0 * REGRA_DE_OURO else "não",
                     ("sim" if razao <= 100.0 * lim else "não") if lim else None,
                     min(e[1], g[1])])
    return fora


CABECALHO = ["semana", "âmbito", "etanol R$/l", "gasolina R$/l", "razão %",
             "regra dos 70%", "limiar técnico %", "compensa (regra)",
             "compensa (técnico)", "coletas"]


if __name__ == "__main__":
    linhas = serie()
    br = [l for l in linhas if l[1] == "Brasil"]
    print("%d semanas, de %s a %s\n" % (len(br), br[0][0], br[-1][0]))
    print("%-12s %8s %9s %8s %9s %10s" % ("semana", "etanol", "gasolina",
                                          "razão", "regra 70%", "técnico"))
    for l in br[::52] + [br[-1]]:
        print("%-12s %8.3f %9.3f %7.1f%% %9s %10s"
              % (l[0], l[2], l[3], l[4], l[7], l[8]))

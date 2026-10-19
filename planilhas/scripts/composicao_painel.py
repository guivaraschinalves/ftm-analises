#!/usr/bin/env python3
"""
A composição do preço SEMANAL e POR REGIÃO, do painel da ANP.

Uso:
    ~/.venvs/dados-economicos/bin/python scripts/composicao_painel.py

POR QUE ESTE SCRIPT EXISTE

  A ANP publica a composição do preço em três lugares, e os três são
  diferentes:

    1. Síntese Semanal (PDF)       semanal, só Brasil          → composicao_anp.py
    2. Planilhas "cefp" (xlsx)     mensal, Brasil e regiões    → composicao_anp.py
    3. Painel Power BI             SEMANAL e por região        → este arquivo

  O 2 é a única fonte em arquivo com corte regional, e está parada em março de
  2026. O 3 tem a mesma conta, semanal, por região, desde 2021, e continua
  saindo — mas só existe dentro de um painel.

  https://app.powerbi.com/view?r=eyJrIjoiZTgwYzBlOTgtMjU5YS00OGRjLWEzYjUtMDY2OTBjYjhmZDc5IiwidCI6IjVlMzk3OGI5LTQ5NTAtNDM3Yy04N2I2LTQ5MmYxMjY4ZGVjOCJ9

COMO ELE PEGA

  O painel busca os números numa API pública da Power BI, e a requisição que
  ele faz pode ser repetida. O molde dela está em dados/, capturado uma vez
  com o navegador; aqui só se troca o filtro de PRODUTO e de LOCAL e se
  derruba o filtro de ano, que no painel limita a 2026.

  A resposta vem num formato comprimido da Power BI, o DSR, que o
  dsr_powerbi.py desfaz.

O QUE ELE NÃO É

  Não é para rodar toda semana. É extração única, de tudo que existe até
  hoje, e o resultado fica versionado em dados/. Painel não é contrato: se a
  ANP mexer nele, isto quebra — e quebra em silêncio, o que é o motivo de o
  resultado ficar guardado em CSV em vez de ser buscado na hora.
"""
import csv
import datetime
import gzip
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsr_powerbi                                            # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DADOS = os.path.join(RAIZ, "dados")
MOLDE = os.path.join(DADOS, "painel-composicao-molde.json")
SAIDA = os.path.join(DADOS, "anp-composicao-painel.csv")

PRODUTOS = ["DIESEL S10", "DIESEL S500", "GASOLINA", "GLP"]
LOCAIS = ["BRASIL", "CENTRO-OESTE", "NORDESTE", "NORTE", "SUDESTE", "SUL"]
ANOS = range(2021, datetime.date.today().year + 1)
MESES = ("janeiro fevereiro março abril maio junho julho agosto setembro "
         "outubro novembro dezembro").split()
CABECALHO = ["produto", "local", "data", "parcela", "valor"]


def valores_de(condicao):
    """Os literais de uma condição In, para trocá-los."""
    alvo = condicao["Condition"]
    if "Not" in alvo:
        alvo = alvo["Not"]["Expression"]
    return alvo["In"]["Values"]


def corpo_para(molde, produto, local, ano):
    """O corpo da requisição com os filtros deste produto, local e ano.

    UM ANO POR VEZ, de propósito. A resposta é truncada em 200 pontos: pedir
    a série inteira devolve 2021 a 2024 e perde o resto sem avisar. Ano a ano
    cabe com folga (são ~52 semanas) e dispensa paginação."""
    b = json.loads(json.dumps(molde["body"]))     # cópia funda
    cmd = b["queries"][0]["Query"]["Commands"][0]["SemanticQueryDataShapeCommand"]
    onde = cmd["Query"]["Where"]
    for cond in onde:
        texto = json.dumps(cond, ensure_ascii=False)
        if '"PRODUTO"' in texto:
            valores_de(cond)[:] = [[{"Literal": {"Value": "'%s'" % produto}}]]
        elif '"LOCAL"' in texto:
            valores_de(cond)[:] = [[{"Literal": {"Value": "'%s'" % local}}]]
        elif '"Ano"' in texto:
            # no painel esta condição é um "Not In" que exclui tudo menos
            # 2026; vira um "In" com o ano que se quer
            alvo = cond["Condition"].pop("Not")["Expression"]
            alvo["In"]["Values"][:] = [[{"Literal": {"Value": "%dL" % ano}}]]
            cond["Condition"]["In"] = alvo["In"]
    return json.dumps(b, ensure_ascii=False).encode()


def buscar(molde, produto, local, ano):
    req = urllib.request.Request(
        molde["url"], data=corpo_para(molde, produto, local, ano), method="POST",
        headers=dict(molde["headers"], **{
            "Origin": "https://app.powerbi.com",
            "Accept-Encoding": "gzip",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"}))
    with urllib.request.urlopen(req, timeout=180) as r:
        bruto = r.read()
    if bruto[:2] == b"\x1f\x8b":
        bruto = gzip.decompress(bruto)
    return json.loads(bruto)


def linhas_de(resposta, produto, local):
    ds = resposta["results"][0]["result"]["data"]["dsr"]["DS"][0]
    parcelas = ds.get("ValueDicts", {}).get("D0", [])
    fora = []
    for ext, internos in dsr_powerbi.tabela(ds):
        ano, mes, dia = ext.get("G0"), ext.get("G1"), ext.get("G2")
        if not (ano and mes and dia):
            continue
        data = datetime.date(int(ano), MESES.index(mes) + 1, int(dia))
        for parcela, interno in zip(parcelas, internos):
            v = interno.get("M1")
            if v in (None, ""):
                continue
            fora.append([produto, local, data.isoformat(), parcela,
                         "%.6g" % float(v)])
    return fora


def main():
    if not os.path.exists(MOLDE):
        raise SystemExit("falta o molde da requisição em %s" % MOLDE)
    molde = json.load(open(MOLDE, encoding="utf-8"))
    tudo = []
    for produto in PRODUTOS:
        for local in LOCAIS:
            linhas = []
            for ano in ANOS:
                try:
                    linhas += linhas_de(buscar(molde, produto, local, ano),
                                        produto, local)
                except Exception as e:
                    print("  %-12s %-13s %d falhou: %s" % (produto, local, ano, e),
                          file=sys.stderr)
            datas = sorted({l[2] for l in linhas})
            print("  %-12s %-13s %5d linhas, %3d semanas, de %s a %s"
                  % (produto, local, len(linhas), len(datas),
                     datas[0] if datas else "—", datas[-1] if datas else "—"))
            tudo += linhas
    if not tudo:
        raise SystemExit("nada veio — o painel deve ter mudado")
    tudo.sort(key=lambda l: (l[0], l[1], l[2], l[3]))
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CABECALHO)
        w.writerows(tudo)
    print("\ngravado %s (%d linhas)" % (os.path.relpath(SAIDA, RAIZ), len(tudo)))


if __name__ == "__main__":
    main()

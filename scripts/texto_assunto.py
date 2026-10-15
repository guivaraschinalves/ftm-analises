#!/usr/bin/env python3
"""
Lê o texto de um assunto de um arquivo em textos/, para que mudar uma palavra
não exija mexer em código.

O FORMATO, que é de propósito pobre

    # Título do assunto

    ## Título da seção
    chave: gasolina-probabilidade
    fonte: ANP, produção e vendas | https://...
    figura: abicom-tabela | assets/x.png | legenda | crédito | https://...

    Primeiro parágrafo, com **negrito** quando precisar.

    Segundo parágrafo.

    [figura:abicom-tabela]

Regras, todas elas:

  - `#` abre o assunto, `##` abre uma seção. Um `##` sem texto depois é uma
    seção SEM título, que é legítima: a primeira costuma continuar o título do
    assunto, e repetir cabeçalho ali só empurra o texto para baixo.
  - Linha que começa em `chave:`, `fonte:` ou `figura:` é metadado, em
    qualquer lugar da seção, e não entra na prosa. O resto é prosa.
  - Linha em branco separa parágrafo. `**assim**` fica em negrito. Nada mais:
    não é Markdown de verdade, e é melhor assim, porque o que o site aceita é
    exatamente isto.
  - `chave:` liga a seção aos gráficos que o gerador monta para ela. Sem
    chave, a seção não recebe gráfico nenhum.
  - Um parágrafo que seja só `[figura:id]` vira a imagem declarada na seção.

O QUE ESTE MÓDULO NÃO FAZ

  Não valida se a figura referida existe, nem se a chave casa com algum
  gráfico. Quem monta o JSON é que sabe disso, e é lá que o erro aparece.
"""
import io
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTOS = os.path.join(RAIZ, "textos")

METADADO = re.compile(r"^(chave|fonte|figura):\s*(.*)$")


def partes(linha):
    return [p.strip() for p in linha.split("|")]


def ler(nome):
    """{assunto, secoes: [{chave, titulo, texto, fontes, figuras}]}."""
    caminho = nome if os.path.sep in nome else os.path.join(TEXTOS, nome)
    with io.open(caminho, encoding="utf-8") as f:
        linhas = f.read().split("\n")

    doc = {"assunto": "", "secoes": []}
    atual = None
    for n, linha in enumerate(linhas, 1):
        if linha.startswith("# "):
            doc["assunto"] = linha[2:].strip()
            continue
        if linha.startswith("##"):
            atual = {"chave": "", "titulo": linha[2:].strip(),
                     "linhas": [], "fontes": [], "figuras": []}
            doc["secoes"].append(atual)
            continue
        if atual is None:
            if linha.strip():
                raise SystemExit("%s linha %d: texto antes da primeira seção"
                                 % (caminho, n))
            continue

        m = METADADO.match(linha)
        if not m:
            atual["linhas"].append(linha)
            continue
        tipo, resto = m.group(1), m.group(2)
        if tipo == "chave":
            atual["chave"] = resto.strip()
        elif tipo == "fonte":
            p = partes(resto)
            atual["fontes"].append(
                {"rot": p[0], "url": p[1]} if len(p) > 1 and p[1] else {"rot": p[0]})
        else:
            p = partes(resto)
            if len(p) < 3:
                raise SystemExit("%s linha %d: figura precisa de pelo menos "
                                 "id, arquivo e legenda" % (caminho, n))
            fig = {"id": p[0], "arquivo": p[1], "legenda": p[2]}
            if len(p) > 3 and p[3]:
                fig["fonte"] = p[3]
            if len(p) > 4 and p[4]:
                fig["url"] = p[4]
            atual["figuras"].append(fig)

    for sec in doc["secoes"]:
        # junta as linhas e colapsa as sobras de linha em branco que os
        # metadados deixaram para trás
        texto = "\n".join(sec.pop("linhas")).strip()
        sec["texto"] = re.sub(r"\n{3,}", "\n\n", texto)
    return doc

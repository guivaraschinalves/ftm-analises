#!/usr/bin/env python3
"""Monta dados/leituras-de-ciclo.json: as leituras de ciclo da Missão Global
Miami (o ciclo brasileiro e o americano, tudo o que vem antes da parte "Alta
de juros no mundo"), no estilo da Missão. Pedido dele em 24/11/2026, para ir
ao ftm.app.br/interno/analises, de onde a Missão inteira fica de fora.

Não refaz nenhum gráfico: recorta dados/missao-global-miami.json na ordem em
que a página da Missão mostra (dados/ordens/missao-global-miami.json, com a
mesma regra do app para gráfico novo que o arquivo não cita). As divisórias de
parte ficam nas vagas, como no app. Roda sozinho no fim do missao_miami.py.

    python3 scripts/leituras_ciclo.py
"""
import json
import os

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MISSAO = os.path.join(RAIZ, "dados", "missao-global-miami.json")
ORDEM = os.path.join(RAIZ, "dados", "ordens", "missao-global-miami.json")
SAIDA = os.path.join(RAIZ, "dados", "leituras-de-ciclo.json")
ATE_A_PARTE = "Alta de juros no mundo"      # a primeira parte que fica de fora


def ordem_da_pagina(original):
    """A mesma conta do completar() do app.js (ligarReordenar)."""
    try:
        with open(ORDEM, encoding="utf-8") as f:
            lista = json.load(f).get("ordem") or []
    except FileNotFoundError:
        lista = []
    fora = [x for i, x in enumerate(lista) if x in original and lista.index(x) == i]
    for k, x in enumerate(original):
        if x in fora:
            continue
        j = k - 1
        while j >= 0 and original[j] not in fora:
            j -= 1
        fora.insert(0 if j < 0 else fora.index(original[j]) + 1, x)
    return fora


def main():
    with open(MISSAO, encoding="utf-8") as f:
        m = json.load(f)
    secoes = m["secoes"]
    if any(len(s.get("graficos") or []) != 1 for s in secoes):
        raise SystemExit("a Missão mudou de formato: seção sem um gráfico só")
    original = [s["graficos"][0]["id"] for s in secoes]
    partes = {i: s["parte"] for i, s in enumerate(secoes) if s.get("parte")}
    fim = next((i for i, p in partes.items() if p == ATE_A_PARTE), None)
    if fim is None:
        raise SystemExit("a Missão não tem mais a parte %r" % ATE_A_PARTE)
    por_id = {s["graficos"][0]["id"]: s for s in secoes}
    mostrada = ordem_da_pagina(original)
    novas = []
    for i, gid in enumerate(mostrada[:fim]):
        s = {k: v for k, v in por_id[gid].items() if k != "parte"}
        if i in partes:
            s["parte"] = partes[i]
        novas.append(s)
    doc = {k: v for k, v in m.items() if k not in ("secoes", "reordenar", "assunto")}
    doc["assunto"] = "Leituras de ciclo"
    doc["secoes"] = novas
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado %s: %d gráficos (%s a %s), partes %s (%.0f KB)"
          % (SAIDA, len(novas), mostrada[0], mostrada[fim - 1],
             [p for i, p in sorted(partes.items()) if i < fim], os.path.getsize(SAIDA) / 1024))


if __name__ == "__main__":
    main()

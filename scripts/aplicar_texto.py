#!/usr/bin/env python3
"""
Costura a prosa de textos/*.md no JSON que já existe em dados/, sem recalcular
nada.

Uso:
    python3 scripts/aplicar_texto.py

É o que a Action roda. A diferença para o defasagem_combustiveis.py é o que
ela NÃO faz: não abre planilha, não baixa PDF da Petrobras, não consulta o
SIDRA, não precisa do cache da ANP. Roda em segundos, com a biblioteca padrão,
e por isso uma correção de vírgula nunca falha porque a ANP está fora do ar.

Os gráficos ficam como estão. Quem os atualiza é o gerador completo, rodado à
mão quando os números mudam.

O QUE ACONTECE SE AS SEÇÕES NÃO BATEREM

  O casamento é pelo TÍTULO, e a seção sem título casa pela posição. Se você
  renomear uma seção no .md, ela deixa de encontrar os gráficos dela e o
  script avisa em vez de publicar uma seção vazia. Acrescentar seção nova, ou
  reordenar, funciona: a sem gráfico nenhum simplesmente não tem com que
  casar.
"""
import io
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import texto_assunto as ta                                    # noqa: E402

PARES = [("defasagem-combustiveis.md", "defasagem-combustiveis.json"),
         ("petroleo.md", "petroleo.json"),
         ("cenario-2026-10-28-fomc.md", "cenario-2026-10-28-fomc.json")]


def aplicar(nome_texto, nome_json):
    caminho = os.path.join(RAIZ, "dados", nome_json)
    with io.open(caminho, encoding="utf-8") as f:
        doc = json.load(f)
    dt = ta.ler(nome_texto)

    # os gráficos de antes, para reencontrá-los depois do texto novo
    antigos, por_posicao = {}, {}
    for i, s in enumerate(doc["secoes"]):
        por_posicao[i] = s.get("graficos", [])
        if s.get("titulo"):
            antigos[s["titulo"]] = s.get("graficos", [])

    perdidos, novas = [], []
    for i, sec in enumerate(dt["secoes"]):
        if sec["titulo"]:
            graficos = antigos.pop(sec["titulo"], None)
            if graficos is None:
                graficos = []
                novas.append(sec["titulo"])
        else:
            graficos = por_posicao.get(i, [])
        sec_nova = {"titulo": sec["titulo"], "texto": sec["texto"],
                    "fontes": sec["fontes"], "figuras": sec["figuras"],
                    "graficos": graficos}
        if i < len(doc["secoes"]):
            doc["secoes"][i] = sec_nova
        else:
            doc["secoes"].append(sec_nova)
    del doc["secoes"][len(dt["secoes"]):]

    perdidos = [t for t, g in antigos.items() if g]
    doc["assunto"] = dt["assunto"]

    with io.open(caminho, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    print("%s → %s" % (nome_texto, nome_json))
    print("  %d seções, %d gráficos preservados, %d figuras"
          % (len(doc["secoes"]),
             sum(len(s["graficos"]) for s in doc["secoes"]),
             sum(len(s.get("figuras", [])) for s in doc["secoes"])))
    if novas:
        print("  seção nova, ainda sem gráfico: %s" % "; ".join(novas))
    if perdidos:
        print("  AVISO: estes gráficos ficaram órfãos porque a seção mudou de "
              "nome: %s. Rode o gerador completo." % "; ".join(perdidos),
              file=sys.stderr)
        return 1
    return 0


def main():
    erros = sum(aplicar(t, j) for t, j in PARES)
    raise SystemExit(1 if erros else 0)


if __name__ == "__main__":
    main()

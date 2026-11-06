#!/usr/bin/env python3
"""
Exporta uma análise do site para um arquivo de texto (Markdown) que dá para
mandar a outra pessoa ou colar numa IA: o texto de cada seção, os números de
cada gráfico em tabela e as fontes com link, numeradas.

    python3 scripts/exportar_md.py dados/ueno-bank.json saida.md

As séries mensais saem trimestrais (março, junho, setembro, dezembro), mais o
primeiro e o último mês, para a tabela caber; a página tem a série inteira.

Só biblioteca padrão.
"""
import json
import re
import sys

MESES = "jan fev mar abr mai jun jul ago set out nov dez".split()


def fmt_num(v, casas):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt(v, unidade):
    if v is None:
        return ""
    if unidade.startswith("pct"):
        return fmt_num(v, 1) + "%"
    if unidade == "gs-tri":
        return "₲ " + fmt_num(v, 2) + " tri"
    if abs(v) >= 1000 or float(v).is_integer():
        return fmt_num(v, 0)
    return fmt_num(v, 1)


def mes(m):
    return f"{MESES[int(m[5:7]) - 1]}/{m[:4]}" if re.fullmatch(r"\d{4}-\d{2}", m) else m


def tabela(grafico, var):
    unidade = var.get("unidade") or grafico.get("unidade", "")
    series = var["series"]
    linhas = []
    if grafico.get("categorias"):
        cats = grafico["categorias"]
        cab = ["Categoria"] + [s["nome"] for s in series]
        dic = [dict(s["dados"]) for s in series]
        for i, c in enumerate(cats):
            linhas.append([c] + [fmt(d.get(str(i)), unidade) for d in dic])
    else:
        todos = sorted({x for s in series for x, _ in s["dados"]})
        escolhidos = [m for m in todos if m in (todos[0], todos[-1]) or m[5:7] in ("03", "06", "09", "12")]
        cab = ["Mês"] + [s["nome"] for s in series]
        dic = [dict(s["dados"]) for s in series]
        for m in escolhidos:
            linhas.append([mes(m)] + [fmt(d.get(m), unidade) for d in dic])
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    out += ["| " + " | ".join(l) + " |" for l in linhas]
    return "\n".join(out)


def main():
    entrada, saida = sys.argv[1], sys.argv[2]
    d = json.load(open(entrada, encoding="utf-8"))
    refs, numero = [], {}

    def citar(m):
        trecho, fid = m.group(1), m.group(2)
        if fid not in numero:
            f = fontes_secao.get(fid, {"rot": fid})
            refs.append(f)
            numero[fid] = len(refs)
        return f"{trecho} [{numero[fid]}]"

    a = d["atualizado"]
    partes = [f"# {d['assunto']}", "",
              f"Follow the Money, Análises. Atualizado em {a[8:10]}/{a[5:7]}/{a[:4]}"
              + (f"; dados até {mes(d['referencia'])}." if d.get("referencia") else "."),
              "",
              "Este arquivo reúne o texto da análise, os números de cada gráfico em tabela e as fontes. "
              "As séries mensais aparecem trimestrais, mais o primeiro e o último mês.", ""]
    for s in d["secoes"]:
        fontes_secao = {f["id"]: f for f in s.get("fontes", [])}
        partes += [f"## {s['titulo']}", ""]
        if s.get("texto"):
            partes += [re.sub(r"\[([^\]]+)\]\(fonte:([^)]+)\)", citar, s["texto"]), ""]
        for g in s.get("graficos", []):
            partes += [f"### Gráfico: {g['titulo']}", ""]
            if g.get("subtitulo"):
                partes += [g["subtitulo"] + ".", ""]
            for v in g.get("variantes", [g]):
                if "variantes" in g:
                    partes += [f"**{v['rot']}**", ""]
                partes += [tabela(g, v), ""]
            if g.get("fonte"):
                partes += [f"Fonte: {g['fonte']}.", ""]
    partes += ["## Fontes e notas", ""]
    for i, f in enumerate(refs, 1):
        partes.append(f"{i}. {f['rot']}" + (f": {f['url']}" if f.get("url") else ""))
    open(saida, "w", encoding="utf-8").write("\n".join(partes) + "\n")
    print(f"gravado {saida}: {len(d['secoes'])} seções, {len(refs)} fontes")


if __name__ == "__main__":
    main()

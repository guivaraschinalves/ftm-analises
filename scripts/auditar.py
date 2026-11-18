#!/usr/bin/env python3
"""Auditor automático para os sites FtM Dados e FtM Análises (só biblioteca padrão).

Modos de uso:
  1. Auditoria estrutural e de regras FtM em um JSON de tema:
       python3 scripts/auditar.py dados/pib.json
       python3 scripts/auditar.py dados/pib.json --estrito

  2. Auditoria ponto a ponto de uma série contra um CSV da fonte:
       python3 scripts/auditar.py dados/pib.json pib-familias-4tri "PIB" fonte.csv data valor [tolerancia]

Regras verificadas:
  - JSON sem NaN/Infinity e valores numéricos válidos em todas as séries.
  - Nenhum travessão (—) em textos visíveis (títulos, subtítulos, notas, séries).
  - Ordem cronológica/numérica das chaves em cada série.
  - Paleta para daltonismo: no máximo 7 cores cromáticas, pares proibidos e
    ΔE (OKLab * 100) >= 8 sob protanopia e deuteranopia para cores fora da paleta oficial.
  - Comparação exata contra CSV de origem dentro da tolerância (padrão 0,005).
"""
import argparse
import csv
import json
import math
import re
import sys

PALETA_OFICIAL = {
    "#4F81BD",  # azul
    "#C0504D",  # vermelho
    "#9BBB59",  # verde
    "#1F497D",  # azul-escuro
    "#8EB4E3",  # azul-claro
    "#632523",  # vinho
    "#FFFF00",  # amarelo
}
NEUTRAS = {"#8A8A86", "#FFFFFF", "#000000"}
PARES_PROIBIDOS = [
    ("#F79646", "#9BBB59", "laranja #F79646 x verde #9BBB59"),
]
RE_CHAVE_DATA = re.compile(r"^(\d{4})(?:-Q([1-4])|-(\d{2})(?:-(\d{2}))?)?$")

# Matrizes Machado et al. (2009) em RGB linear para dicromacia severidade 1.0.
MAT_PROTANOPIA = (
    (0.152286, 1.052583, -0.204868),
    (0.114503, 0.786281, 0.099216),
    (-0.003882, -0.048116, 1.051998),
)
MAT_DEUTERANOPIA = (
    (0.367322, 0.860646, -0.227968),
    (0.280085, 0.672501, 0.047413),
    (-0.011820, 0.042940, 0.968881),
)


def norm_hex(cor):
    """Normaliza código hex #RGB ou #RRGGBB para #RRGGBB maiúsculo."""
    if not isinstance(cor, str):
        return None
    c = cor.strip().upper()
    if re.fullmatch(r"#[0-9A-F]{3}", c):
        return "#" + "".join(ch * 2 for ch in c[1:])
    if re.fullmatch(r"#[0-9A-F]{6}", c):
        return c
    return None


def _srgb_para_linear(u):
    return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4


def _cbrt(x):
    return math.copysign(abs(x) ** (1.0 / 3.0), x)


def _hex_para_linear(hex_cor):
    r = _srgb_para_linear(int(hex_cor[1:3], 16) / 255.0)
    g = _srgb_para_linear(int(hex_cor[3:5], 16) / 255.0)
    b = _srgb_para_linear(int(hex_cor[5:7], 16) / 255.0)
    return (r, g, b)


def _simular_cvd(rgb_lin, matriz):
    r, g, b = rgb_lin
    out = []
    for row in matriz:
        v = row[0] * r + row[1] * g + row[2] * b
        out.append(max(0.0, min(1.0, v)))
    return tuple(out)


def _linear_para_oklab(rgb_lin):
    r, g, b = rgb_lin
    l = _cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = _cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = _cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    b_ok = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return (L, a, b_ok)


def delta_e_oklab_cvd(hex1, hex2):
    """Retorna o menor ΔE (OKLab * 100) entre duas cores sob protanopia e deuteranopia."""
    rgb1 = _hex_para_linear(hex1)
    rgb2 = _hex_para_linear(hex2)
    pior = float("inf")
    for mat in (MAT_PROTANOPIA, MAT_DEUTERANOPIA):
        lab1 = _linear_para_oklab(_simular_cvd(rgb1, mat))
        lab2 = _linear_para_oklab(_simular_cvd(rgb2, mat))
        de = math.sqrt(sum((u - v) ** 2 for u, v in zip(lab1, lab2))) * 100.0
        if de < pior:
            pior = de
    return pior


def carregar_json_estrito(caminho):
    """Carrega JSON recusando NaN, Infinity e -Infinity."""
    def _rejeitar(const):
        raise ValueError(f"constante JSON inválida encontrada: {const}")

    with open(caminho, encoding="utf-8") as f:
        return json.load(f, parse_constant=_rejeitar)


def chave_ordenavel(chave):
    """Gera tupla comparável para datas ISO/trimestres ou índices numéricos."""
    s = str(chave)
    if s.isdigit():
        return (0, int(s), 0, 0, "")
    m = RE_CHAVE_DATA.match(s)
    if m:
        ano = int(m.group(1))
        tri = int(m.group(2)) if m.group(2) else 0
        mes = int(m.group(3)) if m.group(3) else 0
        dia = int(m.group(4)) if m.group(4) else 0
        return (1, ano, tri, mes, dia, "")
    return None


def _checar_travessao(texto, contexto, erros):
    if isinstance(texto, str) and "—" in texto:
        erros.append(f"{contexto}: contém travessão '—' proibido em texto visível")


def _checar_cores(series, contexto, erros, avisos):
    cores_vistas = []
    cromaticas = set()
    for s in series:
        cor = norm_hex(s.get("cor"))
        if not cor:
            continue
        if cor not in cores_vistas:
            cores_vistas.append(cor)
        if cor not in NEUTRAS:
            cromaticas.add(cor)

    if len(cromaticas) > 7:
        erros.append(f"{contexto}: {len(cromaticas)} séries coloridas (máximo 7; restante deve usar #8a8a86)")

    conjunto = set(cores_vistas)
    for c1, c2, desc in PARES_PROIBIDOS:
        if c1 in conjunto and c2 in conjunto:
            erros.append(f"{contexto}: par de cores proibido para daltonismo ({desc})")

    for i in range(len(cores_vistas)):
        for j in range(i + 1, len(cores_vistas)):
            c1, c2 = cores_vistas[i], cores_vistas[j]
            if c1 in NEUTRAS or c2 in NEUTRAS:
                continue
            if c1 in PALETA_OFICIAL and c2 in PALETA_OFICIAL:
                continue
            de = delta_e_oklab_cvd(c1, c2)
            if de < 8.0:
                avisos.append(
                    f"{contexto}: cores {c1} e {c2} fora da paleta oficial com ΔE={de:.1f} (< 8) sob daltonismo"
                )


def _checar_serie_dados(s, contexto, erros):
    dados = s.get("dados")
    if dados is None:
        return
    if not isinstance(dados, list):
        erros.append(f"{contexto}: 'dados' não é uma lista")
        return

    chaves_ord = []
    todos_ord = True
    for idx, ponto in enumerate(dados):
        if not isinstance(ponto, list) or len(ponto) < 2:
            erros.append(f"{contexto}: ponto #{idx} inválido (esperado [chave, valor])")
            continue
        chave, valor = ponto[0], ponto[1]
        if valor is not None:
            if not isinstance(valor, (int, float)) or isinstance(valor, bool):
                erros.append(f"{contexto} [{chave}]: valor não numérico ({valor!r})")
            elif not math.isfinite(valor):
                erros.append(f"{contexto} [{chave}]: valor não finito ({valor!r})")
        k = chave_ordenavel(chave)
        if k is None:
            todos_ord = False
        else:
            chaves_ord.append((k, str(chave)))

    if todos_ord and len(chaves_ord) > 1:
        esperado = sorted(chaves_ord, key=lambda item: item[0])
        if [c for _, c in chaves_ord] != [c for _, c in esperado]:
            erros.append(f"{contexto}: ordem das chaves não é cronológica/numérica")


def auditar_grafico(g, prefixo, erros, avisos):
    """Audita regras estruturais, de texto, de ordem e de cor em um gráfico."""
    gid = g.get("id", "<sem-id>")
    ctx = f"{prefixo}/{gid}"
    for campo in ("titulo", "subtitulo", "nota", "comentario"):
        _checar_travessao(g.get(campo), f"{ctx}.{campo}", erros)

    conjuntos = []
    if g.get("series"):
        conjuntos.append((ctx, g["series"]))
    for v in g.get("variantes", []):
        rot = v.get("rot", "variante")
        _checar_travessao(rot, f"{ctx}[{rot}].rot", erros)
        if v.get("series"):
            conjuntos.append((f"{ctx}[{rot}]", v["series"]))

    for subctx, series in conjuntos:
        _checar_cores(series, subctx, erros, avisos)
        for s in series:
            nome = s.get("nome", "<sem-nome>")
            _checar_travessao(nome, f"{subctx}/{nome}.nome", erros)
            _checar_serie_dados(s, f"{subctx}/{nome}", erros)


def auditar_documento(doc, caminho):
    """Executa auditoria completa em todas as seções e gráficos do JSON."""
    erros, avisos = [], []
    if not isinstance(doc, dict) or "secoes" not in doc:
        erros.append(f"{caminho}: documento sem chave 'secoes'")
        return erros, avisos

    total_graficos = 0
    for sec in doc.get("secoes", []):
        titulo_sec = sec.get("titulo", "<sem-titulo>")
        _checar_travessao(titulo_sec, f"secao[{titulo_sec}].titulo", erros)
        for g in sec.get("graficos", []):
            total_graficos += 1
            auditar_grafico(g, titulo_sec, erros, avisos)

    return erros, avisos, total_graficos


def _carregar_csv_fonte(caminho, col_chave, col_valor):
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        amostra = f.read(4096)
        f.seek(0)
        try:
            dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t")
        except csv.Error:
            dialeto = csv.excel
        leitor = csv.DictReader(f, dialect=dialeto)
        if not leitor.fieldnames or col_chave not in leitor.fieldnames or col_valor not in leitor.fieldnames:
            raise ValueError(
                f"colunas '{col_chave}' e '{col_valor}' não encontradas em {caminho} (encontradas: {leitor.fieldnames})"
            )
        origem = {}
        for row in leitor:
            bruto = (row[col_valor] or "").strip().replace(",", ".")
            if bruto == "":
                continue
            origem[row[col_chave].strip()] = float(bruto)
    return origem


def auditar_csv(doc, gid, nome_serie, fonte_csv, col_chave, col_valor, tol):
    """Compara uma série específica de um gráfico contra um CSV de referência."""
    graficos = [g for s in doc.get("secoes", []) for g in s.get("graficos", [])]
    g = next((item for item in graficos if item.get("id") == gid), None)
    if g is None:
        raise ValueError(f"gráfico '{gid}' não encontrado")

    erros, avisos = [], []
    auditar_grafico(g, "grafico", erros, avisos)

    series = list(g.get("series") or [])
    for v in g.get("variantes", []):
        series.extend(v.get("series") or [])
    s = next((item for item in series if item.get("nome") == nome_serie), None)
    if s is None:
        raise ValueError(f"série '{nome_serie}' não encontrada em '{gid}'")

    desenho = {str(k): v for k, v in s.get("dados", [])}
    if "categorias" in g:
        cats = g["categorias"]
        desenho = {str(cats[int(k)]): v for k, v in desenho.items()}

    origem = _carregar_csv_fonte(fonte_csv, col_chave, col_valor)
    for k, v in desenho.items():
        if k not in origem:
            erros.append(f"{k}: está no gráfico e não na fonte")
        elif v is None:
            erros.append(f"{k}: valor nulo no gráfico × fonte {origem[k]}")
        elif abs(v - origem[k]) > tol:
            erros.append(f"{k}: gráfico {v} × fonte {origem[k]} (dif. {v - origem[k]:+.4f})")

    faltam = sorted(set(origem) - set(desenho))
    if faltam:
        avisos.append(
            f"{len(faltam)} ponto(s) da fonte fora do gráfico (ex.: {faltam[:3]}); ok se houver recorte de período"
        )

    return len(desenho), erros, avisos


def main():
    parser = argparse.ArgumentParser(description="Auditor automático FtM Dados / FtM Análises")
    parser.add_argument("json_path", help="Caminho para dados/<tema>.json")
    parser.add_argument("restante", nargs="*", help="[grafico_id nome_serie fonte.csv col_chave col_valor [tolerancia]]")
    parser.add_argument("--estrito", action="store_true", help="Trata avisos (incluindo ΔE < 8) como erro")
    args = parser.parse_args()

    try:
        doc = carregar_json_estrito(args.json_path)
    except Exception as exc:
        print(f"ERRO ao ler {args.json_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    if not args.restante:
        res = auditar_documento(doc, args.json_path)
        if len(res) == 2:
            erros, avisos = res
            total = 0
        else:
            erros, avisos, total = res
        if args.estrito and avisos:
            erros.extend(avisos)
            avisos = []
        print(f"{args.json_path}: {total} gráfico(s) auditado(s), {len(erros)} erro(s), {len(avisos)} aviso(s)")
        for a in avisos[:20]:
            print("  AVISO:", a)
        for e in erros[:20]:
            print("  ERRO:", e)
        sys.exit(1 if erros else 0)

    if len(args.restante) not in (5, 6):
        parser.error("Modo CSV exige: <grafico_id> <nome_serie> <fonte.csv> <col_chave> <col_valor> [tolerancia]")

    gid, nome, fonte, col_chave, col_valor = args.restante[:5]
    tol = float(args.restante[5]) if len(args.restante) == 6 else 0.005
    try:
        n_pontos, erros, avisos = auditar_csv(doc, gid, nome, fonte, col_chave, col_valor, tol)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.estrito and avisos:
        erros.extend(avisos)
        avisos = []
    print(f"{gid} / {nome}: {n_pontos} ponto(s) conferido(s), {len(erros)} problema(s), {len(avisos)} aviso(s)")
    for a in avisos[:20]:
        print("  AVISO:", a)
    for e in erros[:20]:
        print("  ERRO:", e)
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()

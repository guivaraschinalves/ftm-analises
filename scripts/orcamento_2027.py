#!/usr/bin/env python3
"""
Monta dados/orcamento-2027.json — o assunto "Promessas de gasto e o resultado
primário de 2027".

Uso:
    python3 scripts/orcamento_2027.py

Não baixa nada: os números são transcritos de documentos em PDF, e cada bloco
abaixo diz de onde veio. A prosa mora em textos/orcamento-2027.md.

FONTES

  - Relatório de Avaliação de Receitas e Despesas Primárias (RARDP) do 4º
    bimestre de 2026, apresentação de 24/9/2026 (MPO): resultado de 2026.
  - Informativo conjunto das consultorias de orçamento da Câmara e do Senado
    sobre o PLOA 2027 (setembro de 2026): resultado e despesa por grupo, 2025
    a 2027 (o 2026 ali é a reprogramação do 3º bimestre).
  - IFI, RAF nº 118 (19/11/2026): medidas anunciadas depois do PLOA (Tabela 1),
    discricionárias não rígidas por cenário (Gráfico 1), cenários de resultado
    (Gráfico 2), subvenções aos combustíveis (Gráfico 5 e texto).
  - IFI, RAF nº 116 e nº 117; Decreto nº 13.120/2026; CNN Brasil (19/9/2026)
    para custos de 2026 informados pelo governo.

O QUE CONFERE

  As somas que a fonte também publica: grupos de despesa contra o total do
  PLOA, subtotais da Tabela 1 da IFI e os cenários contra o ponto de partida.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texto_assunto as ta                                    # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "dados", "orcamento-2027.json")
ARQUIVO_TEXTO = "orcamento-2027.md"

# Paleta validada para daltonismo (a do crédito no ftm-dados): pior par 14,9.
AZUL, VERMELHO, VERDE = "#4F81BD", "#C0504D", "#9BBB59"
AZUL_ESCURO, AZUL_CLARO, VINHO, CINZA = "#1F497D", "#8EB4E3", "#632523", "#8a8a86"

FONTE = "PLOA 2027, MPO (RARDP), IFI e FtM"
FONTE_IFI = "IFI (RAF nº 118, 19/11/2026) e FtM"


def conferir(cond, msg):
    if not cond:
        raise SystemExit("conferência falhou: " + msg)


def por_indice(vals):
    """Série em eixo de categorias: chave é o índice da categoria."""
    return [[str(i), v] for i, v in enumerate(vals) if v is not None]


def serie(nome, cor, vals, **extra):
    d = {"nome": nome, "cor": cor, "dados": por_indice(vals)}
    d.update(extra)
    return d


# ---------------------------------------------------------------------------
# 1. Resultado primário: efetivo, para fins de meta, centro e piso da meta
# ---------------------------------------------------------------------------
# 2025: realizado (informativo do PLOA): −61,7 + 3,0 de discrepância = −58,7;
#       dedução 48,7; meta zero, piso −0,25% do PIB (R$ 30,97 bi, LDO 2025).
# 2026: RARDP do 4º bimestre: −80,9 efetivo e −13,6 para fins de meta antes do
#       contingenciamento de 13,6, que leva o resultado para fins de meta ao
#       piso (zero) e o efetivo a −67,3.
# 2027: PLOA: 18,6 efetivo, dedução 64,7, 83,4 para fins de meta; meta 73,2,
#       piso 36,6.
RESULTADO = [
    # rótulo, efetivo, para fins de meta, centro, piso
    ("2025", -58.7, -10.0, 0.0, -31.0),
    ("2026 (projeção)", -67.3, 0.0, 34.3, 0.0),
    ("2027 (PLOA)", 18.6, 83.4, 73.2, 36.6),
]


def grafico_resultado():
    conferir(abs(18.6 + 64.7 - 83.4) < 0.15, "PLOA: efetivo + dedução != meta")
    conferir(abs(-80.9 + 67.3 - (-13.6)) < 0.15, "RARDP 4º bim: efetivo + dedução")
    cats = [r[0] for r in RESULTADO]
    return {
        "id": "orc27-resultado",
        "titulo": "Resultado primário do governo central: efetivo e para fins de meta",
        "subtitulo": "R$ bilhões; 2026 pelo relatório do 4º bimestre, já com o contingenciamento",
        "unidade": "bi",
        "fonte": FONTE,
        "categorias": cats,
        "agrupadas": True,
        "valores": True,
        "series": [
            serie("Resultado efetivo", AZUL_ESCURO, [r[1] for r in RESULTADO], tipo="barra"),
            serie("Para fins de meta", AZUL_CLARO, [r[2] for r in RESULTADO], tipo="barra"),
            serie("Centro da meta", VERMELHO, [r[3] for r in RESULTADO], tipo="barra"),
            serie("Limite inferior da meta", CINZA, [r[4] for r in RESULTADO], tipo="barra"),
        ],
    }


# ---------------------------------------------------------------------------
# 2. Despesa primária por grupo (informativo do PLOA, tabela do item 3)
# ---------------------------------------------------------------------------
GRUPOS = [
    ("Benefícios previdenciários", AZUL_ESCURO, [1026.9, 1133.0, 1215.1]),
    ("Pessoal e encargos", AZUL, [402.6, 449.9, 474.1]),
    ("Outras obrigatórias", AZUL_CLARO, [390.6, 455.4, 477.8]),
    ("Obrigatórias com controle de fluxo", VINHO, [369.4, 381.0, 396.3]),
    ("Emendas impositivas", VERMELHO, [34.3, 37.8, 44.8]),
    ("Discricionárias do Executivo", VERDE, [170.6, 188.5, 222.1]),
]
TOTAL_DESPESA = [2394.2, 2645.6, 2830.1]


def grafico_despesa():
    cats = ["2025", "2026 (projeção)", "2027 (PLOA)"]
    for k in range(3):
        soma = sum(g[2][k] for g in GRUPOS)
        conferir(abs(soma - TOTAL_DESPESA[k]) < 0.25, "grupos de despesa %s: %.1f != %.1f"
                 % (cats[k], soma, TOTAL_DESPESA[k]))
    pct = [[g[2][k] / TOTAL_DESPESA[k] * 100 for k in range(3)] for g in GRUPOS]
    obrig = [sum(pct[i][k] for i in range(4)) for k in range(3)]
    print("  obrigatórias (sem emendas): %s" % ", ".join("%.1f%%" % v for v in obrig))
    return {
        "id": "orc27-despesa",
        "titulo": "Despesa primária do governo central por grupo",
        "subtitulo": "R$ bilhões; 2026 pela reprogramação do 3º bimestre",
        "unidade": "bi",
        "fonte": "Consultorias de Orçamento da Câmara e do Senado (Informativo do PLOA 2027) e FtM",
        "categorias": cats,
        "variantes": [
            {"rot": "R$ bilhões", "unidade": "bi",
             "series": [serie(n, c, v, tipo="barra") for n, c, v in GRUPOS]},
            {"rot": "% do total", "unidade": "pct1", "subtitulo": "% da despesa primária; 2026 pela reprogramação do 3º bimestre",
             "series": [serie(g[0], g[1], [round(x, 2) for x in pct[i]], tipo="barra") for i, g in enumerate(GRUPOS)]},
        ],
    }


# ---------------------------------------------------------------------------
# 3. O cronograma: tabela das medidas e o efeito em 2027
# ---------------------------------------------------------------------------
# Tabela 1 do RAF nº 118 (medidas depois do PLOA) e notas dela (já no PLOA:
# Pé-de-Meia R$ 10,5 bi, Gás do Povo R$ 7,0 bi); subvenções: seção do RAF nº
# 118; Bolsa Família em 2026: governo, via CNN (19/9/2026); Gás do Povo e Luz
# do Povo em 2026: MME e BTG, via CNN; Anexo V: informativo do PLOA.
DEPOIS_DO_PLOA = [
    # nome curto, despesa 2027, perda de receita 2027
    ("Bolsa Família (15,04%)", 22.7, None),
    ("Desenrola 3.0", 5.0, None),
    ("Pé-de-Meia no ensino médio todo", 5.0, None),
    ("Pé-de-Meia universitário", 4.6, None),
    ("Canetas emagrecedoras no SUS", 1.5, None),
    ("Pix MEI", 1.3, None),
    ("Fim das bets", None, 5.3),
    ("Perdão de dívidas de MEIs", None, 1.1),
]

# trocar a cada novo RAF da IFI ou mensagem modificativa do PLOA (versão de 24/11/2026)
COLUNAS = [
    {"rot": "Medida"}, {"rot": "Início"}, {"rot": "2026", "num": True}, {"rot": "2027", "num": True},
    {"rot": "Tratamento fiscal"}, {"rot": "No PLOA 2027"},
]
PRIM = "Primária: ocupa o limite e conta na meta"
MEDIDAS = [
    ["Isenção do IR até R$ 5 mil", "jan/2026", "", "", "Renúncia compensada pelo imposto mínimo", "Sim"],
    ["Gás do Povo", "fev/2026", "5,1", "7,0", PRIM, "Sim"],
    ["Subvenções a diesel, gasolina, GLP e etanol", "mar/2026", "53,9 a 69,8 (20,5 pagos)",
     "Até 45,0 + 10,5 por mês", "Crédito extraordinário: fora do limite, conta na meta", "Não"],
    ["Luz do Povo", "2026", "4,3", "", "Conta de luz (CDE): fora do orçamento", "Não se aplica"],
    ["Desenrola 3.0 (MP 1.393)", "set/2026", "", "5,0 (teto 15,0)", "Primária ou financeira, a definir", "Não"],
    ["Reajuste de 15,04% do Bolsa Família", "out/2026", "5,8", "22,7", "Obrigatória: ocupa o limite e conta na meta", "Não"],
    ["Perdão de dívidas de MEIs (LC 238)", "out/2026", "", "−1,1", "Renúncia: conta na meta", "Não"],
    ["Fim das bets", "2027", "", "−5,3", "Perda de receita: conta na meta", "Não"],
    ["Salário mínimo de R$ 1.741", "jan/2027", "", "", "Obrigatória (benefícios indexados)", "Sim"],
    ["Reajustes e contratações de servidores", "2027", "", "15,4", "Obrigatória (pessoal)", "Sim"],
    ["Pé-de-Meia (programa atual)", "2024", "", "10,5", PRIM, "Sim"],
    ["Pé-de-Meia no ensino médio público todo", "mar/2027", "", "5,0", PRIM, "Não"],
    ["Pé-de-Meia universitário", "2027, sem data", "", "4,6", PRIM, "Não"],
    ["Canetas emagrecedoras no SUS", "2027", "", "1,5", PRIM, "Não"],
    ["Pix MEI", "2027", "", "1,3", "Despesa ou renúncia, a definir", "Não"],
    ["Tarifa zero no transporte nos fins de semana", "Depende de PEC", "", "12,0 de emendas",
     "Remanejamento de emendas: não soma despesa", "Não"],
]


def graficos_medidas():
    desp = sum(d for _, d, _ in DEPOIS_DO_PLOA if d)
    rec = sum(r for _, _, r in DEPOIS_DO_PLOA if r)
    conferir(abs(desp - 40.1) < 0.05 and abs(rec - 6.4) < 0.05,
             "Tabela 1 da IFI: despesa %.1f (40,1) e receita %.1f (6,4)" % (desp, rec))
    tabela = {
        "id": "orc27-cronograma",
        "tipo": "tabela",
        "titulo": "Medidas de gasto e receita anunciadas em 2026: início, custo e tratamento fiscal",
        "subtitulo": "R$ bilhões; em ordem de início; receita perdida com sinal negativo",
        "fonte": "IFI (RAF nº 118), Informativo do PLOA 2027, Decreto nº 13.120/2026, MME, BTG via CNN Brasil e FtM",
        "colunas": COLUNAS,
        "linhas": MEDIDAS,
    }
    barras = {
        "id": "orc27-medidas-2027",
        "titulo": "Medidas anunciadas depois do PLOA 2027: efeito em 2027",
        "subtitulo": "R$ bilhões; despesa nova e receita perdida",
        "unidade": "bi",
        "fonte": FONTE_IFI,
        "categorias": [m[0] for m in DEPOIS_DO_PLOA],
        "series": [
            serie("Despesa nova", AZUL, [m[1] for m in DEPOIS_DO_PLOA], tipo="barra", valores=True),
            serie("Receita perdida", VERMELHO, [m[2] for m in DEPOIS_DO_PLOA], tipo="barra", valores=True),
        ],
    }
    return tabela, barras


# ---------------------------------------------------------------------------
# 4. Discricionárias não rígidas por cenário (Gráfico 1 do RAF nº 118)
# ---------------------------------------------------------------------------
def grafico_discricionarias():
    cats = ["PLOA", "Medidas, R$ 20 bi remanejados de fora",
            "Medidas, corte só nas discricionárias", "Remanejamento e contingenciamento do PLP"]
    conferir(138 - 20.1 - 118 < 0.2 and 138 - 40.1 - 98 < 0.2, "cenários de discricionárias")
    return {
        "id": "orc27-discricionarias",
        "titulo": "Despesas discricionárias não rígidas em 2027 por cenário",
        "subtitulo": "R$ bilhões; no último cenário, 100 a 105 conforme o contingenciamento",
        "unidade": "bi",
        "fonte": FONTE_IFI,
        "categorias": cats,
        "series": [
            serie("Discricionárias não rígidas", AZUL, [138, 118, 98, 100], tipo="barra", valores=True,
                  rotulos={"3": "100 a 105"}),
            serie("Mínimo para funcionamento (0,7% do PIB)", VERMELHO, [103.5] * 4, largura=3, traco="pontilhado"),
        ],
    }


# ---------------------------------------------------------------------------
# 5. Resultado para fins de meta em 2027 por cenário (Gráfico 2 do RAF nº 118)
# ---------------------------------------------------------------------------
CENARIOS = [
    # rótulo, antes do PLP, com o ganho não condicionado do PLP (+19,5)
    ("PLOA", 83.4, None),
    ("Com as medidas anunciadas", 77.0, 96.5),
    ("+ Imposto Seletivo sem janeiro", 72.8, 92.3),
    ("+ CBS pela regra legal", 67.6, 87.1),
    ("+ MP do Imposto Seletivo não convertida", 30.2, 49.7),
    ("+ CBS sem ganho de conformidade", 26.2, 45.7),
]


def grafico_cenarios():
    conferir(abs(83.4 - 6.4 - 77.0) < 0.05, "cenário A")
    for rot, a, b in CENARIOS[1:]:
        conferir(abs(b - a - 19.5) < 0.05, "ganho do PLP em %s" % rot)
    n = len(CENARIOS)
    return {
        "id": "orc27-cenarios",
        "titulo": "Resultado primário para fins de meta em 2027 por cenário",
        "subtitulo": "R$ bilhões; cada risco somado isoladamente às medidas anunciadas",
        "unidade": "bi",
        "fonte": FONTE_IFI,
        "categorias": [c[0] for c in CENARIOS],
        "agrupadas": True,
        "valores": True,
        "series": [
            serie("Antes do PLP 299", AZUL_ESCURO, [c[1] for c in CENARIOS], tipo="barra"),
            serie("Com o ganho não condicionado do PLP (R$ 19,5 bi)", AZUL_CLARO, [c[2] for c in CENARIOS],
                  tipo="barra"),
            serie("Centro da meta", VERMELHO, [73.2] * n, largura=3),
            serie("Limite inferior da meta", CINZA, [36.6] * n, largura=3, traco="pontilhado"),
        ],
    }


# ---------------------------------------------------------------------------
# 6. Subvenções aos combustíveis: estoque devido e não pago (Gráfico 5)
# ---------------------------------------------------------------------------
ESTOQUE = [("2026-06", 7.9), ("2026-07", 15.1), ("2026-08", 20.7), ("2026-09", 21.4), ("2026-10", 29.2)]


def grafico_diesel():
    return {
        "id": "orc27-subvencoes",
        "titulo": "Subvenções aos combustíveis: estoque devido e não pago no fim do mês",
        "subtitulo": "R$ bilhões; vendas a partir de junho de 2026, fator de elegibilidade de 0,93",
        "unidade": "bi",
        "fonte": FONTE_IFI,
        "series": [{"nome": "Estoque não pago", "cor": VERMELHO, "tipo": "barra", "valores": True,
                    "dados": [[m, v] for m, v in ESTOQUE]}],
    }


GRAFICOS = {
    "resultado": lambda: [grafico_resultado()],
    "despesa": lambda: [grafico_despesa()],
    "cronograma": lambda: [graficos_medidas()[0]],
    "medidas-2027": lambda: [graficos_medidas()[1]],
    "discricionarias": lambda: [grafico_discricionarias()],
    "cenarios": lambda: [grafico_cenarios()],
    "diesel": lambda: [grafico_diesel()],
}


def main():
    dt = ta.ler(ARQUIVO_TEXTO)
    secoes = []
    for sec in dt["secoes"]:
        g = GRAFICOS.get(sec["chave"])
        if sec["chave"] and not g:
            raise SystemExit("chave sem gráfico: %s" % sec["chave"])
        s = {"titulo": sec["titulo"], "texto": sec["texto"], "fontes": sec["fontes"],
             "figuras": sec["figuras"], "graficos": g() if g else []}
        if sec.get("parte"):
            s["parte"] = sec["parte"]
        secoes.append(s)
    doc = {
        "atualizado": datetime.date.today().isoformat(),
        "referencia": "2026-11-19",
        "fonte": FONTE,
        "assunto": dt["assunto"],
        "grupo": "Análises Variadas",
        "formato": "artigo",
        "secoes": secoes,
    }
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print("escrito: %s (%d seções, %d gráficos)" % (SAIDA, len(secoes), sum(len(s["graficos"]) for s in secoes)))


if __name__ == "__main__":
    main()

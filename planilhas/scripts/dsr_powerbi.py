"""Decodifica o formato DSR da Power BI.

As linhas vêm comprimidas de três jeitos, e é preciso desfazer os três:

  S  o esquema das colunas. Vem UMA vez e vale para as linhas seguintes até
     outro S aparecer — inclusive para os blocos aninhados, que só declaram o
     esquema na primeira linha externa.
  R  máscara de bits: bit i ligado = a coluna i repete o valor da linha
     anterior, e por isso não vem em C.
  Ø  máscara de bits: bit i ligado = a coluna i é nula.

C traz, em ordem, só os valores que sobraram depois dessas duas máscaras.
"""


class Estado:
    """Esquema e última linha, que persistem entre as linhas de um nível."""

    def __init__(self, dicts):
        self.dicts = dicts
        self.esquema = []
        self.anterior = {}

    def linha(self, bruta):
        if "S" in bruta:
            self.esquema = bruta["S"]
        r, nulo = bruta.get("R", 0), bruta.get("Ø", 0)
        valores, c = {}, list(bruta.get("C", []))
        for i, col in enumerate(self.esquema):
            nome = col["N"]
            if nome in bruta:
                # a linha pode trazer o valor direto, com o nome da coluna
                # como chave, em vez de empilhado em C
                v = bruta[nome]
                dn = col.get("DN")
                if dn and isinstance(v, int) and dn in self.dicts:
                    v = self.dicts[dn][v]
            elif nulo & (1 << i):
                v = None
            elif r & (1 << i):
                v = self.anterior.get(nome)
            else:
                v = c.pop(0) if c else None
                dn = col.get("DN")
                if dn and isinstance(v, int) and dn in self.dicts:
                    v = self.dicts[dn][v]
            valores[nome] = v
            self.anterior[nome] = v
        return valores


def tabela(ds):
    """[(dict externo, [dict interno…])] de um DS da resposta."""
    dicts = ds.get("ValueDicts", {})
    fora = []
    for ph in ds.get("PH", []):
        externo, interno = Estado(dicts), Estado(dicts)
        for bruta in (ph.get("DM0") or ph.get("DM1") or []):
            ext = externo.linha(bruta)
            ints = [interno.linha(b) for b in (bruta.get("X") or [])]
            fora.append((ext, ints))
    return fora

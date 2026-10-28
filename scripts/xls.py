"""
Leitor mínimo de .xls (Excel 97-2003, BIFF8), só com a biblioteca padrão.

Existe porque algumas tabelas especiais do BC só saem em .xls (a DivExt_T,
por exemplo) e o runner não tem xlrd. Lê o texto e os números das células;
fórmula vale pelo último resultado gravado. Não lê formatação nem datas.

    from xls import abas
    planilhas = abas(conteudo)            # {nome da aba: {(linha, coluna): valor}}
"""
import struct

FIM_DE_CADEIA = 0xFFFFFFFE


def _fluxo(dados, nome="Workbook"):
    """O fluxo "Workbook" de dentro do arquivo OLE2 (o .xls é um contêiner)."""
    if dados[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ValueError("não é um arquivo .xls (OLE2)")
    tam = 1 << struct.unpack_from("<H", dados, 0x1E)[0]
    n_fat, dir1 = struct.unpack_from("<II", dados, 0x2C)
    difat1, n_difat = struct.unpack_from("<II", dados, 0x44)
    setor = lambda i: dados[512 + i * tam: 512 + (i + 1) * tam]      # noqa: E731

    # setores da FAT: 109 no cabeçalho, o resto em setores DIFAT encadeados
    lista = list(struct.unpack_from("<109I", dados, 0x4C))
    s = difat1
    for _ in range(n_difat):
        bloco = struct.unpack("<%dI" % (tam // 4), setor(s))
        lista += bloco[:-1]
        s = bloco[-1]
    fat = []
    for i in lista[:n_fat]:
        fat += struct.unpack("<%dI" % (tam // 4), setor(i))

    def cadeia(i):
        out, vistos = [], set()
        while i < 0xFFFFFFFA and i not in vistos:
            vistos.add(i)
            out.append(setor(i))
            i = fat[i]
        return b"".join(out)

    diretorio = cadeia(dir1)
    for k in range(0, len(diretorio), 128):
        e = diretorio[k:k + 128]
        n = struct.unpack_from("<H", e, 0x40)[0]
        if e[:max(n - 2, 0)].decode("utf-16-le", "replace") in (nome, "Book"):
            ini, tamanho = struct.unpack_from("<II", e, 0x74)
            if tamanho < 4096:
                raise ValueError("fluxo pequeno demais (mini-stream não suportado)")
            return cadeia(ini)[:tamanho]
    raise ValueError("o .xls não tem o fluxo Workbook")


def _registros(fluxo, pos=0):
    while pos + 4 <= len(fluxo):
        tipo, n = struct.unpack_from("<HH", fluxo, pos)
        yield pos, tipo, fluxo[pos + 4:pos + 4 + n]
        pos += 4 + n


def _sst(partes):
    """A tabela de textos (SST), que pode vir quebrada em vários CONTINUE.
    Quando um texto atravessa a quebra, o pedaço seguinte começa com um byte
    que diz se os caracteres continuam em 1 ou 2 bytes."""
    textos = []
    total = struct.unpack_from("<I", partes[0], 4)[0]
    p, pos = 0, 8
    while len(textos) < total:
        if pos >= len(partes[p]):
            p, pos = p + 1, 0
        d = partes[p]
        n, flags = struct.unpack_from("<HB", d, pos)
        pos += 3
        rich = struct.unpack_from("<H", d, pos)[0] if flags & 8 else 0
        pos += 2 if flags & 8 else 0
        ext = struct.unpack_from("<I", d, pos)[0] if flags & 4 else 0
        pos += 4 if flags & 4 else 0
        largo, txt = flags & 1, []
        while n:
            if pos >= len(partes[p]):
                p, pos = p + 1, 0
                largo = partes[p][0] & 1
                pos = 1
            d = partes[p]
            cabe = min(n, (len(d) - pos) // (2 if largo else 1))
            bruto = d[pos:pos + cabe * (2 if largo else 1)]
            txt.append(bruto.decode("utf-16-le") if largo else bruto.decode("latin-1"))
            pos += len(bruto)
            n -= cabe
        textos.append("".join(txt))
        # formatação (rich text) e extensão ficam no fim; podem cruzar CONTINUE
        resto = rich * 4 + ext
        while resto:
            if pos >= len(partes[p]):
                p, pos = p + 1, 0
            anda = min(resto, len(partes[p]) - pos)
            pos += anda
            resto -= anda
    return textos


def _rk(v):
    if v & 2:
        x = v >> 2
        if x & 0x20000000:
            x -= 0x40000000
    else:
        x = struct.unpack("<d", struct.pack("<Q", (v & 0xFFFFFFFC) << 32))[0]
    return x / 100 if v & 1 else x


def abas(conteudo):
    """{nome da aba: {(linha, coluna): texto ou número}} (base 0)."""
    fluxo = _fluxo(conteudo)
    nomes, sst, partes = [], [], None
    for pos, tipo, d in _registros(fluxo):
        if tipo == 0x0085:                                           # BOUNDSHEET
            ini = struct.unpack_from("<I", d, 0)[0]
            n, flags = d[6], d[7]
            nome = d[8:8 + n * 2].decode("utf-16-le") if flags & 1 else d[8:8 + n].decode("latin-1")
            nomes.append((nome, ini))
        elif tipo == 0x00FC:                                         # SST
            partes = [d]
        elif tipo == 0x003C and partes is not None:                  # CONTINUE do SST
            partes.append(d)
        elif partes is not None:
            sst, partes = _sst(partes), None
        if tipo == 0x000A:                                           # EOF do globais
            break

    fora = {}
    for nome, ini in nomes:
        celulas = {}
        for _, tipo, d in _registros(fluxo, ini):
            if tipo == 0x000A:
                break
            if tipo == 0x00FD:                                       # LABELSST
                r, c, _, i = struct.unpack_from("<HHHI", d)
                celulas[(r, c)] = sst[i]
            elif tipo == 0x0203:                                     # NUMBER
                r, c, _, v = struct.unpack_from("<HHHd", d)
                celulas[(r, c)] = v
            elif tipo == 0x027E:                                     # RK
                r, c, _, v = struct.unpack_from("<HHHI", d)
                celulas[(r, c)] = _rk(v)
            elif tipo == 0x00BD:                                     # MULRK
                r, c = struct.unpack_from("<HH", d)
                for k in range((len(d) - 6) // 6):
                    celulas[(r, c + k)] = _rk(struct.unpack_from("<I", d, 4 + k * 6 + 2)[0])
            elif tipo == 0x0006:                                     # FORMULA
                r, c = struct.unpack_from("<HH", d)
                if d[12:14] != b"\xff\xff":                          # resultado numérico
                    celulas[(r, c)] = struct.unpack_from("<d", d, 6)[0]
            elif tipo == 0x0204:                                     # LABEL
                r, c, _, n, flags = struct.unpack_from("<HHHHB", d)
                b = d[9:]
                celulas[(r, c)] = b[:n * 2].decode("utf-16-le") if flags & 1 else b[:n].decode("latin-1")
        fora[nome] = celulas
    return fora

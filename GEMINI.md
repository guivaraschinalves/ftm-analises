# Instruções do Projeto — FtM Dados e FtM Análises

Regras operacionais obrigatórias para qualquer agente (Gemini, Claude ou outro) trabalhando nos repositórios `ftm-dados` e `ftm-analises`. Mantenha `AGENTS.md` e `GEMINI.md` idênticos.

---

## 1. Regra zero: proteção absoluta dos números

1. **Nenhum número digitado a partir de tela.** Todo dado vem por script da API oficial, planilha em `dados/` ou `git show` do `ftm-dados`. Exceção rara (série sem acesso aberto): guardar em constante em `MAIÚSCULAS` no topo do script, com a data e o comentário `"trocar a cada ..."`.
2. **Conferência que aborta (`raise RuntimeError` / `SystemExit`).** Todo script com cálculo próprio precisa recalcular algo que a fonte também publica (ou conferir uma identidade contábil) e abortar se passar da tolerância. Exemplos reais:
   - Acumulado em 12 meses refeito × série publicada pelo BC: ≤ `0,02 p.p.`
   - Acumulado no ano em dezembro × acumulado em 12 meses: ≤ `0,02 p.p.`
   - Esferas do governo somam o consolidado: ≤ `R$ 1 milhão`
   - Ótica da demanda fecha o PIB nominal: ≤ `0,01% do PIB`
   - Subitens da despesa somam o total (RTN): aborta se não somar
   - Balanço do ouro (oferta = demanda): ≤ `0,2 t`
3. **Imprimir o último ponto no log.** Ao criar ou alterar gráfico, imprimir o último valor gerado e comparar com o dado publicado na fonte (ou slide de referência).
4. **Segunda fonte quando possível.** Séries de mercado ou sujeitas a erro de ajuste (ex.: proventos no Yahoo) devem ser cruzadas com outra fonte antes de entrar.
5. **Ordem garantida no código.** Usar `ordem()` numérica para chaves numéricas (senão `"10"` vem antes de `"2"`). A ordem de categorias (`FONTES` no `app.js`), seções e gráficos vem de listas fixas, nunca alfabética.
6. **Arredondar só na saída.** Contas rodam em precisão cheia; `round(v, casas)` só na montagem final do JSON (`serie()`), sempre com `allow_nan=False`.
7. **Buraco continua buraco.** Não interpolar nem atravessar mês faltante em acumulados; área preenchida é um polígono por trecho contínuo.
8. **Planilhas lidas por rótulo, nunca por posição.** Localizar abas e linhas pelo texto do rótulo e selecionar o arquivo por padrão de nome explícito.
9. **Datas honestas.** Usar o último dado até a data de referência; preço intradia nunca entra como fechamento.

---

## 2. Arquitetura e restrições técnicas

- **Sem build e sem biblioteca externa de gráficos.** O site é `index.html` + `app.js` + `styles.css` (SVG desenhado à mão a partir de `dados/*.json`).
- **Espelhamento `ftm-dados` ↔ `ftm-analises`:** o `ftm-analises` usa uma cópia do motor do `ftm-dados`. Toda mudança de desenho/renderização que valha para os dois deve ser replicada nos dois repositórios.
- **Cache bust:** sempre incrementar `?v=N` em `index.html` ao alterar `app.js` ou `styles.css`.
- **Python 3 só com biblioteca padrão** (`urllib`, `json`, `csv`, `datetime`). `openpyxl` apenas quando houver `.xlsx`; para `.xls` antigo, usar `scripts/xls.py`. **Proibido `pandas`** nos scripts da GitHub Action.
- **Moldes de referência:** antes de escrever script novo, ler `scripts/pib.py` e `scripts/fiscal.py` no `ftm-dados` (ou equivalentes em `scripts/`).

### Armadilhas conhecidas das APIs
- **BCB/SGS:** séries diárias exigem janelas de até 10 anos; sem `dataInicial` pode voltar `304`; às vezes retorna HTTP `200` com objeto de erro no lugar da lista — tratar como falha e repetir.
- **FRED:** enviar **sem** `User-Agent` (com `User-Agent` trava).
- **FMI:** retorna `403` com `User-Agent` de navegador.
- **Yahoo:** conferir fechamento ajustado/proventos contra outra fonte.

---

## 3. Paleta para daltonismo (regra dura)

O dono do projeto é daltônico. Respeitar estritamente esta ordem de cores:

| Ordem | Nome | Hex |
|---:|---|---|
| 1 | azul | `#4F81BD` |
| 2 | vermelho | `#C0504D` |
| 3 | verde | `#9BBB59` |
| 4 | azul-escuro | `#1F497D` |
| 5 | azul-claro | `#8EB4E3` |
| 6 | vinho | `#632523` |
| 7 | amarelo | `#FFFF00` (só por último; evitar em área grande) |

- **Máximo de 7 séries coloridas** por gráfico; demais séries vão em cinza `#8a8a86`.
- **Série principal no tema escuro:** branco `#FFFFFF`, mais grossa e com `rotulo: true`.
- **Pares proibidos no mesmo gráfico:** laranja `#F79646` × verde `#9BBB59`; vermelho-alaranjado × ocre.
- **Cor nova:** só usar após calcular ΔE (OKLab × 100) ≥ `8` contra **todas** as demais cores do gráfico no pior caso entre protanopia e deuteranopia.
- **Cor fixa por série:** a cor segue a identidade da série, nunca sua posição na lista (desligar uma série não pode repintar as outras).
- **Balanço de pagamentos:** reservas = apenas borda laranja, sem preenchimento; conta financeira: investimento direto azul/vermelho, carteira verde/azul-escuro, outros azul-claro.

---

## 4. Texto visível e tipografia

- **Fontes:** `Inter` na interface e nos gráficos; `Newsreader` apenas em texto editorial.
- **Nenhum travessão (`—`)** em texto visível (títulos, subtítulos, notas, comentários, nomes de séries). Usar dois-pontos, ponto e vírgula, vírgula ou parênteses.
- **Título:** curto, técnico, nomeando o dado (série, medida, período). Não usar perguntas nem chamadas jornalísticas.
- **Subtítulo:** direto ao que mede, unidade e ressalva após ponto e vírgula (ex.: `"Variação % acumulada em 12 meses; EX1 exclui combustíveis e alimentos com preços mais voláteis"`). Nada didático ou interpretativo.
- **Nota de rodapé:** só quando pedida explicitamente, e apenas metodológica (código/aba, fórmula, limite de comparação). Nunca explicar como ler o gráfico ou botões.
- **Fonte no rodapé:** `"Órgão (Pesquisa)"`, terminando em `" e FtM"` quando houver cálculo próprio.
- **Análises (`ftm-analises`):** um comentário logo antes de cada gráfico (sempre intercalados), com no máximo **3 frases corridas** por parágrafo.

---

## 5. Checklist obrigatório antes de concluir qualquer tarefa

1. Rodar o script do tema e confirmar que nenhuma conferência abortou:
   ```bash
   python3 scripts/<tema>.py
   ```
2. Rodar o auditor automático no JSON gerado:
   ```bash
   python3 scripts/auditar.py dados/<tema>.json
   ```
   E, havendo CSV/tabela-fonte de referência, auditar ponto a ponto:
   ```bash
   python3 scripts/auditar.py dados/<tema>.json <grafico_id> "<Nome da Série>" <fonte.csv> <col_chave> <col_valor>
   ```
3. Quando mexer em layout, eixo, rótulo ou novo gráfico, subir o servidor local e validar a captura no Chrome headless:
   ```bash
   python3 -m http.server 8000
   chrome --headless=new --window-size=1100,3000 --screenshot=tela.png http://localhost:8000/
   ```
   (Remover `tela.png` após inspecionar se não for parte do repositório.)

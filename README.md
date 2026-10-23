# Comparação de benchmarks

Instale as dependências: `python3 -m pip install matplotlib pandas`.

Para comparar relatórios da mesma biblioteca com tamanhos diferentes:

```bash
python3 benchmark_analysis.py teste_512.json teste_1024.json \
  --funcoes assina \
  --metricas tempo_medio_ms operacoes_por_segundo taxa_kbps --saida comparacao_tamanhos
```

Abra `comparacao_tamanhos/index.html` para visualizar os gráficos. Em uma máquina remota, baixe a pasta inteira, incluindo os PNGs. A saída informa os caminhos absolutos.

A análise sempre compara os tamanhos no mesmo gráfico. Cada relatório vira uma série identificada pelo label (ou biblioteca) e tamanho em bytes. Funções e algoritmos diferentes continuam separados, e as amostras de relatórios diferentes nunca são misturadas. O CSV preserva o tamanho original de cada série. Labels iguais são diferenciados pelo tamanho; se ainda repetirem, recebem identificação por arquivo.

O aviso de um único relatório significa que apenas um arquivo forneceu resultados para aquele grupo; não indica falha na geração.

São gerados gráficos de barras (média e desvio padrão amostral), boxplots (quartis, mediana e pavios do mínimo ao máximo, com valores anotados), uma galeria HTML e `resumo.csv`. Com uma única amostra, o desvio padrão é indisponível. Não há geração de candlesticks. As estatísticas são recalculadas a partir das amostras brutas do JSON. Use `--help` para listar as métricas.

Para interpretar uma comparação de tamanhos, considere que tempos por operação podem crescer com a quantidade de bytes. A taxa `taxa_kbps` pode ajudar a comparar vazão, conforme a definição da biblioteca C. Mantenha hardware, opções de compilação e demais parâmetros constantes. Arquivos com o mesmo nome são substituídos ao repetir a execução na mesma pasta; imagens antigas não são excluídas, mas a galeria lista apenas a execução atual.

## Colunas agrupadas

Por padrão, são analisadas as métricas `tempo_medio_ms`, `operacoes_por_segundo` e `taxa_kbps`. Os gráficos de colunas agrupadas reúnem os algoritmos de cada função: o eixo X contém os tamanhos em ordem crescente e a legenda identifica cada combinação de label (ou biblioteca) e algoritmo. Use o mesmo label nos arquivos de uma opção para acompanhar essa opção entre tamanhos. Arquivos com labels diferentes formam séries diferentes. Células sem dados ficam vazias, sem valores zero artificiais. Relatórios repetidos da mesma opção/tamanho são mantidos em séries separadas, pela ordem de entrada, sem mesclar amostras.

```bash
python3 benchmark_analysis.py resultados/*.json --saida comparacao
```

As colunas mostram média e desvio padrão amostral. Os boxplots continuam separados por algoritmo. `--metricas` permite selecionar outras métricas ou limitar a análise. A galeria lista somente os gráficos da execução atual.

## DataFrame e tabelas

As estatísticas são reunidas em um `pandas.DataFrame`, com uma linha por relatório, função, algoritmo e métrica, preservando o tamanho de dados e o arquivo de origem. A função `gerar` retorna `(arquivos, dataframe)` para uso em Python. O DataFrame completo é exportado para `resumo.csv`. No final da galeria HTML, as tabelas de resumo seguem os mesmos títulos, colunas, agrupamentos e ordenação do terminal, em vez de exibir uma tabela única com todos os campos.

No final da execução, o terminal imprime tabelas por função, algoritmo e métrica, com teste, tamanho, número de amostras, média, desvio padrão, mínimo, mediana, P95 e máximo. Relatórios diferentes não são agregados. Com apenas uma amostra, o desvio padrão é `n/a`. A taxa usa o campo `taxa_kbps` informado pelo C, sem conversão de unidades. Os JSONs precisam conter essa métrica nas amostras; para relatórios antigos sem ela, selecione explicitamente as métricas disponíveis usando `--metricas`.

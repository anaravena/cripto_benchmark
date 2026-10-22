# Comparação de benchmarks

Instale a dependência: `python3 -m pip install matplotlib`.

Para comparar relatórios da mesma biblioteca com tamanhos diferentes:

```bash
python3 benchmark_analysis.py teste_512.json teste_1024.json \
  --comparar-tamanhos --funcoes assina \
  --metricas tempo_medio_ms operacoes_por_segundo --saida comparacao_tamanhos
```

Abra `comparacao_tamanhos/index.html` para visualizar os gráficos. Em uma máquina remota, baixe a pasta inteira, incluindo os PNGs. A saída informa os caminhos absolutos.

Com `--comparar-tamanhos`, cada relatório vira uma série identificada pelo label (ou biblioteca) e tamanho em bytes. Funções e algoritmos diferentes continuam separados, e as amostras de relatórios diferentes nunca são misturadas. O CSV preserva o tamanho original de cada série. Labels iguais são diferenciados pelo tamanho; se ainda repetirem, recebem identificação por arquivo.

Sem a opção, cada tamanho de dados gera gráficos separados, como antes. O aviso de um único relatório significa que apenas um arquivo forneceu resultados para aquele grupo; não indica falha na geração.

São gerados gráficos de barras (média e desvio padrão amostral), boxplots (quartis, mediana e pavios do mínimo ao máximo, com valores anotados), uma galeria HTML e `resumo.csv`. Com uma única amostra, o desvio padrão é indisponível. Não há geração de candlesticks. As estatísticas são recalculadas a partir das amostras brutas do JSON. Use `--help` para listar as métricas.

Para interpretar uma comparação de tamanhos, considere que tempos por operação podem crescer com a quantidade de bytes. A taxa `taxa_kbps` pode ajudar a comparar vazão, conforme a definição da biblioteca C. Mantenha hardware, opções de compilação e demais parâmetros constantes. Arquivos com o mesmo nome são substituídos ao repetir a execução na mesma pasta; imagens antigas não são excluídas, mas a galeria lista apenas a execução atual.

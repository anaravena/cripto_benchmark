#!/usr/bin/env python3
"""Compare resultados JSON do benchmark.py, por biblioteca e tamanho dos dados."""
import argparse
from collections import Counter, defaultdict
import html
import json
import math
from pathlib import Path
import re
import statistics
import sys
from urllib.parse import quote

METRICAS = {
    'tempo_medio_ms': 'Tempo médio por operação (ms)',
    'tempo_chamada_ms': 'Tempo da chamada Python (ms)',
    'tempo_total_s': 'Tempo total reportado pelo C (s)',
    'operacoes_por_segundo': 'Operações por segundo',
    'taxa_kbps': 'Taxa (kbps, conforme a biblioteca)',
    'operacoes_total': 'Operações por chamada',
}


def percentil(valores, fracao):
    valores = sorted(valores)
    pos = (len(valores) - 1) * fracao
    baixo, alto = math.floor(pos), math.ceil(pos)
    return valores[baixo] + (valores[alto] - valores[baixo]) * (pos - baixo)


def carregar(caminhos, metricas, funcoes=None):
    documentos = []
    grupos = defaultdict(list)
    for caminho in caminhos:
        with caminho.open(encoding='utf-8') as arquivo:
            dados = json.load(arquivo)
        if not isinstance(dados, dict):
            raise ValueError(f'{caminho}: esperado um objeto JSON.')
        tamanho = dados.get('data_size')
        if type(tamanho) is not int or tamanho <= 0:
            raise ValueError(f'{caminho}: data_size deve ser inteiro positivo.')
        label = dados.get('label') or dados.get('biblioteca') or caminho.stem
        if not isinstance(label, str):
            raise ValueError(f'{caminho}: label deve ser texto.')
        if not isinstance(dados.get('benchmarks'), list) or not dados['benchmarks']:
            raise ValueError(f'{caminho}: benchmarks deve ser uma lista não vazia.')
        nome = f'{label} — {tamanho} bytes'
        documentos.append((caminho, dados, tamanho, nome))
    contagens = Counter(d[3] for d in documentos)
    for numero, (caminho, dados, tamanho, nome) in enumerate(documentos, 1):
        label = f'{nome} [{numero}: {caminho.name}]' if contagens[nome] > 1 else nome
        vistos = set()
        for benchmark in dados['benchmarks']:
            if not isinstance(benchmark, dict):
                raise ValueError(f'{caminho}: benchmark inválido.')
            funcao, algoritmo = benchmark.get('funcao'), benchmark.get('algoritmo')
            if not isinstance(funcao, str) or not funcao or (algoritmo is not None and not isinstance(algoritmo, str)):
                raise ValueError(f'{caminho}: função ou algoritmo inválido.')
            if (funcao, algoritmo) in vistos:
                raise ValueError(f'{caminho}: benchmark duplicado: {funcao}/{algoritmo}.')
            vistos.add((funcao, algoritmo))
            if funcoes and funcao not in funcoes:
                continue
            amostras = benchmark.get('amostras')
            if not isinstance(amostras, list) or not amostras:
                raise ValueError(f'{caminho}: {funcao} precisa de amostras brutas não vazias.')
            valores = {}
            for metrica in metricas:
                serie = []
                for amostra in amostras:
                    valor = amostra.get(metrica) if isinstance(amostra, dict) else None
                    if type(valor) not in (int, float) or not math.isfinite(valor) or valor < 0:
                        raise ValueError(f'{caminho}: amostra inválida para {funcao}/{metrica}.')
                    serie.append(valor)
                valores[metrica] = serie
            chave = (funcao, algoritmo)
            grupos[chave].append({'label': label, 'opcao': dados.get('label') or dados.get('biblioteca') or caminho.stem, 'arquivo': str(caminho),
                                  'biblioteca': dados.get('biblioteca'), 'data_size': tamanho,
                                  'valores': valores})
    if not grupos:
        raise ValueError('Nenhum benchmark corresponde às funções selecionadas.')
    return grupos


def slug(texto):
    return re.sub(r'[^a-zA-Z0-9_-]+', '_', texto).strip('_') or 'benchmark'


def gerar_barras_agrupadas(grupos, metricas, destino):
    """Uma figura por função/métrica; tamanhos no eixo X, opções na legenda."""
    import matplotlib.pyplot as plt
    por_funcao = defaultdict(list)
    for (funcao, algoritmo), testes in grupos.items():
        for teste in testes:
            por_funcao[funcao].append((algoritmo, teste))
    arquivos = []
    for numero, (funcao, testes) in enumerate(sorted(por_funcao.items()), 1):
        tamanhos = sorted({teste['data_size'] for _, teste in testes})
        # Repetições da mesma opção/tamanho permanecem em séries separadas.
        contadores = Counter()
        series = defaultdict(dict)
        for algoritmo, teste in testes:
            base = (teste['opcao'], algoritmo or '')
            chave = (base, teste['data_size'])
            contadores[chave] += 1
            series[(base, contadores[chave])][teste['data_size']] = teste
        opcoes = sorted(series)
        largura = .8 / len(opcoes)
        for metrica in metricas:
            fig, ax = plt.subplots(figsize=(max(9, len(tamanhos) * len(opcoes) * .7), 6))
            try:
                for indice, opcao in enumerate(opcoes):
                    (label, algoritmo), repeticao = opcao
                    legenda = label + (f' / {algoritmo}' if algoritmo else '')
                    if repeticao > 1:
                        legenda += f' / repetição {repeticao}'
                    posicoes, medias, desvios, quantidades = [], [], [], []
                    for x, tamanho in enumerate(tamanhos):
                        teste = series[opcao].get(tamanho)
                        if teste is None:
                            continue  # Ausência de dados não vira uma barra de valor zero.
                        amostras = teste['valores'][metrica]
                        posicoes.append(x - .4 + largura * (indice + .5))
                        medias.append(statistics.mean(amostras))
                        desvios.append(statistics.stdev(amostras) if len(amostras) > 1 else 0)
                        quantidades.append(len(amostras))
                    ax.bar(posicoes, medias, width=largura, yerr=desvios, capsize=3,
                           label=legenda, color=plt.get_cmap('tab20')(indice % 20))
                    for x, media, desvio, n in zip(posicoes, medias, desvios, quantidades):
                        ax.annotate(f'{media:.4g}\nn={n}', (x, media + desvio),
                                    xytext=(0, 4), textcoords='offset points', ha='center', fontsize=8)
                ax.set_xticks(list(range(len(tamanhos))))
                ax.set_xticklabels([str(t) for t in tamanhos])
                ax.set_xlabel('Tamanho dos dados (bytes)')
                ax.set_ylabel(METRICAS[metrica])
                ax.set_title(f'{funcao} — comparação por tamanho\nMédia ± desvio padrão amostral (n=1: desvio indisponível)', fontsize=11)
                ax.legend(title='Opção / algoritmo', loc='upper left', bbox_to_anchor=(1.02, 1))
                ax.grid(axis='y', alpha=.25)
                ax.set_axisbelow(True)
                inferior, superior = ax.get_ylim()
                ax.set_ylim(min(0, inferior), superior * 1.18 if superior > 0 else 1)
                fig.tight_layout()
                arquivo = destino / f'{numero:03d}_{slug(funcao)}_tamanhos_{metrica}_barras_agrupadas.png'
                fig.savefig(arquivo, dpi=160)
                arquivos.append(arquivo)
            finally:
                plt.close(fig)
    return arquivos


def gerar(grupos, metricas, destino):
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    destino.mkdir(parents=True, exist_ok=True)
    arquivos, linhas = [], []
    for numero, (chave, testes) in enumerate(sorted(grupos.items(), key=lambda item: (item[0][0], item[0][1] or '')), 1):
        funcao, algoritmo = chave
        titulo = funcao + (f' / {algoritmo}' if algoritmo is not None else '')
        titulo += ' — comparação de tamanhos'
        if len(testes) < 2:
            print(f'Aviso: {titulo} possui apenas um relatório neste grupo; não há outra série para comparar.', file=sys.stderr)
        labels = [t['label'] for t in testes]
        cores = [plt.get_cmap('tab10')(i % 10) for i in range(len(testes))]
        for metrica in metricas:
            series = [t['valores'][metrica] for t in testes]
            medias = [statistics.mean(s) for s in series]
            desvios = [statistics.stdev(s) if len(s) > 1 else 0 for s in series]
            for teste, serie, media in zip(testes, series, medias):
                linhas.append({'funcao': funcao, 'algoritmo': algoritmo, 'data_size': teste['data_size'],
                               'label': teste['label'], 'arquivo': teste['arquivo'], 'biblioteca': teste['biblioteca'],
                               'metrica': metrica, 'n': len(serie), 'media': media,
                               'desvio_padrao_amostral': statistics.stdev(serie) if len(serie) > 1 else None,
                               'minimo': min(serie), 'p25': percentil(serie, .25),
                               'mediana': statistics.median(serie), 'p75': percentil(serie, .75),
                               'p95': percentil(serie, .95), 'maximo': max(serie)})
            for tipo in ('boxplot',):
                fig, ax = plt.subplots(figsize=(max(8, len(testes) * 1.6), 6))
                try:
                    boxes = ax.boxplot(series, positions=list(range(len(testes))), patch_artist=True,
                                       medianprops={'color': 'black'}, widths=.6,
                                       whis=(0, 100), showfliers=False)
                    for caixa, cor in zip(boxes['boxes'], cores):
                        caixa.set_facecolor(cor)
                        caixa.set_alpha(.5)
                    for i, serie in enumerate(series):
                        ax.annotate(f'máx: {max(serie):.4g}', (i, max(serie)),
                                    xytext=(8, 5), textcoords='offset points', fontsize=8)
                        ax.annotate(f'mín: {min(serie):.4g}', (i, min(serie)),
                                    xytext=(8, -12), textcoords='offset points', fontsize=8)
                    subtitulo = 'Corpo: P25–P75 | linha preta: mediana | pavios: mínimo–máximo'
                    ax.set_xticks(list(range(len(testes))))
                    ax.set_xticklabels(labels, rotation=25, ha='right')
                    ax.set_ylabel(METRICAS[metrica])
                    ax.set_title(titulo + '\n' + subtitulo, fontsize=11)
                    ax.grid(axis='y', alpha=.25)
                    ax.set_axisbelow(True)
                    inferior, superior = ax.get_ylim()
                    ax.set_ylim(min(0, inferior), superior * 1.15 if superior > 0 else 1)
                    fig.tight_layout()
                    nome = f'{numero:03d}_{slug(funcao)}_{slug(algoritmo or "sem_algoritmo")}_tamanhos_{metrica}_{tipo}.png'
                    arquivo = destino / nome
                    fig.savefig(arquivo, dpi=160)
                    arquivos.append(arquivo)
                finally:
                    plt.close(fig)
    arquivos.extend(gerar_barras_agrupadas(grupos, metricas, destino))
    dataframe = pd.DataFrame.from_records(linhas)
    dataframe.to_csv(destino / 'resumo.csv', index=False, encoding='utf-8')
    galeria = ['<!doctype html><html lang="pt-BR"><meta charset="utf-8">',
               '<title>Comparação de benchmarks</title>',
               '<style>body{font-family:sans-serif;margin:2rem}img{max-width:100%;height:auto}'
               'figure{margin:2rem 0}figcaption{overflow-wrap:anywhere}</style>',
               '<h1>Comparação de benchmarks</h1><p><a href="resumo.csv">Resumo CSV</a></p>']
    for arquivo in arquivos:
        nome, url = html.escape(arquivo.name), html.escape(quote(arquivo.name))
        galeria.append(f'<figure><a href="{url}"><img src="{url}" alt="{nome}" loading="lazy"></a><figcaption>{nome}</figcaption></figure>')
    galeria.append('<h2>Resumo estatístico</h2>')
    galeria.append(dataframe.to_html(index=False, na_rep='n/a', float_format=lambda v: f'{v:.6g}', escape=True))
    (destino / 'index.html').write_text('\n'.join(galeria + ['</html>']), encoding='utf-8')
    return arquivos, dataframe


def imprimir_tabelas(dataframe):
    """Imprima cada observação do DataFrame sem agregar relatórios distintos."""
    colunas = ['label', 'data_size', 'n', 'media', 'desvio_padrao_amostral',
               'minimo', 'mediana', 'p95', 'maximo']
    nomes = {'label': 'Teste', 'data_size': 'Bytes', 'n': 'N', 'media': 'Média',
             'desvio_padrao_amostral': 'Desvio padrão', 'minimo': 'Mínimo',
             'mediana': 'Mediana', 'p95': 'P95', 'maximo': 'Máximo'}
    print('\nTABELAS DE RESUMO (n/a: desvio padrão indisponível com uma amostra)')
    # dropna=False preserva funções que não recebem algoritmo.
    for (funcao, algoritmo, metrica), grupo in dataframe.groupby(
            ['funcao', 'algoritmo', 'metrica'], dropna=False, sort=False):
        titulo = funcao
        if isinstance(algoritmo, str):
            titulo += f' / {algoritmo}'
        print(f'\n{titulo} — {METRICAS[metrica]}')
        tabela = grupo.sort_values(['data_size', 'label'], kind='stable')[colunas].rename(columns=nomes)
        print(tabela.to_string(index=False, na_rep='n/a', float_format=lambda v: f'{v:.6g}'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resultados', nargs='+', type=Path, help='Relatórios JSON do benchmark.py.')
    parser.add_argument('--metricas', nargs='+', choices=METRICAS, default=['tempo_medio_ms', 'operacoes_por_segundo', 'taxa_kbps'], help='Padrão: tempo_medio_ms, operacoes_por_segundo e taxa_kbps.')
    parser.add_argument('--funcoes', nargs='+', help='Filtrar funções, por exemplo: assina keygen.')
    parser.add_argument('--saida', type=Path, default=Path('comparacao'))
    args = parser.parse_args()
    destino = args.saida.expanduser().resolve()
    caminhos = list(dict.fromkeys(p.expanduser().resolve() for p in args.resultados))
    try:
        metricas = list(dict.fromkeys(args.metricas))
        grupos = carregar(caminhos, metricas, args.funcoes)
        arquivos, dataframe = gerar(grupos, metricas, destino)
    except ImportError:
        parser.exit(1, 'Erro: instale as dependências com: python3 -m pip install matplotlib pandas\n')
    except (OSError, ValueError, OverflowError) as erro:
        parser.exit(1, f'Erro: {erro}\n')
    print(f'Gerados {len(arquivos)} gráficos PNG e resumo.csv em {destino}.')
    print(f'Abra a galeria no navegador: {destino / "index.html"}')
    print('As imagens são salvas em disco; nenhuma janela é aberta automaticamente.')
    for arquivo in arquivos:
        print(f'  {arquivo}')
    imprimir_tabelas(dataframe)


if __name__ == '__main__':
    main()

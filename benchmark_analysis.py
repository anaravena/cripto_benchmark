#!/usr/bin/env python3
"""Compare resultados JSON do benchmark.py, por biblioteca e tamanho dos dados."""
import argparse
from collections import Counter, defaultdict
import csv
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


def carregar(caminhos, metricas, funcoes=None, comparar_tamanhos=False):
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
        nome = f'{label} — {tamanho} bytes' if comparar_tamanhos else label
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
            chave = (funcao, algoritmo, None if comparar_tamanhos else tamanho)
            grupos[chave].append({'label': label, 'arquivo': str(caminho),
                                  'biblioteca': dados.get('biblioteca'), 'data_size': tamanho,
                                  'valores': valores})
    if not grupos:
        raise ValueError('Nenhum benchmark corresponde às funções selecionadas.')
    return grupos


def slug(texto):
    return re.sub(r'[^a-zA-Z0-9_-]+', '_', texto).strip('_') or 'benchmark'


def gerar(grupos, metricas, destino):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    destino.mkdir(parents=True, exist_ok=True)
    arquivos, linhas = [], []
    for numero, (chave, testes) in enumerate(sorted(grupos.items(), key=lambda item: (item[0][0], item[0][1] or '', item[0][2] or 0)), 1):
        funcao, algoritmo, tamanho = chave
        titulo = funcao + (f' / {algoritmo}' if algoritmo is not None else '')
        titulo += f' — {tamanho} bytes' if tamanho is not None else ' — comparação de tamanhos'
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
            for tipo in ('barras', 'boxplot'):
                fig, ax = plt.subplots(figsize=(max(8, len(testes) * 1.6), 6))
                try:
                    if tipo == 'barras':
                        ax.bar(range(len(testes)), medias, color=cores, yerr=desvios, capsize=5)
                        subtitulo = 'Média ± desvio padrão amostral (n=1: desvio indisponível)'
                        for i, (media, serie) in enumerate(zip(medias, series)):
                            ax.annotate(f'{media:.4g}\nn={len(serie)}', (i, media + desvios[i]),
                                        xytext=(0, 5), textcoords='offset points', ha='center', fontsize=9)
                    else:
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
                    nome = f'{numero:03d}_{slug(funcao)}_{slug(algoritmo or "sem_algoritmo")}_{tamanho if tamanho is not None else "tamanhos"}_{metrica}_{tipo}.png'
                    arquivo = destino / nome
                    fig.savefig(arquivo, dpi=160)
                    arquivos.append(arquivo)
                finally:
                    plt.close(fig)
    with (destino / 'resumo.csv').open('w', encoding='utf-8', newline='') as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        writer.writeheader()
        writer.writerows(linhas)
    galeria = ['<!doctype html><html lang="pt-BR"><meta charset="utf-8">',
               '<title>Comparação de benchmarks</title>',
               '<style>body{font-family:sans-serif;margin:2rem}img{max-width:100%;height:auto}'
               'figure{margin:2rem 0}figcaption{overflow-wrap:anywhere}</style>',
               '<h1>Comparação de benchmarks</h1><p><a href="resumo.csv">Resumo CSV</a></p>']
    for arquivo in arquivos:
        nome, url = html.escape(arquivo.name), html.escape(quote(arquivo.name))
        galeria.append(f'<figure><a href="{url}"><img src="{url}" alt="{nome}" loading="lazy"></a><figcaption>{nome}</figcaption></figure>')
    (destino / 'index.html').write_text('\n'.join(galeria + ['</html>']), encoding='utf-8')
    return arquivos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resultados', nargs='+', type=Path, help='Relatórios JSON do benchmark.py.')
    parser.add_argument('--metricas', nargs='+', choices=METRICAS, default=['tempo_medio_ms'])
    parser.add_argument('--funcoes', nargs='+', help='Filtrar funções, por exemplo: assina keygen.')
    parser.add_argument('--comparar-tamanhos', action='store_true', help='Comparar tamanhos de dados no mesmo gráfico, mantendo função e algoritmo separados.')
    parser.add_argument('--saida', type=Path, default=Path('comparacao'))
    args = parser.parse_args()
    destino = args.saida.expanduser().resolve()
    caminhos = list(dict.fromkeys(p.expanduser().resolve() for p in args.resultados))
    try:
        metricas = list(dict.fromkeys(args.metricas))
        grupos = carregar(caminhos, metricas, args.funcoes, args.comparar_tamanhos)
        arquivos = gerar(grupos, metricas, destino)
    except ImportError:
        parser.exit(1, 'Erro: instale matplotlib com: python3 -m pip install matplotlib\n')
    except (OSError, ValueError, OverflowError) as erro:
        parser.exit(1, f'Erro: {erro}\n')
    print(f'Gerados {len(arquivos)} gráficos PNG e resumo.csv em {destino}.')
    print(f'Abra a galeria no navegador: {destino / "index.html"}')
    print('As imagens são salvas em disco; nenhuma janela é aberta automaticamente.')
    for arquivo in arquivos:
        print(f'  {arquivo}')


if __name__ == '__main__':
    main()

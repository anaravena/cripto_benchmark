#!/usr/bin/env python3
"""Execute benchmarks de uma biblioteca C compartilhada e exporte resultados JSON."""
import argparse
import ctypes
import json
import math
from pathlib import Path
import statistics
import sys
import time


class Resultado(ctypes.Structure):
    _fields_ = [
        ('operacoes_total', ctypes.c_long),
        ('tempo_total_s', ctypes.c_double),
        ('tempo_medio_ms', ctypes.c_double),
        ('taxa_kbps', ctypes.c_double),
        ('operacoes_por_segundo', ctypes.c_double),
    ]


FUNCOES = {'cifracao': False, 'decifracao': False, 'cifra_autentica': False,
           'decifra_verifica': False, 'keygen': True, 'assina': True, 'verifica': True}
ALGORITMOS = {'classico': 0, 'hibrido': 1, 'pos_quantico': 2}


def positivo(texto):
    valor = int(texto)
    if valor <= 0:
        raise argparse.ArgumentTypeError('O valor deve ser maior que zero.')
    return valor


def estatisticas(valores):
    ordenados = sorted(valores)
    pos = (len(ordenados) - 1) * .95
    baixo, alto = math.floor(pos), math.ceil(pos)
    return {'media': statistics.mean(valores), 'mediana': statistics.median(valores),
            'desvio_padrao_amostral': statistics.stdev(valores) if len(valores) > 1 else None,
            'minimo': min(valores), 'maximo': max(valores),
            'p95': ordenados[baixo] + (ordenados[alto] - ordenados[baixo]) * (pos - baixo)}


def executar(args):
    caminho = Path(args.biblioteca).expanduser().resolve(strict=True)
    biblioteca = ctypes.CDLL(str(caminho))
    tarefas = []
    # Verifique todos os símbolos selecionados antes de executar o primeiro teste.
    for nome in dict.fromkeys(args.funcoes):
        funcao = getattr(biblioteca, 'benchmark_' + nome)
        funcao.restype = ctypes.c_int
        funcao.argtypes = [ctypes.POINTER(Resultado), ctypes.c_int]
        if FUNCOES[nome]:
            funcao.argtypes.append(ctypes.c_int)
        for algoritmo in (list(dict.fromkeys(args.algoritmos)) if FUNCOES[nome] else [None]):
            tarefas.append((nome, algoritmo, funcao))
    relatorio = {'label': args.label, 'biblioteca': str(caminho), 'data_size': args.data_size,
                 'repeticoes': args.repeticoes, 'aquecimento': args.aquecimento,
                 'retorno_sucesso': args.retorno_sucesso, 'benchmarks': []}
    if args.label is not None:
        print(f'Teste: {args.label}', flush=True)
    for nome, algoritmo, funcao in tarefas:
        rotulo = nome + (f'/{algoritmo}' if algoritmo is not None else '')
        print(f'Executando {rotulo}...', file=sys.stderr, flush=True)
        amostras = []
        for indice in range(args.aquecimento + args.repeticoes):
            resultado = Resultado()
            parametros = [ctypes.byref(resultado), args.data_size]
            if algoritmo is not None:
                parametros.append(ALGORITMOS[algoritmo])
            inicio = time.perf_counter_ns()
            codigo = funcao(*parametros)
            duracao = (time.perf_counter_ns() - inicio) / 1_000_000
            if codigo != args.retorno_sucesso:
                raise RuntimeError(f'{rotulo}: chamada {indice + 1} retornou {codigo}; esperado {args.retorno_sucesso}.')
            amostra = {campo: getattr(resultado, campo) for campo, _ in Resultado._fields_}
            if any(not math.isfinite(v) or v < 0 for v in amostra.values()):
                raise RuntimeError(f'{rotulo}: Resultado contém valor negativo ou não finito.')
            amostra['tempo_chamada_ms'] = duracao
            if indice >= args.aquecimento:
                amostras.append(amostra)
        resumo = {campo: estatisticas([a[campo] for a in amostras]) for campo in amostras[0]}
        operacoes = sum(a['operacoes_total'] for a in amostras)
        tempo = sum(a['tempo_total_s'] for a in amostras)
        agregado = {'operacoes_total': operacoes, 'tempo_total_s': tempo,
                    'operacoes_por_segundo': operacoes / tempo if tempo > 0 else None,
                    'tempo_por_operacao_ms': tempo * 1000 / operacoes if operacoes > 0 else None}
        relatorio['benchmarks'].append({'funcao': nome, 'algoritmo': algoritmo,
                                       'estatisticas': resumo, 'agregado': agregado, 'amostras': amostras})
        print(f'\n{rotulo} ({len(amostras)} execuções medidas)')
        print(f'{"Métrica":27} {"Média":>12} {"Mediana":>12} {"Desv. padrão":>12} {"Mínimo":>12} {"Máximo":>12} {"P95":>12}')
        for campo, valores in resumo.items():
            numeros = [valores[k] for k in ('media', 'mediana', 'desvio_padrao_amostral', 'minimo', 'maximo', 'p95')]
            print(f'{campo:27} ' + ' '.join(f'{n:12.6g}' if n is not None else f'{"n/a":>12}' for n in numeros))
        print(f'Total: {operacoes} operações; {tempo:.6g} s reportados pelo C.')
    if args.json:
        with Path(args.json).expanduser().open('w', encoding='utf-8') as arquivo:
            json.dump(relatorio, arquivo, ensure_ascii=False, indent=2, allow_nan=False)
        print(f'\nRelatório JSON salvo em {args.json}')
    return relatorio


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--biblioteca', required=True, help='Caminho da biblioteca compartilhada (.so, .dll ou .dylib).')
    parser.add_argument('--label', help='Identificação do teste no terminal e no JSON.')
    parser.add_argument('--funcoes', nargs='+', choices=FUNCOES, default=list(FUNCOES))
    parser.add_argument('--algoritmos', nargs='+', choices=ALGORITMOS, default=list(ALGORITMOS))
    parser.add_argument('--repeticoes', type=positivo, default=10, help='Chamadas medidas por função e algoritmo (padrão: 10).')
    parser.add_argument('--data-size', type=positivo, default=1024, help='Tamanho em bytes (padrão: 1024).')
    parser.add_argument('--aquecimento', type=int, default=0, help='Chamadas iniciais descartadas por função e algoritmo.')
    parser.add_argument('--retorno-sucesso', type=int, default=0, help='Código int de sucesso do C (padrão: 0).')
    parser.add_argument('--json', metavar='ARQUIVO', help='Salvar estatísticas e amostras brutas em JSON.')
    args = parser.parse_args()
    if args.aquecimento < 0:
        parser.error('--aquecimento deve ser maior ou igual a zero.')
    if args.data_size > 2 ** (ctypes.sizeof(ctypes.c_int) * 8 - 1) - 1:
        parser.error('--data-size excede o limite de int da ABI C.')
    try:
        executar(args)
    except (OSError, AttributeError, RuntimeError, ValueError) as erro:
        parser.exit(1, f'Erro: {erro}\n')


if __name__ == '__main__':
    main()

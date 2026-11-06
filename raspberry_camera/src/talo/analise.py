"""Analisa uma foto do talo e grava a resposta que a API publica em /api/talo.

Roda em subprocesso separado (prioridade baixa, com timeout) logo após cada
captura, para não disputar CPU com a leitura dos sensores. Duas medidas:

- mudança: diferença média de cor (0-255) entre esta foto e a de ~6 h antes,
  em 160 x 120. O talo secando muda de cor e encolhe; quando a mudança cai ao
  nível do ruído, o talo parou de mudar. Usa só o Pillow, já instalado.
- modelo (opcional): se ``talo_analysis.model_paths`` tiver arquivos .pth e o
  torch estiver instalado, classifica a foto. Sem isso, informa o motivo.

A interpretação (estabilizou ou não) fica no controlador que consulta a API.
Uso: python3 -m src.talo.analise <foto> <config.json>
"""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import time

VERSAO = 1
TAMANHO_COMPARACAO = (160, 120)


def instante_da_foto(caminho):
    """O nome photo_AAAAMMDDTHHMMSS_ffffff.bmp traz o horário UTC da captura."""
    try:
        return datetime.strptime(Path(caminho).name[6:21], '%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def foto_de_comparacao(foto, pasta, horas, tolerancia_min):
    """Foto mais próxima de ``horas`` antes, dentro da tolerância; None se não houver."""
    instante = instante_da_foto(foto)
    if instante is None:
        return None
    alvo = instante - timedelta(hours=horas)
    tolerancia = timedelta(minutes=tolerancia_min)
    melhor, melhor_distancia = None, None
    for candidata in Path(pasta).glob('photo_*' + Path(foto).suffix):
        momento = instante_da_foto(candidata)
        if momento is None or momento >= instante:
            continue
        distancia = abs(momento - alvo)
        if distancia <= tolerancia and (melhor_distancia is None or distancia < melhor_distancia):
            melhor, melhor_distancia = candidata, distancia
    return melhor


def imagem_reduzida(caminho):
    from PIL import Image

    with Image.open(caminho) as imagem:
        return imagem.convert('RGB').resize(TAMANHO_COMPARACAO)


def media(imagem):
    from PIL import ImageStat

    return sum(ImageStat.Stat(imagem).mean) / 3


def fracao_verde(imagem):
    """% dos pixels iluminados que são verdes (talo/folha ainda verde).

    HSV do Pillow (0-255): matiz 35-110, saturação > 40; sombra (V <= 25) fica fora.
    Na Secagem 1 o talo verde ficou em 10-15 % até a fixação e caiu para ~3 %.
    """
    verdes = iluminados = 0
    dados = imagem.convert('HSV').tobytes()  # funciona no Pillow 9.4 do 111 e nos novos
    for i in range(0, len(dados), 3):
        matiz, saturacao, valor = dados[i], dados[i + 1], dados[i + 2]
        if valor <= 25:
            continue
        iluminados += 1
        if 35 < matiz < 110 and saturacao > 40:
            verdes += 1
    return 100 * verdes / iluminados if iluminados else None


def mudanca_entre(atual, anterior):
    from PIL import ImageChops

    return media(ImageChops.difference(atual, anterior))


def classificar(foto, caminhos_pesos, threads):
    """Mesmo formato de checkpoint do treinador do V3 (modelo, classes, img_size, modelo_state_dict)."""
    pesos = [Path(p).expanduser() for p in caminhos_pesos]
    if not pesos:
        return {'disponivel': False, 'motivo': 'Nenhum modelo de talo configurado'}
    ausentes = [str(p) for p in pesos if not p.is_file()]
    if ausentes:
        return {'disponivel': False, 'motivo': 'Modelo ausente: ' + ', '.join(ausentes)}
    try:
        import torch
    except ImportError:
        return {'disponivel': False, 'motivo': 'torch nao instalado neste Raspberry'}
    from PIL import Image
    from src.talo.modelo import construir_modelo, criar_transformacao

    torch.set_num_threads(threads)
    inicio = time.monotonic()
    resultados = []
    for caminho in pesos:
        checkpoint = torch.load(caminho, map_location='cpu', weights_only=True)
        classes = checkpoint['classes']
        modelo = construir_modelo(checkpoint['modelo'], len(classes))
        modelo.load_state_dict(checkpoint['modelo_state_dict'], strict=True)
        modelo.eval()
        with Image.open(foto) as imagem:
            entrada = criar_transformacao(checkpoint['img_size'])(imagem.convert('RGB')).unsqueeze(0)
        with torch.inference_mode():
            probabilidades = torch.softmax(modelo(entrada), dim=1)[0].tolist()
        indice = max(range(len(probabilidades)), key=probabilidades.__getitem__)
        resultados.append({
            'modelo': checkpoint['modelo'],
            'arquivo': caminho.name,
            'classe': classes[indice],
            'score_softmax': round(probabilidades[indice], 4),
            'probabilidades': {c: round(p, 4) for c, p in zip(classes, probabilidades)},
        })
        del modelo, checkpoint
    return {'disponivel': True, 'resultados': resultados, 'segundos': round(time.monotonic() - inicio, 1)}


def salvar_json_atomico(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + '.tmp')
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporario, caminho)


def pasta_resultados(project_root, config):
    pasta = Path(config.get('talo_analysis', {}).get('directory', 'data/talo')).expanduser()
    return pasta if pasta.is_absolute() else project_root / pasta


def analisar(foto, config, project_root):
    ajustes = config.get('talo_analysis', {})
    horas = ajustes.get('comparison_hours', 6)
    instante = instante_da_foto(foto)
    resposta = {
        'versao': VERSAO,
        'foto': Path(foto).name,
        'capturada_em': instante.isoformat() if instante else None,
        'analisada_em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'brilho': None,
        'verde_pct': None,
        'comparacao': None,
        'modelo': None,
        'erro': None,
    }
    try:
        atual = imagem_reduzida(foto)
        resposta['brilho'] = round(media(atual), 2)
        verde = fracao_verde(atual)
        resposta['verde_pct'] = None if verde is None else round(verde, 2)
        anterior = foto_de_comparacao(foto, Path(foto).parent, horas, ajustes.get('tolerance_minutes', 40))
        if anterior is None:
            resposta['comparacao'] = {'mudanca': None, 'motivo': f'Sem foto de ~{horas:g} h antes'}
        else:
            resposta['comparacao'] = {
                'foto': anterior.name,
                'horas': round((instante - instante_da_foto(anterior)).total_seconds() / 3600, 2),
                'mudanca': round(mudanca_entre(atual, imagem_reduzida(anterior)), 2),
            }
    except Exception as erro:
        resposta['erro'] = f'{type(erro).__name__}: {erro}'
    try:
        resposta['modelo'] = classificar(foto, ajustes.get('model_paths', []), ajustes.get('threads', 2))
    except Exception as erro:
        resposta['modelo'] = {'disponivel': False, 'motivo': f'Falha no modelo: {type(erro).__name__}: {erro}'}
    return resposta


def salvar_jpeg(foto, pasta):
    """Cópia JPEG (~40 KB) servida em /api/talo/foto/<nome> para o painel do 222."""
    from PIL import Image

    destino = pasta / 'fotos' / (Path(foto).stem + '.jpg')
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix('.tmp')
    with Image.open(foto) as imagem:
        imagem.convert('RGB').save(temporario, 'JPEG', quality=85)
    os.replace(temporario, destino)
    return destino.name


def main(argumentos=None):
    argumentos = sys.argv[1:] if argumentos is None else argumentos
    foto = Path(argumentos[0])
    config_path = Path(argumentos[1])
    project_root = config_path.resolve().parents[1]
    config = json.loads(config_path.read_text(encoding='utf-8'))
    resposta = analisar(foto, config, project_root)
    pasta = pasta_resultados(project_root, config)
    try:
        resposta['jpeg'] = salvar_jpeg(foto, pasta)
    except Exception as erro:
        resposta['jpeg'] = None
        print(f'Falha ao gravar o JPEG do talo: {type(erro).__name__}: {erro}', file=sys.stderr, flush=True)
    salvar_json_atomico(pasta / 'ultima_talo.json', resposta)
    with open(pasta / 'historico_talo.jsonl', 'a', encoding='utf-8') as historico:
        historico.write(json.dumps(resposta, ensure_ascii=False) + '\n')
    print(json.dumps(resposta, ensure_ascii=False), flush=True)
    return 1 if resposta['erro'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

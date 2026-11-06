"""Executa a iluminação e a captura periódica das fotografias."""

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import time


def capture_photos(project_root, config, simulation, hardware, stop_event, photo_queue=None, once=False):
    """Repete iluminação → estabilização → captura → desligamento do LED.

    A câmera roda em subprocesso com timeout e o LED é apagado no bloco finally.
    """
    photo_directory = project_root / 'data/photos/simulation' if simulation else Path(config['photo_directory']).expanduser()
    photo_directory.mkdir(parents=True, exist_ok=True)

    while not stop_event.is_set():
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%f')
        extension = '.txt' if simulation else '.' + config['photo_format']
        photo_path = photo_directory / ('photo_' + timestamp + extension)
        event = {
            'photo': str(photo_path),
            'ok': False,
            'resolution': [config['camera_width'], config['camera_height']],
        }

        try:
            print('Ligando LED e aguardando estabilização...', flush=True)
            hardware.set_light(True, config['led_rgb'])
            if stop_event.wait(config['light_settle_seconds']):
                break

            if simulation:
                photo_path.write_text('SIMULAÇÃO: este arquivo não é uma fotografia.', encoding='utf-8')
            else:
                capture_script = project_root / 'src/camera/capture_once.py'
                subprocess.run(
                    [sys.executable, str(capture_script), str(photo_path), str(project_root / 'config/config.json')],
                    check=True,
                    timeout=config['capture_timeout'],
                )
            event['ok'] = True
            print(f'Captura salva: {photo_path}', flush=True)
        except Exception as error:
            event['error'] = f'Falha na captura: {type(error).__name__}: {error}'
            print(event['error'], flush=True)
        finally:
            hardware.set_light(False)

        analysis_started = time.monotonic()
        if event['ok'] and not simulation and config.get('talo_analysis', {}).get('enabled', False):
            run_talo_analysis(project_root, photo_path, config, stop_event)
        if photo_queue is not None:
            photo_queue.put(event)
        if once:
            break
        print(f'LED desligado. Próxima captura em {config["photo_interval"]} segundos.', flush=True)
        # O tempo da análise conta dentro do intervalo, para manter as fotos no photo_interval (15 min).
        stop_event.wait(max(0.0, config['photo_interval'] - (time.monotonic() - analysis_started)))


def run_talo_analysis(project_root, photo_path, config, stop_event):
    """Analisa a foto em subprocesso com prioridade baixa; falha ou timeout não param as fotos.

    O resultado vai para data/talo/ultima_talo.json, servido em GET /api/talo.
    """
    timeout = config['talo_analysis'].get('timeout', 600)
    threads = str(config['talo_analysis'].get('threads', 2))
    environment = {**os.environ, 'OMP_NUM_THREADS': threads, 'MKL_NUM_THREADS': threads}
    command = [sys.executable, '-m', 'src.talo.analise', str(photo_path), str(project_root / 'config/config.json')]
    try:
        process = subprocess.Popen(
            command,
            cwd=project_root,
            env=environment,
            stdout=subprocess.DEVNULL,
            preexec_fn=(lambda: os.nice(10)) if os.name == 'posix' else None,
        )
    except Exception as error:
        print(f'Falha ao iniciar a análise do talo: {type(error).__name__}: {error}', flush=True)
        return
    deadline = time.monotonic() + timeout
    # Espera em passos curtos para encerrar logo quando o serviço for parado.
    while process.poll() is None:
        if stop_event.wait(1) or time.monotonic() > deadline:
            process.kill()
            process.wait()
            print('Análise do talo interrompida (encerramento ou tempo limite).', flush=True)
            return
    print(f'Análise do talo concluída (código {process.returncode}).', flush=True)

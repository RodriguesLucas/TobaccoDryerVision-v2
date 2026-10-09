"""Executa a iluminação e a captura periódica das fotografias."""

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys


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

        if photo_queue is not None:
            photo_queue.put(event)
        if once:
            break
        print(f'LED desligado. Próxima captura em {config["photo_interval"]} segundos.', flush=True)
        stop_event.wait(config['photo_interval'])

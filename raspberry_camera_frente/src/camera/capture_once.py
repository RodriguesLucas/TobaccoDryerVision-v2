"""Captura uma fotografia na resolução configurada, usando a câmera flat."""

import json
from pathlib import Path
import sys
import time


def configure_camera(config):
    """Aplica a resolução e os controles fixos utilizados nas fotografias anteriores."""
    from picamera2 import Picamera2

    camera = Picamera2()
    try:
        size = (config['camera_width'], config['camera_height'])
        still_configuration = camera.create_still_configuration(main={'size': size})
        camera.configure(still_configuration)

        controls = dict(config['camera_controls'])
        controls['ColourGains'] = tuple(controls['ColourGains'])
        camera.set_controls(controls)
        camera.start()
        time.sleep(config['camera_settle_seconds'])
        return camera
    except BaseException:
        camera.close()
        raise


def capture_image(destination, config):
    """Salva a fotografia e fecha a câmera mesmo se a gravação falhar.

    O LED é comandado pelo trabalhador no processo principal, que o desliga
    também quando este subprocesso falha ou excede o tempo limite.
    """
    camera = configure_camera(config)
    try:
        camera.capture_file(destination)
    finally:
        camera.close()


if __name__ == '__main__':
    destination = sys.argv[1]
    configuration_path = Path(sys.argv[2])
    config = json.loads(configuration_path.read_text(encoding='utf-8'))
    capture_image(destination, config)

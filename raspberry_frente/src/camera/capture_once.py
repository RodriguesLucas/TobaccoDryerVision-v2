"""Captura uma única fotografia pela câmera CSI conectada por cabo flat."""

import sys
import time


def capture_image(destination):
    """Configura a câmera, estabiliza a exposição e salva a imagem no destino informado."""
    from picamera2 import Picamera2

    camera = Picamera2()
    try:
        camera.configure(camera.create_still_configuration())
        camera.start()
        # Este tempo é inicial; calibrar exposição e balanço de branco em campo.
        time.sleep(1)
        camera.capture_file(destination)
    finally:
        camera.close()


if __name__ == '__main__':
    capture_image(sys.argv[1])

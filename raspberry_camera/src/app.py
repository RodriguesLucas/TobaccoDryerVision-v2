"""Executa fotos, leitura local do SHT20 e relé ligado durante a execução."""

import argparse
import json
from pathlib import Path
import signal
import threading

from src.camera.photo_worker import capture_photos
from src.control.hardware import CameraHardware


def load_configuration(project_root):
    """Carrega os ajustes do LED, da câmera e do intervalo entre as fotos."""
    path = project_root / 'config/config.json'
    return json.loads(path.read_text(encoding='utf-8'))


def monitor_sensor(hardware, config, simulation, stop_event):
    """Mostra temperatura e umidade sem interromper a captura periódica das fotos.

    As leituras são apenas monitoramento: não decidem o estado do relé.
    """
    while not stop_event.is_set():
        try:
            sample = {'temperature_c': 30.0, 'humidity': 80.0} if simulation else hardware.sensor.read()
            temperature_c = sample['temperature_c']
            temperature_f = temperature_c * 1.8 + 32
            print(f"SHT20: {temperature_c:.2f} °C / {temperature_f:.2f} °F | Umidade: {sample['humidity']:.2f}%", flush=True)
        except Exception as error:
            print(f'Falha no SHT20: {type(error).__name__}: {error}', flush=True)
        stop_event.wait(config['sample_interval'])


def main():
    """Inicia as capturas e garante que o LED seja apagado no encerramento."""
    parser = argparse.ArgumentParser(description='Captura de fotos com iluminação LED.')
    parser.add_argument('--simulate', action='store_true', help='Testa o fluxo sem acessar LED ou câmera.')
    parser.add_argument('--once', action='store_true', help='Tira apenas uma foto e encerra.')
    arguments = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    config = load_configuration(project_root)
    stop_event = threading.Event()
    # Os sinais pedem o encerramento; a captura atual termina ou atinge o timeout.
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    hardware = None
    sensor_worker = None
    try:
        hardware = CameraHardware(config, arguments.simulate)
        hardware.set_power(True)
        print('Relé 1 ligado durante a execução.' if not arguments.simulate else 'SIMULAÇÃO: relé 1 ligado virtualmente.', flush=True)
        sensor_worker = threading.Thread(target=monitor_sensor, args=(hardware, config, arguments.simulate, stop_event), daemon=True)
        sensor_worker.start()
        print('Captura iniciada. Pressione Ctrl+C para encerrar.', flush=True)
        capture_photos(project_root, config, arguments.simulate, hardware, stop_event, once=arguments.once)
    finally:
        stop_event.set()
        # Desliga a fonte antes de aguardar o término da leitura do sensor.
        try:
            if hardware is not None:
                hardware.set_power(False)
        finally:
            try:
                if sensor_worker is not None:
                    sensor_worker.join(timeout=2)
            finally:
                if hardware is not None:
                    sensor_is_idle = sensor_worker is None or not sensor_worker.is_alive()
                    hardware.close(close_sensor=sensor_is_idle)
        print('Programa encerrado. Relé 1 e LED desligados.', flush=True)


if __name__ == '__main__':
    main()

"""Executa fotos, leituras locais dos sensores e relé ligado durante a execução."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import signal
import threading
import time
from zoneinfo import ZoneInfo

from src.camera.photo_worker import capture_photos
from src.api.sensor_server import SensorHTTPServer, SensorReadingStore
from src.control.hardware import CameraHardware
from src.storage.sensor_log import append_sensor_log


def load_configuration(project_root):
    """Carrega os ajustes do LED, da câmera e do intervalo entre as fotos."""
    path = project_root / 'config/config.json'
    return json.loads(path.read_text(encoding='utf-8'))


def monitor_sensors(hardware, config, simulation, stop_event, reading_store):
    """Lê e publica os sensores sem interromper a captura periódica das fotos.

    As leituras são apenas monitoramento: não decidem o estado do relé.
    """
    while not stop_event.is_set():
        cycle_started = time.monotonic()
        for name in ('SHT20', 'SHT41'):
            try:
                if simulation:
                    sample = (
                        {'temperature_c': 30.0, 'humidity': 80.0}
                        if name == 'SHT20'
                        else {'temperature_c': 31.0, 'humidity': 79.0}
                    )
                else:
                    sample = hardware.sensors[name].read()
            except Exception as error:
                reading_store.record_error(name, error)
                print(f'Falha na leitura do {name}: {type(error).__name__}: {error}', flush=True)
                continue

            local_time = datetime.now(ZoneInfo(config.get('log_timezone', 'America/Sao_Paulo')))
            timestamp = local_time.isoformat(timespec='microseconds')
            reading_store.record_success(name, sample, timestamp)
            temperature_c = sample['temperature_c']
            temperature_f = temperature_c * 1.8 + 32
            print(f"{name}: {temperature_c:.2f} °C / {temperature_f:.2f} °F | Umidade: {sample['humidity']:.2f}%", flush=True)
            try:
                append_sensor_log(config, sample, simulation=simulation, sensor_name=name)
            except Exception as error:
                print(f'Falha ao registrar {name}: {type(error).__name__}: {error}', flush=True)
        remaining = max(0.0, config['sample_interval'] - (time.monotonic() - cycle_started))
        stop_event.wait(remaining)


def main():
    """Inicia as capturas e garante que o LED seja apagado no encerramento."""
    parser = argparse.ArgumentParser(description='Captura de fotos com iluminação LED.')
    parser.add_argument('--simulate', action='store_true', help='Testa o fluxo sem acessar LED ou câmera.')
    parser.add_argument('--once', action='store_true', help='Tira apenas uma foto e encerra.')
    arguments = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    config = load_configuration(project_root)
    stop_event = threading.Event()
    reading_store = SensorReadingStore()
    # Os sinais pedem o encerramento; a captura atual termina ou atinge o timeout.
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    hardware = None
    sensor_worker = None
    sensor_server = None
    try:
        hardware = CameraHardware(config, arguments.simulate)
        hardware.set_power(True)
        print('Relé 1 ligado durante a execução.' if not arguments.simulate else 'SIMULAÇÃO: relé 1 ligado virtualmente.', flush=True)
        sensor_server = SensorHTTPServer(
            reading_store,
            host=config.get('sensor_api_host', '0.0.0.0'),
            port=config.get('sensor_api_port', 8000),
        )
        sensor_server.start()
        print(
            f"API dos sensores disponível em http://<IP-DESTE-RASPBERRY>:{config.get('sensor_api_port', 8000)}/api/sensors",
            flush=True,
        )
        sensor_worker = threading.Thread(
            target=monitor_sensors,
            args=(hardware, config, arguments.simulate, stop_event, reading_store),
            daemon=True,
        )
        sensor_worker.start()
        print('Captura iniciada. Pressione Ctrl+C para encerrar.', flush=True)
        capture_photos(project_root, config, arguments.simulate, hardware, stop_event, once=arguments.once)
    finally:
        stop_event.set()
        try:
            if sensor_server is not None:
                sensor_server.close()
        finally:
            try:
                # Desliga a fonte antes de aguardar o término da leitura do sensor.
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

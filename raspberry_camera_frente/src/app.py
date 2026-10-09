"""Coordena a aquisição, a câmera e o relé da fonte no Raspberry da cápsula."""

import argparse
import json
import math
from pathlib import Path
import queue
import signal
import threading
import time

from src.camera.photo_worker import capture_photos
from src.communication.remote_client import read_remote_sample
from src.control.hardware import CameraHardware
from src.control.logic import HeatingController, is_valid_sample, calculate_dew_point, to_fahrenheit
from src.storage.history import HistoryStore


def parse_arguments():
    """Lê as opções de simulação e duração informadas no terminal."""
    parser = argparse.ArgumentParser(description='Monitoramento da cápsula e captura de imagens.')
    parser.add_argument('--simulate', action='store_true', help='Executa sem acessar o hardware.')
    parser.add_argument('--seconds', type=float, default=0, help='Duração em segundos; 0 executa continuamente.')
    return parser.parse_args()


def load_configuration(project_root, simulation):
    """Carrega o JSON e impede operação física com polaridade ou limites indefinidos."""
    configuration_path = project_root / 'config/config.json'
    config = json.loads(configuration_path.read_text(encoding='utf-8'))

    if not simulation and type(config['relay_active_low']) is not bool:
        raise ValueError('Confirme relay_active_low: true para LOW ou false para HIGH.')

    if config['heating_enabled']:
        maximum = config['max_capsule_c']
        valid_maximum = type(maximum) in (int, float) and math.isfinite(maximum)
        valid_thresholds = 0 <= config['humidity_off'] < config['humidity_on'] <= 100
        if not (config['humidity_policy_accepted'] and valid_maximum and valid_thresholds):
            raise ValueError('Defina o limite térmico e os limiares de umidade antes de habilitar o aquecimento.')

    return config


def collect_samples(config, simulation, hardware, stop_event, sample_queue):
    """Lê os sensores em uma thread para não bloquear o controle da fonte.

    Mantém somente o conjunto mais recente na fila. Leituras com falha não
    reutilizam valores antigos como se fossem medições novas.
    """
    while not stop_event.is_set():
        cycle_started = time.monotonic()
        local_sample = None
        remote_sample = None
        errors = []

        try:
            if simulation:
                local_sample = {'temperature_c': 30.0, 'humidity': 80.0}
            else:
                local_sample = hardware.sensor.read()
        except Exception as error:
            errors.append('Falha no sensor local: ' + type(error).__name__)
        local_received_at = time.monotonic()

        try:
            if simulation:
                remote_sample = {'temperature_c': 40.0, 'humidity': 75.0, 'age_seconds': 0.0}
            else:
                remote_sample = read_remote_sample(config)
        except Exception as error:
            errors.append('Falha no sensor remoto: ' + type(error).__name__)

        samples = {
            'local': local_sample,
            'remote': remote_sample,
            'local_at': local_received_at,
            'remote_at': time.monotonic(),
            'errors': errors,
        }
        try:
            sample_queue.get_nowait()
        except queue.Empty:
            pass
        sample_queue.put_nowait(samples)

        elapsed = time.monotonic() - cycle_started
        stop_event.wait(max(0.1, config['sample_interval'] - elapsed))


def samples_are_fresh(samples, now, maximum_age):
    """Verifica a idade local e soma a idade declarada pelo servidor à espera no cliente."""
    if samples is None or samples['remote'] is None:
        return False

    local_age = now - samples['local_at']
    remote_age = now - samples['remote_at'] + samples['remote']['age_seconds']
    return local_age <= maximum_age and remote_age <= maximum_age


def build_snapshot(samples, is_fresh, power_enabled, reason):
    """Organiza os dados de monitoramento e substitui leituras inválidas por None."""
    local_sample = samples['local'] if samples else None
    remote_sample = samples['remote'] if samples else None

    return {
        'local': local_sample if is_valid_sample(local_sample) else None,
        'remote': remote_sample if is_valid_sample(remote_sample) else None,
        'local_f': to_fahrenheit(local_sample),
        'remote_f': to_fahrenheit(remote_sample),
        'dewpoint_capsule_c': calculate_dew_point(local_sample),
        'dewpoint_kiln_c': calculate_dew_point(remote_sample),
        'data_fresh': is_fresh,
        'power_command': power_enabled,
        'reserved_command': False,
        'reason': reason,
        'errors': samples['errors'] if samples else ['Aguardando a primeira leitura.'],
    }


def record_photo_events(photo_queue, history, snapshot):
    """Associa as fotos ao estado disponível no recebimento e grava o histórico.

    O snapshot não representa uma leitura sincronizada com a exposição da câmera.
    Essa limitação fica explicitamente registrada no banco.
    """
    while True:
        try:
            photo_event = photo_queue.get_nowait()
        except queue.Empty:
            break
        photo_event['snapshot'] = snapshot
        photo_event['snapshot_timing'] = 'Dados associados no recebimento do resultado da captura.'
        history.save('photo', photo_event)


def print_status(snapshot):
    """Mostra mensagens em português sem expor ao operador os nomes internos dos campos."""
    local_sample = snapshot['local']
    remote_sample = snapshot['remote']

    if local_sample:
        print(f"Cápsula: {local_sample['temperature_c']:.2f} °C / {snapshot['local_f']:.2f} °F | Umidade: {local_sample['humidity']:.2f}%")
    else:
        print('Cápsula: leitura indisponível.')

    if remote_sample:
        print(f"Outro Raspberry: {remote_sample['temperature_c']:.2f} °C / {snapshot['remote_f']:.2f} °F | Umidade: {remote_sample['humidity']:.2f}%")
    else:
        print('Outro Raspberry: leitura indisponível.')

    power_status = 'ligada' if snapshot['power_command'] else 'desligada'
    print(f"Fonte {power_status}. {snapshot['reason']}")


def run_control_loop(config, arguments, hardware, stop_event, sample_queue, photo_queue, history):
    """Atualiza o relé a cada 0,1 s e registra leituras no intervalo configurado."""
    controller = HeatingController()
    current_samples = None
    program_started = time.monotonic()
    next_log_at = 0

    while not stop_event.is_set():
        now = time.monotonic()
        if arguments.seconds > 0 and now - program_started >= arguments.seconds:
            break

        try:
            current_samples = sample_queue.get_nowait()
        except queue.Empty:
            pass

        is_fresh = samples_are_fresh(current_samples, now, config['max_sample_age'])
        local_sample = current_samples['local'] if current_samples else None
        remote_sample = current_samples['remote'] if current_samples else None
        power_enabled, reason = controller.update(local_sample, remote_sample, is_fresh, config)
        hardware.set_power(power_enabled)

        snapshot = build_snapshot(current_samples, is_fresh, power_enabled, reason)
        if now >= next_log_at:
            history.save('sensors', snapshot)
            print_status(snapshot)
            next_log_at = now + config['log_interval']

        record_photo_events(photo_queue, history, snapshot)
        stop_event.wait(0.1)


def main():
    """Inicializa os recursos, inicia as tarefas e garante o desligamento ao sair."""
    arguments = parse_arguments()
    project_root = Path(__file__).resolve().parents[1]
    config = load_configuration(project_root, arguments.simulate)
    (project_root / 'data/photos').mkdir(parents=True, exist_ok=True)

    stop_event = threading.Event()
    sample_queue = queue.Queue(maxsize=1)
    photo_queue = queue.Queue()
    hardware = None
    history = None
    workers = []

    try:
        hardware = CameraHardware(config, arguments.simulate)
        history = HistoryStore(project_root / 'data/camera.sqlite')
        workers = [
            threading.Thread(
                target=collect_samples,
                args=(config, arguments.simulate, hardware, stop_event, sample_queue),
                name='sensor-worker',
                daemon=True,
            ),
            threading.Thread(
                target=capture_photos,
                args=(project_root, config, arguments.simulate, hardware, stop_event, photo_queue),
                name='photo-worker',
                daemon=True,
            ),
        ]
        for worker in workers:
            worker.start()

        signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
        run_control_loop(config, arguments, hardware, stop_event, sample_queue, photo_queue, history)
    except KeyboardInterrupt:
        print('Encerramento solicitado pelo usuário.')
    finally:
        stop_event.set()
        try:
            if hardware is not None:
                hardware.turn_off_relays()
            for worker in workers:
                if worker.ident is not None:
                    worker.join(config['capture_timeout'] + 2)
        finally:
            try:
                if hardware is not None:
                    sensor_is_idle = not workers or not workers[0].is_alive()
                    hardware.close(close_sensor=sensor_is_idle)
            finally:
                if history is not None:
                    history.close()


if __name__ == '__main__':
    main()

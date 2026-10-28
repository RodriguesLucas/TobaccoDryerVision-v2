"""Registros independentes das imagens, no padrão JSON Lines do projeto de cura."""

from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def append_sensor_log(config, sample, simulation=False, sensor_name='SHT20'):
    """Adiciona uma linha JSON por leitura; nunca reescreve o histórico."""
    local_time = datetime.now(ZoneInfo(config.get('log_timezone', 'America/Sao_Paulo')))
    destination = Path(config.get('sensor_log_directory', 'data/sensor_logs')).expanduser()
    if not destination.is_absolute():
        destination = PROJECT_ROOT / destination
    if simulation:
        destination = destination / 'simulation'
    destination.mkdir(parents=True, exist_ok=True)
    record = {
        'timestamp': local_time.isoformat(timespec='microseconds'),
        'sensor': sensor_name,
        'temperature_c': round(float(sample['temperature_c']), 3),
        'temperature_f': round(float(sample['temperature_c']) * 1.8 + 32, 3),
        'humidity': round(float(sample['humidity']), 3),
    }
    filepath = destination / ('leituras_' + local_time.strftime('%Y-%m-%d') + '.jsonl')
    with filepath.open('a', encoding='utf-8') as output:
        output.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
        output.flush()
        os.fsync(output.fileno())
    return filepath

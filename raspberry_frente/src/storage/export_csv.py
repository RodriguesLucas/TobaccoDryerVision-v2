"""Exportação dos eventos registrados pelo Raspberry da câmera."""

import csv
import json
from pathlib import Path
import sqlite3


def main():
    """Converte o histórico SQLite em CSV com cabeçalhos em português para o Excel."""
    project_root = Path(__file__).resolve().parents[2]
    database_path = project_root / 'data/camera.sqlite'
    output_path = project_root / 'data/history.csv'

    headers = [
        'Data/hora UTC', 'Tipo de evento',
        'Temperatura local °C', 'Temperatura local °F', 'Umidade local %',
        'Temperatura remota °C', 'Temperatura remota °F', 'Umidade remota %',
        'Comando da fonte', 'Motivo', 'Fotografia', 'Captura concluída',
    ]

    connection = sqlite3.connect(database_path)
    try:
        with output_path.open('w', newline='', encoding='utf-8-sig') as output_file:
            writer = csv.writer(output_file, delimiter=';')
            writer.writerow(headers)
            events = connection.execute('SELECT utc, kind, json FROM events ORDER BY id')

            for timestamp, event_type, serialized_payload in events:
                payload = json.loads(serialized_payload)
                snapshot = payload.get('snapshot', payload)
                local_sample = snapshot.get('local') or {}
                remote_sample = snapshot.get('remote') or {}

                # As chaves internas permanecem em inglês; somente a apresentação muda.
                event_label = 'Fotografia' if event_type == 'photo' else 'Leitura dos sensores'
                writer.writerow([
                    timestamp, event_label,
                    local_sample.get('temperature_c'), snapshot.get('local_f'), local_sample.get('humidity'),
                    remote_sample.get('temperature_c'), snapshot.get('remote_f'), remote_sample.get('humidity'),
                    'Ligada' if snapshot.get('power_command') else 'Desligada',
                    snapshot.get('reason'), payload.get('photo'),
                    'Sim' if payload.get('ok') else 'Não' if event_type == 'photo' else '',
                ])
    finally:
        connection.close()

    print(f'Histórico exportado para: {output_path}')

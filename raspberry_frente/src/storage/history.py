"""Persistência dos eventos em SQLite, utilizada somente pela thread principal."""

from datetime import datetime, timezone
import json
import sqlite3


class HistoryStore:
    """Salva leituras, decisões e fotografias com data/hora em UTC."""

    def __init__(self, database_path):
        """Abre o banco e cria a tabela de eventos caso ela ainda não exista."""
        self.connection = sqlite3.connect(database_path)
        self.connection.execute(
            'CREATE TABLE IF NOT EXISTS events '
            '(id INTEGER PRIMARY KEY, utc TEXT, kind TEXT, json TEXT)'
        )

    def save(self, event_type, payload):
        """Grava um evento em uma transação e rejeita valores NaN no JSON."""
        timestamp = datetime.now(timezone.utc).isoformat()
        serialized_payload = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        with self.connection:
            self.connection.execute(
                'INSERT INTO events(utc, kind, json) VALUES (?, ?, ?)',
                (timestamp, event_type, serialized_payload),
            )

    def close(self):
        """Fecha a conexão após finalizar os registros."""
        self.connection.close()

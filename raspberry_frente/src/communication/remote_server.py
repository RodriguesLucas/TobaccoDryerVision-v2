"""Servidor de leituras para executar no outro Raspberry, usando um segundo SHT20."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import time

from src.sensors.sht20 import SHT20
from src.control.logic import is_valid_sample

sample_cache = {}
cache_lock = threading.Lock()


def read_sensor(sensor):
    """Obtém a leitura do sensor remoto; adapte este método se o modelo for diferente."""
    return sensor.read()


def acquire_samples():
    """Atualiza o cache a cada dois segundos e invalida os dados quando a leitura falha."""
    sensor = SHT20()
    try:
        while True:
            try:
                sample = read_sensor(sensor)
                if not is_valid_sample(sample):
                    raise ValueError('Leitura inválida do sensor remoto.')
                with cache_lock:
                    sample_cache.clear()
                    sample_cache.update(**sample, measured_at=time.monotonic(), ok=True)
            except Exception:
                with cache_lock:
                    sample_cache.clear()
                    sample_cache.update(ok=False)
            time.sleep(2)
    finally:
        sensor.close()


class SensorRequestHandler(BaseHTTPRequestHandler):
    """Atende consultas autenticadas sem iniciar uma leitura I²C por requisição."""

    def do_GET(self):
        """Retorna o cache com sua idade; rejeita token incorreto e caminhos desconhecidos."""
        expected_token = os.environ['CURING_TOKEN']
        if self.headers.get('Authorization') != 'Bearer ' + expected_token:
            self.send_error(401, 'Acesso não autorizado.')
            return
        if self.path != '/sensors':
            self.send_error(404, 'Endereço não encontrado.')
            return

        with cache_lock:
            response_data = dict(sample_cache)

        measurement_time = response_data.pop('measured_at', time.monotonic() - 9999)
        sample_age = time.monotonic() - measurement_time
        response_data['age_seconds'] = sample_age
        response_data['ok'] = response_data.get('ok', False) and sample_age <= 10
        response_body = json.dumps(response_data, allow_nan=False).encode('utf-8')

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, *arguments):
        """Suprime o registro HTTP padrão para não poluir o terminal a cada consulta."""
        return


def main():
    """Inicia o coletor e o servidor na porta 8080; exige token definido no ambiente."""
    if not os.environ.get('CURING_TOKEN'):
        raise SystemExit('Defina CURING_TOKEN antes de iniciar o servidor.')

    threading.Thread(target=acquire_samples, daemon=True, name='remote-sensor-worker').start()
    bind_address = os.environ.get('CURING_BIND', '0.0.0.0')
    server = ThreadingHTTPServer((bind_address, 8080), SensorRequestHandler)
    print('Servidor de leituras iniciado na porta 8080.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Servidor encerrado pelo usuário.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

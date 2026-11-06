"""API HTTP local para disponibilizar a última leitura dos sensores."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading

# Só o nome gerado pela análise do talo: sem barras nem subida de pasta.
NOME_JPEG_TALO = re.compile(r'^photo_\d{8}T\d{6}_\d{6}\.jpg$')


class SensorReadingStore:
    """Mantém as últimas leituras e erros de cada sensor com acesso sincronizado."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sensors = {}

    def record_success(self, name, sample, timestamp):
        """Atualiza a última medição válida do sensor."""
        with self._lock:
            self._sensors[name] = {
                'status': 'ok',
                'timestamp': timestamp,
                'temperature_c': round(float(sample['temperature_c']), 3),
                'temperature_f': round(float(sample['temperature_c']) * 1.8 + 32, 3),
                'humidity': round(float(sample['humidity']), 3),
            }

    def record_error(self, name, error):
        """Registra falha sem descartar a última medição válida."""
        with self._lock:
            reading = dict(self._sensors.get(name, {}))
            reading['status'] = 'error'
            reading['error'] = f'{type(error).__name__}: {error}'
            self._sensors[name] = reading

    def snapshot(self):
        """Retorna uma cópia consistente dos dados para serialização."""
        with self._lock:
            return {'sensors': {name: dict(reading) for name, reading in self._sensors.items()}}


class SensorHTTPServer:
    """Serve as leituras em GET /api/sensors e a última análise do talo em GET /api/talo."""

    def __init__(self, store, host='0.0.0.0', port=8000, talo_path=None):
        self.store = store

        class RequestHandler(BaseHTTPRequestHandler):
            def do_GET(handler_self):
                if handler_self.path == '/api/talo':
                    handler_self._send_talo()
                    return
                if handler_self.path.startswith('/api/talo/foto/'):
                    handler_self._send_talo_photo(handler_self.path.rsplit('/', 1)[1])
                    return
                if handler_self.path != '/api/sensors':
                    handler_self.send_error(404, 'Use /api/sensors ou /api/talo')
                    return

                payload = json.dumps(store.snapshot(), ensure_ascii=False, allow_nan=False).encode('utf-8')
                handler_self._send_json(200, payload)

            def _send_talo(handler_self):
                """Última análise do talo, gravada pelo subprocesso src.talo.analise."""
                try:
                    if talo_path is None:
                        raise FileNotFoundError('análise do talo desativada')
                    payload = talo_path.read_bytes()
                    json.loads(payload)
                    handler_self._send_json(200, payload)
                except (OSError, ValueError) as error:
                    body = {'erro': f'Sem análise do talo: {type(error).__name__}: {error}'}
                    handler_self._send_json(503, json.dumps(body, ensure_ascii=False).encode('utf-8'))

            def _send_talo_photo(handler_self, name):
                """JPEG de uma foto analisada (data/talo/fotos), para o painel do outro Raspberry."""
                path = None if talo_path is None else talo_path.parent / 'fotos' / name
                if path is None or not NOME_JPEG_TALO.match(name) or not path.is_file():
                    handler_self.send_error(404, 'Foto do talo nao encontrada')
                    return
                payload = path.read_bytes()
                handler_self.send_response(200)
                handler_self.send_header('Content-Type', 'image/jpeg')
                handler_self.send_header('Content-Length', str(len(payload)))
                handler_self.end_headers()
                handler_self.wfile.write(payload)

            def _send_json(handler_self, status, payload):
                handler_self.send_response(status)
                handler_self.send_header('Content-Type', 'application/json; charset=utf-8')
                handler_self.send_header('Content-Length', str(len(payload)))
                handler_self.send_header('Cache-Control', 'no-store')
                handler_self.end_headers()
                handler_self.wfile.write(payload)

        self._server = ThreadingHTTPServer((host, port), RequestHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._started = False

    def start(self):
        """Inicia o servidor HTTP em segundo plano."""
        self._thread.start()
        self._started = True

    def close(self):
        """Interrompe o servidor e libera a porta."""
        if self._started:
            self._server.shutdown()
        self._server.server_close()
        if self._started:
            self._thread.join(timeout=2)

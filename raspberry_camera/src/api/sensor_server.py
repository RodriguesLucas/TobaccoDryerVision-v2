"""API HTTP local para disponibilizar a última leitura dos sensores."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading


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
    """Serve as leituras em GET /api/sensors na rede local."""

    def __init__(self, store, host='0.0.0.0', port=8000):
        self.store = store

        class RequestHandler(BaseHTTPRequestHandler):
            def do_GET(handler_self):
                if handler_self.path != '/api/sensors':
                    handler_self.send_error(404, 'Use /api/sensors')
                    return

                payload = json.dumps(store.snapshot(), ensure_ascii=False, allow_nan=False).encode('utf-8')
                handler_self.send_response(200)
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

"""RAIZTRACE local HTTP entry point; Python standard library only."""
import argparse
import json
import os
import mimetypes
import threading
from urllib.parse import urlsplit, unquote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


MAX_ABS_INTEGER = 10 ** 15


def reject_huge_integers(value, depth=0):
    """Integers beyond 10^15 cannot be converted safely to float in the calculations."""
    if depth > 32:
        raise ValueError('JSON aninhado demais.')
    if isinstance(value, bool):
        return
    if isinstance(value, int) and abs(value) > MAX_ABS_INTEGER:
        raise HugeNumber()
    if isinstance(value, dict):
        for item in value.values():
            reject_huge_integers(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            reject_huge_integers(item, depth + 1)


class HugeNumber(Exception):
    pass


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def trusted_host(self):
        if self.headers.get('Host') not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}:
            self.respond({'error': {'code': 'host_forbidden', 'message': 'Use o endereço local exibido na inicialização.'}}, 403)
            return False
        return True

    def respond(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def handle_one_request(self):
        """Last-resort guard: unexpected failures answer JSON 500 instead of dropping the socket."""
        try:
            super().handle_one_request()
        except (ConnectionError, TimeoutError):
            self.close_connection = True
        except Exception as error:  # noqa: BLE001 - boundary of the HTTP server
            import sys
            print(f'RAIZTRACE erro interno: {type(error).__name__}: {error}', file=sys.stderr)
            self.close_connection = True
            try:
                self.respond({'error': {'code': 'internal_error', 'message': 'Falha interna inesperada; nenhum dado foi alterado fora de transação. Tente novamente.'}}, 500)
            except Exception:  # noqa: BLE001
                pass

    def send_bytes(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.trusted_host():
            return
        self.path = urlsplit(self.path).path
        if self.path == '/' or self.path.startswith('/static/'):
            relative = 'index.html' if self.path == '/' else unquote(self.path.removeprefix('/static/'))
            base = (ROOT / 'static').resolve()
            target = (base / relative).resolve()
            if target.is_relative_to(base) and target.is_file():
                mime = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
                self.send_bytes(target.read_bytes(), mime + ('; charset=utf-8' if mime.startswith('text/') or mime == 'application/javascript' else ''))
            else:
                self.respond({'error': {'code': 'not_found', 'message': 'Recurso não encontrado.'}}, 404)
            return
        if self.path == '/api/health':
            self.respond({'name': 'RAIZTRACE', 'version': '1.0.0', 'local_only': True})
        else:
            from domain import DomainError
            try:
                if self.path == '/api/ml/model':
                    from ml import train_and_evaluate
                    self.respond(train_and_evaluate())
                elif self.path == '/api/territory':
                    self.respond(self.territory())
                elif self.path == '/api/audit':
                    self.respond(self.server.ledger.verify_chain())
                elif self.path == '/api/state':
                    self.respond(self.server.ledger.state())
                elif self.path.startswith('/passport/'):
                    from documents import render_passport
                    passport = self.server.ledger.passport(self.path.removeprefix('/passport/'))
                    self.send_bytes(render_passport(passport).encode('utf-8'), 'text/html; charset=utf-8')
                elif self.path.startswith('/api/passports/'):
                    self.respond(self.server.ledger.passport(self.path.removeprefix('/api/passports/')))
                else:
                    self.respond({'error': {'code': 'not_found', 'message': 'Recurso não encontrado.'}}, 404)
            except DomainError as error:
                self.respond({'error': {'code': error.code, 'message': str(error)}}, error.status)

    def do_POST(self):
        if not self.trusted_host():
            return
        allowed = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
        if self.headers.get('Origin') and self.headers['Origin'] not in allowed:
            self.respond({'error': {'code': 'origin_forbidden', 'message': 'Origem externa não permitida.'}}, 403)
            return
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            self.respond({'error': {'code': 'content_type', 'message': 'Envie application/json.'}}, 415)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                self.respond({'error': {'code': 'body_size', 'message': 'Corpo deve ter entre 1 e 65536 bytes.'}}, 413)
                return
            def reject_constant(value):
                raise ValueError(f'Constante JSON inválida: {value}')
            payload = json.loads(self.rfile.read(length), parse_constant=reject_constant)
            if not isinstance(payload, dict):
                raise ValueError('Objeto JSON obrigatório.')
            reject_huge_integers(payload)
        except HugeNumber:
            self.respond({'error': {'code': 'validation_error', 'message': 'Número fora da faixa suportada (|valor| ≤ 10¹⁵).'}}, 422)
            return
        except (ValueError, UnicodeError, RecursionError):
            self.respond({'error': {'code': 'invalid_json', 'message': 'Envie um objeto JSON válido, sem NaN ou Infinity.'}}, 400)
            return
        from domain import DomainError
        from calculations import inventory, weigh
        try:
            if self.path == '/api/sources/refresh':
                if not self.server.refresh_lock.acquire(blocking=False):
                    self.respond({'error': {'code': 'refresh_busy', 'message': 'Atualização já em andamento. Aguarde e consulte as fontes.'}}, 409)
                    return
                try:
                    self.respond(self.territory(refresh=True))
                finally:
                    self.server.refresh_lock.release()
                return
            if self.path == '/api/assessments':
                self.respond(self.server.ledger.assess(payload), 201)
                return
            if self.path == '/api/review':
                self.respond(self.server.ledger.review(payload))
                return
            if self.path == '/api/ml':
                from ml import predict
                try:
                    self.respond(predict(payload.get('features')))
                except (ValueError, TypeError) as error:
                    self.respond({'error': {'code': 'validation_error', 'message': str(error)}}, 422)
                return
            if self.path == '/api/weigh':
                self.respond(weigh(payload.get('volume_m3'), payload.get('gross_kg'), payload.get('tare_kg')))
                return
            if self.path == '/api/shipments':
                self.respond(self.server.ledger.reserve(payload, self.headers.get('Idempotency-Key')), 201)
                return
            if self.path == '/api/inventory':
                self.respond(inventory(payload.get('diameter_cm'), payload.get('height_m'), payload.get('form_factor')))
                return
        except DomainError as error:
            self.respond({'error': {'code': error.code, 'message': str(error)}}, error.status)
            return
        self.respond({'error': {'code': 'not_found', 'message': 'Recurso não encontrado.'}}, 404)

    def territory(self, refresh=False):
        from integrations import SourceService, spatial_context, proximity_context
        result = SourceService(self.server.cache_dir).get(refresh=refresh)
        result['demo'] = json.loads((ROOT / 'data' / 'demo.geojson').read_text(encoding='utf-8'))
        alert_source = next((s for s in result['sources'] if s['id'] == 'deter_alerts'), {})
        if alert_source.get('status') == 'unavailable':
            result['spatial'] = {'status': 'not_evaluated', 'count': 0, 'intersections': [], 'notice': 'Fonte indisponível: sobreposição não avaliada. Ausência de dados não confirma regularidade.'}
            result['proximity'] = None
        else:
            result['proximity'] = proximity_context(result['demo']['features'][0], result['alerts'], result['municipality'])
            result['proximity'].update(source_fetched_at=alert_source.get('fetched_at'), partial=alert_source.get('partial'), total_available=alert_source.get('total_available'))
            result['spatial'] = spatial_context(result['demo']['features'][0], result['alerts'])
            result['spatial'].update(status='evaluated_partial' if alert_source.get('partial') else 'evaluated', source_fetched_at=alert_source.get('fetched_at'), source_sha256=alert_source.get('sha256'), plot_id='AREA-DEMO-001', plot_simulated=True)
        return result

    def log_message(self, *_args):
        pass


def create_server(port=8765, db_path=None, cache_dir=None):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.db_path = Path(db_path or ROOT / 'data' / 'raiztrace.sqlite')
    server.cache_dir = Path(cache_dir or ROOT / 'data' / 'sources')
    server.db_path.parent.mkdir(parents=True, exist_ok=True)
    from domain import Ledger
    server.ledger = Ledger(server.db_path)
    server.refresh_lock = threading.Lock()
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RAIZTRACE — demonstração local')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--db', default=os.environ.get('RAIZTRACE_DB'))
    args = parser.parse_args()
    server = create_server(args.port, args.db)
    print(f'RAIZTRACE: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

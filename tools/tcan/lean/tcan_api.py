"""LANLink routes for the local, non-transmitting T-CAN observer."""
import asyncio
import json
import socket
import urllib.error
import urllib.request

from sanic.response import json as json_response, raw

BACKEND = 'http://127.0.0.1:8099'
MAX_BODY = 262144


def register_tcan(app):
  pending = asyncio.Lock()

  async def forward(request):
    local_ip, local_port = request.transport.get_extra_info('sockname')[:2]
    hosts = {f'{local_ip}:{local_port}'}
    if local_ip == '127.0.0.1':
      hosts.add(f'localhost:{local_port}')
    if request.host not in hosts:
      return json_response({'error': 'use the LANLink device IP and port'}, status=421)
    if request.method == 'POST':
      if request.headers.get('origin') != f'http://{request.host}':
        return json_response({'error': 'same-origin LANLink request required'}, status=403)
      if request.headers.get('content-type') != 'application/json':
        return json_response({'error': 'application/json required'}, status=415)
      if len(request.body) > MAX_BODY:
        return json_response({'error': 'T-CAN request exceeds 262144 bytes'}, status=413)
    if pending.locked():
      return json_response({'error': 'T-CAN observer is busy'}, status=503)

    def exchange():
      req = urllib.request.Request(BACKEND + '/api' + request.path.removeprefix('/api/tcan'),
                                   data=request.body if request.method == 'POST' else None,
                                   headers={'Content-Type': 'application/json', 'Origin': BACKEND}, method=request.method)
      # The endpoint is constant and never redirects to a user-supplied destination.
      opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
      try:
        with opener.open(req, timeout=2) as response:
          return response.status, response.read(MAX_BODY + 1)
      except urllib.error.HTTPError as exc:
        return exc.code, exc.read(MAX_BODY + 1)

    async with pending:
      try:
        status, body = await asyncio.to_thread(exchange)
      except (TimeoutError, socket.timeout):
        return json_response({'error': 'T-CAN observer timed out'}, status=504)
      except urllib.error.URLError:
        return json_response({'error': 'T-CAN observer unavailable; start it on 127.0.0.1:8099'}, status=503)
    if len(body) > MAX_BODY or 300 <= status < 400:
      return json_response({'error': 'invalid T-CAN observer response'}, status=502)
    try:
      json.loads(body)
    except (ValueError, UnicodeDecodeError):
      return json_response({'error': 'invalid T-CAN observer JSON'}, status=502)
    return raw(body, status=status, content_type='application/json', headers={'Cache-Control': 'no-store'})

  for method, operation in (('GET', 'status'), ('GET', 'capture'), ('POST', 'preview')):
    app.add_route(forward, '/api/tcan/' + operation, methods=[method], name='tcan_' + operation)


class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self, req, fp, code, msg, headers, newurl):
    return None

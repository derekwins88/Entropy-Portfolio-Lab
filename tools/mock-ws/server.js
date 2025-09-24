// Minimal WS mock used by CI to let the UI connect.
// Listens on MOCK_WS_PORT (default 8787)
import { WebSocketServer } from 'ws';

const PORT = parseInt(process.env.MOCK_WS_PORT || '8787', 10);
const wss = new WebSocketServer({ port: PORT });

function log(...args) {
  console.log('[mock-ws]', ...args);
}

wss.on('listening', () => log(`listening on ws://127.0.0.1:${PORT}`));

wss.on('connection', (ws) => {
  log('client connected');
  ws.send(JSON.stringify({ type: 'hello', t: Date.now() }));

  ws.on('message', (raw) => {
    let msg = raw.toString();
    if (msg === 'ping') ws.send('pong');
  });
});

// Broadcast a lightweight tick so the UI sees activity
setInterval(() => {
  const payload = JSON.stringify({ type: 'tick', t: Date.now() });
  wss.clients.forEach((c) => c.readyState === 1 && c.send(payload));
}, 1000);

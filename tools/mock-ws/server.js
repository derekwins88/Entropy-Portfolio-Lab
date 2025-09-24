import { WebSocketServer } from 'ws';

const PORT = Number(process.env.MOCK_WS_PORT || 8787);
const wss = new WebSocketServer({ port: PORT });

// Simple echo/heartbeat mock so the UI can connect and tests can probe.
wss.on('connection', (ws) => {
  ws.send(JSON.stringify({ type: 'hello', ts: Date.now() }));
  ws.on('message', (msg) => {
    ws.send(JSON.stringify({ type: 'echo', data: msg.toString() }));
  });
});

// Keep the process alive and log a single “ready” line for humans.
console.log(`[mock-ws] listening on ws://127.0.0.1:${PORT}`);
setInterval(() => {}, 1 << 30);


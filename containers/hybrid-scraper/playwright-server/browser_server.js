const { chromium } = require('playwright');
const { WebSocketServer, WebSocket } = require('ws');
const fs = require('fs');
const path = require('path');
const http = require('http');

const CONFIG_PATH = path.join(__dirname, 'config.json');

// Socket path on the shared volume — agents connect here from outside the container
const SCRAPER_ID = process.env.SCRAPER_ID || '';
const SOCKET_DIR = SCRAPER_ID ? `/fleet-data/${SCRAPER_ID}` : null;
const SOCKET_PATH = SOCKET_DIR ? path.join(SOCKET_DIR, 'browser.sock') : null;

function proxyWebSocket(clientWs, targetUrl) {
  const upstream = new WebSocket(targetUrl);

  upstream.on('open', () => {
    clientWs.on('message', (data) => upstream.send(data));
    upstream.on('message', (data) => clientWs.send(data));
  });

  clientWs.on('close', () => upstream.close());
  upstream.on('close', () => clientWs.close());
  clientWs.on('error', () => upstream.close());
  upstream.on('error', () => clientWs.close());
}

(async () => {
  const browserServer = await chromium.launchServer({
    headless: true,
    channel: 'chromium',
    host: '0.0.0.0',
    args: [
      '--disable-blink-features=AutomationControlled',
      '--disable-features=site-per-process',
      '--no-sandbox',
    ],
  });

  const wsEndpoint = browserServer.wsEndpoint();
  console.log(`TCP endpoint: ${wsEndpoint}`);

  fs.writeFileSync(CONFIG_PATH, JSON.stringify({ ws_endpoint: wsEndpoint }, null, 2));

  // Start Unix socket proxy if we have a scraper ID and fleet-data is mounted
  if (SOCKET_PATH && fs.existsSync(SOCKET_DIR)) {
    // Clean up stale socket
    if (fs.existsSync(SOCKET_PATH)) {
      fs.unlinkSync(SOCKET_PATH);
    }

    const socketServer = http.createServer();
    const wss = new WebSocketServer({ server: socketServer });

    wss.on('connection', (ws) => {
      console.log('Unix socket: new connection, proxying to browser');
      proxyWebSocket(ws, wsEndpoint);
    });

    socketServer.listen(SOCKET_PATH, () => {
      // Make socket world-accessible
      fs.chmodSync(SOCKET_PATH, 0o777);
      console.log(`Unix socket endpoint: ${SOCKET_PATH}`);
    });

    // Write socket path to config so agents can find it
    fs.writeFileSync(CONFIG_PATH, JSON.stringify({
      ws_endpoint: wsEndpoint,
      socket_path: SOCKET_PATH,
    }, null, 2));
  }

  const shutdown = async () => {
    await browserServer.close();
    if (SOCKET_PATH && fs.existsSync(SOCKET_PATH)) {
      fs.unlinkSync(SOCKET_PATH);
    }
    process.exit(0);
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
})();

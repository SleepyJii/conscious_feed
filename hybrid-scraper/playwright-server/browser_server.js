const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CONFIG_PATH = path.join(__dirname, 'config.json');

(async () => {
  const browserServer = await chromium.launchServer({
    headless: true,
  });

  const wsEndpoint = browserServer.wsEndpoint();
  console.log(wsEndpoint);

  fs.writeFileSync(CONFIG_PATH, JSON.stringify({ ws_endpoint: wsEndpoint }, null, 2));

  process.on('SIGINT', async () => {
    await browserServer.close();
    process.exit(0);
  });

  process.on('SIGTERM', async () => {
    await browserServer.close();
    process.exit(0);
  });
})();

import { defineConfig } from '@playwright/test';
import path from 'path';

const rootDir = path.resolve(__dirname, '..');
const pythonExe = process.platform === 'win32'
  ? `"${path.join(rootDir, '.venv', 'Scripts', 'python.exe')}"`
  : `"${path.join(rootDir, '.venv', 'bin', 'python')}"`;

const backendPort = process.env.BACKEND_PORT || '8000';
const frontendPort = process.env.PORT || '3000';

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  use: {
    baseURL: `http://localhost:${frontendPort}`,
    screenshot: 'only-on-failure',
    video: 'off',
  },
  webServer: [
    {
      command: `${pythonExe} -m uvicorn semanticgraph.adapters.inbound.api.app:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: rootDir,
      url: `http://127.0.0.1:${backendPort}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: `npm run dev -- -p ${frontendPort}`,
      url: `http://localhost:${frontendPort}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        BACKEND_API_URL: `http://127.0.0.1:${backendPort}`,
      },
    },
  ],
  reporter: [['html', { open: 'never' }]],
});

import { defineConfig } from '@playwright/test';
import path from 'path';

const rootDir = path.resolve(__dirname, '..');
const pythonExe = process.platform === 'win32'
  ? `"${path.join(rootDir, '.venv', 'Scripts', 'python.exe')}"`
  : `"${path.join(rootDir, '.venv', 'bin', 'python')}"`;

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  webServer: [
    {
      command: `${pythonExe} -m uvicorn semanticgraph.adapters.inbound.api.app:app --host 127.0.0.1 --port 8000`,
      cwd: rootDir,
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
  reporter: [['html', { open: 'never' }]],
});

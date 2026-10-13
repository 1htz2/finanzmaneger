import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'

const backend = path.resolve(import.meta.dirname, '../backend')
const python = path.join(backend, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python')
const dataDir = path.resolve(import.meta.dirname, 'artifacts/data')

export default defineConfig({
  testDir: './tests',
  outputDir: './artifacts/results',
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  reporter: [['list']],
  globalSetup: './global-setup.ts',
  use: {
    baseURL: 'http://127.0.0.1:8765',
    locale: 'de-DE',
    timezoneId: 'Europe/Berlin',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'mobile', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' } },
  ],
  webServer: {
    command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8765`,
    cwd: backend,
    url: 'http://127.0.0.1:8765/api/health',
    reuseExistingServer: false,
    env: { FM_DATA_DIR: dataDir, FM_ENV: 'production' },
    timeout: 60_000,
  },
})

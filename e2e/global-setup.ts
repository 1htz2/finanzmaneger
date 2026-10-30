import fs from 'node:fs'
import path from 'node:path'

// The database folder is cleared in playwright.config.ts, before the web server starts.
export default function globalSetup() {
  fs.mkdirSync(path.resolve(import.meta.dirname, 'artifacts/shots'), { recursive: true })
}

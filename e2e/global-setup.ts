import fs from 'node:fs'
import path from 'node:path'

// Every run starts from an empty database. The web server creates it on startup,
// so the folder is cleared before Playwright launches the server.
export default function globalSetup() {
  fs.mkdirSync(path.resolve(import.meta.dirname, 'artifacts/shots'), { recursive: true })
}

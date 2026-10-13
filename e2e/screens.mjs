// Desktop + dark-mode screenshots against a demo database (manual design review aid).
import { chromium } from '@playwright/test'
const base = process.argv[2] ?? 'http://127.0.0.1:8766'
const out = 'artifacts/screens'
const browser = await chromium.launch()
for (const scheme of ['light', 'dark']) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme, locale: 'de-DE', timezoneId: 'Europe/Berlin' })
  const page = await ctx.newPage()
  await page.goto(base)
  if (await page.getByText('Willkommen').isVisible().catch(() => false)) {
    await page.getByLabel('Benutzername').fill('demo')
    await page.getByLabel('Passwort', { exact: true }).fill('demo-passwort-123')
    await page.getByLabel('Passwort wiederholen').fill('demo-passwort-123')
    await page.getByRole('button', { name: 'Konto anlegen' }).click()
  } else if (await page.getByText('Anmelden').first().isVisible().catch(() => false)) {
    await page.getByLabel('Benutzername').fill('demo')
    await page.getByLabel('Passwort').fill('demo-passwort-123')
    await page.getByRole('button', { name: 'Anmelden' }).click()
  }
  await page.getByText('Wie viel darf ich noch ausgeben?').waitFor()
  for (const [path, name] of [['/', 'dashboard'], ['/transaktionen', 'transactions'], ['/budget', 'budget'], ['/fixkosten', 'fixed'], ['/reserve', 'reserve'], ['/sparziele', 'savings'], ['/statistiken', 'stats'], ['/einstellungen', 'settings']]) {
    await page.goto(base + path)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(400)
    await page.screenshot({ path: `${out}/${scheme}-${name}.png`, fullPage: true })
  }
  await ctx.close()
}
await browser.close()
console.log('screens written')

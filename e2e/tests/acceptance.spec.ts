import { expect, test, type Page } from '@playwright/test'

// Brief section 22, steps 1-15, driven through the real UI on a phone-sized viewport.
// Step 16 (data survives a restart) is checked by scripts/verify-restart.sh.

const shot = (page: Page, name: string) => page.screenshot({ path: `artifacts/shots/${name}.png`, fullPage: true })

function berlinDate(offsetDays: number): string {
  const d = new Date(Date.now() + offsetDays * 86_400_000)
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Berlin' }).format(d)
}

const YESTERDAY = berlinDate(-1)

async function pick(page: Page, label: string | RegExp, option: string) {
  await page.getByLabel(label).click()
  await page.getByRole('option', { name: option, exact: true }).click()
}

async function goto(page: Page, area: string) {
  await page.getByRole('button', { name: 'Mehr' }).click()
  await page.getByRole('dialog').getByRole('link', { name: area }).click()
}

async function addExpense(page: Page, amount: string, category: string, description: string, when: string) {
  await page.getByRole('button', { name: 'Ausgabe erfassen' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Betrag').fill(amount)
  await pick(page, 'Kategorie', category)
  await dialog.getByLabel('Beschreibung').fill(description)
  await dialog.getByLabel('Datum und Uhrzeit').fill(when)
  await dialog.getByRole('button', { name: 'Erfassen' }).click()
  await expect(page.getByText('Buchung erfasst', { exact: true })).toBeVisible()
  await expect(dialog).toBeHidden()
}

test('acceptance flow: two salary periods, expenses, fixed costs, goals, reserve', async ({ page }) => {
  // 1-2: start and set up the login
  await page.goto('/')
  await expect(page.getByText('Willkommen')).toBeVisible()
  await page.getByLabel('Benutzername').fill('oskar')
  await page.getByLabel('Passwort', { exact: true }).fill('mein-sicheres-passwort')
  await page.getByLabel('Passwort wiederholen').fill('mein-sicheres-passwort')
  await page.getByRole('button', { name: 'Konto anlegen' }).click()
  await expect(page.getByText('Noch kein Budgetzeitraum')).toBeVisible()
  await shot(page, '01-empty-dashboard')

  // 3-4: salary of 1.300 € (received yesterday) -> automatic 20/50/30 split
  await page.getByRole('button', { name: 'Gehalt', exact: true }).click()
  let dialog = page.getByRole('dialog')
  await dialog.getByLabel('Nettogehalt').fill('1.300,00')
  await dialog.getByLabel('Geldeingang').fill(`${YESTERDAY}T09:00`)
  await dialog.getByLabel(/Erwarteter nächster Zahltag/).fill(berlinDate(28))
  await dialog.getByRole('button', { name: /Weiter zur Vorschau/ }).click()
  const split = dialog.getByRole('list')
  await expect(split).toContainText('Sparen · 20 %260,00 €')
  await expect(split).toContainText('Fixkosten · 50 %650,00 €')
  await expect(split).toContainText('Freizeit · 30 %390,00 €')
  await shot(page, '02-salary-preview')
  await dialog.getByRole('button', { name: 'Budget starten' }).click()
  await expect(dialog.getByText('Neue Budgetperiode gestartet')).toBeVisible()
  await dialog.getByRole('button', { name: 'Fertig' }).click()

  const hero = page.getByText('Freizeit · noch verfügbar').locator('..')
  await expect(hero).toContainText('390,00 €')
  await expect(page.getByText(/pro Tag/)).toBeVisible()
  await shot(page, '03-dashboard-after-salary')

  // 5: fixed costs: plan the rent and book it as paid
  await goto(page, 'Fixkosten')
  await page.getByRole('button', { name: 'Fixkosten anlegen', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Name').fill('Miete')
  await dialog.getByLabel('Betrag').fill('600')
  await pick(page, 'Kategorie', 'Miete')
  await dialog.getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(page.getByText('Gespeichert', { exact: true })).toBeVisible()
  await expect(page.getByText('Noch offen (Periode)').locator('..')).toContainText('600,00 €')
  await page.getByRole('button', { name: 'Bezahlt buchen' }).click()
  await expect(page.getByText('Miete als bezahlt gebucht', { exact: true })).toBeVisible()
  await expect(page.getByText('Noch offen (Periode)').locator('..')).toContainText('0,00 €')
  await shot(page, '04-fixed-costs')

  // 6-7: leisure expense changes the available budget
  await page.getByRole('link', { name: 'Dashboard' }).click()
  await addExpense(page, '176,40', 'Restaurants', 'Essen mit Freunden', `${YESTERDAY}T20:00`)
  await expect(hero).toContainText('213,60 €')
  await expect(page.getByText('45,2 %')).toBeVisible()
  await addExpense(page, '12,00', 'Kleidung', 'Socken', `${YESTERDAY}T21:00`)
  await expect(hero).toContainText('201,60 €')
  await shot(page, '05-dashboard-after-expenses')

  // 8: edit one expense and delete another
  await page.getByRole('link', { name: 'Buchungen' }).click()
  await page.getByRole('button', { name: /Essen mit Freunden/ }).click()
  await page.getByRole('button', { name: 'Bearbeiten', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Betrag').fill('180,00')
  await dialog.getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(page.getByText('Buchung gespeichert', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /Socken/ }).click()
  await page.getByRole('button', { name: 'Löschen', exact: true }).click()
  await page.getByRole('button', { name: 'Wirklich löschen' }).click()
  await expect(page.getByText('Ausgabe gelöscht', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /Socken/ })).toHaveCount(0)
  await shot(page, '06-transactions')

  // 9: savings goal
  await goto(page, 'Sparziele')
  await page.getByRole('button', { name: 'Sparziel', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Titel').fill('Neuer Laptop')
  await dialog.getByLabel('Zielbetrag').fill('2.000')
  await dialog.getByRole('button', { name: 'Speichern', exact: true }).click()
  await page.getByRole('button', { name: 'Geld zuweisen oder freigeben' }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Betrag').fill('100')
  await dialog.getByRole('button', { name: 'Zuweisen' }).last().click()
  await expect(page.getByText('5 %', { exact: true })).toBeVisible()
  await shot(page, '07-savings-goal')

  // 10: reserve is still empty before the first close
  await goto(page, 'Reserve')
  await expect(page.getByText('Aktuelle Reserve').locator('..')).toContainText('0,00 €')

  // 11-13: second salary closes the period; 50 € fixed + 210 € leisure go to the reserve
  await page.getByRole('button', { name: 'Gehalt', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Nettogehalt').fill('1500')
  await dialog.getByRole('button', { name: /Weiter zur Vorschau/ }).click()
  await expect(dialog.getByText('wandern in deine Reserve')).toContainText('260,00 €')
  await shot(page, '08-second-salary-preview')
  await dialog.getByRole('button', { name: 'Periode abschließen & starten' }).click()
  await expect(dialog.getByText('Neue Budgetperiode gestartet')).toBeVisible()
  await expect(dialog).toContainText('260,00 € zur Reserve')
  await dialog.getByRole('button', { name: 'Fertig' }).click()
  await expect(page.getByText('Aktuelle Reserve').locator('..')).toContainText('260,00 €')
  await expect(page.getByText('Übertrag aus Periode')).toBeVisible()
  await shot(page, '09-reserve-after-close')

  // 14: compare historical periods
  await page.getByRole('link', { name: 'Budget' }).click()
  const rows = page.locator('tbody tr')
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(1)).toContainText('+260,00 €')
  await rows.nth(1).click()
  await expect(page.getByRole('dialog')).toContainText('Zur Reserve')
  await shot(page, '10-period-detail')
  await page.keyboard.press('Escape')

  await goto(page, 'Statistiken')
  await expect(page.getByText('Ausgaben je Budgetperiode')).toBeVisible()
  await expect(page.locator('.recharts-surface').first()).toBeVisible()
  await shot(page, '11-stats')

  // 16 (in-session part): reload keeps everything
  await page.reload()
  await expect(page.getByText('Ausgaben je Budgetperiode')).toBeVisible()
  await page.getByRole('link', { name: 'Dashboard' }).click()
  await expect(page.getByText('Freizeit · noch verfügbar').locator('..')).toContainText('450,00 €')
  await shot(page, '12-dashboard-period-2')
})

test('closed-period correction asks for confirmation and books the delta', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Benutzername').fill('oskar')
  await page.getByLabel('Passwort').fill('mein-sicheres-passwort')
  await page.getByRole('button', { name: 'Anmelden' }).click()
  await expect(page.getByText('Freizeit · noch verfügbar')).toBeVisible()

  await addExpenseExpectCorrection(page)
  await goto(page, 'Reserve')
  await expect(page.getByText('Aktuelle Reserve').locator('..')).toContainText('240,00 €')
  await expect(page.getByText('Korrektur abgeschlossener Periode')).toBeVisible()
  await shot(page, '13-correction')
})

async function addExpenseExpectCorrection(page: Page) {
  await page.getByRole('button', { name: 'Ausgabe erfassen' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Betrag').fill('20')
  await pick(page, 'Kategorie', 'Kleidung')
  await dialog.getByLabel('Beschreibung').fill('Vergessene Barzahlung')
  await dialog.getByLabel('Datum und Uhrzeit').fill(`${YESTERDAY}T22:00`)
  await dialog.getByRole('button', { name: 'Erfassen' }).click()
  const confirm = page.getByRole('alertdialog')
  await expect(confirm).toContainText('Abgeschlossenen Zeitraum korrigieren?')
  await expect(confirm).toContainText('-20,00 €')
  await shot(page, '13a-correction-dialog')
  await confirm.getByRole('button', { name: 'Korrektur buchen' }).click()
  await expect(page.getByText('Buchung erfasst', { exact: true })).toBeVisible()
}

test('an expense linked to a planned fixed cost closes the plan instead of counting twice', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Benutzername').fill('oskar')
  await page.getByLabel('Passwort').fill('mein-sicheres-passwort')
  await page.getByRole('button', { name: 'Anmelden' }).click()
  await goto(page, 'Fixkosten')
  await page.getByRole('button', { name: 'Fixkosten anlegen', exact: true }).click()
  let dialog = page.getByRole('dialog')
  await dialog.getByLabel('Name').fill('Handyvertrag')
  await dialog.getByLabel('Betrag').fill('19,99')
  await pick(page, 'Kategorie', 'Handy und Internet')
  await dialog.getByRole('button', { name: 'Speichern', exact: true }).click()
  await expect(page.getByText('Noch offen (Periode)').locator('..')).toContainText('19,99 €')

  await page.getByRole('button', { name: 'Ausgabe erfassen' }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Betrag').fill('19,99')
  await pick(page, 'Kategorie', 'Handy und Internet')
  await pick(page, 'Geplante Fixkosten', 'Zahlung für „Handyvertrag“')
  await dialog.getByRole('button', { name: 'Erfassen' }).click()
  await expect(page.getByText('Buchung erfasst', { exact: true })).toBeVisible()
  await expect(page.getByText('Noch offen (Periode)').locator('..')).toContainText('0,00 €')
  await expect(page.getByText('Bezahlt (Periode)').locator('..')).toContainText('19,99 €')
  await shot(page, '14-linked-fixed-cost')
})

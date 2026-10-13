/** Display formatting only. All arithmetic happens on integer cents in the backend. */

const TZ = 'Europe/Berlin'

const eur = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' })
const eurCompact = new Intl.NumberFormat('de-DE', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

export function formatEur(cents: number): string {
  return eur.format(cents / 100)
}

export function formatEurCompact(cents: number): string {
  return eurCompact.format(Math.round(cents / 100))
}

export function formatSignedEur(cents: number): string {
  return cents > 0 ? `+${formatEur(cents)}` : formatEur(cents)
}

/** Basis points (4523) -> "45,23 %". */
export function formatPercent(bp: number | null | undefined, digits = 2): string {
  if (bp === null || bp === undefined) return '–'
  return `${(bp / 100).toLocaleString('de-DE', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} %`
}

/**
 * Parses German money input ("1.234,56", "12,5", "12") into cents without floats.
 * Returns null for anything that is not a non-negative amount with at most 2 decimals.
 */
export function parseEuroInput(raw: string): number | null {
  const s = raw.trim().replace(/\s|€/g, '')
  if (!s) return null
  // German input: "." groups thousands, "," is the decimal mark. Without a comma,
  // "2.000" is two thousand while "12.50" is read as a decimal (common on phones).
  const normalized = s.includes(',')
    ? s.replace(/\./g, '').replace(',', '.')
    : /^\d{1,3}(\.\d{3})+$/.test(s)
      ? s.replace(/\./g, '')
      : s
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(normalized)
  if (!match) return null
  const euros = Number(match[1])
  const cents = Number((match[2] ?? '').padEnd(2, '0'))
  const total = euros * 100 + cents
  return Number.isSafeInteger(total) ? total : null
}

export function centsToInput(cents: number): string {
  const euros = Math.trunc(cents / 100)
  const rest = Math.abs(cents % 100)
  return `${euros},${String(rest).padStart(2, '0')}`
}

const dateFmt = new Intl.DateTimeFormat('de-DE', { timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric' })
const shortDateFmt = new Intl.DateTimeFormat('de-DE', { timeZone: TZ, day: '2-digit', month: 'short' })
const dateTimeFmt = new Intl.DateTimeFormat('de-DE', {
  timeZone: TZ,
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})
const weekdayFmt = new Intl.DateTimeFormat('de-DE', { timeZone: TZ, weekday: 'short', day: '2-digit', month: 'short' })

/** ISO date ("2026-10-15") must not be shifted by time zones. */
function parseDateOnly(iso: string): Date {
  return new Date(`${iso}T12:00:00Z`)
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '–'
  return dateFmt.format(iso.length === 10 ? parseDateOnly(iso) : new Date(iso))
}

export function formatShortDate(iso: string): string {
  return shortDateFmt.format(iso.length === 10 ? parseDateOnly(iso) : new Date(iso))
}

export function formatDateTime(iso: string): string {
  return dateTimeFmt.format(new Date(iso))
}

export function formatWeekday(iso: string): string {
  return weekdayFmt.format(new Date(iso))
}

export function periodRange(startedAt: string, endedAt: string | null): string {
  if (!endedAt) return `seit ${formatDate(startedAt)}`
  const end = new Date(new Date(endedAt).getTime() - 1000)
  return `${formatDate(startedAt)} – ${formatDate(end.toISOString())}`
}

/** Local wall-clock value for <input type="datetime-local">, in Europe/Berlin. */
export function nowLocalInput(): string {
  const parts = new Intl.DateTimeFormat('sv-SE', {
    timeZone: TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date())
  return parts.replace(' ', 'T')
}

export function isoToLocalInput(iso: string): string {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
    .format(new Date(iso))
    .replace(' ', 'T')
}

export function todayLocal(): string {
  return nowLocalInput().slice(0, 10)
}

/** Sent without offset on purpose: the backend interprets naive times as Europe/Berlin. */
export function localInputToApi(value: string): string {
  return value.length === 16 ? `${value}:00` : value
}

/** Thin fetch client. Same origin, cookie session, CSRF double-submit header. */

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown

  constructor(status: number, code: string, message: string, details: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

function csrfToken(): string | undefined {
  return document.cookie
    .split('; ')
    .find((c) => c.startsWith('fm_csrf='))
    ?.slice('fm_csrf='.length)
}

/**
 * UUID v4 from getRandomValues. crypto.randomUUID only exists in secure contexts,
 * and a phone on plain http://192.168.x.x is not one.
 */
export function newIdempotencyKey(): string {
  const b = crypto.getRandomValues(new Uint8Array(16))
  b[6] = (b[6]! & 0x0f) | 0x40
  b[8] = (b[8]! & 0x3f) | 0x80
  const hex = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

type Query = Record<string, string | number | boolean | null | undefined>

function withQuery(path: string, query?: Query): string {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

interface RequestOptions {
  query?: Query
  body?: unknown
  idempotencyKey?: string
}

export const unauthorizedListeners = new Set<() => void>()

async function request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET') {
    const token = csrfToken()
    if (token) headers['X-CSRF-Token'] = token
  }
  if (opts.idempotencyKey) headers['Idempotency-Key'] = opts.idempotencyKey

  let response: Response
  try {
    response = await fetch(withQuery(`/api${path}`, opts.query), {
      method,
      headers,
      credentials: 'same-origin',
      cache: 'no-store',
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Server nicht erreichbar. Läuft das Backend?', null)
  }

  if (response.status === 204) return undefined as T
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const err = (payload as { error?: { code: string; message: string; details: unknown } } | null)?.error
    if (response.status === 401 && !path.startsWith('/auth/')) {
      unauthorizedListeners.forEach((fn) => fn())
    }
    throw new ApiError(
      response.status,
      err?.code ?? 'http_error',
      err?.message ?? `Fehler ${response.status}`,
      err?.details ?? null,
    )
  }
  return payload as T
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>('GET', path, { query }),
  post: <T>(path: string, body?: unknown, idempotencyKey?: string) =>
    request<T>('POST', path, { body: body ?? {}, idempotencyKey }),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, { body }),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, { body }),
  delete: <T = void>(path: string, query?: Query) => request<T>('DELETE', path, { query }),
}

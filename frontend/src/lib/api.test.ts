import { describe, expect, it } from 'vitest'

import { newIdempotencyKey } from '@/lib/api'

describe('newIdempotencyKey', () => {
  it('returns distinct RFC 4122 v4 UUIDs without crypto.randomUUID', () => {
    const original = crypto.randomUUID
    Object.defineProperty(crypto, 'randomUUID', { value: undefined, configurable: true })
    try {
      const keys = new Set(Array.from({ length: 200 }, newIdempotencyKey))
      expect(keys.size).toBe(200)
      for (const k of keys) expect(k).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
    } finally {
      Object.defineProperty(crypto, 'randomUUID', { value: original, configurable: true })
    }
  })
})

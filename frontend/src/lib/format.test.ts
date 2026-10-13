import { describe, expect, it } from 'vitest'

import { formatEur, formatPercent, parseEuroInput } from '@/lib/format'

describe('parseEuroInput', () => {
  it.each([
    ['1.300,00', 130_000],
    ['2.000', 200_000],
    ['1.234.567,89', 123_456_789],
    ['176,40', 17_640],
    ['12,5', 1_250],
    ['12.50', 1_250],
    ['1500', 150_000],
    ['  42 € ', 4_200],
    ['0', 0],
  ])('%s -> %i cents', (input, cents) => {
    expect(parseEuroInput(input)).toBe(cents)
  })

  it.each(['', 'abc', '-5', '1,234', '1.2.3', '12,345'])('rejects %j', (input) => {
    expect(parseEuroInput(input)).toBeNull()
  })
})

describe('display formatting', () => {
  it('formats cents as German euros', () => {
    expect(formatEur(21_360)).toBe('213,60 €')
    expect(formatEur(123_456_789)).toBe('1.234.567,89 €')
  })

  it('formats basis points as percent', () => {
    expect(formatPercent(4523)).toBe('45,23 %')
    expect(formatPercent(null)).toBe('–')
  })
})

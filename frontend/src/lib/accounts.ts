import { Banknote, Bitcoin, CandlestickChart, CreditCard, Landmark, Lock, Wallet, type LucideIcon } from 'lucide-react'

import type { Account, AccountKind } from '@/lib/types'

export const ACCOUNT_KINDS: Record<AccountKind, { label: string; icon: LucideIcon; investment: boolean }> = {
  savings_account: { label: 'Tagesgeld', icon: Landmark, investment: false },
  brokerage: { label: 'Depot (ETF, Aktien)', icon: CandlestickChart, investment: true },
  checking: { label: 'Girokonto', icon: CreditCard, investment: false },
  fixed_deposit: { label: 'Festgeld', icon: Lock, investment: false },
  crypto: { label: 'Krypto', icon: Bitcoin, investment: true },
  cash: { label: 'Bargeld', icon: Banknote, investment: false },
  other: { label: 'Sonstiges', icon: Wallet, investment: false },
}

/** Color follows the account, fixed at creation (dataviz categorical order, 8 slots). */
export function accountColor(account: Pick<Account, 'color_index'>): string {
  return `var(--acct-${(account.color_index % 8) + 1})`
}

export const ACCOUNT_ENTRY_LABELS: Record<string, string> = {
  auto_split: 'Sparrate',
  salary_correction: 'Gehaltskorrektur',
  assign: 'Zugeordnet',
  move: 'Verschoben',
  income: 'Einnahme',
  transfer: 'Umbuchung',
  withdrawal: 'Entnahme',
  reversal: 'Storno',
}

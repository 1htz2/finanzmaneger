import { Building2, Landmark, PiggyBank, ShieldCheck, Sparkles, Wallet } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import type { Bucket, BucketStatus, PeriodSummary, Pot } from '@/lib/types'

export const BUCKETS: Record<Bucket, { label: string; color: string; text: string; bg: string; icon: LucideIcon }> = {
  savings: { label: 'Sparen', color: 'var(--savings)', text: 'text-savings', bg: 'bg-savings', icon: PiggyBank },
  fixed: { label: 'Fixkosten', color: 'var(--fixed)', text: 'text-fixed', bg: 'bg-fixed', icon: Building2 },
  leisure: { label: 'Freizeit', color: 'var(--leisure)', text: 'text-leisure', bg: 'bg-leisure', icon: Sparkles },
}

export const BUCKET_ORDER: Bucket[] = ['leisure', 'fixed', 'savings']

export const POTS: Record<Pot, { label: string; icon: LucideIcon }> = {
  period: { label: 'Laufendes Budget', icon: Wallet },
  reserve: { label: 'Reserve', icon: ShieldCheck },
  savings: { label: 'Sparen', icon: Landmark },
}

export const INTERVAL_LABELS = { monthly: 'monatlich', quarterly: 'quartalsweise', yearly: 'jährlich' } as const

export const CATEGORY_KIND_LABELS = { leisure: 'Freizeit', fixed: 'Fixkosten', income: 'Einnahmen' } as const

export const RESERVE_KIND_LABELS: Record<string, string> = {
  period_close: 'Übertrag aus Periode',
  period_correction: 'Korrektur abgeschlossener Periode',
  deposit: 'Manuelle Zuführung',
  withdrawal: 'Entnahme',
  income: 'Einnahme',
  transfer: 'Umbuchung',
  reversal: 'Storno',
}

export const SAVINGS_KIND_LABELS: Record<string, string> = {
  period_savings: 'Sparanteil aus Gehalt',
  salary_correction: 'Gehaltskorrektur',
  income: 'Einnahme',
  transfer: 'Umbuchung',
  withdrawal: 'Entnahme',
  reversal: 'Storno',
}

export function bucketOf(period: PeriodSummary, bucket: Bucket): BucketStatus {
  return (
    period.buckets.find((b) => b.bucket === bucket) ?? {
      bucket,
      budget_cents: 0,
      spent_cents: 0,
      available_cents: 0,
      used_bp: null,
    }
  )
}


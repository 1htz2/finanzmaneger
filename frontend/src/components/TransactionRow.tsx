import { ArrowDownLeft, ArrowLeftRight, Repeat, Undo2 } from 'lucide-react'

import { Money } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { BUCKETS, POTS } from '@/lib/domain'
import { formatDateTime } from '@/lib/format'
import type { Transaction } from '@/lib/types'
import { cn } from '@/lib/utils'

export function TransactionRow({ t, onClick }: { t: Transaction; onClick?: () => void }) {
  const isExpense = t.type === 'expense'
  const isTransfer = t.type === 'transfer'
  const reversed = t.reversed_at !== null
  const color = t.category?.color ?? (t.bucket ? BUCKETS[t.bucket].color : 'var(--muted-foreground)')
  const subtitle = [
    t.category?.name,
    isTransfer && t.transfer_from && t.transfer_to
      ? `${POTS[t.transfer_from].label} → ${POTS[t.transfer_to].label}`
      : null,
    t.type === 'income' && t.income_kind === 'other' && t.income_target ? `→ ${POTS[t.income_target].label}` : null,
    t.merchant,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className="flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left transition-colors enabled:hover:bg-muted/60"
    >
      <span
        className="flex size-9 shrink-0 items-center justify-center rounded-full text-white"
        style={{ background: isExpense ? color : 'var(--muted)' }}
        aria-hidden
      >
        {isExpense ? (
          <span className="text-xs font-semibold">{(t.category?.name ?? '?').slice(0, 2)}</span>
        ) : isTransfer ? (
          <ArrowLeftRight className="size-4 text-foreground" />
        ) : (
          <ArrowDownLeft className="size-4 text-good" />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className={cn('flex items-center gap-1.5 truncate text-sm font-medium', reversed && 'line-through opacity-60')}>
          <span className="truncate">{t.description}</span>
          {(t.is_recurring || t.recurring_expense_id) && <Repeat className="size-3.5 shrink-0 text-muted-foreground" aria-label="wiederkehrend" />}
          {t.income_kind === 'salary' && <Badge variant="secondary">Gehalt</Badge>}
          {reversed && (
            <Badge variant="outline" className="no-underline">
              <Undo2 /> storniert
            </Badge>
          )}
        </span>
        <span className="block truncate text-xs text-muted-foreground">
          {formatDateTime(t.occurred_at)}
          {subtitle && ` · ${subtitle}`}
        </span>
      </span>
      <Money
        cents={isExpense ? -t.amount_cents : t.amount_cents}
        signed={!isTransfer}
        className={cn(
          'text-sm font-semibold',
          t.type === 'income' && 'text-good',
          isTransfer && 'text-muted-foreground',
          reversed && 'line-through opacity-60',
        )}
      />
    </button>
  )
}

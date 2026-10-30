import { ArrowDownUp, Filter, Pencil, Plus, Repeat, Search, Trash2, Undo2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'
import { toast } from 'sonner'

import { useActions } from '@/components/Actions'
import { EmptyState, ErrorState, LoadingState, Money, PageHeader, errorMessage } from '@/components/common'
import { useCorrection } from '@/components/CorrectionProvider'
import { MoneyInput } from '@/components/MoneyInput'
import { ResponsiveDialog } from '@/components/ResponsiveDialog'
import { TransactionRow } from '@/components/TransactionRow'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api } from '@/lib/api'
import { BUCKETS, POTS } from '@/lib/domain'
import { formatDateTime, parseEuroInput } from '@/lib/format'
import {
  useCategories,
  useDebts,
  useFinanceMutation,
  useRecurringSuggestions,
  useTransactions,
  type TransactionFilters,
} from '@/lib/queries'
import type { Transaction } from '@/lib/types'

const PAGE = 50
const ALL = 'all'

export function TransactionsPage() {
  const { addTransaction } = useActions()
  const [q, setQ] = useState('')
  const [type, setType] = useState(ALL)
  const [bucket, setBucket] = useState(ALL)
  const [categoryId, setCategoryId] = useState(ALL)
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [minAmount, setMinAmount] = useState('')
  const [maxAmount, setMaxAmount] = useState('')
  const [sort, setSort] = useState('occurred_at:desc')
  const [limit, setLimit] = useState(PAGE)
  const [showFilters, setShowFilters] = useState(false)
  const [selected, setSelected] = useState<Transaction | null>(null)
  // Set by the debts page to list the repayments of one debt.
  const [params, setParams] = useSearchParams()
  const debtId = Number(params.get('debt_id')) || undefined
  const debts = useDebts()
  const debtName = debts.data?.items.find((d) => d.id === debtId)?.name

  const [sortField, order] = sort.split(':') as [string, 'asc' | 'desc']
  const filters: TransactionFilters = useMemo(
    () => ({
      q: q || undefined,
      type: type === ALL ? undefined : type,
      bucket: bucket === ALL ? undefined : bucket,
      category_id: categoryId === ALL ? undefined : Number(categoryId),
      date_from: from || undefined,
      date_to: to || undefined,
      min_amount: parseEuroInput(minAmount) ?? undefined,
      max_amount: parseEuroInput(maxAmount) ?? undefined,
      sort: sortField,
      order,
      debt_id: debtId,
      limit,
    }),
    [q, type, bucket, categoryId, from, to, minAmount, maxAmount, sortField, order, limit, debtId],
  )
  const { data, isLoading, error, refetch, isFetching } = useTransactions(filters)
  const categories = useCategories()

  const activeFilterCount = [type, bucket, categoryId].filter((v) => v !== ALL).length + [from, to, minAmount, maxAmount].filter(Boolean).length

  function reset() {
    setType(ALL)
    setBucket(ALL)
    setCategoryId(ALL)
    setFrom('')
    setTo('')
    setMinAmount('')
    setMaxAmount('')
  }

  return (
    <div>
      <PageHeader
        title="Transaktionen"
        description="Alle Ausgaben, Einnahmen und Umbuchungen."
        actions={
          <Button onClick={() => addTransaction()}>
            <Plus /> Neue Buchung
          </Button>
        }
      />

      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setLimit(PAGE)
            }}
            placeholder="Suchen nach Beschreibung, Händler oder Kategorie"
            className="pl-9"
            aria-label="Transaktionen durchsuchen"
          />
        </div>
        <div className="flex gap-2">
          <Select value={sort} onValueChange={setSort}>
            <SelectTrigger className="w-full sm:w-48" aria-label="Sortierung">
              <ArrowDownUp className="size-4" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="occurred_at:desc">Neueste zuerst</SelectItem>
              <SelectItem value="occurred_at:asc">Älteste zuerst</SelectItem>
              <SelectItem value="amount_cents:desc">Höchster Betrag</SelectItem>
              <SelectItem value="amount_cents:asc">Niedrigster Betrag</SelectItem>
              <SelectItem value="description:asc">Beschreibung A–Z</SelectItem>
            </SelectContent>
          </Select>
          <Button variant={showFilters ? 'secondary' : 'outline'} onClick={() => setShowFilters((s) => !s)}>
            <Filter /> Filter {activeFilterCount > 0 && <Badge>{activeFilterCount}</Badge>}
          </Button>
        </div>
      </div>

      {debtId !== undefined && (
        <div className="mb-4 flex items-center gap-2 text-sm">
          <Badge variant="secondary" className="gap-1.5 py-1">
            Rückzahlungen: {debtName ?? 'Schuld'}
            <button type="button" aria-label="Filter entfernen" onClick={() => setParams({})} className="rounded-full hover:text-foreground">
              <X className="size-3.5" />
            </button>
          </Badge>
        </div>
      )}

      {showFilters && (
        <Card className="mb-4">
          <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <FilterSelect label="Typ" value={type} onChange={setType} options={[['expense', 'Ausgaben'], ['income', 'Einnahmen'], ['transfer', 'Umbuchungen']]} />
            <FilterSelect label="Topf" value={bucket} onChange={setBucket} options={[['leisure', 'Freizeit'], ['fixed', 'Fixkosten']]} />
            <FilterSelect
              label="Kategorie"
              value={categoryId}
              onChange={setCategoryId}
              options={(categories.data ?? []).map((c) => [String(c.id), c.name])}
            />
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label htmlFor="f-min">Betrag ab</Label>
                <MoneyInput id="f-min" value={minAmount} onChange={(e) => setMinAmount(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="f-max">bis</Label>
                <MoneyInput id="f-max" value={maxAmount} onChange={(e) => setMaxAmount(e.target.value)} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="f-from">Von</Label>
              <Input id="f-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="f-to">Bis</Label>
              <Input id="f-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
            </div>
            <div className="flex items-end">
              <Button variant="ghost" onClick={reset} disabled={activeFilterCount === 0}>
                <X /> Filter zurücksetzen
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <LoadingState />
      ) : error || !data ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{data.total} Buchungen</CardTitle>
            <CardDescription>
              Ausgaben <Money cents={data.expense_sum_cents} /> · Einnahmen <Money cents={data.income_sum_cents} />
            </CardDescription>
          </CardHeader>
          <CardContent className="px-3">
            {data.items.length === 0 ? (
              <EmptyState title="Keine Buchungen gefunden" text="Passe Suche oder Filter an oder erfasse eine neue Buchung." />
            ) : (
              <div className="divide-y">
                {data.items.map((t) => (
                  <TransactionRow key={t.id} t={t} onClick={() => setSelected(t)} />
                ))}
              </div>
            )}
            {data.items.length < data.total && (
              <div className="mt-3 flex justify-center">
                <Button variant="outline" onClick={() => setLimit((l) => l + PAGE)} disabled={isFetching}>
                  Mehr laden
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <RecurringSuggestions />
      <TransactionDetail t={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: string[][]
}) {
  const id = `f-${label}`
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Alle</SelectItem>
          {options.map(([v, l]) => (
            <SelectItem key={v} value={v!}>
              {l}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function TransactionDetail({ t, onClose }: { t: Transaction | null; onClose: () => void }) {
  const { editTransaction } = useActions()
  const runCorrection = useCorrection()
  const [confirmDelete, setConfirmDelete] = useState(false)

  const remove = useFinanceMutation((txn: Transaction) =>
    runCorrection((flags) =>
      api.delete(`/transactions/${txn.id}`, {
        confirm_correction: flags.confirm_correction,
        correction_reason: flags.correction_reason,
      }).then(() => true),
    ),
  )
  const reverse = useFinanceMutation((txn: Transaction) =>
    runCorrection((flags) => api.post<Transaction>(`/transactions/${txn.id}/reverse`, flags)),
  )

  if (!t) return null
  const canReverse = t.type !== 'expense' && t.income_kind !== 'salary' && !t.reversed_at

  function done(msg: string) {
    return (result: unknown) => {
      if (result === undefined) return
      toast.success(msg)
      setConfirmDelete(false)
      onClose()
    }
  }

  return (
    <ResponsiveDialog
      open={t !== null}
      onOpenChange={(o) => {
        if (!o) {
          setConfirmDelete(false)
          onClose()
        }
      }}
      title={t.description}
      description={formatDateTime(t.occurred_at)}
      footer={
        <div className="flex w-full flex-col gap-2 sm:flex-row sm:justify-end">
          {!t.reversed_at && (
            <Button
              variant="outline"
              onClick={() => {
                onClose()
                editTransaction(t)
              }}
            >
              <Pencil /> Bearbeiten
            </Button>
          )}
          {canReverse && (
            <Button
              variant="outline"
              disabled={reverse.isPending}
              onClick={() => reverse.mutate(t, { onSuccess: done('Buchung storniert'), onError: (e) => toast.error(errorMessage(e)) })}
            >
              <Undo2 /> Stornieren
            </Button>
          )}
          {t.type === 'expense' &&
            (confirmDelete ? (
              <Button
                variant="destructive"
                disabled={remove.isPending}
                onClick={() => remove.mutate(t, { onSuccess: done('Ausgabe gelöscht'), onError: (e) => toast.error(errorMessage(e)) })}
              >
                <Trash2 /> Wirklich löschen
              </Button>
            ) : (
              <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
                <Trash2 /> Löschen
              </Button>
            ))}
        </div>
      }
    >
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="text-muted-foreground">Betrag</dt>
        <dd className="text-right font-semibold">
          <Money cents={t.amount_cents} />
        </dd>
        <dt className="text-muted-foreground">Typ</dt>
        <dd className="text-right">
          {t.type === 'expense' ? 'Ausgabe' : t.type === 'income' ? (t.income_kind === 'salary' ? 'Gehalt' : 'Einnahme') : 'Umbuchung'}
        </dd>
        {t.bucket && (
          <>
            <dt className="text-muted-foreground">Topf</dt>
            <dd className="text-right">{BUCKETS[t.bucket].label}</dd>
          </>
        )}
        {t.category && (
          <>
            <dt className="text-muted-foreground">Kategorie</dt>
            <dd className="text-right">{t.category.name}</dd>
          </>
        )}
        {t.transfer_from && t.transfer_to && (
          <>
            <dt className="text-muted-foreground">Umbuchung</dt>
            <dd className="text-right">
              {POTS[t.transfer_from].label} → {POTS[t.transfer_to].label}
            </dd>
          </>
        )}
        {t.income_target && t.income_kind === 'other' && (
          <>
            <dt className="text-muted-foreground">Zugeordnet zu</dt>
            <dd className="text-right">{POTS[t.income_target].label}</dd>
          </>
        )}
        {t.merchant && (
          <>
            <dt className="text-muted-foreground">Händler</dt>
            <dd className="text-right">{t.merchant}</dd>
          </>
        )}
        <dt className="text-muted-foreground">Erfasst</dt>
        <dd className="text-right">{formatDateTime(t.created_at)}</dd>
        {t.updated_at !== t.created_at && (
          <>
            <dt className="text-muted-foreground">Geändert</dt>
            <dd className="text-right">{formatDateTime(t.updated_at)}</dd>
          </>
        )}
      </dl>
      {confirmDelete && (
        <p className="mt-4 rounded-lg bg-destructive/10 p-3 text-sm">Die Ausgabe wird endgültig gelöscht und das Budget entsprechend angepasst.</p>
      )}
    </ResponsiveDialog>
  )
}

function RecurringSuggestions() {
  const { data } = useRecurringSuggestions()
  const mark = useFinanceMutation((ids: number[]) => api.post('/transactions/mark-recurring', { transaction_ids: ids, is_recurring: true }))
  const open = (data ?? []).filter((s) => s.occurrences > 0)
  if (open.length === 0) return null
  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Repeat className="size-4" /> Mögliche wiederkehrende Zahlungen
        </CardTitle>
        <CardDescription>Ähnliche Ausgaben in mehreren Budgetperioden.</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y">
          {open.slice(0, 6).map((s) => (
            <li key={s.label} className="flex items-center gap-3 py-2.5 text-sm">
              <span className="flex-1">
                <span className="font-medium">{s.label}</span>
                <span className="block text-xs text-muted-foreground">
                  {s.occurrences}× in {s.periods} Perioden · typisch <Money cents={s.typical_amount_cents} />
                </span>
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => mark.mutate(s.transaction_ids, { onSuccess: () => toast.success('Als wiederkehrend markiert') })}
              >
                Markieren
              </Button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

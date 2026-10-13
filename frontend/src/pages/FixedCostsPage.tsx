import { CheckCircle2, CircleDashed, Pencil, Plus, Trash2, TriangleAlert } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { UsageBar } from '@/components/charts'
import { EmptyState, ErrorState, LoadingState, Money, PageHeader, StatTile, errorMessage } from '@/components/common'
import { useCorrection } from '@/components/CorrectionProvider'
import { MoneyInput } from '@/components/MoneyInput'
import { ResponsiveDialog } from '@/components/ResponsiveDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { api, newIdempotencyKey } from '@/lib/api'
import { INTERVAL_LABELS } from '@/lib/domain'
import { centsToInput, formatDate, formatPercent, parseEuroInput } from '@/lib/format'
import { useCategories, useFinanceMutation, useRecurring, useRecurringOverview } from '@/lib/queries'
import type { Interval, RecurringExpense, RecurringPlanItem, Transaction } from '@/lib/types'
import { cn } from '@/lib/utils'

export function FixedCostsPage() {
  const overview = useRecurringOverview()
  const all = useRecurring()
  const [editing, setEditing] = useState<RecurringExpense | 'new' | null>(null)

  const inactive = (all.data ?? []).filter((r) => !r.active)
  const ov = overview.data

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fixkosten"
        description="Geplante regelmäßige Kosten. Sie zählen erst als Ausgabe, wenn du sie als bezahlt buchst."
        actions={
          <Button onClick={() => setEditing('new')}>
            <Plus /> Fixkosten anlegen
          </Button>
        }
      />

      {overview.isLoading ? (
        <LoadingState />
      ) : overview.error || !ov ? (
        <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="Monatlich (Ø)" value={<Money cents={ov.monthly_total_cents} />} hint="inkl. anteiliger Jahreskosten" />
            <StatTile label="Pro Jahr" value={<Money cents={ov.yearly_total_cents} />} />
            <StatTile label="Bezahlt (Periode)" value={<Money cents={ov.paid_in_period_cents} />} />
            <StatTile label="Noch offen (Periode)" value={<Money cents={ov.open_in_period_cents} />} />
          </div>

          {ov.has_active_period && (
            <Card>
              <CardHeader>
                <CardTitle>Reicht das Fixkostenbudget?</CardTitle>
                <CardDescription>
                  Zeitraum {formatDate(ov.window_start)} bis {formatDate(ov.window_end)}
                  {ov.window_estimated && ' (angenommen ein Monat, da kein Zahltag hinterlegt ist)'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <UsageBar bucket="fixed" usedBp={ov.fixed_budget_cents ? Math.round(((ov.fixed_spent_cents + ov.open_in_period_cents) * 10_000) / ov.fixed_budget_cents) : null} />
                <div className="grid gap-2 text-sm sm:grid-cols-4">
                  <div>
                    <div className="text-xs text-muted-foreground">Fixkostenbudget</div>
                    <Money cents={ov.fixed_budget_cents} className="font-semibold" />
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Tatsächlich gebucht</div>
                    <Money cents={ov.fixed_spent_cents} className="font-semibold" />
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Verplant</div>
                    <Money cents={ov.planned_in_period_cents} className="font-semibold" /> <span className="text-xs text-muted-foreground">({formatPercent(ov.planned_share_bp, 0)})</span>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Noch offen</div>
                    <Money cents={ov.open_in_period_cents} className="font-semibold" />
                  </div>
                </div>
                {ov.sufficient ? (
                  <p className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="size-4 text-good" /> Das Budget reicht für gebuchte und offene Fixkosten.
                  </p>
                ) : (
                  <p className="flex items-center gap-2 text-sm">
                    <TriangleAlert className="size-4 text-critical" /> Es fehlen <Money cents={ov.shortfall_cents} className="font-semibold" /> im Fixkostenbudget.
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Aktive Fixkosten</CardTitle>
            </CardHeader>
            <CardContent className="px-3 sm:px-6">
              {ov.items.length === 0 ? (
                <EmptyState
                  title="Noch keine Fixkosten"
                  text="Zum Beispiel Miete, Krankenversicherung, Handyvertrag oder Abos."
                  action={
                    <Button variant="outline" onClick={() => setEditing('new')}>
                      <Plus /> Erste Fixkosten anlegen
                    </Button>
                  }
                />
              ) : (
                <ul className="divide-y">
                  {ov.items.map((item) => (
                    <PlanRow key={item.expense.id} item={item} hasPeriod={ov.has_active_period} onEdit={() => setEditing(item.expense)} />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <SinkingFunds items={ov.items} />
        </>
      )}

      {inactive.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Inaktiv</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y text-sm">
              {inactive.map((r) => (
                <li key={r.id} className="flex items-center gap-3 py-2">
                  <span className="flex-1 text-muted-foreground">{r.name}</span>
                  <Money cents={r.amount_cents} />
                  <Button variant="ghost" size="icon-sm" aria-label="Bearbeiten" onClick={() => setEditing(r)}>
                    <Pencil />
                  </Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <RecurringDialog value={editing} onClose={() => setEditing(null)} />
    </div>
  )
}

function PlanRow({ item, hasPeriod, onEdit }: { item: RecurringPlanItem; hasPeriod: boolean; onEdit: () => void }) {
  const r = item.expense
  const runCorrection = useCorrection()
  const [key] = useState(newIdempotencyKey)
  const pay = useFinanceMutation(() =>
    runCorrection((flags) => api.post<Transaction>(`/recurring-expenses/${r.id}/pay`, flags, `${key}-${item.paid_count}`)),
  )
  const paidAll = item.open_count === 0 && item.paid_count > 0
  return (
    <li className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center">
      <div className="flex flex-1 items-start gap-3">
        <span className="mt-1.5 size-2.5 shrink-0 rounded-full" style={{ background: r.category.color ?? 'var(--fixed)' }} />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 font-medium">
            {r.name}
            <Badge variant="outline">{INTERVAL_LABELS[r.interval]}</Badge>
            {paidAll && (
              <Badge variant="secondary">
                <CheckCircle2 className="text-good" /> bezahlt
              </Badge>
            )}
            {item.open_count > 0 && (
              <Badge variant="secondary">
                <CircleDashed /> offen
              </Badge>
            )}
          </div>
          <div className="text-xs text-muted-foreground">
            {r.category.name}
            {r.interval !== 'monthly' && (
              <>
                {' '}· rechnerisch <Money cents={r.monthly_equivalent_cents} /> pro Monat
              </>
            )}
            {item.next_due_date && <> · nächste Fälligkeit {formatDate(item.next_due_date)}</>}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 pl-5 sm:pl-0">
        <Money cents={r.amount_cents} className="mr-2 font-semibold" />
        {hasPeriod && item.open_count > 0 && (
          <Button
            size="sm"
            variant="outline"
            disabled={pay.isPending}
            onClick={() =>
              pay.mutate(undefined, {
                onSuccess: (res) => res && toast.success(`${r.name} als bezahlt gebucht`),
                onError: (e) => toast.error(errorMessage(e)),
              })
            }
          >
            Bezahlt buchen
          </Button>
        )}
        <Button variant="ghost" size="icon-sm" aria-label="Bearbeiten" onClick={onEdit}>
          <Pencil />
        </Button>
      </div>
    </li>
  )
}

function SinkingFunds({ items }: { items: RecurringPlanItem[] }) {
  const funds = items.filter((i) => i.expense.interval !== 'monthly')
  if (funds.length === 0) return null
  const total = funds.reduce((sum, i) => sum + i.expense.monthly_equivalent_cents, 0)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Rücklage für seltene Zahlungen</CardTitle>
        <CardDescription>
          Wer monatlich <Money cents={total} /> zurücklegt, hat jährliche und quartalsweise Kosten gedeckt, wenn sie fällig werden.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y text-sm">
          {funds.map((i) => (
            <li key={i.expense.id} className="flex items-center gap-3 py-2">
              <span className="flex-1">
                {i.expense.name}
                <span className="block text-xs text-muted-foreground">
                  <Money cents={i.expense.amount_cents} /> {INTERVAL_LABELS[i.expense.interval]}
                </span>
              </span>
              <span className="text-right">
                <Money cents={i.expense.monthly_equivalent_cents} className="font-medium" />
                <span className="block text-xs text-muted-foreground">pro Monat</span>
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

function RecurringDialog({ value, onClose }: { value: RecurringExpense | 'new' | null; onClose: () => void }) {
  const editing = value !== null && value !== 'new' ? value : null
  const categories = useCategories()
  const [name, setName] = useState('')
  const [amount, setAmount] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [interval, setInterval] = useState<Interval>('monthly')
  const [dueDate, setDueDate] = useState('')
  const [active, setActive] = useState(true)
  const [description, setDescription] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)

  const [lastValue, setLastValue] = useState<typeof value>(null)
  if (value !== lastValue) {
    setLastValue(value)
    setConfirmDelete(false)
    setName(editing?.name ?? '')
    setAmount(editing ? centsToInput(editing.amount_cents) : '')
    setCategoryId(editing ? String(editing.category.id) : '')
    setInterval(editing?.interval ?? 'monthly')
    setDueDate(editing?.due_date ?? '')
    setActive(editing?.active ?? true)
    setDescription(editing?.description ?? '')
  }

  const save = useFinanceMutation(async () => {
    const cents = parseEuroInput(amount)
    if (!cents) throw new Error('Bitte einen gültigen Betrag eingeben')
    if (!categoryId) throw new Error('Bitte eine Kategorie wählen')
    const body = {
      name,
      amount_cents: cents,
      category_id: Number(categoryId),
      interval,
      due_date: dueDate || null,
      active,
      description: description || null,
    }
    if (editing) {
      return api.patch(`/recurring-expenses/${editing.id}`, { ...body, clear_due_date: !dueDate })
    }
    return api.post('/recurring-expenses', body)
  })
  const remove = useFinanceMutation(() => api.delete(`/recurring-expenses/${editing!.id}`))

  function submit(e: FormEvent) {
    e.preventDefault()
    save.mutate(undefined, {
      onSuccess: () => {
        toast.success('Gespeichert')
        onClose()
      },
      onError: (err) => toast.error(errorMessage(err)),
    })
  }

  return (
    <ResponsiveDialog
      open={value !== null}
      onOpenChange={(o) => !o && onClose()}
      title={editing ? 'Fixkosten bearbeiten' : 'Fixkosten anlegen'}
      footer={
        <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          {editing && (
            <Button
              variant="destructive"
              onClick={() =>
                confirmDelete
                  ? remove.mutate(undefined, { onSuccess: () => { toast.success('Gelöscht'); onClose() } })
                  : setConfirmDelete(true)
              }
            >
              <Trash2 /> {confirmDelete ? 'Wirklich löschen' : 'Löschen'}
            </Button>
          )}
          <Button type="submit" form="rec-form" disabled={save.isPending}>
            Speichern
          </Button>
        </div>
      }
    >
      <form id="rec-form" onSubmit={submit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="rec-name">Name</Label>
          <Input id="rec-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={128} placeholder="z. B. Miete" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="rec-amount">Betrag</Label>
            <MoneyInput id="rec-amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="rec-interval">Intervall</Label>
            <Select value={interval} onValueChange={(v) => setInterval(v as Interval)}>
              <SelectTrigger id="rec-interval" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="monthly">monatlich</SelectItem>
                <SelectItem value="quarterly">quartalsweise</SelectItem>
                <SelectItem value="yearly">jährlich</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="rec-category">Kategorie</Label>
          <Select value={categoryId} onValueChange={setCategoryId}>
            <SelectTrigger id="rec-category" className="w-full">
              <SelectValue placeholder="Kategorie wählen" />
            </SelectTrigger>
            <SelectContent>
              {(categories.data ?? [])
                .filter((c) => c.kind === 'fixed' && (!c.archived || String(c.id) === categoryId))
                .map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.name}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="rec-due">Fällig am (optional)</Label>
          <Input id="rec-due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          <p className="text-xs text-muted-foreground">Ein Fälligkeitsdatum; die App rechnet die weiteren Termine im Intervall weiter.</p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="rec-desc">Beschreibung (optional)</Label>
          <Textarea id="rec-desc" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} />
        </div>
        <label className={cn('flex items-center justify-between rounded-lg border p-3 text-sm')}>
          Aktiv
          <Switch checked={active} onCheckedChange={setActive} />
        </label>
      </form>
    </ResponsiveDialog>
  )
}

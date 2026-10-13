import { Banknote, CalendarClock, ChevronRight, History, PencilLine, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { useActions } from '@/components/Actions'
import { UsageBar } from '@/components/charts'
import { EmptyState, ErrorState, LoadingState, Money, PageHeader, errorMessage } from '@/components/common'
import { MoneyInput } from '@/components/MoneyInput'
import { ResponsiveDialog } from '@/components/ResponsiveDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, newIdempotencyKey } from '@/lib/api'
import { BUCKET_ORDER, BUCKETS, bucketOf } from '@/lib/domain'
import { centsToInput, formatDate, formatDateTime, formatPercent, parseEuroInput, periodRange } from '@/lib/format'
import { useActivePeriod, useFinanceMutation, usePeriod, usePeriods } from '@/lib/queries'
import type { Allocation, PeriodDetail, PeriodSummary } from '@/lib/types'
import { cn } from '@/lib/utils'

const SOURCE_LABELS: Record<Allocation['source'], string> = {
  salary: 'Gehalt',
  salary_correction: 'Gehaltskorrektur',
  income: 'Weitere Einnahme',
  transfer: 'Umbuchung',
  reversal: 'Storno',
}

export function BudgetPage() {
  const active = useActivePeriod()
  const periods = usePeriods()
  const { recordSalary } = useActions()
  const [detailId, setDetailId] = useState<number | null>(null)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Budget"
        description="Jeder Gehaltseingang startet einen neuen Budgetzeitraum. Nicht verbrauchtes Geld wandert beim Abschluss in die Reserve."
        actions={
          <Button onClick={recordSalary}>
            <Banknote /> Gehalt erfassen
          </Button>
        }
      />

      {active.isLoading ? (
        <LoadingState rows={2} />
      ) : active.error ? (
        <ErrorState error={active.error} onRetry={() => active.refetch()} />
      ) : active.data ? (
        <ActivePeriod period={active.data} />
      ) : (
        <EmptyState
          icon={<Banknote />}
          title="Kein aktiver Budgetzeitraum"
          text="Erfasse deinen Gehaltseingang, um zu starten."
          action={<Button onClick={recordSalary}>Gehalt erfassen</Button>}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="size-4" /> Alle Budgetzeiträume
          </CardTitle>
          <CardDescription>Vergleich nach tatsächlichen Gehaltsperioden, nicht nach Kalendermonaten.</CardDescription>
        </CardHeader>
        <CardContent className="px-0 sm:px-6">
          {periods.isLoading ? (
            <LoadingState rows={2} />
          ) : periods.error ? (
            <ErrorState error={periods.error} onRetry={() => periods.refetch()} />
          ) : (periods.data ?? []).length === 0 ? (
            <EmptyState title="Noch keine Zeiträume" />
          ) : (
            <PeriodTable periods={periods.data ?? []} onOpen={setDetailId} />
          )}
        </CardContent>
      </Card>

      <PeriodDetailDialog id={detailId} onClose={() => setDetailId(null)} />
    </div>
  )
}

function PeriodTable({ periods, onOpen }: { periods: PeriodSummary[]; onOpen: (id: number) => void }) {
  return (
    <>
    <ul className="divide-y sm:hidden">
      {periods.map((p) => (
        <li key={p.id}>
          <button type="button" onClick={() => onOpen(p.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm">
            <span className="flex-1">
              <span className="flex items-center gap-2 font-medium">
                {periodRange(p.started_at, p.ended_at)}
                {p.status === 'active' && <Badge variant="secondary">aktiv</Badge>}
              </span>
              <span className="block text-xs text-muted-foreground">
                Gehalt <Money cents={p.net_salary_cents + p.extra_income_cents} /> · ausgegeben <Money cents={p.spent_cents} /> · Sparquote{' '}
                {p.actual_savings_rate_bp === null ? 'läuft' : formatPercent(p.actual_savings_rate_bp, 1)}
              </span>
            </span>
            <Money cents={p.leftover_cents} signed className={cn('font-semibold', p.leftover_cents < 0 && 'text-critical')} />
            <ChevronRight className="size-4 text-muted-foreground" />
          </button>
        </li>
      ))}
    </ul>
    <div className="hidden overflow-x-auto sm:block">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="px-4 py-2 font-medium sm:px-2">Zeitraum</th>
            <th className="px-2 py-2 text-right font-medium">Gehalt</th>
            <th className="px-2 py-2 text-right font-medium">Fixkosten</th>
            <th className="px-2 py-2 text-right font-medium">Freizeit</th>
            <th className="px-2 py-2 text-right font-medium">Ergebnis</th>
            <th className="px-2 py-2 text-right font-medium">Sparquote</th>
            <th className="w-8" />
          </tr>
        </thead>
        <tbody>
          {periods.map((p) => (
            <tr key={p.id} className="cursor-pointer border-b last:border-0 hover:bg-muted/50" onClick={() => onOpen(p.id)}>
              <td className="px-4 py-3 sm:px-2">
                <div className="font-medium">{periodRange(p.started_at, p.ended_at)}</div>
                {p.status === 'active' && <Badge variant="secondary">aktiv</Badge>}
              </td>
              <td className="px-2 text-right">
                <Money cents={p.net_salary_cents + p.extra_income_cents} />
              </td>
              <td className="px-2 text-right">
                <Money cents={bucketOf(p, 'fixed').spent_cents} />
              </td>
              <td className="px-2 text-right">
                <Money cents={bucketOf(p, 'leisure').spent_cents} />
              </td>
              <td className={cn('px-2 text-right font-medium', p.leftover_cents < 0 && 'text-critical')}>
                <Money cents={p.leftover_cents} signed />
              </td>
              <td className="px-2 text-right">
                {p.actual_savings_rate_bp === null ? (
                  <span className="text-muted-foreground">läuft</span>
                ) : (
                  formatPercent(p.actual_savings_rate_bp, 1)
                )}
              </td>
              <td className="pr-2">
                <ChevronRight className="size-4 text-muted-foreground" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    </>
  )
}

function ActivePeriod({ period }: { period: PeriodDetail }) {
  const [paydayOpen, setPaydayOpen] = useState(false)
  const [salaryOpen, setSalaryOpen] = useState(false)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Aktueller Zeitraum {periodRange(period.started_at, null)}</CardTitle>
        <CardDescription>
          Nettogehalt <Money cents={period.net_salary_cents} />
          {period.extra_income_cents !== 0 && (
            <>
              {' '}· weitere Einnahmen <Money cents={period.extra_income_cents} />
            </>
          )}
          {period.transfer_net_cents !== 0 && (
            <>
              {' '}· Umbuchungen <Money cents={period.transfer_net_cents} signed />
            </>
          )}
        </CardDescription>
        <CardAction>
          <Button variant="ghost" size="sm" onClick={() => setSalaryOpen(true)}>
            <PencilLine /> Gehalt korrigieren
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 md:grid-cols-3">
          {BUCKET_ORDER.map((b) => {
            const s = bucketOf(period, b)
            const meta = BUCKETS[b]
            return (
              <div key={b} className="space-y-2 rounded-xl border p-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <span className="size-2.5 rounded-full" style={{ background: meta.color }} />
                  {meta.label}
                </div>
                <Money cents={b === 'savings' ? s.budget_cents : s.available_cents} className="block text-2xl font-semibold" />
                <UsageBar bucket={b} usedBp={b === 'savings' ? 10_000 : s.used_bp} />
                <p className="text-xs text-muted-foreground">
                  {b === 'savings' ? (
                    'zurückgelegt beim Gehaltseingang'
                  ) : (
                    <>
                      verfügbar · <Money cents={s.spent_cents} /> von <Money cents={s.budget_cents} /> ({formatPercent(s.used_bp)})
                    </>
                  )}
                </p>
              </div>
            )
          })}
        </div>

        <div className="flex flex-col gap-3 rounded-xl bg-muted/50 p-4 sm:flex-row sm:items-center">
          <CalendarClock className="size-5 shrink-0 text-muted-foreground" />
          <div className="flex-1 text-sm">
            {period.expected_next_payday ? (
              <>Erwarteter nächster Zahltag: <span className="font-medium">{formatDate(period.expected_next_payday)}</span></>
            ) : (
              <>Kein erwarteter Zahltag hinterlegt. Mit Datum zeigt das Dashboard ein Tages- und Wochenbudget.</>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={() => setPaydayOpen(true)}>
            {period.expected_next_payday ? 'Ändern' : 'Zahltag eintragen'}
          </Button>
        </div>

        <div>
          <h3 className="mb-2 text-sm font-medium">Zusammensetzung des Budgets</h3>
          <AllocationList allocations={period.allocations} />
        </div>
      </CardContent>
      <PaydayDialog open={paydayOpen} onOpenChange={setPaydayOpen} current={period.expected_next_payday} />
      <SalaryCorrectionDialog open={salaryOpen} onOpenChange={setSalaryOpen} current={period.net_salary_cents} />
    </Card>
  )
}

function AllocationList({ allocations }: { allocations: Allocation[] }) {
  return (
    <ul className="divide-y rounded-lg border text-sm">
      {allocations.map((a) => (
        <li key={a.id} className="flex items-center gap-3 px-3 py-2">
          <span className="size-2 rounded-full" style={{ background: BUCKETS[a.bucket].color }} />
          <span className="flex-1">
            {BUCKETS[a.bucket].label} · {SOURCE_LABELS[a.source]}
            {a.note && <span className="block text-xs text-muted-foreground">{a.note}</span>}
          </span>
          <Money cents={a.amount_cents} signed className="font-medium" />
        </li>
      ))}
    </ul>
  )
}

function PaydayDialog({ open, onOpenChange, current }: { open: boolean; onOpenChange: (o: boolean) => void; current: string | null }) {
  const [value, setValue] = useState(current ?? '')
  const save = useFinanceMutation((date: string | null) => api.put('/periods/active/expected-payday', { expected_next_payday: date }))
  function submit(e: FormEvent) {
    e.preventDefault()
    save.mutate(value || null, {
      onSuccess: () => {
        toast.success('Zahltag gespeichert')
        onOpenChange(false)
      },
      onError: (err) => toast.error(errorMessage(err)),
    })
  }
  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={(o) => {
        if (o) setValue(current ?? '')
        onOpenChange(o)
      }}
      title="Erwarteter nächster Zahltag"
      description="Nur eine Planungshilfe. Die Periode endet erst, wenn du das nächste Gehalt erfasst."
      footer={
        <div className="flex w-full gap-2 sm:w-auto">
          {current && (
            <Button variant="ghost" onClick={() => save.mutate(null, { onSuccess: () => onOpenChange(false) })}>
              Entfernen
            </Button>
          )}
          <Button type="submit" form="payday-form" disabled={save.isPending} className="flex-1">
            Speichern
          </Button>
        </div>
      }
    >
      <form id="payday-form" onSubmit={submit} className="space-y-1.5">
        <Label htmlFor="payday">Datum</Label>
        <Input id="payday" type="date" value={value} onChange={(e) => setValue(e.target.value)} required />
      </form>
    </ResponsiveDialog>
  )
}

function SalaryCorrectionDialog({ open, onOpenChange, current }: { open: boolean; onOpenChange: (o: boolean) => void; current: number }) {
  const [amount, setAmount] = useState(centsToInput(current))
  const [reason, setReason] = useState('')
  const save = useFinanceMutation((body: { amount_cents: number; reason: string }) => api.put('/periods/active/salary', body))
  function submit(e: FormEvent) {
    e.preventDefault()
    const cents = parseEuroInput(amount)
    if (!cents) return toast.error('Bitte einen gültigen Betrag eingeben')
    save.mutate(
      { amount_cents: cents, reason },
      {
        onSuccess: () => {
          toast.success('Gehalt korrigiert, Budget neu aufgeteilt')
          onOpenChange(false)
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    )
  }
  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={(o) => {
        if (o) {
          setAmount(centsToInput(current))
          setReason('')
        }
        onOpenChange(o)
      }}
      title="Gehalt korrigieren"
      description="Für Tippfehler im aktuellen Zeitraum. Die Differenz wird als Korrekturbuchung nachvollziehbar verteilt."
      footer={
        <Button type="submit" form="salary-corr-form" disabled={save.isPending}>
          Korrektur buchen
        </Button>
      }
    >
      <form id="salary-corr-form" onSubmit={submit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="corr-amount">Richtiges Nettogehalt</Label>
          <MoneyInput id="corr-amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="corr-reason">Grund</Label>
          <Input id="corr-reason" value={reason} onChange={(e) => setReason(e.target.value)} required placeholder="z. B. Tippfehler" />
        </div>
      </form>
    </ResponsiveDialog>
  )
}

function PeriodDetailDialog({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { data, isLoading } = usePeriod(id)
  const [key] = useState(newIdempotencyKey)
  const cover = useFinanceMutation((periodId: number) => api.post(`/periods/${periodId}/cover-deficit`, {}, `${key}-${periodId}`))
  return (
    <ResponsiveDialog open={id !== null} onOpenChange={(o) => !o && onClose()} title={data ? `Zeitraum ${periodRange(data.started_at, data.ended_at)}` : 'Zeitraum'} wide>
      {isLoading || !data ? (
        <LoadingState rows={2} />
      ) : (
        <div className="space-y-5 text-sm">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Kpi label="Gehalt" cents={data.net_salary_cents} />
            <Kpi label="Ausgaben" cents={data.spent_cents} />
            <Kpi label={data.status === 'closed' ? 'Zur Reserve' : 'Rest bisher'} cents={data.status === 'closed' ? data.reserve_transfer_cents : data.leftover_cents} />
            <div className="rounded-lg border p-3">
              <div className="text-xs text-muted-foreground">Sparquote</div>
              <div className="font-semibold">
                {data.actual_savings_rate_bp === null ? 'läuft' : formatPercent(data.actual_savings_rate_bp, 1)}
              </div>
              <div className="text-xs text-muted-foreground">geplant {formatPercent(data.planned_savings_rate_bp, 0)}</div>
            </div>
          </div>

          {data.deficit_cents > 0 && (
            <div className="flex flex-col gap-2 rounded-lg bg-critical/10 p-3 sm:flex-row sm:items-center">
              <span className="flex-1">
                Defizit von <Money cents={data.deficit_cents} className="font-semibold" />. Es wurde nichts in die Reserve übertragen.
              </span>
              {data.status === 'closed' && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={cover.isPending}
                  onClick={() =>
                    cover.mutate(data.id, {
                      onSuccess: () => toast.success('Defizit aus der Reserve gedeckt'),
                      onError: (e) => toast.error(errorMessage(e)),
                    })
                  }
                >
                  <ShieldCheck /> Bewusst aus Reserve decken
                </Button>
              )}
            </div>
          )}

          <div className="space-y-2">
            {BUCKET_ORDER.map((b) => {
              const s = bucketOf(data, b)
              return (
                <div key={b} className="flex items-center gap-3">
                  <span className="w-24 shrink-0">{BUCKETS[b].label}</span>
                  <div className="flex-1">
                    <UsageBar bucket={b} usedBp={b === 'savings' ? 10_000 : s.used_bp} />
                  </div>
                  <span className="w-44 shrink-0 text-right text-xs text-muted-foreground">
                    {b === 'savings' ? <Money cents={s.budget_cents} /> : <><Money cents={s.spent_cents} /> / <Money cents={s.budget_cents} /></>}
                  </span>
                </div>
              )
            })}
          </div>

          <div>
            <h3 className="mb-2 font-medium">Zusammensetzung</h3>
            <AllocationList allocations={data.allocations} />
          </div>

          {data.corrections.length > 0 && (
            <div>
              <h3 className="mb-2 font-medium">Nachträgliche Korrekturen</h3>
              <ul className="divide-y rounded-lg border">
                {data.corrections.map((c) => (
                  <li key={c.id} className="flex items-start gap-3 px-3 py-2">
                    <span className="flex-1">
                      {c.reason}
                      <span className="block text-xs text-muted-foreground">
                        {formatDateTime(c.created_at)} · Ergebnis <Money cents={c.leftover_before_cents} signed /> → <Money cents={c.leftover_after_cents} signed />
                      </span>
                    </span>
                    <Money cents={c.reserve_delta_cents} signed className="font-medium" />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </ResponsiveDialog>
  )
}

function Kpi({ label, cents }: { label: string; cents: number }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <Money cents={cents} className="font-semibold" />
    </div>
  )
}

import { Archive, CalendarCheck, HandCoins, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { useActions } from '@/components/Actions'
import { ProgressBar } from '@/components/charts'
import { EmptyState, ErrorState, LoadingState, Money, PageHeader, StatTile, errorMessage } from '@/components/common'
import { MoneyInput } from '@/components/MoneyInput'
import { ResponsiveDialog } from '@/components/ResponsiveDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { api, newIdempotencyKey } from '@/lib/api'
import { centsToInput, formatDate, formatPercent, parseEuroInput } from '@/lib/format'
import { useCategories, useDebts, useFinanceMutation } from '@/lib/queries'
import type { Debt } from '@/lib/types'

const RATE_CATEGORY = 'Kredite und Raten'

export function DebtsPage() {
  const { data, isLoading, error, refetch } = useDebts()
  const categories = useCategories()
  const { addTransaction } = useActions()
  const [editing, setEditing] = useState<Debt | 'new' | null>(null)
  const [session, setSession] = useState(0)

  if (isLoading) return <LoadingState rows={3} />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />

  const open = data.items.filter((d) => !d.archived && d.status === 'open')
  const done = data.items.filter((d) => d.archived || d.status === 'paid_off')
  const rateCategory = categories.data?.find((c) => c.kind === 'fixed' && c.name === RATE_CATEGORY && !c.archived)

  function edit(value: Debt | 'new') {
    setSession((n) => n + 1)
    setEditing(value)
  }

  function pay(d: Debt) {
    addTransaction({
      tab: 'expense',
      presetDebtId: d.id,
      presetCategoryId: rateCategory?.id,
      presetAmountCents: d.monthly_rate_cents ? Math.min(d.monthly_rate_cents, d.remaining_cents) : undefined,
      presetDescription: `Rate ${d.name}`,
    })
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Schulden"
        description="Was du anderen schuldest. Raten buchst du als normale Ausgabe, sie senken automatisch die Restschuld."
        actions={
          <Button onClick={() => edit('new')}>
            <Plus /> Schuld erfassen
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile label="Restschuld gesamt" icon={<HandCoins />} value={<Money cents={data.total_remaining_cents} />} />
        <StatTile label="Raten pro Monat" value={<Money cents={data.total_monthly_rate_cents} />} hint="laut deinen Angaben" />
        <StatTile label="Getilgt in dieser Periode" value={<Money cents={data.repaid_this_period_cents} />} />
      </div>

      {open.length === 0 ? (
        <EmptyState
          icon={<HandCoins />}
          title={done.length > 0 ? 'Keine offenen Schulden' : 'Noch keine Schulden erfasst'}
          text="Zum Beispiel ein Autokredit, ein Ratenkauf, ein Dispo oder Geld, das dir jemand geliehen hat."
          action={
            <Button onClick={() => edit('new')}>
              <Plus /> Schuld erfassen
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {open.map((d) => (
            <DebtCard key={d.id} debt={d} onEdit={() => edit(d)} onPay={() => pay(d)} />
          ))}
        </div>
      )}

      {done.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Abbezahlt und archiviert</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y text-sm">
              {done.map((d) => (
                <li key={d.id} className="flex items-center gap-3 py-2">
                  <span className="flex-1">
                    <span className="font-medium">{d.name}</span>
                    {d.status === 'paid_off' && <Badge className="ml-2 bg-good text-white">abbezahlt</Badge>}
                    {d.archived && d.status === 'open' && (
                      <span className="block text-xs text-muted-foreground">
                        archiviert, Rest <Money cents={d.remaining_cents} />
                      </span>
                    )}
                  </span>
                  <Money cents={d.original_cents} className="text-muted-foreground" />
                  <Button size="icon-sm" variant="ghost" aria-label={`${d.name} bearbeiten`} onClick={() => edit(d)}>
                    <Pencil />
                  </Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <DebtDialog key={`debt-${session}`} value={editing} onClose={() => setEditing(null)} />
    </div>
  )
}

function DebtCard({ debt, onEdit, onPay }: { debt: Debt; onEdit: () => void; onPay: () => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{debt.name}</CardTitle>
        <CardDescription>
          {debt.creditor ? `bei ${debt.creditor} · ` : ''}
          ursprünglich <Money cents={debt.original_cents} />
        </CardDescription>
        <CardAction>
          <Button variant="ghost" size="icon-sm" aria-label={`${debt.name} bearbeiten`} onClick={onEdit}>
            <Pencil />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <div className="text-xs text-muted-foreground">Restschuld</div>
          <Money cents={debt.remaining_cents} className="block text-2xl font-semibold tracking-tight" />
        </div>
        <ProgressBar bp={debt.progress_bp} color="var(--good)" label={`${debt.name} getilgt`} />
        <div className="flex justify-between text-sm">
          <span className="font-medium">{formatPercent(debt.progress_bp, 0)} getilgt</span>
          {debt.repayment_count > 0 && (
            <Link to={`/transaktionen?debt_id=${debt.id}`} className="text-muted-foreground underline-offset-4 hover:underline">
              {debt.repayment_count} {debt.repayment_count === 1 ? 'Rückzahlung' : 'Rückzahlungen'}
            </Link>
          )}
        </div>
        <dl className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg bg-muted/60 p-2">
            <dt className="text-muted-foreground">Monatliche Rate</dt>
            <dd className="font-medium">{debt.monthly_rate_cents ? <Money cents={debt.monthly_rate_cents} /> : '–'}</dd>
            {debt.planned_recurring_ids.length > 0 && <dd className="text-muted-foreground">in Fixkosten geplant</dd>}
          </div>
          <div className="rounded-lg bg-muted/60 p-2">
            <dt className="flex items-center gap-1 text-muted-foreground">
              <CalendarCheck className="size-3" /> Schuldenfrei
            </dt>
            <dd className="font-medium">{debt.projected_payoff ? `ca. ${formatDate(debt.projected_payoff)}` : '–'}</dd>
            {!debt.projected_payoff && <dd className="text-muted-foreground">Rate angeben für Prognose</dd>}
          </div>
        </dl>
        <Button variant="outline" className="w-full" onClick={onPay}>
          <HandCoins /> Rückzahlung buchen
        </Button>
      </CardContent>
    </Card>
  )
}

function DebtDialog({ value, onClose }: { value: Debt | 'new' | null; onClose: () => void }) {
  const debt = value !== null && value !== 'new' ? value : null
  // Fresh state per dialog session: the page remounts this component with a new key on each open.
  const [name, setName] = useState(debt?.name ?? '')
  const [creditor, setCreditor] = useState(debt?.creditor ?? '')
  const [original, setOriginal] = useState(debt ? centsToInput(debt.original_cents) : '')
  const [opening, setOpening] = useState(debt ? centsToInput(debt.opening_balance_cents) : '')
  const [rate, setRate] = useState(debt?.monthly_rate_cents ? centsToInput(debt.monthly_rate_cents) : '')
  const [note, setNote] = useState(debt?.note ?? '')
  const [planRate, setPlanRate] = useState(false)
  const [dueDate, setDueDate] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [key] = useState(newIdempotencyKey)

  const save = useFinanceMutation(() => {
    const originalCents = parseEuroInput(original)
    if (!originalCents) throw new Error('Bitte den ursprünglichen Betrag eingeben')
    const openingCents = opening.trim() === '' ? null : parseEuroInput(opening)
    if (opening.trim() !== '' && openingCents === null) throw new Error('Bitte eine gültige Restschuld eingeben')
    const rateCents = rate.trim() === '' ? null : parseEuroInput(rate)
    if (rate.trim() !== '' && !rateCents) throw new Error('Bitte eine gültige Rate eingeben')
    const body = {
      name,
      creditor: creditor.trim() || null,
      original_cents: originalCents,
      opening_balance_cents: openingCents ?? (debt ? undefined : null),
      monthly_rate_cents: rateCents,
      note: note.trim() || null,
    }
    if (debt) return api.patch(`/debts/${debt.id}`, body)
    return api.post('/debts', { ...body, plan_rate: planRate && rateCents !== null, rate_due_date: dueDate || null }, key)
  })
  const archive = useFinanceMutation(() => api.patch(`/debts/${debt!.id}`, { archived: !debt!.archived }))
  const remove = useFinanceMutation(() => api.delete(`/debts/${debt!.id}`))
  const done = (msg: string) => () => {
    toast.success(msg)
    onClose()
  }
  const fail = (err: unknown) => toast.error(errorMessage(err))
  const canDelete = debt !== null && debt.repayment_count === 0

  return (
    <ResponsiveDialog
      open={value !== null}
      onOpenChange={(o) => !o && onClose()}
      title={debt ? 'Schuld bearbeiten' : 'Schuld erfassen'}
      description={
        debt
          ? debt.repayment_count > 0
            ? 'Schulden mit Rückzahlungen werden archiviert statt gelöscht, damit die Buchungen nachvollziehbar bleiben.'
            : undefined
          : 'Erfasse, was du noch schuldest. Rückzahlungen buchst du später als Ausgabe.'
      }
      footer={
        <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          {debt && (
            <Button variant="ghost" onClick={() => archive.mutate(undefined, { onSuccess: done(debt.archived ? 'Reaktiviert' : 'Archiviert'), onError: fail })}>
              <Archive /> {debt.archived ? 'Reaktivieren' : 'Archivieren'}
            </Button>
          )}
          {canDelete && (
            <Button
              variant="destructive"
              onClick={() => (confirmDelete ? remove.mutate(undefined, { onSuccess: done('Schuld gelöscht'), onError: fail }) : setConfirmDelete(true))}
            >
              <Trash2 /> {confirmDelete ? 'Wirklich löschen' : 'Löschen'}
            </Button>
          )}
          <Button type="submit" form="debt-form" disabled={save.isPending}>
            Speichern
          </Button>
        </div>
      }
    >
      <form
        id="debt-form"
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          save.mutate(undefined, { onSuccess: done(debt ? 'Schuld gespeichert' : 'Schuld erfasst'), onError: fail })
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="debt-name">Bezeichnung</Label>
            <Input id="debt-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={128} placeholder="z. B. Autokredit" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="debt-creditor">Bei wem (optional)</Label>
            <Input id="debt-creditor" value={creditor} onChange={(e) => setCreditor(e.target.value)} maxLength={128} placeholder="z. B. Bank, Eltern" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="debt-original">Ursprünglicher Betrag</Label>
            <MoneyInput id="debt-original" value={original} onChange={(e) => setOriginal(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="debt-opening">Noch offen bei Erfassung</Label>
            <MoneyInput id="debt-opening" value={opening} onChange={(e) => setOpening(e.target.value)} placeholder={debt ? undefined : 'leer = voller Betrag'} />
            <p className="text-xs text-muted-foreground">Für Kredite, die du schon länger abzahlst.</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="debt-rate">Monatliche Rate (optional)</Label>
            <MoneyInput id="debt-rate" value={rate} onChange={(e) => setRate(e.target.value)} />
          </div>
        </div>
        {!debt && rate.trim() !== '' && (
          <div className="space-y-3 rounded-lg border p-3">
            <label className="flex items-center justify-between gap-3">
              <span className="text-sm">
                Rate als Fixkosten einplanen
                <span className="block text-xs text-muted-foreground">Erscheint monatlich unter Fixkosten. „Als bezahlt buchen“ tilgt die Schuld.</span>
              </span>
              <Switch checked={planRate} onCheckedChange={setPlanRate} />
            </label>
            {planRate && (
              <div className="space-y-1.5">
                <Label htmlFor="debt-due">Nächste Fälligkeit (optional)</Label>
                <Input id="debt-due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
              </div>
            )}
          </div>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="debt-note">Notiz (optional)</Label>
          <Textarea id="debt-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={2} />
        </div>
      </form>
    </ResponsiveDialog>
  )
}

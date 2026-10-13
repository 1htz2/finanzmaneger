import { Archive, ArrowUpFromLine, CalendarCheck, Pencil, PiggyBank, Plus, Target, Trash2 } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { BalanceChart, UsageBar } from '@/components/charts'
import { EmptyState, ErrorState, LoadingState, Money, PageHeader, StatTile, errorMessage } from '@/components/common'
import { MoneyInput } from '@/components/MoneyInput'
import { ResponsiveDialog } from '@/components/ResponsiveDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, newIdempotencyKey } from '@/lib/api'
import { SAVINGS_KIND_LABELS } from '@/lib/domain'
import { centsToInput, formatDate, formatDateTime, formatPercent, parseEuroInput } from '@/lib/format'
import { useFinanceMutation, useSavings } from '@/lib/queries'
import type { Goal } from '@/lib/types'
import { cn } from '@/lib/utils'

export function SavingsPage() {
  const { data, isLoading, error, refetch } = useSavings()
  const [goalDialog, setGoalDialog] = useState<Goal | 'new' | null>(null)
  const [allocate, setAllocate] = useState<Goal | null>(null)
  const [withdrawOpen, setWithdrawOpen] = useState(false)

  if (isLoading) return <LoadingState rows={3} />
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />
  const goals = data.goals.filter((g) => !g.archived)
  const archived = data.goals.filter((g) => g.archived)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sparziele"
        description="Dein Erspartes aus dem 20-%-Sparanteil und zusätzlichen Einzahlungen. Sparziele reservieren einen Teil davon, sie erzeugen kein zusätzliches Geld."
        actions={
          <>
            <Button variant="outline" onClick={() => setWithdrawOpen(true)}>
              <ArrowUpFromLine /> Entnehmen
            </Button>
            <Button onClick={() => setGoalDialog('new')}>
              <Plus /> Sparziel
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile label="Ersparnisse gesamt" icon={<PiggyBank />} value={<Money cents={data.balance_cents} />} />
        <StatTile label="In Sparzielen" icon={<Target />} value={<Money cents={data.allocated_cents} />} />
        <StatTile label="Frei verfügbar" value={<Money cents={data.unallocated_cents} />} hint="noch keinem Ziel zugewiesen" />
      </div>

      {goals.length === 0 ? (
        <EmptyState
          icon={<Target />}
          title="Noch keine Sparziele"
          text="Zum Beispiel Notfallreserve 3.000 €, neuer Laptop 2.000 € oder Urlaub 1.500 €."
          action={
            <Button onClick={() => setGoalDialog('new')}>
              <Plus /> Erstes Sparziel anlegen
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {goals.map((g) => (
            <GoalCard key={g.id} goal={g} onAllocate={() => setAllocate(g)} onEdit={() => setGoalDialog(g)} />
          ))}
        </div>
      )}

      {data.history.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Entwicklung der Ersparnisse</CardTitle>
          </CardHeader>
          <CardContent>
            <BalanceChart points={data.history} name="Ersparnisse" color="var(--savings)" />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Bewegungen</CardTitle>
        </CardHeader>
        <CardContent>
          {data.entries.length === 0 ? (
            <EmptyState title="Noch keine Bewegungen" text="Mit jedem Gehaltseingang werden 20 % hier zurückgelegt." />
          ) : (
            <ul className="divide-y text-sm">
              {data.entries.slice(0, 50).map((e) => (
                <li key={e.id} className="flex items-start gap-3 py-2.5">
                  <span className="flex-1">
                    <span className="font-medium">{SAVINGS_KIND_LABELS[e.kind] ?? e.kind}</span>
                    <span className="block text-xs text-muted-foreground">
                      {formatDateTime(e.occurred_at)}
                      {e.note && ` · ${e.note}`}
                    </span>
                  </span>
                  <Money cents={e.amount_cents} signed className={cn('font-semibold', e.amount_cents > 0 && 'text-good')} />
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {archived.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Archiviert</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y text-sm">
              {archived.map((g) => (
                <li key={g.id} className="flex items-center gap-3 py-2">
                  <span className="flex-1 text-muted-foreground">{g.title}</span>
                  <Money cents={g.saved_cents} />
                  <Button size="icon-sm" variant="ghost" aria-label="Bearbeiten" onClick={() => setGoalDialog(g)}>
                    <Pencil />
                  </Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <GoalDialog value={goalDialog} onClose={() => setGoalDialog(null)} />
      <AllocateDialog goal={allocate} free={data.unallocated_cents} onClose={() => setAllocate(null)} />
      <WithdrawDialog open={withdrawOpen} goals={goals} free={data.unallocated_cents} onClose={() => setWithdrawOpen(false)} />
    </div>
  )
}

function GoalCard({ goal, onAllocate, onEdit }: { goal: Goal; onAllocate: () => void; onEdit: () => void }) {
  const reached = goal.remaining_cents === 0
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {goal.title} {reached && <Badge className="bg-good text-white">erreicht</Badge>}
        </CardTitle>
        <CardDescription>
          <Money cents={goal.saved_cents} /> von <Money cents={goal.target_cents} />
        </CardDescription>
        <CardAction>
          <Button variant="ghost" size="icon-sm" aria-label="Bearbeiten" onClick={onEdit}>
            <Pencil />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        <UsageBar bucket="savings" usedBp={goal.progress_bp} />
        <div className="flex justify-between text-sm">
          <span className="font-medium">{formatPercent(goal.progress_bp, 0)}</span>
          <span className="text-muted-foreground">
            noch <Money cents={goal.remaining_cents} />
          </span>
        </div>
        <dl className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg bg-muted/60 p-2">
            <dt className="text-muted-foreground">Zieldatum</dt>
            <dd className="font-medium">{goal.target_date ? formatDate(goal.target_date) : '–'}</dd>
            {goal.required_per_month_cents !== null && (
              <dd className="text-muted-foreground">
                <Money cents={goal.required_per_month_cents} /> / Monat nötig
              </dd>
            )}
          </div>
          <div className="rounded-lg bg-muted/60 p-2">
            <dt className="flex items-center gap-1 text-muted-foreground">
              <CalendarCheck className="size-3" /> Prognose
            </dt>
            <dd className="font-medium">{reached ? 'erreicht' : goal.projected_date ? formatDate(goal.projected_date) : 'noch keine'}</dd>
            {!reached && !goal.projected_date && <dd className="text-muted-foreground">braucht etwas Sparverlauf</dd>}
          </div>
        </dl>
        <Button variant="outline" className="w-full" onClick={onAllocate}>
          Geld zuweisen oder freigeben
        </Button>
      </CardContent>
    </Card>
  )
}

function GoalDialog({ value, onClose }: { value: Goal | 'new' | null; onClose: () => void }) {
  const goal = value !== null && value !== 'new' ? value : null
  const [title, setTitle] = useState('')
  const [target, setTarget] = useState('')
  const [date, setDate] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [last, setLast] = useState<typeof value>(null)
  if (value !== last) {
    setLast(value)
    setTitle(goal?.title ?? '')
    setTarget(goal ? centsToInput(goal.target_cents) : '')
    setDate(goal?.target_date ?? '')
    setConfirmDelete(false)
  }

  const save = useFinanceMutation(() => {
    const cents = parseEuroInput(target)
    if (!cents) throw new Error('Bitte einen gültigen Zielbetrag eingeben')
    const body = { title, target_cents: cents, target_date: date || null }
    return goal ? api.patch(`/savings/goals/${goal.id}`, body) : api.post('/savings/goals', body)
  })
  const archive = useFinanceMutation(() => api.patch(`/savings/goals/${goal!.id}`, { archived: !goal!.archived }))
  const remove = useFinanceMutation(() => api.delete(`/savings/goals/${goal!.id}`))
  const close = (msg: string) => () => {
    toast.success(msg)
    onClose()
  }

  return (
    <ResponsiveDialog
      open={value !== null}
      onOpenChange={(o) => !o && onClose()}
      title={goal ? 'Sparziel bearbeiten' : 'Neues Sparziel'}
      description={goal && goal.saved_cents > 0 ? 'Beim Löschen wird das zugewiesene Geld wieder frei, es geht nichts verloren.' : undefined}
      footer={
        <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          {goal && (
            <>
              <Button variant="ghost" onClick={() => archive.mutate(undefined, { onSuccess: close(goal.archived ? 'Reaktiviert' : 'Archiviert') })}>
                <Archive /> {goal.archived ? 'Reaktivieren' : 'Archivieren'}
              </Button>
              <Button
                variant="destructive"
                onClick={() => (confirmDelete ? remove.mutate(undefined, { onSuccess: close('Sparziel gelöscht') }) : setConfirmDelete(true))}
              >
                <Trash2 /> {confirmDelete ? 'Wirklich löschen' : 'Löschen'}
              </Button>
            </>
          )}
          <Button type="submit" form="goal-form" disabled={save.isPending}>
            Speichern
          </Button>
        </div>
      }
    >
      <form
        id="goal-form"
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          save.mutate(undefined, { onSuccess: close('Sparziel gespeichert'), onError: (err) => toast.error(errorMessage(err)) })
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="goal-title">Titel</Label>
          <Input id="goal-title" value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={128} placeholder="z. B. Neuer Laptop" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="goal-target">Zielbetrag</Label>
          <MoneyInput id="goal-target" value={target} onChange={(e) => setTarget(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="goal-date">Zieldatum (optional)</Label>
          <Input id="goal-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
      </form>
    </ResponsiveDialog>
  )
}

function AllocateDialog({ goal, free, onClose }: { goal: Goal | null; free: number; onClose: () => void }) {
  const [direction, setDirection] = useState<'add' | 'release'>('add')
  const [amount, setAmount] = useState('')
  const key = useMemo(() => (goal ? newIdempotencyKey() : ''), [goal])
  const save = useFinanceMutation(() => {
    const cents = parseEuroInput(amount)
    if (!cents) throw new Error('Bitte einen gültigen Betrag eingeben')
    return api.post(`/savings/goals/${goal!.id}/allocate`, { amount_cents: direction === 'add' ? cents : -cents }, key)
  })
  return (
    <ResponsiveDialog
      open={goal !== null}
      onOpenChange={(o) => {
        if (!o) {
          setAmount('')
          setDirection('add')
          onClose()
        }
      }}
      title={goal?.title ?? ''}
      description={
        direction === 'add' ? (
          <>Frei verfügbar: <Money cents={free} /></>
        ) : (
          <>Im Ziel angespart: <Money cents={goal?.saved_cents ?? 0} /></>
        )
      }
      footer={
        <Button type="submit" form="alloc-form" disabled={save.isPending}>
          {direction === 'add' ? 'Zuweisen' : 'Freigeben'}
        </Button>
      }
    >
      <form
        id="alloc-form"
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate(undefined, {
            onSuccess: () => {
              toast.success('Gespeichert')
              setAmount('')
              onClose()
            },
            onError: (err) => toast.error(errorMessage(err)),
          })
        }}
      >
        <Tabs value={direction} onValueChange={(v) => setDirection(v as 'add' | 'release')}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="add">Zuweisen</TabsTrigger>
            <TabsTrigger value="release">Freigeben</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="space-y-1.5">
          <Label htmlFor="alloc-amount">Betrag</Label>
          <MoneyInput id="alloc-amount" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
        </div>
      </form>
    </ResponsiveDialog>
  )
}

function WithdrawDialog({ open, goals, free, onClose }: { open: boolean; goals: Goal[]; free: number; onClose: () => void }) {
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [goalId, setGoalId] = useState('none')
  const key = useMemo(() => (open ? newIdempotencyKey() : ''), [open])
  const save = useFinanceMutation(() => {
    const cents = parseEuroInput(amount)
    if (!cents) throw new Error('Bitte einen gültigen Betrag eingeben')
    return api.post('/savings/withdraw', { amount_cents: cents, reason, goal_id: goalId === 'none' ? null : Number(goalId) }, key)
  })
  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title="Aus Ersparnissen entnehmen"
      description={<>Zum Beispiel für den Kauf, auf den du gespart hast. Frei verfügbar: <Money cents={free} /></>}
      footer={
        <Button type="submit" form="sw-form" disabled={save.isPending}>
          Entnehmen
        </Button>
      }
    >
      <form
        id="sw-form"
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate(undefined, {
            onSuccess: () => {
              toast.success('Entnahme gebucht')
              setAmount('')
              setReason('')
              setGoalId('none')
              onClose()
            },
            onError: (err) => toast.error(errorMessage(err)),
          })
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="sw-amount">Betrag</Label>
          <MoneyInput id="sw-amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sw-goal">Aus Sparziel</Label>
          <Select value={goalId} onValueChange={setGoalId}>
            <SelectTrigger id="sw-goal" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Freies Erspartes</SelectItem>
              {goals.map((g) => (
                <SelectItem key={g.id} value={String(g.id)}>
                  {g.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sw-reason">Grund</Label>
          <Input id="sw-reason" value={reason} onChange={(e) => setReason(e.target.value)} required maxLength={255} />
        </div>
      </form>
    </ResponsiveDialog>
  )
}

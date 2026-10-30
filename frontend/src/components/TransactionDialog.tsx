import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { errorMessage } from '@/components/common'
import { useCorrection } from '@/components/CorrectionProvider'
import { AccountPicker, NO_ACCOUNT, accountIdOrNull } from '@/components/AccountPicker'
import { MoneyInput } from '@/components/MoneyInput'
import { ResponsiveDialog } from '@/components/ResponsiveDialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, newIdempotencyKey } from '@/lib/api'
import { POTS } from '@/lib/domain'
import {
  centsToInput,
  formatEur,
  isoToLocalInput,
  localInputToApi,
  nowLocalInput,
  parseEuroInput,
} from '@/lib/format'
import { useCategories, useDebts, useFinanceMutation, useGoals, useRecurring } from '@/lib/queries'
import type { Pot, SpendingBucket, Transaction } from '@/lib/types'

export type TxTab = 'expense' | 'income' | 'transfer'

export interface TransactionDialogState {
  open: boolean
  tab?: TxTab
  edit?: Transaction
  presetCategoryId?: number
  presetDebtId?: number
  presetAmountCents?: number
  presetDescription?: string
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  )
}

export function TransactionDialog({
  state,
  onOpenChange,
}: {
  state: TransactionDialogState
  onOpenChange: (open: boolean) => void
}) {
  const edit = state.edit
  // Fresh state per dialog session: the provider remounts this component with a new key on each open.
  const [tab, setTab] = useState<TxTab>(edit?.type ?? state.tab ?? 'expense')
  const [amount, setAmount] = useState(
    edit ? centsToInput(edit.amount_cents) : state.presetAmountCents ? centsToInput(state.presetAmountCents) : '',
  )
  const [categoryId, setCategoryId] = useState<string>(
    edit?.category ? String(edit.category.id) : state.presetCategoryId ? String(state.presetCategoryId) : '',
  )
  const [description, setDescription] = useState(edit?.description ?? state.presetDescription ?? '')
  const [merchant, setMerchant] = useState(edit?.merchant ?? '')
  const [when, setWhen] = useState(edit ? isoToLocalInput(edit.occurred_at) : nowLocalInput())
  const [whenEdited, setWhenEdited] = useState(false)
  const [isRecurring, setIsRecurring] = useState(edit?.is_recurring ?? false)
  const [target, setTarget] = useState<Pot>('period')
  const [bucket, setBucket] = useState<SpendingBucket>('leisure')
  const [fromPot, setFromPot] = useState<Pot>('reserve')
  const [toPot, setToPot] = useState<Pot>('savings')
  const [goalId, setGoalId] = useState<string>('none')
  const [accountId, setAccountId] = useState<string>(NO_ACCOUNT)
  const [recurringId, setRecurringId] = useState<string>(edit?.recurring_expense_id ? String(edit.recurring_expense_id) : 'none')
  const [debtId, setDebtId] = useState<string>(
    edit?.debt_id ? String(edit.debt_id) : state.presetDebtId ? String(state.presetDebtId) : 'none',
  )
  const [invalid, setInvalid] = useState(false)
  const [idempotencyKey] = useState(newIdempotencyKey)

  const categories = useCategories()
  const goals = useGoals()
  const recurring = useRecurring()
  const debts = useDebts()
  const debtChoices = (debts.data?.items ?? []).filter(
    (d) => (!d.archived && d.status === 'open') || String(d.id) === debtId,
  )
  // Linking a booked payment to its planned fixed cost keeps it from being counted twice.
  const plansForCategory = (recurring.data ?? []).filter(
    (r) => r.active && categoryId !== '' && String(r.category.id) === categoryId,
  )
  const runCorrection = useCorrection()


  const active = (categories.data ?? []).filter((c) => !c.archived || String(c.id) === categoryId)
  const leisureCats = active.filter((c) => c.kind === 'leisure')
  const fixedCats = active.filter((c) => c.kind === 'fixed')
  const incomeCats = active.filter((c) => c.kind === 'income' && c.name !== 'Gehalt')

  const linkedPlan =
    recurringId !== 'none' && plansForCategory.some((r) => String(r.id) === recurringId) ? Number(recurringId) : null

  const mutation = useFinanceMutation(async () => {
    const cents = parseEuroInput(amount)
    if (cents === null || cents === 0) {
      setInvalid(true)
      throw new Error('Bitte einen gültigen Betrag eingeben, z. B. 12,50')
    }
    // An untouched time on a new booking means "now", to the second. The input only
    // shows minutes, and rounding down could place it before a salary booked moments ago.
    const occurred_at = !edit && !whenEdited ? new Date().toISOString() : localInputToApi(when)
    if (edit) {
      const body =
        edit.type === 'expense'
          ? {
              amount_cents: cents,
              category_id: Number(categoryId),
              description,
              merchant: merchant || null,
              occurred_at,
              is_recurring: isRecurring,
              debt_id: debtId === 'none' ? null : Number(debtId),
            }
          : { description, ...(categoryId ? { category_id: Number(categoryId) } : {}) }
      return runCorrection((flags) => api.patch<Transaction>(`/transactions/${edit.id}`, { ...body, ...flags }))
    }
    if (tab === 'expense') {
      if (!categoryId) throw new Error('Bitte eine Kategorie wählen')
      return runCorrection((flags) =>
        api.post<Transaction>(
          '/transactions',
          {
            amount_cents: cents,
            category_id: Number(categoryId),
            description: description || categories.data?.find((c) => String(c.id) === categoryId)?.name,
            merchant: merchant || null,
            occurred_at,
            is_recurring: isRecurring,
            recurring_expense_id: linkedPlan,
            debt_id: debtId === 'none' ? null : Number(debtId),
            ...flags,
          },
          idempotencyKey,
        ),
      )
    }
    if (tab === 'income') {
      return runCorrection((flags) =>
        api.post<Transaction>(
          '/incomes',
          {
            amount_cents: cents,
            category_id: categoryId ? Number(categoryId) : null,
            description: description || 'Einnahme',
            occurred_at,
            target,
            bucket,
            account_id: target === 'savings' ? accountIdOrNull(accountId) : null,
            ...flags,
          },
          idempotencyKey,
        ),
      )
    }
    const involvesPeriod = fromPot === 'period' || toPot === 'period'
    return api.post<Transaction>(
      '/transfers',
      {
        from_pot: fromPot,
        to_pot: toPot,
        amount_cents: cents,
        bucket: involvesPeriod ? bucket : null,
        savings_goal_id: fromPot === 'savings' && goalId !== 'none' ? Number(goalId) : null,
        account_id: fromPot === 'savings' || toPot === 'savings' ? accountIdOrNull(accountId) : null,
        note: description || null,
      },
      idempotencyKey,
    )
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    mutation.mutate(undefined, {
      onSuccess: (result) => {
        if (result === undefined) return
        toast.success(edit ? 'Buchung gespeichert' : 'Buchung erfasst')
        onOpenChange(false)
      },
      onError: (err) => toast.error(errorMessage(err)),
    })
  }

  const title = edit
    ? 'Buchung bearbeiten'
    : tab === 'expense'
      ? 'Neue Ausgabe'
      : tab === 'income'
        ? 'Weitere Einnahme'
        : 'Umbuchung'
  const moneyLocked = edit !== undefined && edit.type !== 'expense'

  return (
    <ResponsiveDialog
      open={state.open}
      onOpenChange={onOpenChange}
      title={title}
      description={
        tab === 'income' && !edit
          ? 'Erstattungen, Geschenke oder Nebeneinkommen. Ein Gehalt erfasst du über „Gehalt erfassen“.'
          : tab === 'transfer' && !edit
            ? 'Verschiebt Geld zwischen Töpfen. Das ist weder Einnahme noch Ausgabe.'
            : moneyLocked
              ? 'Betrag und Datum von Einnahmen und Umbuchungen sind fest. Zum Ändern stornieren und neu erfassen.'
              : undefined
      }
      footer={
        <Button type="submit" form="tx-form" size="lg" className="w-full sm:w-auto" disabled={mutation.isPending}>
          {mutation.isPending ? 'Speichert …' : edit ? 'Speichern' : 'Erfassen'}
        </Button>
      }
    >
      <form id="tx-form" onSubmit={submit} className="space-y-4">
        {!edit && (
          <Tabs value={tab} onValueChange={(v) => setTab(v as TxTab)}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="expense">Ausgabe</TabsTrigger>
              <TabsTrigger value="income">Einnahme</TabsTrigger>
              <TabsTrigger value="transfer">Umbuchung</TabsTrigger>
            </TabsList>
          </Tabs>
        )}

        <Field label="Betrag" htmlFor="tx-amount">
          <MoneyInput
            id="tx-amount"
            value={amount}
            onChange={(e) => {
              setAmount(e.target.value)
              setInvalid(false)
            }}
            invalid={invalid}
            disabled={moneyLocked}
            autoFocus={!edit}
            className="h-12 text-lg font-semibold"
          />
        </Field>

        {tab === 'transfer' && !edit ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Von" htmlFor="tx-from">
                <Select value={fromPot} onValueChange={(v) => setFromPot(v as Pot)}>
                  <SelectTrigger id="tx-from" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(POTS) as Pot[]).map((p) => (
                      <SelectItem key={p} value={p}>
                        {POTS[p].label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Nach" htmlFor="tx-to">
                <Select value={toPot} onValueChange={(v) => setToPot(v as Pot)}>
                  <SelectTrigger id="tx-to" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(POTS) as Pot[])
                      .filter((p) => p !== fromPot)
                      .map((p) => (
                        <SelectItem key={p} value={p}>
                          {POTS[p].label}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </Field>
            </div>
            {(fromPot === 'period' || toPot === 'period') && (
              <BucketSelect value={bucket} onChange={setBucket} label="Budget-Topf" />
            )}
            {fromPot === 'savings' && (goals.data?.length ?? 0) > 0 && (
              <Field label="Aus Sparziel lösen (optional)" htmlFor="tx-goal">
                <Select value={goalId} onValueChange={setGoalId}>
                  <SelectTrigger id="tx-goal" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Freies Erspartes</SelectItem>
                    {goals.data?.map((g) => (
                      <SelectItem key={g.id} value={String(g.id)}>
                        {g.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            )}
            {(fromPot === 'savings' || toPot === 'savings') && (
              <AccountPicker
                id="tx-account"
                label={fromPot === 'savings' ? 'Von Anlageort' : 'Auf Anlageort'}
                value={accountId}
                onChange={setAccountId}
              />
            )}
            <Field label="Notiz (optional)" htmlFor="tx-desc">
              <Input id="tx-desc" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={255} />
            </Field>
          </>
        ) : (
          <>
            <Field label="Kategorie" htmlFor="tx-category">
              <Select value={categoryId} onValueChange={setCategoryId}>
                <SelectTrigger id="tx-category" className="w-full">
                  <SelectValue placeholder="Kategorie wählen" />
                </SelectTrigger>
                <SelectContent>
                  {tab === 'expense' ? (
                    <>
                      <SelectGroup>
                        <SelectLabel>Freizeit &amp; variabel</SelectLabel>
                        {leisureCats.map((c) => (
                          <SelectItem key={c.id} value={String(c.id)}>
                            {c.name}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                      <SelectGroup>
                        <SelectLabel>Fixkosten</SelectLabel>
                        {fixedCats.map((c) => (
                          <SelectItem key={c.id} value={String(c.id)}>
                            {c.name}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </>
                  ) : (
                    incomeCats.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </Field>

            <Field label="Beschreibung" htmlFor="tx-desc">
              <Input
                id="tx-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={tab === 'expense' ? 'z. B. Abendessen' : 'z. B. Rückerstattung'}
                maxLength={255}
              />
            </Field>

            {tab === 'expense' && (
              <Field label="Händler / Empfänger (optional)" htmlFor="tx-merchant">
                <Input id="tx-merchant" value={merchant} onChange={(e) => setMerchant(e.target.value)} maxLength={128} />
              </Field>
            )}

            <Field label="Datum und Uhrzeit" htmlFor="tx-when">
              <Input
                id="tx-when"
                type="datetime-local"
                value={when}
                onChange={(e) => {
                  setWhen(e.target.value)
                  setWhenEdited(true)
                }}
                disabled={moneyLocked}
                required
              />
            </Field>

            {tab === 'income' && !edit && (
              <>
                <Field label="Zuordnen zu" htmlFor="tx-target">
                  <Select value={target} onValueChange={(v) => setTarget(v as Pot)}>
                    <SelectTrigger id="tx-target" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="period">Laufende Budgetperiode</SelectItem>
                      <SelectItem value="reserve">Reserve</SelectItem>
                      <SelectItem value="savings">Ersparnisse</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                {target === 'period' && <BucketSelect value={bucket} onChange={setBucket} label="Budget-Topf" />}
                {target === 'savings' && <AccountPicker id="tx-account" label="Auf Anlageort" value={accountId} onChange={setAccountId} />}
              </>
            )}

            {tab === 'expense' && !edit && plansForCategory.length > 0 && (
              <Field label="Geplante Fixkosten" htmlFor="tx-plan">
                <Select value={recurringId} onValueChange={setRecurringId}>
                  <SelectTrigger id="tx-plan" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Keine Zuordnung</SelectItem>
                    {plansForCategory.map((r) => (
                      <SelectItem key={r.id} value={String(r.id)}>
                        Zahlung für „{r.name}“
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Zugeordnet gilt der geplante Betrag als bezahlt und wird nicht doppelt gezählt.
                </p>
              </Field>
            )}

            {tab === 'expense' && debtChoices.length > 0 && (
              <Field label="Rückzahlung einer Schuld (optional)" htmlFor="tx-debt">
                <Select value={debtId} onValueChange={setDebtId}>
                  <SelectTrigger id="tx-debt" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Keine Rückzahlung</SelectItem>
                    {debtChoices.map((d) => (
                      <SelectItem key={d.id} value={String(d.id)}>
                        {d.name} · noch {formatEur(d.remaining_cents)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Die Ausgabe zählt normal im Budget und senkt zusätzlich die Restschuld.
                </p>
              </Field>
            )}

            {tab === 'expense' && (
              <label className="flex items-center justify-between gap-3 rounded-lg border p-3">
                <span className="text-sm">
                  Wiederkehrende Zahlung
                  <span className="block text-xs text-muted-foreground">Markiert die Buchung als regelmäßig.</span>
                </span>
                <Switch checked={isRecurring || linkedPlan !== null} onCheckedChange={setIsRecurring} disabled={linkedPlan !== null} />
              </label>
            )}
          </>
        )}
      </form>
    </ResponsiveDialog>
  )
}

function BucketSelect({
  value,
  onChange,
  label,
}: {
  value: SpendingBucket
  onChange: (b: SpendingBucket) => void
  label: string
}) {
  return (
    <Field label={label} htmlFor="tx-bucket">
      <Select value={value} onValueChange={(v) => onChange(v as SpendingBucket)}>
        <SelectTrigger id="tx-bucket" className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="leisure">Freizeit</SelectItem>
          <SelectItem value="fixed">Fixkosten</SelectItem>
        </SelectContent>
      </Select>
    </Field>
  )
}

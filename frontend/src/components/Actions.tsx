import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import { SalaryDialog } from '@/components/SalaryDialog'
import { TransactionDialog, type TransactionDialogState, type TxTab } from '@/components/TransactionDialog'
import type { Transaction } from '@/lib/types'

type AddTransactionOptions = { tab?: TxTab } & Pick<
  TransactionDialogState,
  'presetCategoryId' | 'presetDebtId' | 'presetAmountCents' | 'presetDescription'
>

interface Actions {
  addTransaction: (opts?: AddTransactionOptions) => void
  editTransaction: (t: Transaction) => void
  recordSalary: () => void
}

const ActionsContext = createContext<Actions | null>(null)

/** The most frequent tasks are reachable from every page with one tap. */
export function ActionsProvider({ children }: { children: ReactNode }) {
  const [tx, setTx] = useState<TransactionDialogState>({ open: false })
  const [salaryOpen, setSalaryOpen] = useState(false)
  const [session, setSession] = useState(0)

  const addTransaction = useCallback<Actions['addTransaction']>(
    (opts) => {
      setSession((n) => n + 1)
      setTx({ open: true, ...opts })
    },
    [],
  )
  const editTransaction = useCallback((t: Transaction) => {
    setSession((n) => n + 1)
    setTx({ open: true, edit: t })
  }, [])
  const recordSalary = useCallback(() => {
    setSession((n) => n + 1)
    setSalaryOpen(true)
  }, [])
  const value = useMemo(
    () => ({ addTransaction, editTransaction, recordSalary }),
    [addTransaction, editTransaction, recordSalary],
  )

  return (
    <ActionsContext.Provider value={value}>
      {children}
      <TransactionDialog key={`tx-${session}`} state={tx} onOpenChange={(open) => setTx((s) => ({ ...s, open }))} />
      <SalaryDialog key={`salary-${session}`} open={salaryOpen} onOpenChange={setSalaryOpen} />
    </ActionsContext.Provider>
  )
}

export function useActions(): Actions {
  const ctx = useContext(ActionsContext)
  if (!ctx) throw new Error('ActionsProvider fehlt')
  return ctx
}

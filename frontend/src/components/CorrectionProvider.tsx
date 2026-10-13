import { History } from 'lucide-react'
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'

import { Money } from '@/components/common'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/lib/api'
import type { CorrectionImpact } from '@/lib/types'

export interface CorrectionFlags {
  confirm_correction: boolean
  correction_reason?: string
}

type Runner = <T>(op: (flags: CorrectionFlags) => Promise<T>) => Promise<T | undefined>

const CorrectionContext = createContext<Runner | null>(null)

/**
 * Changes that touch a closed budget period are rejected by the backend with a
 * preview of the reserve impact. This asks the user and resends with confirmation,
 * so history is never changed silently.
 */
export function CorrectionProvider({ children }: { children: ReactNode }) {
  const [impacts, setImpacts] = useState<CorrectionImpact[] | null>(null)
  const [reason, setReason] = useState('')
  const decide = useRef<(answer: { confirmed: boolean; reason?: string }) => void>(() => {})

  const run = useCallback<Runner>(async (op) => {
    try {
      return await op({ confirm_correction: false })
    } catch (error) {
      if (!(error instanceof ApiError) || error.code !== 'closed_period_correction_required') throw error
      setReason('')
      setImpacts(error.details as CorrectionImpact[])
      const answer = await new Promise<{ confirmed: boolean; reason?: string }>((resolve) => {
        decide.current = resolve
      })
      setImpacts(null)
      if (!answer.confirmed) return undefined
      return op({ confirm_correction: true, correction_reason: answer.reason || undefined })
    }
  }, [])

  return (
    <CorrectionContext.Provider value={run}>
      {children}
      <AlertDialog open={impacts !== null} onOpenChange={(open) => !open && decide.current({ confirmed: false })}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <History className="size-5" /> Abgeschlossenen Zeitraum korrigieren?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Diese Änderung betrifft einen bereits abgeschlossenen Budgetzeitraum. Die Korrektur wird
              nachvollziehbar protokolliert und die Reserve entsprechend angepasst.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-3">
            {impacts?.map((i) => (
              <div key={i.period_id} className="rounded-lg border p-3 text-sm">
                <div className="font-medium">Zeitraum {i.label}</div>
                <dl className="mt-2 grid grid-cols-2 gap-1">
                  <dt className="text-muted-foreground">Ergebnis bisher</dt>
                  <dd className="text-right">
                    <Money cents={i.leftover_before_cents} signed />
                  </dd>
                  <dt className="text-muted-foreground">Ergebnis neu</dt>
                  <dd className="text-right">
                    <Money cents={i.leftover_after_cents} signed />
                  </dd>
                  <dt className="font-medium">Änderung der Reserve</dt>
                  <dd className="text-right font-medium">
                    <Money cents={i.reserve_delta_cents} signed />
                  </dd>
                </dl>
              </div>
            ))}
            <div className="space-y-1.5">
              <Label htmlFor="correction-reason">Grund (optional)</Label>
              <Textarea
                id="correction-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="z. B. vergessene Barzahlung nachgetragen"
                maxLength={500}
              />
            </div>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => decide.current({ confirmed: false })}>Abbrechen</AlertDialogCancel>
            <AlertDialogAction onClick={() => decide.current({ confirmed: true, reason: reason.trim() })}>Korrektur buchen</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </CorrectionContext.Provider>
  )
}

export function useCorrection(): Runner {
  const ctx = useContext(CorrectionContext)
  if (!ctx) throw new Error('CorrectionProvider fehlt')
  return ctx
}

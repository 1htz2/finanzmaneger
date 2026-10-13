import { AlertCircle, Inbox, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api'
import { formatEur, formatSignedEur } from '@/lib/format'
import { cn } from '@/lib/utils'

export function Money({
  cents,
  signed = false,
  className,
}: {
  cents: number
  signed?: boolean
  className?: string
}) {
  return (
    <span className={cn('tabular whitespace-nowrap', className)}>
      {signed ? formatSignedEur(cents) : formatEur(cents)}
    </span>
  )
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function LoadingState({ rows = 3 }: { rows?: number }) {
  return (
    <div className="grid gap-4" aria-busy="true" aria-label="Wird geladen">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-28 w-full rounded-xl" />
      ))}
    </div>
  )
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Unbekannter Fehler'
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <Card className="border-destructive/30">
      <CardContent className="flex flex-col items-start gap-3 sm:flex-row sm:items-center">
        <AlertCircle className="size-5 shrink-0 text-destructive" aria-hidden />
        <p className="flex-1 text-sm">{errorMessage(error)}</p>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw /> Erneut versuchen
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export function EmptyState({
  icon,
  title,
  text,
  action,
  className,
}: {
  icon?: ReactNode
  title: string
  text?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center',
        className,
      )}
    >
      <div className="mb-1 text-muted-foreground [&_svg]:size-8">{icon ?? <Inbox />}</div>
      <p className="font-medium">{title}</p>
      {text && <p className="max-w-sm text-sm text-muted-foreground">{text}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function StatTile({
  label,
  value,
  hint,
  icon,
  className,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: ReactNode
  className?: string
}) {
  return (
    <Card className={cn('gap-1 py-4', className)}>
      <CardContent className="px-4">
        <div className="flex items-center gap-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {icon && <span className="[&_svg]:size-3.5">{icon}</span>}
          {label}
        </div>
        <div className="mt-1 text-xl font-semibold tracking-tight">{value}</div>
        {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
      </CardContent>
    </Card>
  )
}

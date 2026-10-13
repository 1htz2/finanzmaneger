import { forwardRef } from 'react'

import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

type Props = Omit<React.ComponentProps<typeof Input>, 'type' | 'inputMode'> & { invalid?: boolean }

/** Free-text euro input ("12,50"). Parsing to cents happens with parseEuroInput on submit. */
export const MoneyInput = forwardRef<HTMLInputElement, Props>(function MoneyInput(
  { className, invalid, ...props },
  ref,
) {
  return (
    <div className="relative">
      <Input
        ref={ref}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        placeholder="0,00"
        aria-invalid={invalid || undefined}
        className={cn('pr-8 text-right tabular', className)}
        {...props}
      />
      <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm text-muted-foreground">
        €
      </span>
    </div>
  )
})

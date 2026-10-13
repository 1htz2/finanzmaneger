import { QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type {
  AppSettings,
  AuthStatus,
  Category,
  CategoryBreakdown,
  Dashboard,
  Goal,
  PeriodDetail,
  PeriodSummary,
  RecurringExpense,
  RecurringOverview,
  RecurringSuggestion,
  Reserve,
  Savings,
  StatsOverview,
  TransactionList,
} from '@/lib/types'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 15_000, retry: 1, refetchOnWindowFocus: true },
  },
})

export interface TransactionFilters {
  q?: string
  date_from?: string
  date_to?: string
  category_id?: number
  bucket?: string
  type?: string
  min_amount?: number
  max_amount?: number
  period_id?: number
  is_recurring?: boolean
  sort?: string
  order?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

export const useAuthStatus = () =>
  useQuery({ queryKey: ['auth'], queryFn: () => api.get<AuthStatus>('/auth/status'), staleTime: 60_000 })

export const useDashboard = () =>
  useQuery({ queryKey: ['fin', 'dashboard'], queryFn: () => api.get<Dashboard>('/dashboard') })

export const useTransactions = (filters: TransactionFilters) =>
  useQuery({
    queryKey: ['fin', 'transactions', filters],
    queryFn: () => api.get<TransactionList>('/transactions', { ...filters }),
    placeholderData: (prev) => prev,
  })

export const useRecurringSuggestions = () =>
  useQuery({
    queryKey: ['fin', 'recurring-suggestions'],
    queryFn: () => api.get<RecurringSuggestion[]>('/transactions/recurring-suggestions'),
  })

export const usePeriods = () =>
  useQuery({ queryKey: ['fin', 'periods'], queryFn: () => api.get<PeriodSummary[]>('/periods') })

export const useActivePeriod = () =>
  useQuery({ queryKey: ['fin', 'periods', 'active'], queryFn: () => api.get<PeriodDetail | null>('/periods/active') })

export const usePeriod = (id: number | null) =>
  useQuery({
    queryKey: ['fin', 'periods', id],
    queryFn: () => api.get<PeriodDetail>(`/periods/${id}`),
    enabled: id !== null,
  })

export const useCategories = () =>
  useQuery({ queryKey: ['fin', 'categories'], queryFn: () => api.get<Category[]>('/categories'), staleTime: 60_000 })

export const useRecurring = () =>
  useQuery({ queryKey: ['fin', 'recurring'], queryFn: () => api.get<RecurringExpense[]>('/recurring-expenses') })

export const useRecurringOverview = () =>
  useQuery({
    queryKey: ['fin', 'recurring', 'overview'],
    queryFn: () => api.get<RecurringOverview>('/recurring-expenses/overview'),
  })

export const useReserve = () => useQuery({ queryKey: ['fin', 'reserve'], queryFn: () => api.get<Reserve>('/reserve') })

export const useSavings = () => useQuery({ queryKey: ['fin', 'savings'], queryFn: () => api.get<Savings>('/savings') })

export const useGoals = () =>
  useQuery({ queryKey: ['fin', 'goals'], queryFn: () => api.get<Goal[]>('/savings/goals') })

export const useStats = () =>
  useQuery({ queryKey: ['fin', 'stats'], queryFn: () => api.get<StatsOverview>('/stats/overview') })

export const useCategoryBreakdown = (params: { period_id?: number; bucket?: string }) =>
  useQuery({
    queryKey: ['fin', 'stats', 'categories', params],
    queryFn: () => api.get<CategoryBreakdown>('/stats/categories', params),
  })

export const useSettings = () =>
  useQuery({ queryKey: ['fin', 'settings'], queryFn: () => api.get<AppSettings>('/settings') })

/**
 * Every financial write can move several numbers at once (budget, reserve,
 * savings, warnings), so all financial queries refetch after any write.
 */
export function useFinanceMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['fin'] }),
  })
}

// Mirrors backend/app/schemas. All money values are integer cents.

export type Bucket = 'savings' | 'fixed' | 'leisure'
export type SpendingBucket = 'fixed' | 'leisure'
export type Pot = 'period' | 'reserve' | 'savings'
export type TransactionType = 'expense' | 'income' | 'transfer'
export type CategoryKind = 'fixed' | 'leisure' | 'income'
export type Interval = 'monthly' | 'quarterly' | 'yearly'
export type Severity = 'info' | 'warning' | 'critical'

export interface AuthStatus {
  setup_required: boolean
  authenticated: boolean
  username: string | null
}

export interface BucketStatus {
  bucket: Bucket
  budget_cents: number
  spent_cents: number
  available_cents: number
  used_bp: number | null
}

export interface PeriodSummary {
  id: number
  status: 'active' | 'closed'
  started_at: string
  ended_at: string | null
  budget_model_key: string
  net_salary_cents: number
  extra_income_cents: number
  transfer_net_cents: number
  total_budget_cents: number
  expected_next_payday: string | null
  buckets: BucketStatus[]
  spent_cents: number
  leftover_cents: number
  reserve_transfer_cents: number
  deficit_cents: number
  planned_savings_rate_bp: number
  actual_savings_rate_bp: number | null
  transaction_count: number
}

export interface Allocation {
  id: number
  bucket: Bucket
  amount_cents: number
  source: 'salary' | 'salary_correction' | 'income' | 'transfer' | 'reversal'
  note: string | null
  created_at: string
}

export interface Correction {
  id: number
  period_id: number
  transaction_id: number | null
  action: string
  leftover_before_cents: number
  leftover_after_cents: number
  reserve_delta_cents: number
  reason: string
  created_at: string
}

export interface PeriodDetail extends PeriodSummary {
  allocations: Allocation[]
  corrections: Correction[]
}

export interface SalaryPreview {
  closing: {
    period: PeriodSummary
    leftover_cents: number
    reserve_transfer_cents: number
    deficit_cents: number
    coverable_from_reserve_cents: number
    transactions_moving_to_new_period: number
  } | null
  new_split: { bucket: Bucket; percent: number; amount_cents: number }[]
  budget_model_label: string
  reserve_balance_before_cents: number
  reserve_balance_after_cents: number
  savings_balance_before_cents: number
  savings_balance_after_cents: number
}

export interface SalaryResult {
  closed_period: PeriodSummary | null
  reserve_transfer_cents: number
  deficit_cents: number
  deficit_covered_cents: number
  new_period: PeriodSummary
  reserve_balance_cents: number
  savings_balance_cents: number
}

export interface CategoryRef {
  id: number
  name: string
  kind: CategoryKind
  color: string | null
}

export interface Category extends CategoryRef {
  is_default: boolean
  archived: boolean
  usage_count: number
}

export interface Transaction {
  id: number
  type: TransactionType
  occurred_at: string
  amount_cents: number
  bucket: Bucket | null
  category: CategoryRef | null
  description: string
  merchant: string | null
  period_id: number | null
  recurring_expense_id: number | null
  is_recurring: boolean
  income_kind: 'salary' | 'other' | null
  income_target: Pot | null
  transfer_from: Pot | null
  transfer_to: Pot | null
  reversed_at: string | null
  created_at: string
  updated_at: string
}

export interface TransactionList {
  items: Transaction[]
  total: number
  expense_sum_cents: number
  income_sum_cents: number
}

export interface RecurringSuggestion {
  label: string
  merchant: string | null
  category: CategoryRef | null
  typical_amount_cents: number
  occurrences: number
  periods: number
  transaction_ids: number[]
}

export interface BalancePoint {
  at: string
  balance_cents: number
}

export interface ReserveEntry {
  id: number
  amount_cents: number
  kind: string
  occurred_at: string
  period_id: number | null
  transaction_id: number | null
  purpose: string | null
  note: string | null
  created_at: string
}

export interface Reserve {
  balance_cents: number
  minimum_cents: number
  purposes: string[]
  entries: ReserveEntry[]
  history: BalancePoint[]
  total_from_periods_cents: number
  total_withdrawn_cents: number
}

export interface Goal {
  id: number
  title: string
  target_cents: number
  target_date: string | null
  archived: boolean
  saved_cents: number
  remaining_cents: number
  progress_bp: number
  projected_date: string | null
  required_per_month_cents: number | null
  created_at: string
}

export interface SavingsEntry {
  id: number
  amount_cents: number
  kind: string
  occurred_at: string
  period_id: number | null
  transaction_id: number | null
  note: string | null
  created_at: string
}

export interface Savings {
  balance_cents: number
  allocated_cents: number
  unallocated_cents: number
  entries: SavingsEntry[]
  goals: Goal[]
  history: BalancePoint[]
}

export interface RecurringExpense {
  id: number
  name: string
  amount_cents: number
  category: CategoryRef
  interval: Interval
  due_date: string | null
  active: boolean
  description: string | null
  monthly_equivalent_cents: number
  created_at: string
  updated_at: string
}

export interface RecurringPlanItem {
  expense: RecurringExpense
  due_dates: string[]
  paid_count: number
  paid_cents: number
  open_count: number
  open_cents: number
  next_due_date: string | null
}

export interface RecurringOverview {
  has_active_period: boolean
  window_start: string | null
  window_end: string | null
  window_estimated: boolean
  items: RecurringPlanItem[]
  monthly_total_cents: number
  yearly_total_cents: number
  planned_in_period_cents: number
  paid_in_period_cents: number
  open_in_period_cents: number
  fixed_budget_cents: number
  fixed_spent_cents: number
  planned_share_bp: number | null
  sufficient: boolean
  shortfall_cents: number
}

export interface BudgetWarning {
  code: string
  severity: Severity
  title: string
  message: string
}

export interface Pace {
  days_left: number
  per_day_cents: number
  per_week_cents: number
  planned_spent_by_today_cents: number
  ahead_of_plan_by_cents: number
  expected_next_payday: string
}

export interface UpcomingCost {
  recurring_expense_id: number
  name: string
  amount_cents: number
  due_date: string
  category: CategoryRef
}

export interface Dashboard {
  active_period: PeriodSummary | null
  reserve_balance_cents: number
  savings: { balance_cents: number; allocated_cents: number; unallocated_cents: number }
  leisure_pace: Pace | null
  pace_unavailable_reason: 'no_active_period' | 'no_expected_payday' | 'payday_passed' | null
  warnings: BudgetWarning[]
  recent_transactions: Transaction[]
  upcoming_fixed_costs: UpcomingCost[]
  fixed_open_cents: number
  goals: Goal[]
  reserve_history: BalancePoint[]
  period_comparison: PeriodSummary[]
}

export interface StatsOverview {
  periods: PeriodSummary[]
  averages: {
    closed_periods: number
    avg_income_cents: number | null
    avg_fixed_spent_cents: number | null
    avg_leisure_spent_cents: number | null
    avg_actual_savings_rate_bp: number | null
    planned_savings_rate_bp: number
  }
  reserve_history: BalancePoint[]
  savings_history: BalancePoint[]
}

export interface CategoryBreakdown {
  items: { category: CategoryRef | null; total_cents: number; count: number; share_bp: number | null }[]
  total_cents: number
}

export interface AppSettings {
  budget_model_key: string
  budget_models: { key: string; label: string; shares_percent: Record<Bucket, number> }[]
  reserve_minimum_cents: number
  large_expense_threshold_cents: number
  reserve_purposes: string[]
  currency: 'EUR'
  timezone: 'Europe/Berlin'
}

export interface CorrectionImpact {
  period_id: number
  label: string
  leftover_before_cents: number
  leftover_after_cents: number
  reserve_delta_cents: number
}

/**
 * Centralized Typed API Client for Money Lens.
 * Connects the Lovable frontend directly to the existing Money Lens FastAPI backend (http://localhost:8000).
 */

const API_BASE_URL = typeof window !== 'undefined' 
  ? (import.meta.env['VITE_API_BASE_URL'] || 'http://localhost:8000/api/v1')
  : 'http://localhost:8000/api/v1';

export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorData.detail || errorData.message || `API Error: ${response.status}`);
  }

  return response.json();
}

// ----------------------------------------------------------------------
// 1. Profile & Account Types and APIs
// ----------------------------------------------------------------------
export interface UserFinancialProfile {
  id?: string;
  user_id?: string;
  name: string;
  monthly_income: number;
  essential_expenses: number;
  discretionary_expenses: number;
  current_savings: number;
  monthly_investments: number;
  active_emis: number;
  active_loans: number;
  other_recurring_expenses: number;
  total_monthly_expenses: number;
  monthly_surplus: number;
  savings_rate_pct: number;
  dti_ratio_pct: number;
  emergency_fund_runway_months: number;
  health_score: number;
}

export async function fetchProfile(userId: string): Promise<UserFinancialProfile> {
  try {
    return await apiFetch<UserFinancialProfile>(`/profile?user_id=${encodeURIComponent(userId)}`);
  } catch (err) {
    console.warn("Using zero baseline profile:", err);
    return {
      name: "User",
      monthly_income: 0,
      essential_expenses: 0,
      discretionary_expenses: 0,
      current_savings: 0,
      monthly_investments: 0,
      active_emis: 0,
      active_loans: 0,
      other_recurring_expenses: 0,
      total_monthly_expenses: 0,
      monthly_surplus: 0,
      savings_rate_pct: 0,
      dti_ratio_pct: 0,
      emergency_fund_runway_months: 0,
      health_score: 50,
    };
  }
}

export async function updateProfile(updates: Partial<UserFinancialProfile>, userId: string): Promise<UserFinancialProfile> {
  return apiFetch<UserFinancialProfile>(`/profile?user_id=${encodeURIComponent(userId)}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

// ----------------------------------------------------------------------
// 2. Spending Insights Types and APIs
// ----------------------------------------------------------------------
export interface CategorySpending {
  category: string;
  total_amount: number;
  percentage_of_total: number;
  transaction_count: number;
  is_essential: boolean;
  is_recurring: boolean;
}

export interface SpendingInsightsResponse {
  total_spending: number;
  essential_total: number;
  discretionary_total: number;
  essential_pct: number;
  discretionary_pct: number;
  recurring_total: number;
  weekend_spending: number;
  weekday_spending: number;
  weekend_pct: number;
  categories: CategorySpending[];
  observations: {
    type: string;
    title: string;
    summary: string;
    evidence: string;
    implication: string;
    possible_action: string;
  }[];
}

export async function fetchSpendingInsights(userId: string): Promise<SpendingInsightsResponse> {
  return apiFetch<SpendingInsightsResponse>(`/spending/insights?user_id=${encodeURIComponent(userId)}`);
}

// ----------------------------------------------------------------------
// 3. Bank Statement Intelligence
// ----------------------------------------------------------------------
export interface StatementTransactionItem {
  id: string;
  date: string;
  description: string;
  amount: number;
  type: 'debit' | 'credit';
  category: string;
  is_recurring: boolean;
  is_essential: boolean;
  source?: string;
  confidence?: number;
}

export interface PendingObservation {
  type: string;
  field: string;
  amount: number;
  description: string;
  confidence: number;
  current_value: number;
}

export interface StatementAnalysisSummary {
  statement_id: string;
  filename: string;
  save_raw: boolean;
  total_credits: number;
  total_debits: number;
  net_cashflow: number;
  transaction_count: number;
  date_range_start: string | null;
  date_range_end: string | null;
  category_breakdown: Record<string, number>;
  essential_spending: number;
  discretionary_spending: number;
  recurring_spending: number;
  observations: string[];
  extraction_source?: string;
  detected_salary?: number;
  detected_emis?: any[];
  detected_investments?: any[];
  detected_recurring?: any[];
  pending_observations?: PendingObservation[];
}

export async function uploadBankStatement(file: File, saveRaw: boolean, userId: string): Promise<StatementAnalysisSummary> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('save_raw', String(saveRaw));
  formData.append('user_id', userId);

  const res = await fetch(`${API_BASE_URL}/statements/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Failed to upload statement');
  }

  return res.json();
}

export async function fetchStatementTransactions(userId: string): Promise<StatementTransactionItem[]> {
  try {
    return await apiFetch<StatementTransactionItem[]>(`/statements/transactions?user_id=${encodeURIComponent(userId)}`);
  } catch {
    return [];
  }
}

export async function confirmStatementObservation(
  observationType: string,
  field: string,
  value: number,
  userId: string
): Promise<UserFinancialProfile> {
  return apiFetch<UserFinancialProfile>('/statements/confirm-observation', {
    method: 'POST',
    body: JSON.stringify({
      observation_type: observationType,
      field,
      value,
      user_id: userId,
    }),
  });
}


// ----------------------------------------------------------------------
// 4. Goals APIs
// ----------------------------------------------------------------------
export interface GoalItem {
  id: string;
  title: string;
  target_amount: number;
  current_savings_allocated: number;
  target_months?: number;
  target_date?: string;
  category?: string;
  priority?: string;
}

export async function fetchGoals(userId: string): Promise<GoalItem[]> {
  try {
    return await apiFetch<GoalItem[]>(`/goals/saved?user_id=${encodeURIComponent(userId)}`);
  } catch {
    return [];
  }
}

export async function createGoal(goal: {
  title: string;
  target_amount: number;
  target_months?: number;
  current_savings_allocated?: number;
  category?: string;
  priority?: string;
}, userId: string): Promise<GoalItem> {
  return apiFetch<GoalItem>(`/goals/save?user_id=${encodeURIComponent(userId)}`, {
    method: 'POST',
    body: JSON.stringify(goal),
  });
}

export async function deleteGoal(goalId: string, userId: string): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>(`/goals/saved/${goalId}?user_id=${encodeURIComponent(userId)}`, {
    method: 'DELETE',
  });
}

// ----------------------------------------------------------------------
// 5. Simulations & Experiments
// ----------------------------------------------------------------------
export async function simulatePurchase(payload: {
  monthly_income: number;
  monthly_expenses: number;
  current_savings: number;
  existing_emi?: number;
  purchase_amount: number;
}) {
  return apiFetch<any>('/simulate/purchase', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function simulateEMI(payload: {
  monthly_income: number;
  monthly_expenses: number;
  current_savings: number;
  existing_emi?: number;
  loan_amount: number;
  annual_interest_rate: number;
  tenure_months: number;
}) {
  return apiFetch<any>('/simulate/emi', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ----------------------------------------------------------------------
// 6. Conversational Chatbot
// ----------------------------------------------------------------------
export async function sendChatMessage(message: string, sessionId?: string, userId?: string) {
  return apiFetch<any>('/chat/message', {
    method: 'POST',
    body: JSON.stringify({
      message,
      session_id: sessionId,
      user_id: userId,
      include_statement_insights: true,
    }),
  });
}

export async function confirmChatAction(actionType: 'UPDATE_PROFILE' | 'CREATE_GOAL', data: any, userId: string) {
  return apiFetch<any>('/chat/confirm-action', {
    method: 'POST',
    body: JSON.stringify({
      action_type: actionType,
      data,
      user_id: userId,
    }),
  });
}

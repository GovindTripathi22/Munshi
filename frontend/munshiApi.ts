/**
 * Munshi REST API Client & Service Layer
 * Connects the React dashboard to the FastAPI backend (munshi/api.py).
 */

export interface BackendJournalLine {
  account_code: string;
  account_name: string;
  debit: number;
  credit: number;
}

export interface BackendJournalEntry {
  entry_id: string;
  date: string;
  narration: string;
  lines: BackendJournalLine[];
  party?: string | null;
  party_gstin?: string | null;
  utr?: string | null;
  payment_mode?: string;
  status?: string;
  taxable_value?: number;
  cgst?: number;
  sgst?: number;
  igst?: number;
  tds?: number;
  itc_eligible?: boolean;
  total_debit?: number;
  total_credit?: number;
  is_balanced?: boolean;
}

export interface FrontendJournalLine {
  accountCode: string;
  accountName: string;
  debit: number;
  credit: number;
}

export interface FrontendJournalEntry {
  id: string;
  date: string;
  narration: string;
  voucherType?: string;
  party: string;
  partyGstin?: string;
  stateCode?: string;
  utr?: string;
  paymentMode: string;
  status: 'POSTED' | 'PENDING_HITL' | 'REJECTED';
  itcEligible?: boolean;
  blockedItcReason?: string;
  gstRate?: number;
  taxableValue?: number;
  cgst?: number;
  sgst?: number;
  igst?: number;
  tdsDeducted?: number;
  lines: FrontendJournalLine[];
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  database_verified: boolean;
  features: string[];
}

export interface WorkflowResponse {
  thread_id: string;
  status: string;
  requires_hitl: boolean;
  intent?: string;
  entry?: BackendJournalEntry;
  trial_balance?: any;
  profit_and_loss?: any;
  balance_sheet?: any;
  gstr3b?: any;
  reconciliation?: any;
  audit_flags?: any[];
  report_markdown?: string;
}

export interface HITLResponse {
  thread_id: string;
  entry_id: string;
  status: 'APPROVED' | 'REJECTED';
  entry?: BackendJournalEntry;
  reviewer_notes?: string;
  trial_balance?: any;
}

// Storage keys
const API_KEY_STORAGE = 'munshi_api_key';
const API_URL_STORAGE = 'munshi_api_url';

export function getStoredApiKey(): string {
  try {
    return localStorage.getItem(API_KEY_STORAGE) || '';
  } catch {
    return '';
  }
}

export function setStoredApiKey(key: string): void {
  try {
    localStorage.setItem(API_KEY_STORAGE, key.trim());
  } catch {
    // ignore in restricted environments
  }
}

export function getStoredApiUrl(): string {
  try {
    return localStorage.getItem(API_URL_STORAGE) || '';
  } catch {
    return '';
  }
}

export function setStoredApiUrl(url: string): void {
  try {
    localStorage.setItem(API_URL_STORAGE, url.trim());
  } catch {
    // ignore
  }
}

function resolveApiBase(): string {
  const custom = getStoredApiUrl();
  if (custom) return custom.replace(/\/+$/, '');
  // If hosted on backend (e.g. port 8000), use relative origin
  if (typeof window !== 'undefined' && window.location.port === '8000') {
    return '';
  }
  // If running in dev server (port 3000), Vite proxy forwards /v1 and /health
  return '';
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const base = resolveApiBase();
  const url = `${base}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
  const apiKey = getStoredApiKey();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) {
        errDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errDetail);
  }

  return response.json() as Promise<T>;
}

/**
 * Health check & tamper verification endpoint.
 */
export async function checkBackendHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health');
}

/**
 * Post a natural language transaction or structured voucher to the LangGraph pipeline.
 */
export async function postWorkflowTransaction(
  prompt: string,
  amount?: number,
  date?: string,
  threadId: string = 'default'
): Promise<WorkflowResponse> {
  return apiRequest<WorkflowResponse>('/v1/workflows/run', {
    method: 'POST',
    body: JSON.stringify({
      thread_id: threadId,
      prompt,
      amount,
      date,
    }),
  });
}

/**
 * Approve or reject a Human-in-the-Loop voucher checkpoint.
 */
export async function resumeWorkflowHITL(
  threadId: string = 'default',
  entryId: string,
  approved: boolean,
  reviewerNotes?: string
): Promise<HITLResponse> {
  return apiRequest<HITLResponse>(`/v1/workflows/${threadId}/hitl`, {
    method: 'POST',
    body: JSON.stringify({
      approved,
      entry_id: entryId,
      reviewer_notes: reviewerNotes,
    }),
  });
}

/**
 * Fetch live Trial Balance from general ledger engine.
 */
export async function fetchLiveTrialBalance(threadId: string = 'default'): Promise<any> {
  return apiRequest<any>(`/v1/ledger/trial-balance?thread_id=${encodeURIComponent(threadId)}`);
}

/**
 * Fetch live Profit & Loss Statement.
 */
export async function fetchLivePnL(threadId: string = 'default'): Promise<any> {
  return apiRequest<any>(`/v1/ledger/pnl?thread_id=${encodeURIComponent(threadId)}`);
}

/**
 * Fetch live Balance Sheet.
 */
export async function fetchLiveBalanceSheet(threadId: string = 'default'): Promise<any> {
  return apiRequest<any>(`/v1/ledger/balance-sheet?thread_id=${encodeURIComponent(threadId)}`);
}

/**
 * Fetch live GSTR-3B tax summary.
 */
export async function fetchLiveGSTR3B(threadId: string = 'default'): Promise<any> {
  return apiRequest<any>(`/v1/gst/gstr3b?thread_id=${encodeURIComponent(threadId)}`);
}

/**
 * Fetch live forensic audit flags and hash-chain verification.
 */
export async function fetchLiveAuditFindings(threadId: string = 'default'): Promise<any> {
  return apiRequest<any>(`/v1/audit/findings?thread_id=${encodeURIComponent(threadId)}`);
}

/**
 * Run quantitative evaluation benchmark via API.
 */
export async function runApiBenchmark(): Promise<any> {
  return apiRequest<any>('/v1/benchmark');
}

/**
 * Map backend JournalEntry (snake_case) to frontend JournalEntry format (camelCase).
 */
export function backendEntryToFrontend(entry: BackendJournalEntry): FrontendJournalEntry {
  const lines: FrontendJournalLine[] = (entry.lines || []).map(l => ({
    accountCode: l.account_code,
    accountName: l.account_name,
    debit: l.debit,
    credit: l.credit,
  }));

  // Infer voucher type from account codes
  let voucherType = 'JOURNAL';
  const hasRev = lines.some(l => l.accountCode.startsWith('4'));
  const hasExp = lines.some(l => l.accountCode.startsWith('5'));
  const bankLine = lines.find(l => l.accountCode === '1010' || l.accountCode === '1000');

  if (hasRev) {
    voucherType = 'SALES';
  } else if (hasExp && bankLine && bankLine.credit > 0) {
    voucherType = 'PAYMENT';
  } else if (hasExp) {
    voucherType = 'PURCHASE';
  } else if (bankLine && bankLine.debit > 0) {
    voucherType = 'RECEIPT';
  }

  // Extract party state code if GSTIN is present
  const gstin = entry.party_gstin || '';
  const stateCode = gstin.length >= 2 ? gstin.slice(0, 2) : undefined;

  const totalTax = (entry.cgst || 0) + (entry.sgst || 0) + (entry.igst || 0);
  const taxValue = entry.taxable_value || 0;
  const inferredRate = taxValue > 0 ? Math.round((totalTax / taxValue) * 100) : 0;

  return {
    id: entry.entry_id,
    date: entry.date,
    narration: entry.narration,
    voucherType,
    party: entry.party || 'Counterparty',
    partyGstin: entry.party_gstin || undefined,
    stateCode,
    utr: entry.utr || undefined,
    paymentMode: entry.payment_mode || 'BANK',
    status: (entry.status as any) || 'POSTED',
    itcEligible: entry.itc_eligible,
    gstRate: inferredRate > 0 ? inferredRate : undefined,
    taxableValue: entry.taxable_value,
    cgst: entry.cgst,
    sgst: entry.sgst,
    igst: entry.igst,
    tdsDeducted: entry.tds,
    lines,
  };
}

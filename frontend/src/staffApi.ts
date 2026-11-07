// Back-office API client (POLICIES.md §11, §13). Separate cookies and CSRF token from the owner journey.
import { ApiError } from "./api";

export type StaffUser = { username: string; role: "sales_agent" | "partner" | "kyc_reviewer" | "admin"; display: string; partner_id: string | null; csrf_token?: string };
export type Lead = {
  lead_ref: string; session_id: string; stage: string; language: string | null;
  summary: { business_type: string | null; segment: string | null; city: string | null; city_tier: number | null; employees: number | null; sites: number | null; has_gstin: boolean | null; needs: string[] };
  monthly_incl_tax: number | null; claimed_by: string | null; claim_until: string | null;
  notes: { author: string; text: string; at: string }[];
};
export type Callback = {
  lead_id: string; business_name: string; business_type: string; segment: string; city: string; contact_name: string; contact_role: string;
  stage_reached: string; drop_reason: string; gstin: string | null; p_activate: number; expected_monthly_revenue: number; why: string[];
};
export type ReviewItem = { case_id: string; updated_at: string; findings: string[]; gstin: string | null };
export type ReviewCase = {
  case_id: string; outcome: string; gstin_status: string | null; business_proof: string | null;
  findings: { code: string; level: string; doc: string | null; detail: Record<string, unknown> }[];
  fields: Record<string, Record<string, string>>;
};
export type AuditEntry = { seq: number; at: string; actor: string; role: string; action: string; target: string; detail: string | null };

let token: string | null = null;

function cookieValue(name: string): string {
  for (const part of document.cookie.split(";")) {
    const eq = part.indexOf("=");
    if (eq > 0 && part.slice(0, eq).trim() === name) return decodeURIComponent(part.slice(eq + 1).trim());
  }
  return "";
}

async function bo<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  if (method !== "GET") {
    const t = token || cookieValue("udyam_staff_csrf");
    if (t) headers.set("X-CSRF-Token", t);
  }
  const res = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* not JSON */ }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body?: unknown) =>
  bo<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });

export const staff = {
  login: async (username: string, password: string) => {
    const u = await post<StaffUser>("/api/bo/login", { username, password });
    token = u.csrf_token ?? null;
    return u;
  },
  me: async () => { const u = await bo<StaffUser>("/api/bo/me"); token = u.csrf_token ?? token; return u; },
  logout: async () => { try { await post("/api/bo/logout"); } finally { token = null; } },
  queue: () => bo<Lead[]>("/api/bo/queue"),
  claim: (sid: string) => post<Lead>(`/api/bo/leads/${sid}/claim`),
  note: (sid: string, text: string) => post<Lead>(`/api/bo/leads/${sid}/notes`, { text }),
  callbacks: () => bo<{ label: string; total: number; leads: Callback[] }>("/api/bo/callbacks"),
  referrals: () => bo<{ partner: string; sessions_started: number | string; orders_placed: number | string; orders_completed: number | string; note: string }>("/api/bo/referrals"),
  reviewQueue: () => bo<ReviewItem[]>("/api/bo/kyc/review"),
  reviewCase: (id: string) => bo<ReviewCase>(`/api/bo/kyc/cases/${id}`),
  decide: (id: string, approve: boolean, reason: string) => post<{ outcome: string; orders_moved: number }>(`/api/bo/kyc/cases/${id}/decision`, { approve, reason }),
  audit: () => bo<AuditEntry[]>("/api/bo/audit"),
  retention: () => post<Record<string, number>>("/api/bo/admin/retention"),
};

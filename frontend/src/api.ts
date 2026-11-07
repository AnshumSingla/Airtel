// Typed client for the FastAPI backend. Same origin: the PWA is served by the API.
import i18n from "./i18n";

export type Button = { label: string; value: string };
export type Summary = {
  business_type: string | null; segment: string | null; city: string | null; city_tier: number | null;
  employees: number | null; sites: number | null; has_gstin: boolean | null; needs: string[];
  budget: number | null; assumed: string[];
};
export type Turn = {
  reply: string; language: string; status: "asking" | "confirm" | "offer_partial" | "handoff_requested";
  expecting: string | null; buttons: Button[]; summary: Summary | null;
  consent_card: { type: string; purpose: string; text: string } | null; used_llm: boolean;
};
export type Reason = { tag: string; text: string };
export type Line = {
  product_id: string; name: string; description?: string; unit: string; quantity: number;
  unit_monthly: number; monthly: number; one_time: number; term_months: number; install_days: number;
  reasons?: Reason[]; info?: string[];
};
export type Quote = {
  label: string; tax_label: string; monthly_ex_tax: number; monthly_tax: number; monthly_incl_tax: number;
  one_time_ex_tax: number; one_time_tax: number; one_time_incl_tax: number; first_payment: number;
  slowest_install_days: number; longest_term_months?: number;
};
export type Addon = {
  product_id: string; name: string; description: string; unit: string; default_quantity: number;
  unit_monthly: number; setup_per_unit: number; share: number;
};
export type Excluded = { product_id: string; name: string; codes: string[]; text: string };
export type Recommendation = {
  summary: Summary; lines: Line[]; excluded: Excluded[]; dropped_for_budget: string[]; notes: string[];
  quote: Quote; addons: Addon[]; language: string;
};
export type Preview = { lines: Line[]; rejected: Excluded[]; quote: Quote; addons: Addon[] };
export type Finding = { code: string; level: "action" | "review" | "note"; doc: string | null; detail: Record<string, unknown> };
export type KycView = {
  outcome: "checks_passed" | "owner_action_needed" | "manual_review"; label: string; registry: string;
  findings: Finding[]; gstin: string | null; gstin_status: string | null; business_proof: string | null;
  confirm: { field: string; doc: string; reading: string }[];
  lines?: { product_id: string; eligible: boolean; codes: string[] }[];
};
export type Upload = { doc_type: string; refused: string | null; seen_type: string | null; quality: Record<string, unknown>; fields: Record<string, string> };
export type Options = {
  segments: { code: string; label: Record<string, string> }[];
  cities: { name: string; tier: number; state: string }[];
  needs: { product_id: string; label: Record<string, string> }[];
};

export type OrderLine = { product_id: string; name: string; quantity: number; status: string; install_days: number; eta_day: number | null; days_left: number | null; reason: string | null };
export type Order = {
  order_id: string; status: string; hold_reason: string | null; sim_day: number; quote_version: number; quote: Quote;
  kyc_case_id: string | null; lines: OrderLine[]; messages: { text: string; sim_day: number; label: string }[];
  substitute_offer: { failed: string; substitute: string | null; substitute_name: string | null; substitute_description: string | null } | null;
};

const key = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
// Each user action gets one key; creating an order uses a key derived from the session and quote version,
// so a double tap or a network retry can never create two orders.
const postIdem = <T,>(path: string, body: unknown, idemKey: string = key()) =>
  call<T>(path, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idemKey }, body: JSON.stringify(body) });

export class ApiError extends Error {
  constructor(public status: number, message: string, public needsReload = false) { super(message); }
}

// CSRF (POLICIES.md §13). The server computes the expected token from the HttpOnly session cookie, so
// this client only has to present the right one. Sources, in order: the token held in memory (from the
// start-session response), the readable udyam_csrf cookie, then GET /api/advisor/csrf. If a request is
// refused for its token, we fetch a fresh one and retry once.
// The cookie is read by splitting document.cookie. An earlier version used a regex that only matched
// when udyam_csrf was the first cookie, which broke the app whenever another localhost cookie came first.
let memoryToken: string | null = null;
export const setCsrfToken = (t: string | null) => { memoryToken = t; };

function cookieValue(name: string): string {
  for (const part of document.cookie.split(";")) {
    const eq = part.indexOf("=");
    if (eq > 0 && part.slice(0, eq).trim() === name) return decodeURIComponent(part.slice(eq + 1).trim());
  }
  return "";
}

async function refreshToken(): Promise<string> {
  const res = await fetch("/api/advisor/csrf", { credentials: "same-origin" });
  if (!res.ok) return "";
  memoryToken = (await res.json()).csrf_token ?? "";
  return memoryToken ?? "";
}

async function errorFor(res: Response): Promise<ApiError> {
  let detail: unknown = res.statusText;
  let code = "";
  try { const j = await res.json(); detail = j.detail ?? detail; code = j.code ?? ""; } catch { /* not JSON */ }
  const text = typeof detail === "string" ? detail : JSON.stringify(detail);
  if (res.status === 403 && code === "no_session_cookie") return new ApiError(403, i18n.t("errors.cookies"), true);
  if (res.status === 403 && (code === "bad_csrf" || /CSRF/i.test(text))) return new ApiError(403, i18n.t("errors.reload"), true);
  return new ApiError(res.status, text);
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const mutating = method !== "GET";
  for (let attempt = 0; attempt < 2; attempt++) {
    const headers = new Headers(init?.headers);
    if (mutating) {
      const token = (attempt === 0 ? memoryToken || cookieValue("udyam_csrf") : await refreshToken()) || "";
      if (token) headers.set("X-CSRF-Token", token);
    }
    const res = await fetch(path, { ...init, headers, credentials: "same-origin" });
    if (res.ok) return res.json() as Promise<T>;
    const err = await errorFor(res);
    // A refused token on the first try: get a fresh one from the server and try once more.
    if (mutating && attempt === 0 && err.status === 403 && err.needsReload && !path.startsWith("/api/bo/")) continue;
    throw err;
  }
  throw new ApiError(500, "unreachable");
}

const post = <T,>(path: string, body: unknown) =>
  call<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  health: () => call<{ business_as_of: string; demo_clock: boolean; advisor: { llm: string } }>("/api/health"),
  options: () => call<Options>("/api/advisor/options"),
  start: async (language: string, ref?: string | null) => {
    const r = await post<Turn & { session_id: string; csrf_token: string; partner: { id: string; name: string } | null }>(
      "/api/advisor/sessions", { language, ...(ref ? { ref } : {}) });
    setCsrfToken(r.csrf_token);
    return r;
  },
  send: (sid: string, text: string) => post<Turn>(`/api/advisor/sessions/${sid}/messages`, { text }),
  confirm: (sid: string, edits: Record<string, unknown>) => post<Recommendation>(`/api/advisor/sessions/${sid}/confirm`, { edits }),
  preview: (sid: string, items: { product_id: string; quantity: number }[]) => post<Preview>(`/api/advisor/sessions/${sid}/quote`, { items }),
  accept: (sid: string, items: { product_id: string; quantity: number }[]) =>
    post<{ version: number; quote: Quote; lines: Line[] }>(`/api/advisor/sessions/${sid}/accept`, { items }),
  end: (sid: string) => post<{ deleted: boolean }>(`/api/advisor/sessions/${sid}/end`, {}),
  consent: (sid: string, purpose: string, decision: "given" | "declined", language: string, team?: string) =>
    post<{ event_id: string }>("/api/consents", { session_id: sid, purpose, decision, language, ...(team ? { team } : {}) }),
  withdraw: (sid: string, purpose: string) => post<{ effects: string[] }>("/api/consents/withdraw", { session_id: sid, purpose }),
  gstinCheck: (sid: string, gstin: string) =>
    post<{ status: string; gstin?: string; registry: string; prefill?: Record<string, string> }>("/api/registry/gstin-check", { session_id: sid, gstin }),
  openCase: (sid: string) => post<{ case_id: string }>("/api/kyc/cases", { session_id: sid }),
  upload: (caseId: string, docType: string, file: File) => {
    const form = new FormData();
    form.append("doc_type", docType);
    form.append("file", file);
    return call<Upload>(`/api/kyc/cases/${caseId}/documents`, { method: "POST", body: form });
  },
  submit: (caseId: string, productIds: string[]) => post<KycView>(`/api/kyc/cases/${caseId}/submit`, { product_ids: productIds }),
  specimens: () => call<{ sets: Record<string, string[]> }>("/api/demo/specimens"),
  specimenFile: async (setId: string, docType: string) => {
    const res = await fetch(`/api/demo/specimens/${setId}_${docType}`);
    if (!res.ok) throw new ApiError(res.status, res.statusText);
    return new File([await res.blob()], `${setId}_${docType}.png`, { type: "image/png" });
  },
  confirmReading: (caseId: string, accept: boolean) => post<KycView>(`/api/kyc/cases/${caseId}/confirm-identifier`, { field: "gstin", accept }),
};

export const orders = {
  create: (sid: string, version: number) => postIdem<Order>("/api/orders", { session_id: sid, quote_version: version }, `order-${sid}-v${version}`),
  get: (sid: string, id: string) => call<Order>(`/api/orders/${id}?session_id=${encodeURIComponent(sid)}`),
  submitKyc: (sid: string, id: string, caseId: string) => postIdem<Order>(`/api/orders/${id}/submit-kyc`, { session_id: sid, case_id: caseId }),
  continueWithout: (sid: string, id: string) => postIdem<Order>(`/api/orders/${id}/continue-without-excluded`, { session_id: sid }),
  feasibility: (sid: string, id: string, accept: boolean) => postIdem<Order>(`/api/orders/${id}/feasibility-decision`, { session_id: sid, accept_substitute: accept }),
  reschedule: (sid: string, id: string, pid: string) => post<Order>(`/api/orders/${id}/reschedule`, { session_id: sid, product_id: pid }),
  cancel: (sid: string, id: string) => postIdem<Order>(`/api/orders/${id}/cancel`, { session_id: sid }),
  demoAdvance: (sid: string, id: string, days: number) => post<Order>(`/api/demo/orders/${id}/advance`, { session_id: sid, days }),
  demoFailFeasibility: (sid: string, id: string, pid: string) => post<Order>(`/api/demo/orders/${id}/fail-feasibility`, { session_id: sid, product_id: pid }),
};

export const inr = (n: number) => "₹" + n.toLocaleString("en-IN");

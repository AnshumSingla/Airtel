import { Fragment, useCallback, useEffect, useState } from "react";
import i18n from "../i18n";
import { ApiError, inr } from "../api";
import { staff, type AuditEntry, type Callback, type Lead, type ReviewCase, type ReviewItem, type StaffUser } from "../staffApi";
import { Btn, Card, Chip, ErrorNote } from "../ui";

// Internal tool: English only. Finding texts reuse the owner app's English strings.
const en = i18n.getFixedT("en");

const ROLE_LABEL: Record<StaffUser["role"], string> = {
  sales_agent: "Sales agent", partner: "Partner", kyc_reviewer: "KYC reviewer", admin: "Admin",
};
const DEMO_USERS = ["sales1", "partner_sharma", "partner_metro", "reviewer1", "admin1"];

function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reload = useCallback(async () => {
    setBusy(true); setError(null);
    try { setData(await fn()); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { void reload(); }, [reload]);
  return { data, error, busy, reload, setData };
}

function Login({ onUser }: { onUser: (u: StaffUser) => void }) {
  const [username, setUsername] = useState("sales1");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try { onUser(await staff.login(username, password)); }
    catch (err) { setError(err instanceof ApiError && err.status === 423 ? "Too many failed attempts. Try again in 15 minutes." : (err as Error).message); }
    finally { setBusy(false); }
  }
  const field = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-[15px]";
  return (
    <Card className="mx-auto max-w-sm">
      <h1 className="text-xl font-bold">Back office sign-in</h1>
      <form onSubmit={submit} className="mt-4 flex flex-col gap-3 text-sm">
        <label>Username
          <select className={field} value={username} onChange={(e) => setUsername(e.target.value)}>
            {DEMO_USERS.map((u) => <option key={u}>{u}</option>)}
          </select>
        </label>
        <label>Password
          <input className={field} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <Btn type="submit" disabled={busy || !password}>Sign in</Btn>
      </form>
      <ErrorNote message={error} />
      <p className="mt-4 text-[11px] leading-snug text-ink-400">
        Demo accounts only. Passwords are generated each time the server starts and written to
        <code className="mx-1 rounded bg-slate-100 px-1">backend/.demo-staff-credentials.txt</code> (not committed).
        After five wrong passwords an account locks for 15 minutes.
      </p>
    </Card>
  );
}

function LeadQueue({ me }: { me: StaffUser }) {
  const { data, error, busy, reload, setData } = useLoad(staff.queue);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const replace = (l: Lead) => setData((data ?? []).map((x) => (x.session_id === l.session_id ? l : x)));

  async function claim(l: Lead) { setActionError(null); try { replace(await staff.claim(l.session_id)); } catch (e) { setActionError((e as Error).message); } }
  async function addNote(l: Lead) {
    const text = (notes[l.session_id] ?? "").trim(); if (!text) return;
    setActionError(null);
    try { replace(await staff.note(l.session_id, text)); setNotes({ ...notes, [l.session_id]: "" }); } catch (e) { setActionError((e as Error).message); }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Leads shared with {me.role === "partner" ? me.display : "Accel Business sales"}</h2>
        <Btn variant="outline" onClick={reload} disabled={busy}>Refresh</Btn>
      </div>
      <p className="text-xs text-ink-600">Only applications whose owner chose to share them with your team appear here. You see their summary card, never the chat or any identifier.</p>
      <ErrorNote message={error ?? actionError} />
      {data?.length === 0 && <Card><p className="text-sm text-ink-600">No leads have been shared with your team yet.</p></Card>}
      {data?.map((l) => (
        <Card key={l.session_id}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="font-semibold">{l.summary.business_type ?? "Business"} · {l.summary.city ?? "city not given"}</p>
              <p className="text-xs text-ink-600">
                {l.summary.employees ?? "?"} people · {l.summary.sites ?? "?"} site{l.summary.sites === 1 ? "" : "s"} · GSTIN {l.summary.has_gstin ? "yes" : "no"}
                {l.summary.needs.length > 0 && <> · wants {l.summary.needs.join(", ")}</>}
              </p>
            </div>
            <div className="text-right">
              <Chip tone="brand">{l.stage}</Chip>
              {l.monthly_incl_tax !== null && <p className="mt-1 text-sm font-semibold tabular-nums">{inr(l.monthly_incl_tax)} / month</p>}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
            <span className="text-ink-400">Ref {l.lead_ref}</span>
            {l.claimed_by ? <Chip tone="slate">Claimed by {l.claimed_by} until {new Date(l.claim_until!).toLocaleString()}</Chip>
              : <Btn variant="outline" className="!py-1 text-xs" onClick={() => claim(l)}>Claim (48 h)</Btn>}
          </div>
          {l.notes.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm">
              {l.notes.map((n, i) => <li key={i} className="rounded-lg bg-slate-50 px-2.5 py-1.5"><span className="text-ink-400">{n.author}: </span>{n.text}</li>)}
            </ul>
          )}
          <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); void addNote(l); }}>
            <input className="flex-1 rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm" maxLength={500} placeholder="Add a call note"
              aria-label={`Note for lead ${l.lead_ref}`} value={notes[l.session_id] ?? ""} onChange={(e) => setNotes({ ...notes, [l.session_id]: e.target.value })} />
            <Btn type="submit" variant="outline" className="!py-1 text-xs">Add</Btn>
          </form>
        </Card>
      ))}
    </div>
  );
}

function Callbacks() {
  const { data, error } = useLoad(staff.callbacks);
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">Call-back list</h2>
      {data && <p className="text-xs text-ink-600">{data.label} Showing the top {data.leads.length} of {data.total.toLocaleString("en-IN")} dropped leads whose reason our process caused.</p>}
      <ErrorNote message={error} />
      <Card className="overflow-x-auto !p-0">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="text-[11px] uppercase tracking-wide text-ink-400">
            <tr><th className="px-3 py-2">#</th><th className="px-3 py-2">Business</th><th className="px-3 py-2">Dropped because</th><th className="px-3 py-2 text-right">p(activate)</th><th className="px-3 py-2 text-right">Expected ₹/month</th></tr>
          </thead>
          <tbody>
            {data?.leads.map((c: Callback, i) => (
              <Fragment key={c.lead_id}>
                <tr className="cursor-pointer border-t border-slate-100 hover:bg-slate-50" onClick={() => setOpen(open === c.lead_id ? null : c.lead_id)}>
                  <td className="px-3 py-2 text-ink-400">{i + 1}</td>
                  <td className="px-3 py-2"><span className="font-medium">{c.business_name}</span><span className="block text-[11px] text-ink-400">{c.business_type} · {c.city} · {c.contact_name} ({c.contact_role})</span></td>
                  <td className="px-3 py-2 text-ink-600">{c.drop_reason}<span className="block text-[11px] text-ink-400">reached: {c.stage_reached}</span></td>
                  <td className="px-3 py-2 text-right tabular-nums">{(c.p_activate * 100).toFixed(1)}%</td>
                  <td className="px-3 py-2 text-right font-semibold tabular-nums">{inr(c.expected_monthly_revenue)}</td>
                </tr>
                {open === c.lead_id && (
                  <tr className="bg-slate-50"><td /><td colSpan={4} className="px-3 py-2 text-xs text-ink-600">
                    Why it ranks here: {c.why.join(" · ")}. GSTIN {c.gstin ?? "none"}.
                  </td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="text-[11px] text-ink-400">Baseline score: activation rate of similar historical leads (segment, GSTIN yes/no, source), smoothed towards the overall rate, times the segment's median bundle. Revenue, not margin.</p>
    </div>
  );
}

function Referrals() {
  const { data, error } = useLoad(staff.referrals);
  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">Your referrals</h2>
      <ErrorNote message={error} />
      {data && (
        <Card>
          <dl className="grid grid-cols-3 gap-3 text-center">
            {([["Sessions started", data.sessions_started], ["Orders placed", data.orders_placed], ["Orders completed", data.orders_completed]] as const).map(([label, v]) => (
              <div key={label}><dt className="text-[11px] text-ink-400">{label}</dt><dd className="mt-1 text-lg font-bold">{String(v)}</dd></div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-ink-600">{data.note}</p>
        </Card>
      )}
    </div>
  );
}

function Review() {
  const queue = useLoad<ReviewItem[]>(staff.reviewQueue);
  const [open, setOpen] = useState<ReviewCase | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function view(id: string) { setError(null); setDone(null); try { setOpen(await staff.reviewCase(id)); setReason(""); } catch (e) { setError((e as Error).message); } }
  async function decide(approve: boolean) {
    if (!open) return; setError(null);
    try {
      const r = await staff.decide(open.case_id, approve, reason);
      setDone(`${approve ? "Approved" : "Rejected"}. Case is now "${r.outcome}"; ${r.orders_moved} order${r.orders_moved === 1 ? "" : "s"} moved.`);
      setOpen(null); await queue.reload();
    } catch (e) { setError((e as Error).message); }
  }

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">KYC cases waiting for review</h2>
      <p className="text-xs text-ink-600">Automated checks flagged these. Opening a case shows full identifiers and is recorded in the audit log.</p>
      {done && <p className="rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-700" role="status">{done}</p>}
      <ErrorNote message={error ?? queue.error} />
      {queue.data?.length === 0 && !open && <Card><p className="text-sm text-ink-600">Nothing waiting for review.</p></Card>}
      {!open && queue.data?.map((c) => (
        <Card key={c.case_id}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div><p className="font-medium">Case {c.case_id.slice(0, 8)}</p><p className="text-[11px] text-ink-400">{new Date(c.updated_at).toLocaleString()} · GSTIN {c.gstin ?? "not read"}</p></div>
            <div className="flex flex-wrap gap-1">{c.findings.map((f) => <Chip key={f} tone="warn">{f}</Chip>)}</div>
            <Btn variant="outline" onClick={() => view(c.case_id)}>Open</Btn>
          </div>
        </Card>
      ))}
      {open && (
        <Card>
          <p className="rounded-lg bg-warn-50 px-3 py-2 text-xs text-warn-600">Full identifiers are shown below. This view is recorded in the audit log.</p>
          <h3 className="mt-3 font-semibold">Case {open.case_id.slice(0, 8)}: {open.outcome.replace(/_/g, " ")}</h3>
          <p className="text-xs text-ink-600">Registry status: {open.gstin_status ?? "unknown"} · business proof: {open.business_proof ?? "none"}</p>
          <ul className="mt-3 space-y-1.5 text-sm">
            {open.findings.map((f, i) => (
              <li key={i} className="flex gap-2"><Chip tone={f.level === "review" ? "warn" : f.level === "action" ? "bad" : "slate"}>{f.doc ?? "case"}</Chip>
                <span className="text-ink-600">{en(`findings.${f.code}`, { defaultValue: f.code })}</span></li>
            ))}
          </ul>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {Object.entries(open.fields).map(([doc, fields]) => (
              <div key={doc} className="rounded-xl bg-slate-50 p-3">
                <p className="text-xs font-semibold">{doc.replace(/_/g, " ")}</p>
                <dl className="mt-1 grid grid-cols-[auto,1fr] gap-x-3 gap-y-0.5 text-xs">
                  {Object.entries(fields).map(([k, v]) => <Fragment key={k}><dt className="text-ink-400">{k.replace(/_/g, " ")}</dt><dd className="break-all">{v}</dd></Fragment>)}
                </dl>
              </div>
            ))}
          </div>
          <label className="mt-4 block text-sm">Decision reason (required, 3 to 200 characters)
            <input className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
          <div className="mt-3 flex flex-wrap gap-2">
            <Btn disabled={reason.trim().length < 3} onClick={() => decide(true)}>Approve</Btn>
            <Btn variant="danger" disabled={reason.trim().length < 3} onClick={() => decide(false)}>Ask owner to fix</Btn>
            <Btn variant="ghost" onClick={() => setOpen(null)}>Back</Btn>
          </div>
        </Card>
      )}
    </div>
  );
}

function Admin() {
  const log = useLoad<AuditEntry[]>(staff.audit);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function retention() {
    setError(null);
    try { const r = await staff.retention(); setResult(Object.entries(r).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(", ")); await log.reload(); }
    catch (e) { setError((e as Error).message); }
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Audit log</h2>
        <Btn variant="outline" onClick={retention}>Run retention job now</Btn>
      </div>
      {result && <p className="rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-700" role="status">Retention job ran: {result}.</p>}
      <ErrorNote message={error ?? log.error} />
      <p className="text-xs text-ink-600">Latest 100 events. Identifiers are masked; opening full identifiers is itself an event.</p>
      <Card className="overflow-x-auto !p-0">
        <table className="w-full min-w-[620px] text-left text-xs">
          <thead className="text-[11px] uppercase tracking-wide text-ink-400"><tr><th className="px-3 py-2">When</th><th className="px-3 py-2">Who</th><th className="px-3 py-2">Action</th><th className="px-3 py-2">Target</th><th className="px-3 py-2">Detail</th></tr></thead>
          <tbody>
            {log.data?.map((e) => (
              <tr key={e.seq} className="border-t border-slate-100">
                <td className="whitespace-nowrap px-3 py-1.5 text-ink-400">{new Date(e.at).toLocaleTimeString()}</td>
                <td className="px-3 py-1.5">{e.actor}<span className="text-ink-400"> ({e.role})</span></td>
                <td className="px-3 py-1.5 font-medium">{e.action}</td><td className="px-3 py-1.5">{e.target}</td><td className="px-3 py-1.5 text-ink-600">{e.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

const TABS: Record<StaffUser["role"], [string, () => JSX.Element][]> = {
  sales_agent: [["Leads", () => <></>], ["Call-backs", () => <Callbacks />]],
  partner: [["Leads", () => <></>], ["Referrals", () => <Referrals />]],
  kyc_reviewer: [["KYC review", () => <Review />]],
  admin: [["Audit log", () => <Admin />]],
};

export default function StaffApp() {
  const [me, setMe] = useState<StaffUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [tab, setTab] = useState(0);

  useEffect(() => { staff.me().then(setMe).catch(() => setMe(null)).finally(() => setChecking(false)); }, []);
  useEffect(() => { setTab(0); }, [me?.username]);

  async function signOut() { await staff.logout().catch(() => undefined); setMe(null); }

  const tabs = me ? TABS[me.role] : [];
  return (
    <div className="mx-auto min-h-screen max-w-4xl px-4 pb-10">
      <header className="sticky top-0 z-10 -mx-4 bg-slate-50/95 px-4 pb-2 pt-3 backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <img src="/icon.svg" alt="" className="h-7 w-7" />
            <div className="leading-tight"><p className="text-sm font-bold">Back office</p><p className="text-[11px] text-ink-400">Udyam Digital · {me ? `${me.display}` : "staff"}</p></div>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <a className="text-brand-700 underline" href="/">Owner app</a>
            {me && <Btn variant="outline" className="!py-1" onClick={signOut}>Sign out</Btn>}
          </div>
        </div>
        <p className="mt-2 rounded-lg bg-warn-50 px-2.5 py-1.5 text-[11px] text-warn-600">Demo with synthetic data. Staff accounts are demo-only; every view here is recorded in the audit log.</p>
        {me && tabs.length > 1 && (
          <div role="tablist" className="mt-2 flex gap-1">
            {tabs.map(([name], i) => (
              <button key={name} role="tab" aria-selected={tab === i} onClick={() => setTab(i)}
                className={`rounded-full px-3 py-1 text-xs font-semibold ${tab === i ? "bg-brand-500 text-white" : "bg-slate-200 text-ink-600"}`}>{name}</button>
            ))}
          </div>
        )}
      </header>
      <main className="mt-4">
        {checking ? <p className="text-sm text-ink-400">Checking sign-in…</p>
          : !me ? <Login onUser={setMe} />
          : (me.role === "sales_agent" || me.role === "partner") && tab === 0 ? <LeadQueue me={me} />
          : tabs[tab]?.[1]()}
        {me && <p className="mt-6 text-[11px] text-ink-400">Signed in as {me.username} ({ROLE_LABEL[me.role]}). Sessions end after 30 minutes idle or 8 hours.</p>}
      </main>
    </div>
  );
}

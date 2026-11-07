import { useState } from "react";
import { useTranslation } from "react-i18next";
import { inr, orders, type Order } from "../api";
import { Btn, Card, Chip, ErrorNote } from "../ui";

const FIXED = new Set(["P01", "P02", "P03", "P04", "P05", "P06"]);

function lineTone(s: string): "brand" | "slate" | "warn" | "bad" {
  if (s === "ACTIVE") return "brand";
  if (["EXCLUDED", "CANCELLED", "FEASIBILITY_FAILED", "INSTALL_FAILED"].includes(s)) return "bad";
  if (s === "PENDING") return "slate";
  return "warn";
}

export function Tracker({ sid, order, setOrder, onFixDocuments }: { sid: string; order: Order; setOrder: (o: Order) => void; onFixDocuments: () => void }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = order.order_id;

  async function act(fn: () => Promise<Order>) {
    setBusy(true); setError(null);
    try { setOrder(await fn()); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  const excluded = order.lines.filter((l) => l.status === "EXCLUDED");
  const failableLine = order.lines.find((l) => FIXED.has(l.product_id) && l.status === "FEASIBILITY_CHECK");
  const open = !["COMPLETED", "CANCELLED"].includes(order.status);
  const tone = order.status === "COMPLETED" ? "border-brand-500" : order.status === "ON_HOLD" ? "border-warn-600" : order.status === "CANCELLED" ? "border-bad-600" : "border-slate-300";

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("tracker.title")}</h2>
      <Card className={`border-l-4 ${tone}`}>
        <p className="text-base font-semibold">{t(`tracker.status.${order.status}`)}</p>
        {order.hold_reason && <p className="mt-1 text-sm text-ink-600">{t(`tracker.hold.${order.hold_reason}`)}</p>}
        <p className="mt-1 text-[11px] text-ink-400">{t("tracker.version", { v: order.quote_version })} · {inr(order.quote.monthly_incl_tax)} / {t("quote.monthlyTotal").toLowerCase()}</p>

        {order.hold_reason === "KYC_ACTION" && <Btn className="mt-3" onClick={onFixDocuments}>{t("tracker.fixDocs")}</Btn>}
        {order.hold_reason === "BUNDLE_CHANGE_NEEDED" && (
          <div className="mt-3">
            <ul className="text-sm text-ink-600">{excluded.map((l) => <li key={l.product_id}>• {l.name}</li>)}</ul>
            <Btn className="mt-2" disabled={busy} onClick={() => act(() => orders.continueWithout(sid, id))}>{t("tracker.continueWithout")}</Btn>
            <p className="mt-1 text-[11px] text-ink-400">{t("tracker.reaccept")}</p>
          </div>
        )}
        {order.hold_reason === "FEASIBILITY_DECISION" && order.substitute_offer && (
          <div className="mt-3 rounded-xl bg-slate-50 p-3">
            {order.substitute_offer.substitute ? (
              <>
                <p className="text-sm font-semibold">{t("tracker.substitute", { name: order.substitute_offer.substitute_name })}</p>
                <p className="text-xs text-ink-600">{order.substitute_offer.substitute_description}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Btn disabled={busy} onClick={() => act(() => orders.feasibility(sid, id, true))}>{t("tracker.switch")}</Btn>
                  <Btn variant="outline" disabled={busy} onClick={() => act(() => orders.feasibility(sid, id, false))}>{t("tracker.without")}</Btn>
                </div>
                <p className="mt-1 text-[11px] text-ink-400">{t("tracker.reacceptSubstitute")}</p>
              </>
            ) : <Btn variant="outline" disabled={busy} onClick={() => act(() => orders.feasibility(sid, id, false))}>{t("tracker.without")}</Btn>}
          </div>
        )}
      </Card>

      <Card>
        <ul className="divide-y divide-slate-100">
          {order.lines.map((l) => (
            <li key={l.product_id} className="flex items-center justify-between gap-2 py-2.5">
              <div>
                <p className="text-sm font-medium">{l.name} <span className="text-ink-400">× {l.quantity}</span></p>
                {l.days_left !== null && !["ACTIVE", "CANCELLED", "EXCLUDED"].includes(l.status) &&
                  <p className="text-[11px] text-ink-400">{l.days_left === 0 ? t("tracker.today") : t("tracker.eta", { count: l.days_left })}</p>}
                {l.reason === "DEP_LOST" && <p className="text-[11px] text-bad-600">{t("tracker.depLost")}</p>}
              </div>
              <div className="flex flex-col items-end gap-1">
                <Chip tone={lineTone(l.status)}>{t(`tracker.line.${l.status}`)}</Chip>
                {l.status === "SCHEDULED" && open && <button className="text-[11px] text-brand-700 underline" disabled={busy}
                  onClick={() => act(() => orders.reschedule(sid, id, l.product_id))}>{t("tracker.reschedule")}</button>}
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-ink-400">{t("tracker.etaNote")}</p>
      </Card>

      <Card>
        <p className="text-sm font-semibold">{t("tracker.inbox")}</p>
        <ul className="mt-2 space-y-2">
          {[...order.messages].reverse().map((m, i) => (
            <li key={i} className="rounded-xl bg-[#e7f6ee] px-3 py-2 text-sm">
              {m.text}
              <span className="mt-0.5 block text-[10px] uppercase tracking-wide text-ink-400">{t("tracker.simulated")} · {t("tracker.day", { n: m.sim_day })}</span>
            </li>
          ))}
        </ul>
      </Card>

      {open && <Btn variant="danger" disabled={busy} onClick={() => act(() => orders.cancel(sid, id))}>{t("tracker.cancel")}</Btn>}

      <Card className="border border-dashed border-warn-600 bg-warn-50/60">
        <p className="text-xs font-semibold text-warn-600">{t("tracker.demoTitle")}</p>
        <p className="text-[11px] text-ink-600">{t("tracker.demoNote", { n: order.sim_day })}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Btn variant="outline" disabled={busy || !open} onClick={() => act(() => orders.demoAdvance(sid, id, 1))}>{t("tracker.plus", { count: 1 })}</Btn>
          <Btn variant="outline" disabled={busy || !open} onClick={() => act(() => orders.demoAdvance(sid, id, 5))}>{t("tracker.plus", { count: 5 })}</Btn>
          {failableLine && <Btn variant="outline" disabled={busy} onClick={() => act(() => orders.demoFailFeasibility(sid, id, failableLine.product_id))}>{t("tracker.failFeasibility")}</Btn>}
        </div>
      </Card>
      <ErrorNote message={error} />
    </div>
  );
}

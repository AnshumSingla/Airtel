import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, inr, type Addon, type Line, type Preview, type Recommendation } from "../api";
import { Btn, Card, Chip, ErrorNote, Stepper } from "../ui";

type Item = { product_id: string; quantity: number };

export function QuoteScreen({ sid, rec, onAccepted }: { sid: string; rec: Recommendation; onAccepted: (version: number, items: Item[]) => void }) {
  const { t } = useTranslation();
  const reasons = useMemo(() => Object.fromEntries(rec.lines.map((l) => [l.product_id, l])), [rec]);
  const [items, setItems] = useState<Item[]>(rec.lines.map((l) => ({ product_id: l.product_id, quantity: l.quantity })));
  const [preview, setPreview] = useState<Preview>({ lines: rec.lines, rejected: [], quote: rec.quote, addons: rec.addons });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    api.preview(sid, items).then((p) => live && setPreview(p)).catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [sid, items]);

  const setQty = (pid: string, q: number) => setItems(items.map((i) => (i.product_id === pid ? { ...i, quantity: q } : i)));
  const remove = (pid: string) => setItems(items.filter((i) => i.product_id !== pid));
  const add = (a: Addon) => setItems([...items, { product_id: a.product_id, quantity: a.default_quantity }]);

  async function accept() {
    setBusy(true); setError(null);
    try { const v = await api.accept(sid, items); onAccepted(v.version, items); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  const q = preview.quote;
  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("quote.title")}</h2>
      {preview.lines.map((l: Line) => {
        const base = reasons[l.product_id];
        return (
          <Card key={l.product_id}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold">{l.name}</p>
                <p className="text-xs text-ink-600">{base?.description}</p>
              </div>
              <p className="whitespace-nowrap text-right text-sm font-semibold tabular-nums">{inr(l.monthly)}<span className="block text-[11px] font-normal text-ink-400">/ {t("quote.monthlyTotal").toLowerCase()}</span></p>
            </div>
            <ul className="mt-2 space-y-1">
              {(base?.reasons ?? []).filter((r) => r.tag !== "QTY_DEFAULT").map((r, i) => (
                <li key={i} className="text-sm"><Chip tone={r.tag === "YOU_TOLD_US" ? "brand" : "slate"}>{t(`quote.tags.${r.tag}`)}</Chip> <span className="text-ink-600">{r.text}</span></li>
              ))}
              {l.info?.includes("INFO_OFF_TARGET") && !base?.reasons?.some((r) => r.tag === "INFO_OFF_TARGET") && <li><Chip tone="warn">{t("quote.tags.INFO_OFF_TARGET")}</Chip></li>}
            </ul>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-600">
              <span className="flex items-center gap-2">{t("quote.qty")} <Stepper value={l.quantity} onChange={(n) => setQty(l.product_id, n)} /> <span>{l.unit} · {inr(l.unit_monthly)}</span></span>
              <button className="text-bad-600 underline" onClick={() => remove(l.product_id)}>{t("quote.remove")}</button>
            </div>
            <p className="mt-1 text-[11px] text-ink-400">
              {t("quote.term")}: {l.term_months > 1 ? t("quote.months", { n: l.term_months }) : t("quote.monthly")} · {t("quote.install", { count: l.install_days })}
              {l.one_time > 0 && <> · {t("quote.oneTime")}: {inr(l.one_time)}</>}
            </p>
          </Card>
        );
      })}

      {[...rec.excluded, ...preview.rejected].length > 0 && (
        <Card className="bg-slate-50">
          <p className="text-sm font-semibold">{t("quote.excluded")}</p>
          <ul className="mt-1 space-y-1 text-sm text-ink-600">
            {[...rec.excluded, ...preview.rejected].map((e, i) => <li key={i}><span className="font-medium">{e.name}</span>: {e.text}</li>)}
          </ul>
        </Card>
      )}

      {preview.addons.length > 0 && (
        <div>
          <p className="mb-1.5 text-sm font-semibold">{t("quote.addons")}</p>
          <div className="flex flex-col gap-2">
            {preview.addons.map((a) => (
              <div key={a.product_id} className="flex items-center justify-between rounded-xl bg-white px-3 py-2 ring-1 ring-slate-200">
                <div><p className="text-sm font-medium">{a.name}</p><p className="text-[11px] text-ink-400">{inr(a.unit_monthly)} {a.unit}{a.setup_per_unit ? ` · ${t("quote.oneTime")} ${inr(a.setup_per_unit)}` : ""}</p></div>
                <Btn variant="outline" onClick={() => add(a)}>{t("quote.add")}</Btn>
              </div>
            ))}
          </div>
        </div>
      )}

      <Card className="sticky bottom-2 ring-brand-500">
        <dl className="grid grid-cols-2 gap-y-1 text-sm">
          <dt>{t("quote.monthlyTotal")} <span className="text-ink-400">({t("quote.exTax")})</span></dt><dd className="text-right tabular-nums">{inr(q.monthly_ex_tax)}</dd>
          <dt className="text-ink-600">{q.tax_label}</dt><dd className="text-right tabular-nums text-ink-600">{inr(q.monthly_tax)}</dd>
          <dt className="font-semibold">{t("quote.monthlyTotal")} ({t("quote.incl")})</dt><dd className="text-right text-base font-bold tabular-nums">{inr(q.monthly_incl_tax)}</dd>
          <dt>{t("quote.oneTime")} ({t("quote.incl")})</dt><dd className="text-right tabular-nums">{inr(q.one_time_incl_tax)}</dd>
          <dt className="font-semibold">{t("quote.firstPayment")}</dt><dd className="text-right font-semibold tabular-nums">{inr(q.first_payment)}</dd>
        </dl>
        <p className="mt-2 text-[11px] leading-snug text-ink-400">{t("quote.rateCard")} {t("quote.esign")}</p>
        <Btn className="mt-3 w-full" disabled={busy || preview.rejected.length > 0 || items.length === 0} onClick={accept}>{t("quote.accept")}</Btn>
        <ErrorNote message={error} />
      </Card>
    </div>
  );
}

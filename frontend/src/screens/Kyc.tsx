import { Fragment, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, type KycView, type Upload } from "../api";
import { Btn, Card, Chip, ErrorNote } from "../ui";

const SLOTS = ["gst_certificate", "udyam_certificate", "address_proof", "signatory_id"] as const;

export function Kyc({ sid, productIds, names }: { sid: string; productIds: string[]; names: Record<string, string> }) {
  const { t } = useTranslation();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [uploads, setUploads] = useState<Record<string, Upload | "reading">>({});
  const [view, setView] = useState<KycView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.openCase(sid).then((c) => setCaseId(c.case_id)).catch((e) => setError(e.message));
  }, [sid]);

  async function pick(slot: string, file: File | undefined) {
    if (!file || !caseId) return;
    setUploads((u) => ({ ...u, [slot]: "reading" })); setView(null); setError(null);
    try { const r = await api.upload(caseId, slot, file); setUploads((u) => ({ ...u, [slot]: r })); }
    catch (e) { setUploads((u) => { const n = { ...u }; delete n[slot]; return n; }); setError((e as Error).message); }
  }

  async function run() {
    if (!caseId) return;
    setBusy(true); setError(null);
    try { setView(await api.submit(caseId, productIds)); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function confirm(accept: boolean) {
    if (!caseId) return;
    setBusy(true);
    try {
      const v = await api.confirmReading(caseId, accept);
      setView({ ...v, lines: (await api.submit(caseId, productIds)).lines });
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  const tone = view?.outcome === "checks_passed" ? "brand" : view?.outcome === "manual_review" ? "warn" : "bad";
  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("kyc.title")}</h2>
      <p className="text-sm text-ink-600">{t("kyc.hint")}</p>
      {SLOTS.map((slot) => {
        const u = uploads[slot];
        return (
          <Card key={slot}>
            <div className="flex items-center justify-between gap-3">
              <p className="font-medium">{t(`kyc.${slot}`)}</p>
              <label className="cursor-pointer rounded-lg border border-brand-500 px-3 py-1.5 text-sm font-semibold text-brand-700">
                {u && u !== "reading" ? t("kyc.replace") : t("kyc.upload")}
                <input type="file" accept="image/jpeg,image/png" capture="environment" className="sr-only"
                  disabled={!caseId || u === "reading"} onChange={(e) => pick(slot, e.target.files?.[0])} />
              </label>
            </div>
            {u === "reading" && <p className="mt-2 text-sm text-ink-400">{t("kyc.reading")}</p>}
            {u && u !== "reading" && (
              <div className="mt-2 text-sm">
                {u.refused ? <Chip tone="bad">{t(`kyc.refused.${u.refused}`, { defaultValue: u.refused })}</Chip>
                  : u.seen_type && u.seen_type !== slot ? <Chip tone="warn">{t("kyc.wrongType")}</Chip>
                  : <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-0.5 text-xs text-ink-600">
                      {Object.entries(u.fields).map(([k, v]) => <Fragment key={k}><dt className="text-ink-400">{k.replace(/_/g, " ")}</dt><dd className="truncate">{v}</dd></Fragment>)}
                    </dl>}
              </div>
            )}
          </Card>
        );
      })}
      <Btn disabled={!caseId || busy || !Object.values(uploads).some((u) => u !== "reading")} onClick={run}>{busy ? t("kyc.checking") : t("kyc.submit")}</Btn>
      <ErrorNote message={error} />

      {view && (
        <Card className={`border-l-4 ${tone === "brand" ? "border-brand-500" : tone === "warn" ? "border-warn-600" : "border-bad-600"}`}>
          <p className="text-base font-semibold">{t(`kyc.outcome.${view.outcome}`)}</p>
          <p className="mt-1 text-[11px] text-ink-400">{t("kyc.notVerified")} {view.registry}.</p>
          <ul className="mt-3 space-y-1.5 text-sm">
            {view.findings.map((f, i) => (
              <li key={i} className="flex gap-2">
                <Chip tone={f.level === "action" ? "bad" : f.level === "review" ? "warn" : "slate"}>{f.doc ? t(`kyc.${f.doc}`).split(" (")[0] : "•"}</Chip>
                <span className="text-ink-600">{t(`findings.${f.code}`, { defaultValue: f.code })}</span>
              </li>
            ))}
          </ul>
          {view.confirm.map((c) => (
            <div key={c.field} className="mt-4 rounded-xl bg-brand-50 p-3">
              <p className="text-sm font-semibold">{t("kyc.confirmTitle")}</p>
              <p className="mt-1 font-mono text-lg tracking-wider">{c.reading}</p>
              <div className="mt-2 flex gap-2">
                <Btn onClick={() => confirm(true)} disabled={busy}>{t("kyc.confirmYes")}</Btn>
                <Btn variant="danger" onClick={() => confirm(false)} disabled={busy}>{t("kyc.confirmNo")}</Btn>
              </div>
            </div>
          ))}
          {view.lines && view.lines.length > 0 && (
            <div className="mt-4">
              <p className="text-sm font-semibold">{t("kyc.linesTitle")}</p>
              <ul className="mt-1 space-y-1 text-sm">
                {view.lines.map((l) => (
                  <li key={l.product_id} className="flex justify-between gap-2">
                    <span>{names[l.product_id] ?? l.product_id}</span>
                    <Chip tone={l.eligible ? "brand" : "bad"}>{l.eligible ? t("kyc.lineOk") : t("kyc.lineNo")}</Chip>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

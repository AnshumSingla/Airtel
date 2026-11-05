import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, type Options, type Recommendation, type Turn } from "./api";
import { Chat } from "./screens/Chat";
import { Choices } from "./screens/Choices";
import { Kyc } from "./screens/Kyc";
import { QuoteScreen } from "./screens/QuoteScreen";
import { Summary } from "./screens/Summary";
import { Btn, Card, ErrorNote } from "./ui";

type Step = "start" | "chat" | "summary" | "quote" | "choices" | "kyc" | "ended";

export default function App() {
  const { t, i18n } = useTranslation();
  const [step, setStep] = useState<Step>("start");
  const [sid, setSid] = useState<string | null>(null);
  const [first, setFirst] = useState<Turn | null>(null);
  const [summaryTurn, setSummaryTurn] = useState<Turn | null>(null);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [accepted, setAccepted] = useState<{ version: number; ids: string[] } | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [demoDate, setDemoDate] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.health().then((h) => h.demo_clock && setDemoDate(h.business_as_of)).catch(() => undefined);
    api.options().then(setOptions).catch(() => undefined);
  }, []);

  useEffect(() => { window.scrollTo({ top: 0 }); }, [step]);

  function reset(msg?: string) {
    setSid(null); setFirst(null); setSummaryTurn(null); setRec(null); setAccepted(null);
    setStep("start"); setError(msg ?? null);
  }

  async function start() {
    setBusy(true); setError(null);
    try {
      const s = await api.start(i18n.language === "hi" ? "hi" : "en");
      setSid(s.session_id); setFirst(s); setStep("chat");
    } catch (e) { setError(t("errors.generic", { msg: (e as Error).message })); }
    finally { setBusy(false); }
  }

  async function confirm(edits: Record<string, unknown>) {
    if (!sid) return;
    setBusy(true); setError(null);
    try { setRec(await api.confirm(sid, edits)); setStep("quote"); }
    catch (e) {
      if (e instanceof ApiError && e.status === 404) reset(t("errors.expired"));
      else setError(t("errors.generic", { msg: (e as Error).message }));
    } finally { setBusy(false); }
  }

  async function endAndDelete() {
    if (sid) { try { await api.end(sid); } catch { /* already gone */ } }
    reset(); setStep("ended");
  }

  const steps: [Step[], string][] = [[["start", "chat", "summary"], "advisor"], [["quote"], "quote"], [["choices", "kyc"], "kyc"]];
  const names = Object.fromEntries((rec?.lines ?? []).map((l) => [l.product_id, l.name]));

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col px-4 pb-6">
      <header className="sticky top-0 z-10 -mx-4 bg-slate-50/95 px-4 pb-2 pt-3 backdrop-blur">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/icon.svg" alt="" className="h-7 w-7" />
            <div className="leading-tight"><p className="text-sm font-bold">{t("app")}</p><p className="text-[11px] text-ink-400">{t("brand")} · demo</p></div>
          </div>
          <div className="flex items-center gap-1" role="group" aria-label={t("start.lang")}>
            {(["en", "hi"] as const).map((l) => (
              <button key={l} onClick={() => i18n.changeLanguage(l)} aria-pressed={i18n.language === l}
                className={`rounded-md px-2 py-1 text-xs font-semibold ${i18n.language === l ? "bg-brand-500 text-white" : "text-ink-600"}`}>{l === "en" ? "EN" : "हिं"}</button>
            ))}
          </div>
        </div>
        <p className="mt-2 rounded-lg bg-warn-50 px-2.5 py-1.5 text-[11px] text-warn-600">
          {t("banner")} {demoDate && <span className="font-semibold">· {t("demoDate", { date: demoDate })}</span>}
        </p>
        {step !== "start" && step !== "ended" && (
          <ol className="mt-2 flex gap-1 text-[11px]">
            {steps.map(([group, key]) => (
              <li key={key} className={`flex-1 rounded-full py-1 text-center ${group.includes(step) ? "bg-brand-500 text-white" : "bg-slate-200 text-ink-600"}`}>{t(`steps.${key}`)}</li>
            ))}
          </ol>
        )}
      </header>

      <main className="mt-3 flex-1">
        {step === "start" && (
          <Card>
            <h1 className="text-xl font-bold leading-snug">{t("start.title")}</h1>
            <p className="mt-3 text-sm text-ink-600">{t("start.p1")}</p>
            <Btn className="mt-5 w-full" onClick={start} disabled={busy}>{t("start.cta")}</Btn>
          </Card>
        )}
        {step === "ended" && (
          <Card><p>{t("mydata.done")}</p><Btn className="mt-4" onClick={() => setStep("start")}>{t("restart")}</Btn></Card>
        )}
        {step === "chat" && sid && first && (
          <Chat sid={sid} first={first} onExpired={() => reset(t("errors.expired"))}
            onConfirm={(turn) => { setSummaryTurn(turn); setStep("summary"); }} />
        )}
        {step === "summary" && summaryTurn?.summary && (
          <Summary summary={summaryTurn.summary} options={options} busy={busy} onConfirm={confirm} />
        )}
        {step === "quote" && sid && rec && (
          <QuoteScreen sid={sid} rec={rec} onAccepted={(v, items) => { setAccepted({ version: v, ids: items.map((i) => i.product_id) }); setStep("choices"); }} />
        )}
        {step === "choices" && sid && (
          <>
            {accepted && <p className="mb-3 text-sm text-brand-700">{t("quote.accepted", { v: accepted.version })}</p>}
            <Choices sid={sid} onDone={(p3) => (p3 ? setStep("kyc") : setStep("choices"))} />
          </>
        )}
        {step === "kyc" && sid && <Kyc sid={sid} productIds={accepted?.ids ?? []} names={names} />}
        <ErrorNote message={error} />
      </main>

      {sid && (
        <footer className="mt-8 border-t border-slate-200 pt-3 text-center">
          <p className="text-xs font-semibold">{t("mydata.title")}</p>
          <p className="mx-auto mt-1 max-w-xs text-[11px] text-ink-400">{t("mydata.endd")}</p>
          <Btn variant="danger" className="mt-2" onClick={endAndDelete}>{t("mydata.end")}</Btn>
        </footer>
      )}
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, type Turn } from "../api";
import { Btn, Card, ErrorNote } from "../ui";

type Msg = { from: "bot" | "me"; text: string };

export function Chat({ sid, first, onConfirm, onExpired }: { sid: string; first: Turn; onConfirm: (t: Turn) => void; onExpired: () => void }) {
  const { t } = useTranslation();
  const [msgs, setMsgs] = useState<Msg[]>([{ from: "bot", text: first.reply }]);
  const [turn, setTurn] = useState<Turn>(first);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gstin, setGstin] = useState("");
  const [gstinResult, setGstinResult] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  // Braces matter: newer browsers return a Promise from scrollIntoView, and React would call it as a cleanup.
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, turn]);

  async function send(value: string, label?: string) {
    if (!value.trim() || busy) return;
    setBusy(true); setError(null);
    setMsgs((m) => [...m, { from: "me", text: label ?? value }]);
    setText("");
    try {
      const next = await api.send(sid, value);
      setMsgs((m) => [...m, { from: "bot", text: next.reply }]);
      setTurn(next);
      if (next.status === "confirm") onConfirm(next);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) onExpired();
      else setError(t("errors.generic", { msg: (e as Error).message }));
    } finally { setBusy(false); }
  }

  async function checkGstin() {
    setError(null);
    try {
      await api.consent(sid, "P2", "given", turn.language === "hi" ? "hi" : "en");
      const r = await api.gstinCheck(sid, gstin);
      setGstinResult(t(`gstin.${r.status}`) + (r.gstin ? ` (${r.gstin})` : ""));
      setGstin("");
    } catch (e) { setError(t("errors.generic", { msg: (e as Error).message })); }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2" aria-live="polite">
        {msgs.map((m, i) => (
          <div key={i} className={`max-w-[85%] whitespace-pre-line rounded-2xl px-3.5 py-2.5 text-[15px] leading-snug ${m.from === "bot" ? "self-start bg-white ring-1 ring-slate-200" : "self-end bg-brand-500 text-white"}`}>
            {m.text}
          </div>
        ))}
        {busy && <div className="self-start rounded-2xl bg-white px-3.5 py-2.5 text-ink-400 ring-1 ring-slate-200">{t("chat.typing")}</div>}
      </div>

      {turn.consent_card && !gstinResult && (
        <Card className="border-l-4 border-brand-500">
          <p className="text-sm font-semibold">{t("gstin.title")}</p>
          <p className="mt-1 text-sm text-ink-600">{t("gstin.notice")}</p>
          <input value={gstin} onChange={(e) => setGstin(e.target.value.toUpperCase())} maxLength={15} placeholder={t("gstin.placeholder")}
            autoComplete="off" className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm uppercase tracking-wider" />
          <div className="mt-3 flex gap-2">
            <Btn onClick={checkGstin} disabled={gstin.length !== 15}>{t("gstin.allow")}</Btn>
            <Btn variant="ghost" onClick={() => setGstinResult(t("gstin.skip"))}>{t("gstin.skip")}</Btn>
          </div>
        </Card>
      )}
      {gstinResult && <p className="text-sm text-ink-600">GSTIN: {gstinResult}</p>}

      {turn.buttons.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs text-ink-400">{t("chat.buttonsOnly")}</p>
          <div className="flex flex-wrap gap-2">
            {turn.buttons.map((b) => (
              <Btn key={b.value} variant="outline" disabled={busy} onClick={() => send(b.value, b.label)}>{b.label}</Btn>
            ))}
          </div>
        </div>
      )}

      <form className="sticky bottom-0 flex gap-2 bg-slate-50 py-2" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t("chat.placeholder")} maxLength={500}
          className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-[15px]" aria-label={t("chat.placeholder")} />
        <Btn type="submit" disabled={busy || !text.trim()}>{t("chat.send")}</Btn>
      </form>
      <ErrorNote message={error} />
      <div ref={end} />
    </div>
  );
}

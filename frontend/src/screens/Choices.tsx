import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { Btn, Card, ErrorNote } from "../ui";

function ChoiceRow({ on, set, title, desc, badge }: { on: boolean; set: (v: boolean) => void; title: string; desc: string; badge?: string }) {
  const id = useId();
  return (
    <div className="flex gap-3 rounded-xl p-3 ring-1 ring-slate-200">
      <input id={id} type="checkbox" className="mt-1 h-5 w-5 shrink-0 accent-brand-500" checked={on}
        aria-describedby={`${id}-d`} onChange={(e) => set(e.target.checked)} />
      <label htmlFor={id} className="cursor-pointer">
        <span className="font-semibold">{title}</span> {badge && <span className="ml-1 text-[11px] text-brand-700">{badge}</span>}
        <span id={`${id}-d`} className="mt-0.5 block text-sm text-ink-600">{desc}</span>
      </label>
    </div>
  );
}

export function Choices({ sid, onDone }: { sid: string; onDone: (p3: boolean) => void }) {
  const { t, i18n } = useTranslation();
  const [p3, setP3] = useState(false);   // unticked by default (POLICIES.md §2)
  const [p5, setP5] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lang = i18n.language === "hi" ? "hi" : "en";

  async function save() {
    setError(null);
    try {
      await api.consent(sid, "P3", p3 ? "given" : "declined", lang);
      await api.consent(sid, "P5", p5 ? "given" : "declined", lang);
      setDeclined(!p3);
      onDone(p3);
    } catch (e) { setError((e as Error).message); }
  }

  return (
    <Card>
      <h2 className="text-lg font-semibold">{t("choices.title")}</h2>
      <p className="mt-1 text-sm text-ink-600">{t("choices.intro")}</p>
      <div className="mt-4 flex flex-col gap-3">
        <ChoiceRow on={p3} set={setP3} title={t("choices.p3")} desc={t("choices.p3d")} badge={t("choices.required")} />
        <ChoiceRow on={p5} set={setP5} title={t("choices.p5")} desc={t("choices.p5d")} />
      </div>
      {declined && <p className="mt-3 rounded-lg bg-warn-50 px-3 py-2 text-sm text-warn-600">{t("choices.declined")}</p>}
      <Btn className="mt-5 w-full" onClick={save}>{t("choices.continue")}</Btn>
      <ErrorNote message={error} />
    </Card>
  );
}

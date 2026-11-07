import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Options, Summary as S } from "../api";
import { Btn, Card } from "../ui";

export function Summary({ summary, options, onConfirm, busy }: { summary: S; options: Options | null; busy: boolean; onConfirm: (edits: Record<string, unknown>) => void }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === "hi" ? "hi" : "en";
  const [s, setS] = useState<S>(summary);
  const set = (k: keyof S, v: unknown) => setS({ ...s, [k]: v } as S);
  const field = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-[15px]";

  function submit() {
    const edits: Record<string, unknown> = {
      segment: s.segment, city_tier: s.city_tier, employees: s.employees, sites: s.sites,
      has_gstin: s.has_gstin, needs: s.needs, budget: s.budget || null,
    };
    if (s.city) edits.city = s.city;
    onConfirm(edits);
  }

  return (
    <Card>
      <h2 className="text-lg font-semibold">{t("summary.title")}</h2>
      {s.business_type && <p className="mt-1 text-sm text-ink-600">{t("summary.business")}: {s.business_type}</p>}
      {s.assumed.length > 0 && <p className="mt-1 text-xs text-warn-600">{t("summary.assumed", { list: s.assumed.join(", ") })}</p>}
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <label className="col-span-2">{t("summary.segment")}
          <select className={field} value={s.segment ?? ""} onChange={(e) => set("segment", e.target.value)}>
            {options?.segments.map((o) => <option key={o.code} value={o.code}>{o.label[lang]}</option>)}
          </select>
        </label>
        <label>{t("summary.city")}
          <select className={field} value={s.city ?? ""} onChange={(e) => {
            const c = options?.cities.find((x) => x.name === e.target.value);
            setS({ ...s, city: e.target.value || null, city_tier: c ? c.tier : s.city_tier });
          }}>
            <option value="">—</option>
            {options?.cities.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </label>
        <label>{t("summary.tier")}
          <select className={field} value={s.city_tier ?? 2} disabled={!!s.city} onChange={(e) => set("city_tier", Number(e.target.value))}>
            <option value={1}>{t("summary.tier1")}</option><option value={2}>{t("summary.tier2")}</option>
          </select>
        </label>
        <label>{t("summary.employees")}
          <input type="number" min={1} max={500} className={field} value={s.employees ?? 1} onChange={(e) => set("employees", Number(e.target.value))} />
        </label>
        <label>{t("summary.sites")}
          <input type="number" min={1} max={50} className={field} value={s.sites ?? 1} onChange={(e) => set("sites", Number(e.target.value))} />
        </label>
        <fieldset className="col-span-2">
          <legend>{t("summary.gstin")}</legend>
          <div className="mt-1 flex gap-2">
            {[true, false].map((v) => (
              <button key={String(v)} type="button" onClick={() => set("has_gstin", v)}
                className={`rounded-lg px-4 py-1.5 ring-1 ${s.has_gstin === v ? "bg-brand-500 text-white ring-brand-500" : "bg-white ring-slate-300"}`}>
                {v ? t("summary.yes") : t("summary.no")}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset className="col-span-2">
          <legend>{t("summary.needs")}</legend>
          <div className="mt-1 flex flex-wrap gap-2">
            {options?.needs.map((n) => {
              const on = s.needs.includes(n.product_id);
              return (
                <button key={n.product_id} type="button" aria-pressed={on}
                  onClick={() => set("needs", on ? s.needs.filter((x) => x !== n.product_id) : [...s.needs, n.product_id])}
                  className={`rounded-full px-3 py-1 text-xs ring-1 ${on ? "bg-brand-50 text-brand-700 ring-brand-500" : "bg-white text-ink-600 ring-slate-300"}`}>
                  {n.label[lang].charAt(0).toUpperCase() + n.label[lang].slice(1)}
                </button>
              );
            })}
          </div>
        </fieldset>
        <label className="col-span-2">{t("summary.budget")}
          <input type="number" min={0} className={field} value={s.budget ?? ""} onChange={(e) => set("budget", e.target.value ? Number(e.target.value) : null)} />
        </label>
      </div>
      <Btn className="mt-5 w-full" disabled={busy} onClick={submit}>{t("summary.confirm")}</Btn>
    </Card>
  );
}

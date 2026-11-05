import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Btn({ variant = "primary", className = "", ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "outline" | "danger" }) {
  const styles = {
    primary: "bg-brand-500 text-white hover:bg-brand-600 disabled:bg-slate-300",
    outline: "border border-brand-500 text-brand-700 bg-white hover:bg-brand-50 disabled:opacity-50",
    ghost: "text-brand-700 hover:bg-brand-50",
    danger: "border border-bad-600 text-bad-600 bg-white hover:bg-bad-50",
  }[variant];
  return <button className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition ${styles} ${className}`} {...rest} />;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200 ${className}`}>{children}</div>;
}

export function Chip({ children, tone = "brand" }: { children: ReactNode; tone?: "brand" | "slate" | "warn" | "bad" }) {
  const t = { brand: "bg-brand-50 text-brand-700", slate: "bg-slate-100 text-ink-600", warn: "bg-warn-50 text-warn-600", bad: "bg-bad-50 text-bad-600" }[tone];
  return <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${t}`}>{children}</span>;
}

export function Stepper({ value, onChange, min = 1, max = 200 }: { value: number; onChange: (n: number) => void; min?: number; max?: number }) {
  return (
    <div className="inline-flex items-center rounded-lg ring-1 ring-slate-300">
      <button aria-label="decrease" className="px-2.5 py-1 text-lg leading-none text-ink-600 disabled:opacity-30" disabled={value <= min} onClick={() => onChange(value - 1)}>−</button>
      <span className="min-w-[2ch] text-center text-sm font-semibold tabular-nums">{value}</span>
      <button aria-label="increase" className="px-2.5 py-1 text-lg leading-none text-ink-600 disabled:opacity-30" disabled={value >= max} onClick={() => onChange(value + 1)}>+</button>
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return <p role="alert" className="mt-3 rounded-lg bg-bad-50 px-3 py-2 text-sm text-bad-600">{message}</p>;
}

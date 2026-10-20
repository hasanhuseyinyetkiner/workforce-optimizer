import type { ReactNode } from "react";

export function PageIntro({
  eyebrow,
  title,
  description,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
}) {
  return (
    <header className="mb-6 space-y-1">
      {eyebrow ? <p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">{eyebrow}</p> : null}
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      {description ? <p className="max-w-2xl text-sm text-stone-600 dark:text-stone-400">{description}</p> : null}
    </header>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section
      className={`rounded-2xl border border-stone-200/80 bg-white/80 p-4 shadow-sm backdrop-blur dark:border-stone-800 dark:bg-stone-950/70 ${className}`}
    >
      {children}
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <Card>
      <p className="text-xs font-medium uppercase tracking-wide text-stone-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold tabular tracking-tight">{value}</p>
      {hint ? <p className="mt-1 text-xs text-stone-500">{hint}</p> : null}
    </Card>
  );
}

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" }) {
  const styles =
    variant === "primary"
      ? "bg-accent text-white hover:brightness-110 disabled:opacity-50"
      : variant === "danger"
        ? "bg-rose-600 text-white hover:bg-rose-500 disabled:opacity-50"
        : "border border-stone-300 bg-transparent hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-900";
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition ${styles} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const value = status || "UNKNOWN";
  const tone =
    value === "OPTIMAL"
      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
      : value === "FEASIBLE"
        ? "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200"
        : value === "INFEASIBLE"
          ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
          : "bg-stone-200 text-stone-700 dark:bg-stone-800 dark:text-stone-300";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-wide ${tone}`}>
      {value}
    </span>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <Card className="text-center">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm text-stone-500">{detail}</p>
    </Card>
  );
}

export function ErrorState({ error }: { error: Error }) {
  return (
    <Card className="border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
      <p className="font-medium">Could not load data</p>
      <p className="mt-1 text-sm">{error.message}</p>
    </Card>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return <Card className="animate-pulse text-sm text-stone-500">{label}</Card>;
}

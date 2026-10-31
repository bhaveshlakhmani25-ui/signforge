// Shared workbench primitives. One source so status styling can't drift between pages.
export const card = "rounded-xl border border-lavender bg-white p-4";

/** A load or action failure with a way out. Keeps whatever the user already entered on the page. */
export function ErrorBanner({ message, onRetry, retryLabel = "Try again" }: { message: string; onRetry?: () => void; retryLabel?: string }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-900">
      <p className="min-w-0 flex-1 break-words">{message}</p>
      {onRetry && <button onClick={onRetry} className="rounded-lg border border-red-700 px-3 py-1 font-medium text-red-900 hover:bg-red-100">{retryLabel}</button>}
    </div>
  );
}

/** Marks synthetic fixture data everywhere it appears (CLAUDE.md: DEMO DATA is always visibly labelled). */
export function DemoBadge({ className = "" }: { className?: string }) {
  return <span className={`rounded-md bg-amber-200 px-2 py-0.5 text-xs font-semibold text-amber-950 ${className}`}>DEMO DATA</span>;
}

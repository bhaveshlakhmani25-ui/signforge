import Link from "next/link";

/** The camera has two jobs: collect consented samples for the corpus, or interpret signing live. */
export default function CameraModes({ active }: { active: "collect" | "interpret" }) {
  const tab = (href: string, id: typeof active, label: string, hint: string) => (
    <Link href={href} aria-current={active === id ? "page" : undefined}
          className={`rounded-full px-5 py-2 text-sm font-semibold transition-colors ${active === id ? "bg-navy text-white" : "text-navy hover:bg-white"}`}>
      {label}<span className="sr-only">: {hint}</span>
    </Link>
  );
  return (
    <nav aria-label="Camera mode" className="inline-flex gap-1 rounded-full border border-lavender bg-background p-1">
      {tab("/capture", "collect", "Collect samples", "record consented clips for the corpus")}
      {tab("/interpret", "interpret", "Interpret live", "read signing from the camera in real time")}
    </nav>
  );
}

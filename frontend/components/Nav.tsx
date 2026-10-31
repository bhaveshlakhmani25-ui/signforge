"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LIVE = [["/dashboard", "Dashboard"], ["/capture", "Capture"], ["/interpret", "Interpret"], ["/corpus", "Corpus & review"], ["/models", "Models & evaluation"],
                    ["/active-learning", "Active learning"], ["/benchmark", "Benchmark"]] as const;
// Shown so the roadmap is visible, but disabled: these pages are not built yet.
const PLANNED = ["Export", "Project settings"];

export default function Nav() {
  const path = usePathname();
  return (
    <nav aria-label="Main" className="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
      {LIVE.map(([href, label]) => {
        const active = path.startsWith(href);
        return (
          <Link key={href} href={href} aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap px-3 py-2 text-sm ${active ? "bg-[#efeee9] font-semibold text-navy" : "text-lavender hover:bg-white/10 hover:text-white"}`}>
            {label}
          </Link>
        );
      })}
      <p className="hidden px-3 pt-4 pb-1 text-xs uppercase tracking-wider text-lavender/60 md:block">Planned</p>
      {PLANNED.map((label) => (
        <span key={label} title="Not built yet"
              className="hidden whitespace-nowrap px-3 py-2 text-sm text-lavender/60 md:block">
          {label}<span className="sr-only"> (planned, not built yet)</span>
        </span>
      ))}
    </nav>
  );
}

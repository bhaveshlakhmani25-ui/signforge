import Link from "next/link";
import Nav from "@/components/Nav";
import ProjectSwitcher from "@/components/ProjectSwitcher";

/** The workbench: every app page shares the sidebar. The public story page at / does not. */
export default function WorkbenchLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="workbench min-h-full md:flex">
      <aside className="bg-navy px-3 py-3 md:sticky md:top-0 md:h-screen md:w-56 md:shrink-0 md:py-6">
        <Link href="/" className="mb-3 block px-3 text-white md:mb-6">
          <span className="f-display text-lg font-bold uppercase tracking-[0.2em]">Signforge</span>
          <span className="block text-xs text-lavender">Corpus builder</span>
        </Link>
        <ProjectSwitcher />
        <Nav />
      </aside>
      <main className="mx-auto w-full min-w-0 max-w-6xl flex-1 px-4 py-6 md:px-8">
        {process.env.NEXT_PUBLIC_SNAPSHOT === "1" && (
          <p role="note" className="mb-6 border border-lavender border-l-4 border-l-teal bg-white px-4 py-3 text-sm text-indigo">
            <strong className="text-navy">Public read-only demo.</strong> You are browsing a frozen snapshot of the public datasets and DEMO DATA.
            The live camera works here: the model runs in your browser. Recording, review and training need the backend: run SIGNFORGE locally (see the README).
          </p>
        )}
        {children}
      </main>
    </div>
  );
}

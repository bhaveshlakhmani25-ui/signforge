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
      <main className="mx-auto w-full min-w-0 max-w-6xl flex-1 px-4 py-6 md:px-8">{children}</main>
    </div>
  );
}

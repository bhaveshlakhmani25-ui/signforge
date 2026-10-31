import type { Metadata } from "next";
import Link from "next/link";
import Nav from "@/components/Nav";
import ProjectSwitcher from "@/components/ProjectSwitcher";
import "./globals.css";

export const metadata: Metadata = {
  title: "SIGNFORGE",
  description: "Low-resource sign-language corpus builder: the model helps decide what data to collect next.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full md:flex">
        <aside className="bg-navy px-3 py-3 md:sticky md:top-0 md:h-screen md:w-56 md:shrink-0 md:py-6">
          <Link href="/" className="mb-3 block px-3 font-bold tracking-wide text-white md:mb-6">
            SIGNFORGE<span className="block text-xs font-normal tracking-normal text-lavender">Corpus builder</span>
          </Link>
          <ProjectSwitcher />
          <Nav />
        </aside>
        <main className="mx-auto w-full min-w-0 max-w-6xl flex-1 px-4 py-6 md:px-8">{children}</main>
      </body>
    </html>
  );
}

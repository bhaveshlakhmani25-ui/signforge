import type { Metadata } from "next";
import { Bodoni_Moda, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// Self-hosted by next/font at build time: no font request is made at the venue.
const display = Bodoni_Moda({ subsets: ["latin"], style: ["normal", "italic"], axes: ["opsz"], variable: "--font-display" });
const body = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-body" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "SIGNFORGE",
  description: "Low-resource sign-language corpus builder: the model helps decide what data to collect next.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`h-full antialiased ${display.variable} ${body.variable} ${mono.variable}`}>
      <body className="min-h-full">{children}</body>
    </html>
  );
}

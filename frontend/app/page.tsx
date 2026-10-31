import { Bodoni_Moda, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import Landing from "./_landing/Landing";

// Self-hosted by next/font at build time: the page makes no font request at the venue.
const display = Bodoni_Moda({ subsets: ["latin"], style: ["normal", "italic"], axes: ["opsz"], variable: "--font-display" });
const body = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-body" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export default function Page() {
  return <div className={`${display.variable} ${body.variable} ${mono.variable}`}><Landing /></div>;
}

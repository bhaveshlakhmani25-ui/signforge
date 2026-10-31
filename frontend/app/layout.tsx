import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SIGNFORGE",
  description: "Low-resource sign-language corpus builder: the model helps decide what data to collect next.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full">{children}</body>
    </html>
  );
}

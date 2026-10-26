import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

const font = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600", "700"] });
export const metadata: Metadata = {
  title: "Crypty – Digital forensics and sanitization workspace",
  description: "Read-only forensic recovery and documented data sanitization.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className={`${font.className} bg-bg text-ink antialiased`}>{children}</body>
    </html>
  );
}

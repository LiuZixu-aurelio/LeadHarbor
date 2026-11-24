import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LeadHarbor · AI Lead Intelligence",
  description: "Discover, score, and convert high-intent distributor leads worldwide.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

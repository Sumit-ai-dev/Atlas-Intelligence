import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ATLAS ASSURANCE • Autonomous Assurance",
  description: "Atlas Assurance continuously verifies infrastructure projects through satellite evidence, document intelligence, field monitoring, and contractor reliability — closing the loop between detection, accountability, and prevention.",
  keywords: ["infrastructure assurance", "governance", "DPR analysis", "satellite monitoring", "procurement intelligence"],
  openGraph: {
    title: "ATLAS ASSURANCE",
    description: "Autonomous Assurance for Physical Infrastructure. Atlas detects. Atlas explains. Humans decide. Procurement learns.",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "ATLAS ASSURANCE",
    description: "Autonomous Assurance for Physical Infrastructure.",
  },
};


export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${outfit.variable} h-full antialiased`}>
      <body className="min-h-full font-sans bg-background text-foreground">{children}</body>
    </html>
  );
}

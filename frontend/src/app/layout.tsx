import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "CPQ Cognitive — Enterprise Configure, Price, Quote Platform",
    template: "%s | CPQ Cognitive",
  },
  description:
    "AI-native enterprise CPQ platform with Google Gemini copilot, Salesforce CRM sync, dynamic pricing engine, and multi-stage approval workflows.",
  keywords: ["CPQ", "configure price quote", "sales", "enterprise", "AI", "Salesforce"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-canvas-warm font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./compiled.css";
import React from "react";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SemanticGraph Cloud",
  description: "Enterprise Knowledge-Graph Substrate",
};

export const viewport: Viewport = {
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} antialiased dark`}
    >
      <body className="min-h-screen bg-page text-text font-sans">
        {children}
      </body>
    </html>
  );
}

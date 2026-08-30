import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agentic AI Slide Maker",
  description: "Production-grade AI presentation generation",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased font-sans min-h-screen">
        {children}
      </body>
    </html>
  );
}

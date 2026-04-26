import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ESG Intelligence Platform",
  description: "AI-Powered ESG Greenwashing Detection Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased font-sans">{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Hunt - Stop applying blind. Find tech jobs you're actually likely to get.",
  description: "Join the waitlist for smarter job matching. We crawl real company career pages to surface active tech roles — no reposted junk, no expired listings.",
  keywords: ["job search", "tech jobs", "software engineering", "product management", "job matching", "career"],
  openGraph: {
    title: "Hunt - Stop applying blind.",
    description: "Find tech jobs you're actually likely to get. Join the waitlist for smarter job matching.",
    url: "https://hunt.careers",
    siteName: "Hunt",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Hunt - Stop applying blind.",
    description: "Find tech jobs you're actually likely to get. Join the waitlist for smarter job matching.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}

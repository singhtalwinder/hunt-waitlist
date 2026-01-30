import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://hunt.careers"),
  title: "Hunt - Stop applying blind. Find tech jobs you're actually likely to get.",
  description: "Join the waitlist for smarter job matching. We crawl real company career pages to surface active tech roles — no reposted junk, no expired listings.",
  keywords: ["job search", "tech jobs", "software engineering", "product management", "job matching", "career"],
  icons: {
    icon: "/paper.png",
    shortcut: "/paper.png",
    apple: "/paper.png",
  },
  openGraph: {
    title: "Hunt - Stop applying blind.",
    description: "Find tech jobs you're actually likely to get. Join the waitlist for smarter job matching.",
    url: "https://hunt.careers",
    siteName: "Hunt",
    type: "website",
    images: [
      {
        url: "/og-image.png?v=2",
        width: 1220,
        height: 695,
        alt: "Hunt - Stop applying blind. Find tech jobs you're actually likely to get.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Hunt - Stop applying blind.",
    description: "Find tech jobs you're actually likely to get. Join the waitlist for smarter job matching.",
    images: ["/og-image.png?v=2"],
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

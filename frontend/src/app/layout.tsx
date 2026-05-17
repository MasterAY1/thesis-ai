import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://thesisai.vercel.app"),
  title: {
    default: "ThesisAI - AI-Powered Academic Project Evaluation",
    template: "%s | ThesisAI",
  },
  description:
    "Upload your final year project or thesis and receive instant, rubric-based feedback powered by AI. Graded against the official NMCN rubric with evidence-based deductions, supervisor notes, and recoverable marks.",
  keywords: [
    "thesis evaluation",
    "AI grading",
    "NMCN rubric",
    "academic evaluation",
    "Nigeria university",
    "project grading",
    "nursing thesis",
    "research project",
  ],
  authors: [{ name: "ThesisAI" }],
  creator: "ThesisAI",
  openGraph: {
    type: "website",
    locale: "en_NG",
    url: "https://thesisai.vercel.app",
    siteName: "ThesisAI",
    title: "ThesisAI - Grade Your Thesis Before Your Supervisor Does",
    description:
      "AI-powered academic evaluation engine aligned with the NMCN rubric. Get evidence-based feedback, rubric-aware scoring, and actionable improvement paths.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "ThesisAI - AI-Powered Academic Evaluation",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "ThesisAI - AI-Powered Academic Project Evaluation",
    description:
      "Upload your thesis and get instant rubric-based grading with evidence quotes, supervisor notes, and recoverable marks.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
  },
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`h-full antialiased`}
    >
      <body suppressHydrationWarning className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}

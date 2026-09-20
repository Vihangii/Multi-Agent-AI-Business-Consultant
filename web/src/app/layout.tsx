import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: {
    default: "AI Business Consultant",
    template: "%s · AI Business Consultant",
  },
  description:
    "Upload your sales data and get a cleaned dataset, a Prophet revenue forecast with what-if scenarios, and a fact-checked strategy report written by tool-using AI agents.",
  icons: { icon: "/icon.svg" },
};

// Applies the saved theme before first paint so there's no flash.
const themeScript = `
(function(){try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}

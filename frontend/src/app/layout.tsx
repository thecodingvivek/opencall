import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import { instrumentSerif } from "./fonts";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Speech studio | OpenCall",
  description: "Record your voice and turn it into text with OpenCall.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${instrumentSerif.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <main className="flex min-h-screen flex-col items-center justify-center bg-white px-8 text-center sm:hidden">
          <p className="text-sm font-medium tracking-[-0.03em]">opencall</p>
          <h1 className="mt-8 max-w-xs text-4xl tracking-[-0.06em]">A little more room, please.</h1>
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-[#777]">OpenCall is currently available on laptops and larger screens. Please open this page on your laptop to continue.</p>
        </main>
        <div className="hidden min-h-screen sm:block">{children}</div>
      </body>
    </html>
  );
}

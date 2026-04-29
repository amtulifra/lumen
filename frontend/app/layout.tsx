import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lumen",
  description: "Research intelligence layer for ML practitioners",
};

const navLinks = [
  { href: "/", label: "ingest" },
  { href: "/graph", label: "graph" },
  { href: "/frontier", label: "frontier" },
  { href: "/hypotheses", label: "hypotheses" },
  { href: "/benchmarks", label: "benchmarks" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-surface text-text">
        <header className="border-b border-border px-6 py-3 flex items-center gap-8">
          <Link href="/" className="text-accent font-semibold tracking-widest text-sm">
            lumen
          </Link>
          <nav className="flex gap-6">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-muted hover:text-text text-xs transition-colors"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Cruscotto dello studio",
  description: "Come lavora lo studio: costi, tempi e fasi di ogni progetto, in sola lettura.",
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { readonly children: ReactNode }) {
  return (
    <html lang="it">
      <body>
        <header className="top">
          <Link href="/" className="brand">
            Cruscotto dello studio
          </Link>
          <span className="badge">sola lettura</span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}

import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Timeline Cutter",
  description: "AI-assisted proxy review and Resolve export planning."
};

type RootLayoutProps = Readonly<{
  children: React.ReactNode;
}>;

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}


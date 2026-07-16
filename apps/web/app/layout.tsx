import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "African Founder Studies", template: "%s — African Founder Studies" },
  description: "An independent, citation-based educational research platform for African founders' public ideas."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

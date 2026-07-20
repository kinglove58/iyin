import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "African Founder Studies", template: "%s — African Founder Studies" },
  description: "Explore the experiences, convictions and practical lessons African founders share in public.",
  icons: {
    icon: [{ url: "/images/favicon.svg", type: "image/svg+xml" }],
    shortcut: "/images/favicon.svg",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

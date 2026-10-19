import "./globals.css";

export const metadata = { title: "Voice Operator", description: "AI lead qualification dashboard" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

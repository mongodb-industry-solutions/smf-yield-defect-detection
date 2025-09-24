import "@fontsource/geist-mono";
import "./globals.css";
import Header from "@/components/Header/Header";

export const metadata = {
  title: "SMF Yield Defect Detection",
  description: "Real-time semiconductor manufacturing monitoring powered by MongoDB",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "'Geist Mono', monospace" }}>
        <Header />
        <main style={{ paddingTop: '60px' }}>
          {children}
        </main>
      </body>
    </html>
  );
}

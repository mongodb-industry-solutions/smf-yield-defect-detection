import "@fontsource/geist-mono";
import "./globals.css";

export const metadata = {
  title: "Agentic Framework",
  description: "This AI Agent listens to complaints and advises on next course of action",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "'Geist Mono', monospace" }}>
        {children}
      </body>
    </html>
  );
}

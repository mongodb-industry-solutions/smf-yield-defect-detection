import "./globals.css";
import Header from "@/components/Header/Header";
import LeafyGreenProviderWrapper from "@/components/Providers/LeafyGreenProviderWrapper";

export const metadata = {
  title: "SMF Yield Defect Detection | MongoDB",
  description: "Real-time semiconductor manufacturing monitoring powered by MongoDB Atlas",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <LeafyGreenProviderWrapper>
          <Header />
          <main style={{ paddingTop: '60px' }}>
            {children}
          </main>
        </LeafyGreenProviderWrapper>
      </body>
    </html>
  );
}

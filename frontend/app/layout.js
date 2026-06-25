import "./globals.css";
import AppChrome from "./AppChrome";

export const metadata = {
  title: "Taqdeer · تقدير",
  description: "Taqdeer — bilingual (AR/EN) estimation & BoQ automation",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      {/* Bilingual type pair (matched Latin + Arabic cuts), per the brand brief. */}
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      <link
        href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600&display=swap"
        rel="stylesheet"
      />
      <body>
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}

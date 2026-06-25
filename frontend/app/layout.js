import "./globals.css";
import AppChrome from "./AppChrome";

export const metadata = {
  title: "Taqdeer · تقدير",
  description: "Taqdeer — bilingual (AR/EN) estimation & BoQ automation",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}

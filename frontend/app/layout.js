import "./globals.css";
import AppChrome from "./AppChrome";

export const metadata = {
  title: "BoQ Automation",
  description: "Bilingual (AR/EN) BoQ automation MVP",
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

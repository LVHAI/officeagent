import "./globals.css";

export const metadata = {
  title: "OfficeAgent",
  description: "Enterprise Intelligence Decision Agent Platform",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}

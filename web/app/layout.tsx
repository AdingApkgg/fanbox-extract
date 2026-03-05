import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";
import { SocketProvider } from "@/lib/socket";
import { Toaster } from "@/components/ui/toaster"
import "./globals.css";

export const metadata: Metadata = {
  title: "Fanbox Extractor",
  description: "Web UI for Fanbox Extractor",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="flex h-screen w-full overflow-hidden bg-background text-foreground">
        <SocketProvider>
          <Sidebar />
          <main className="flex-1 h-full overflow-y-auto p-8">
            {children}
          </main>
          <Toaster />
        </SocketProvider>
      </body>
    </html>
  );
}

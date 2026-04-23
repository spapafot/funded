import { ReactNode } from "react";
import { Navbar } from "./Navbar";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
      <footer className="border-t border-black/[0.06] bg-white/80 py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-gray-400 font-mono">funded.gr — Greek Startup Showcase</p>
          <nav className="flex items-center gap-5">
            <a href="/contact" className="text-xs text-gray-400 hover:text-gray-600 transition">Contact</a>
            <a href="/legal/terms" className="text-xs text-gray-400 hover:text-gray-600 transition">Terms</a>
            <a href="/legal/privacy" className="text-xs text-gray-400 hover:text-gray-600 transition">Privacy</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}

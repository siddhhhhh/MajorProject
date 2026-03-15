"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  LayoutDashboard, 
  SearchCode, 
  FileText, 
  History, 
  Settings, 
  LogOut,
  ShieldCheck,
  Menu,
  X,
  Bell
} from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Sidebar({ mobileOpen, setMobileOpen }: { mobileOpen: boolean, setMobileOpen: (open: boolean) => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<{name: string, email: string} | null>(null);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    if (userData) {
      setUser(JSON.parse(userData));
    } else {
      router.push("/login");
    }
  }, [router]);

  const navItems = [
    { name: "Dashboard", href: "/dashboard", icon: <LayoutDashboard className="w-5 h-5" /> },
    { name: "Analyze Company", href: "/dashboard/analyze", icon: <SearchCode className="w-5 h-5" /> },
    { name: "My Reports", href: "/dashboard/reports", icon: <FileText className="w-5 h-5" /> },
    { name: "History", href: "/dashboard/history", icon: <History className="w-5 h-5" /> },
    { name: "Settings", href: "/dashboard/settings", icon: <Settings className="w-5 h-5" /> },
  ];

  const handleLogout = () => {
    localStorage.removeItem("user");
    router.push("/login");
  };

  const SidebarContent = (
    <div className="flex flex-col h-full bg-neutral-900 text-neutral-300 w-64 border-r border-neutral-800">
      <div className="p-6 flex items-center gap-3">
        <div className="w-8 h-8 bg-primary-600 rounded-md flex items-center justify-center shrink-0">
          <ShieldCheck className="w-5 h-5 text-white" />
        </div>
        <span className="font-heading font-semibold text-lg text-white tracking-tight">
          ESG Intel
        </span>
        {/* Mobile Close Button */}
        <button 
          className="md:hidden ml-auto text-neutral-400 hover:text-white"
          onClick={() => setMobileOpen(false)}
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="px-4 py-6 flex-1 space-y-1">
        <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-4 px-2">Menu</div>
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.name}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors group ${
                isActive 
                  ? "bg-primary-900/50 text-primary-400 font-medium" 
                  : "hover:bg-neutral-800 hover:text-white"
              }`}
            >
              <div className={`${isActive ? "text-primary-400" : "text-neutral-500 group-hover:text-neutral-300"}`}>
                {item.icon}
              </div>
              <span className="text-sm">{item.name}</span>
            </Link>
          );
        })}
      </div>

      <div className="p-4 border-t border-neutral-800">
        <div className="flex items-center gap-3 mb-4 px-2">
          <div className="w-9 h-9 rounded-full bg-primary-800 flex items-center justify-center text-primary-100 font-medium uppercase shrink-0 border border-primary-700">
            {user?.name?.charAt(0) || "U"}
          </div>
          <div className="overflow-hidden">
            <div className="text-sm font-medium text-white truncate">{user?.name || "User"}</div>
            <div className="text-xs text-neutral-500 truncate">{user?.email || "user@example.com"}</div>
          </div>
        </div>
        <button 
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors w-full text-left text-sm hover:bg-neutral-800 hover:text-white text-neutral-400"
        >
          <LogOut className="w-5 h-5 text-neutral-500" />
          Logout
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside className="hidden md:block fixed inset-y-0 left-0 z-40 w-64 h-screen">
        {SidebarContent}
      </aside>

      {/* Mobile Sidebar */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="fixed inset-0 bg-neutral-900/80 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <div className="relative flex w-full max-w-xs flex-1">
            {SidebarContent}
          </div>
        </div>
      )}
    </>
  );
}

import { useState } from "react";
import { NavLink } from "react-router-dom";
import { motion } from "framer-motion";
import {
  LayoutDashboard, ScanLine, Activity, FileText,
  Clock, MessageSquare, Sun, Moon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/components/theme/ThemeProvider";

const items: { to: string; label: string; icon: any; badge?: string }[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/analyse", label: "New Analysis", icon: ScanLine, badge: "+" },
  { to: "/pipeline", label: "Live Pipeline", icon: Activity },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/history", label: "History", icon: Clock },
  { to: "/chat", label: "ESGLens AI", icon: MessageSquare },
];

export function Sidebar() {
  const [hover, setHover] = useState(false);
  const { theme, toggle } = useTheme();
  const expanded = hover;
  return (
    <motion.aside
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      animate={{ width: expanded ? 240 : 72 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="fixed left-0 top-8 bottom-0 z-40 glass border-r border-bg-border flex flex-col overflow-hidden"
    >
      <NavLink to="/" className="px-5 py-6 flex items-center gap-3 border-b border-bg-border">
        <div className="font-display text-2xl leading-none">
          <span className="italic text-text-primary">ESG</span>
          {expanded && <span className="text-teal-bright ml-1">Lens</span>}
        </div>
      </NavLink>

      <nav className="flex-1 py-4 px-3 space-y-1">
        {items.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            end={it.to === "/"}
            className={({ isActive }) =>
              cn(
                "group relative flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-all",
                "text-text-secondary hover:text-text-primary",
                isActive && "text-teal-bright bg-teal-bright/10"
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-2 bottom-2 w-[2px] bg-teal-bright rounded-r" />
                )}
                <it.icon className="h-[18px] w-[18px] shrink-0" />
                {expanded && (
                  <span className="whitespace-nowrap flex-1 flex items-center justify-between">
                    {it.label}
                    {it.badge && (
                      <span className="text-[10px] font-mono px-1.5 rounded bg-teal-bright/20 text-teal-bright">{it.badge}</span>
                    )}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-bg-border space-y-3">
        <button
          onClick={toggle}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-text-secondary hover:text-teal-bright hover:bg-teal-bright/10 transition text-sm"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun className="h-[18px] w-[18px] shrink-0" /> : <Moon className="h-[18px] w-[18px] shrink-0" />}
          {expanded && <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>}
        </button>
        {expanded ? (
          <div className="font-mono text-[10px] text-text-muted leading-relaxed">
            FCA ALIGNED | TCFD<br />GRI | ISSB
          </div>
        ) : (
          <div className="text-teal-bright text-[10px] font-mono text-center">UK</div>
        )}
      </div>
    </motion.aside>
  );
}
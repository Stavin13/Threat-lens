"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/events", label: "Events" },
  { href: "/ingest", label: "Ingest" },
  { href: "/reports", label: "Reports" },
  { href: "/system", label: "System" },
]

export function SiteHeader() {
  const pathname = usePathname()

  return (
    <header
      role="banner"
      className="sticky top-0 z-40 w-full border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60"
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-4">
          <Link href="/" className="font-semibold">
            <span className="sr-only">ThreatLens home</span>
            ThreatLens
          </Link>
          <nav aria-label="Main" className="hidden md:block">
            <ul className="flex items-center gap-2">
              {navItems.map((item) => {
                const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href))
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "rounded-md px-3 py-2 text-sm transition-colors",
                        active
                          ? "bg-secondary text-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-secondary",
                      )}
                    >
                      {item.label}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </nav>
        </div>
        {/* reserved for future actions (theme switcher, auth) */}
        <div className="text-xs text-muted-foreground">v0</div>
      </div>
    </header>
  )
}

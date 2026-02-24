import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "../auth/AuthContext";

const nav = [
  { to: "/stats", label: "Stats" },
  { to: "/alerts", label: "Alerts" },
  { to: "/policies", label: "Policies" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const { token, logout } = useAuth();

  return (
    <div className="min-h-screen bg-background">
      <div className="flex">
        {/* Sidebar */}
        <aside className="hidden md:flex md:w-64 md:flex-col border-r min-h-screen p-4">
          <div className="text-xl font-semibold">ExpenseVoice</div>
          <div className="text-sm text-muted-foreground mb-4">Admin Dashboard</div>
          <Separator className="my-3" />
          <nav className="flex flex-col gap-2">
            {nav.map((n) => {
              const active = pathname.startsWith(n.to);
              return (
                <Link
                  key={n.to}
                  to={n.to}
                  className={[
                    "rounded-xl px-3 py-2 text-sm",
                    active ? "bg-muted font-medium" : "hover:bg-muted/60",
                  ].join(" ")}
                >
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="mt-auto pt-4">
            {token && (
              <Button variant="outline" className="w-full" onClick={logout}>
                Logout
              </Button>
            )}
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1">
          {/* Topbar */}
          <header className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
            <div className="h-14 px-4 flex items-center justify-between">
              <div className="md:hidden font-semibold">ExpenseVoice</div>
              <div className="text-sm text-muted-foreground">
                Director / Admin view
              </div>
            </div>
          </header>

          <div className="p-4 md:p-6 max-w-6xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}

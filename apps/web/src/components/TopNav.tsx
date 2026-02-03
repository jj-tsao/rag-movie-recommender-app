import { Link, NavLink, useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/useToast";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useProfile } from "@/features/auth/hooks/useProfile";
import { signOut } from "@/features/auth/api";
import { isAnonymousUser } from "@/lib/session";

const NAV_ITEMS = [
  { label: "Explore", to: "/discover/explore" },
  { label: "For You", to: "/discover/for-you" },
  { label: "Watchlist", to: "/watchlist" },
] as const;

export default function TopNav() {
  const { user, loading } = useAuth();
  const isAnonymous = isAnonymousUser(user);
  const { displayName } = useProfile(isAnonymous ? undefined : user?.id);
  const metaName = (() => {
    const meta = user?.user_metadata as Record<string, unknown> | undefined;
    const v = meta && (meta as Record<string, unknown>)["display_name"];
    return typeof v === "string" ? v : undefined;
  })();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const mobileNavRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!mobileNavRef.current) return;
      if (!mobileNavRef.current.contains(e.target as Node)) {
        setMobileNavOpen(false);
      }
    }
    if (mobileNavOpen) {
      document.addEventListener("mousedown", onDocClick);
    }
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [mobileNavOpen]);

  async function handleSignOut() {
    const res = await signOut();
    if (!res.ok) {
      console.warn("Sign out failed", res.error);
      toast({ title: "Sign out failed", description: "Please try again.", variant: "destructive" });
      return;
    }
    toast({ title: "Signed out", description: "See you soon!", variant: "success" });
    navigate("/");
  }
  return (
    <header className="sticky top-0 z-50 w-full flex items-center justify-between px-1 sm:px-4 lg:px-6 py-3 sm:py-4 lg:py-4 bg-background/90 backdrop-blur-md shadow-[0_1px_0_0_rgba(197,165,114,0.15)] relative before:absolute before:inset-0 before:pointer-events-none before:opacity-[0.03] before:bg-[url('data:image/svg+xml,%3Csvg viewBox=%270 0 400 400%27 xmlns=%27http://www.w3.org/2000/svg%27%3E%3Cfilter id=%27noiseFilter%27%3E%3CfeTurbulence type=%27fractalNoise%27 baseFrequency=%270.9%27 numOctaves=%274%27 stitchTiles=%27stitch%27/%3E%3C/filter%3E%3Crect width=%27100%25%27 height=%27100%25%27 filter=%27url(%23noiseFilter)%27/%3E%3C/svg%3E')]">
      <div className="flex items-center gap-6">
        <Link to="/" className="flex items-center gap-3 group">
          <img
            src="/logo/reelix_double_circle.png"
            alt="Reelix logo"
            className="h-14 w-auto transition-transform duration-300 group-hover:scale-105 drop-shadow-[0_0_8px_rgba(197,165,114,0.3)]"
          />
          <span className="font-display text-3xl font-bold tracking-tight text-foreground transition-colors group-hover:text-gold-light">
            Reelix
          </span>
        </Link>
        <nav className="hidden sm:flex items-center gap-6 text-sm font-medium text-muted-foreground">
          {NAV_ITEMS.map(({ label, to }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                [
                  "relative transition-colors hover:text-foreground pb-1",
                  isActive
                    ? "text-foreground after:absolute after:bottom-0 after:left-0 after:right-0 after:h-[2px] after:bg-gold after:rounded-full"
                    : "text-muted-foreground",
                ].join(" ")
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex items-center gap-3 relative">
        <div className="sm:hidden relative" ref={mobileNavRef}>
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-gold/20 bg-gold/8 text-foreground transition-all hover:border-gold/40 hover:bg-gold/12 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50"
            onClick={() => setMobileNavOpen((open) => !open)}
            aria-haspopup="menu"
            aria-expanded={mobileNavOpen}
            aria-label="Toggle navigation"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
              <path
                d="M4 6h16M4 12h16M4 18h16"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </button>
          {mobileNavOpen ? (
            <div
              role="menu"
              className="absolute right-0 mt-2 w-44 rounded-md border border-gold/30 bg-background shadow-xl overflow-hidden z-50"
            >
              {NAV_ITEMS.map(({ label, to }) => (
                <NavLink
                  key={to}
                  to={to}
                  role="menuitem"
                  onClick={() => setMobileNavOpen(false)}
                  className={({ isActive }) =>
                    [
                      "block w-full px-3 py-2 text-sm text-left hover:bg-gold/12 transition-colors",
                      isActive ? "text-foreground bg-gold/10 border-l-2 border-gold" : "text-muted-foreground",
                    ].join(" ")
                  }
                >
                  {label}
                </NavLink>
              ))}
            </div>
          ) : null}
        </div>
        {!loading && user && !isAnonymous ? (
          <UserMenu
            label={displayName || metaName || user.email || "Account"}
            onSignOut={handleSignOut}
          />
        ) : (
          <Button size="sm" asChild className="bg-gold hover:bg-gold-light text-background shadow-sm hover:shadow-md transition-all">
            <Link to="/auth/signin">My Reelix</Link>
          </Button>
        )}
      </div>
    </header>
  );
}

function UserMenu({ label, onSignOut }: { label: string; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        className="inline-flex items-center gap-2 rounded-md border border-gold/20 px-3 py-1.5 text-sm text-foreground bg-gold/8 hover:border-gold/40 hover:bg-gold/12 transition-all focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:outline-none outline-none"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="max-w-[12rem] truncate">{label}</span>
        <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 opacity-70">
          <path fill="currentColor" d="M5.5 7.5L10 12l4.5-4.5h-9z" />
        </svg>
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-44 rounded-md border border-gold/30 bg-background shadow-xl overflow-hidden z-50"
        >
          <button
            role="menuitem"
            className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gold/12 transition-colors"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
          >
            <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 opacity-80">
              <path fill="currentColor" d="M3 3v14h2V3H3zm6 3l4 4-4 4-1.4-1.4L9.2 11H5v-2h4.2L7.6 7.4 9 6z" />
            </svg>
            <span>Sign out</span>
          </button>
        </div>
      )}
    </div>
  );
}

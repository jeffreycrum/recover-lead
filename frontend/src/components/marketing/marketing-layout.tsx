import type { ReactNode } from "react";
import "@/styles/landing.css";
import { SiteNav } from "./site-nav";
import { SiteFooter } from "./site-footer";

export function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="landing-theme">
      <SiteNav />
      <main>{children}</main>
      <SiteFooter />
    </div>
  );
}

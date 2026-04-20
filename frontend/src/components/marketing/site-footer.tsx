import { Link } from "react-router-dom";
import { siteCopy } from "@/lib/marketing-copy";
import { BrandLogo } from "./icons";

export function SiteFooter() {
  return (
    <footer className="lt-footer">
      <div className="wrap foot">
        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <BrandLogo />
          <span>{siteCopy.footer.copyright}</span>
        </div>
        <div style={{ display: "flex", gap: 24 }}>
          {siteCopy.footer.links.map((link) => {
            const isInternal = link.href.startsWith("/");
            return isInternal ? (
              <Link key={link.href} to={link.href}>
                {link.label}
              </Link>
            ) : (
              <a key={link.href} href={link.href}>
                {link.label}
              </a>
            );
          })}
        </div>
      </div>
    </footer>
  );
}

import { Link } from "react-router-dom";
import { siteCopy } from "@/lib/marketing-copy";

export function SiteFooter() {
  return (
    <footer className="border-t border-border/40 bg-background">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          {siteCopy.footer.copyright}
        </p>
        <ul className="flex gap-6 text-sm text-muted-foreground">
          {siteCopy.footer.links.map((link) => {
            const isInternal = link.href.startsWith("/");
            return (
              <li key={link.href}>
                {isInternal ? (
                  <Link to={link.href} className="hover:text-foreground">
                    {link.label}
                  </Link>
                ) : (
                  <a href={link.href} className="hover:text-foreground">
                    {link.label}
                  </a>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </footer>
  );
}

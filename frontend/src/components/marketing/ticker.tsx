import { siteCopy } from "@/lib/marketing-copy";

export function Ticker() {
  const doubled = [...siteCopy.ticker.items, ...siteCopy.ticker.items];
  return (
    <div className="ticker" aria-hidden="true">
      <div className="ticker-inner">
        {doubled.map((t, i) => (
          <span key={i} className="ticker-item">
            <span className="amt">{t.amt}</span>
            <span className="loc">{t.loc}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

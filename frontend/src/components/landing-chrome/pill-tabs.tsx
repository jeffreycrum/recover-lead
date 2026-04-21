import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

interface PillTabItem {
  value: string;
  label: string;
}

interface PillTabsProps {
  items: PillTabItem[];
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
}

export function PillTabs({ items, value, onValueChange, className }: PillTabsProps) {
  return (
    <Tabs value={value} onValueChange={onValueChange} className={className}>
      <TabsList className="inline-flex rounded-[10px] border border-[var(--lt-line)] bg-[var(--lt-surface)] p-1">
        {items.map((item) => (
          <TabsTrigger
            key={item.value}
            value={item.value}
            className={cn(
              "rounded-[7px] px-4 py-2 text-sm font-medium text-[var(--lt-text-muted)] transition-all",
              "data-[state=active]:bg-[var(--lt-surface-2)] data-[state=active]:text-[var(--lt-text)] data-[state=active]:shadow-[inset_0_0_0_1px_var(--lt-line-2)]"
            )}
          >
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}

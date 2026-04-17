import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value)
}

export function formatPercent(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 }).format(value / 100)
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—"
  // Append time to avoid UTC-midnight parsing shifting the date in negative-offset timezones
  const normalized = value.includes("T") ? value : `${value}T00:00:00`
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date(normalized))
}

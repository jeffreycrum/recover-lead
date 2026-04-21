import { Outlet } from "react-router-dom";
import { Header } from "./header";
import { Sidebar } from "./sidebar";
import { UsageBanner } from "@/components/billing/usage-banner";

export function AppShell() {
  return (
    <div className="dashboard-theme flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header />
        <UsageBanner />
        <main className="flex-1 overflow-auto px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

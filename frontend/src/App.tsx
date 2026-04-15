import { SignedIn, SignedOut, SignIn } from "@clerk/clerk-react";
import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/app-shell";
import { ErrorBoundary } from "@/components/common/error-boundary";
import { DashboardPage } from "@/pages/dashboard";
import { LeadsPage } from "@/pages/leads";
import { MyLeadsPage } from "@/pages/my-leads";
import { LettersPage } from "@/pages/letters";
import { ContractsPage } from "@/pages/contracts";
import { CountiesPage } from "@/pages/counties";
import { SettingsPage } from "@/pages/settings";

export default function App() {
  return (
    <ErrorBoundary>
      <SignedOut>
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <h1 className="text-3xl font-bold mb-2">
              <span className="text-emerald">Recover</span>Lead
            </h1>
            <p className="text-muted-foreground mb-8">
              AI-powered surplus funds recovery
            </p>
            <SignIn routing="hash" />
          </div>
        </div>
      </SignedOut>

      <SignedIn>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/leads" element={<LeadsPage />} />
            <Route path="/my-leads" element={<MyLeadsPage />} />
            <Route path="/letters" element={<LettersPage />} />
            <Route path="/contracts" element={<ContractsPage />} />
            <Route path="/counties" element={<CountiesPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </SignedIn>
    </ErrorBoundary>
  );
}

import {
  RedirectToSignIn,
  SignIn,
  SignUp,
  SignedIn,
  SignedOut,
} from "@clerk/clerk-react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "@/components/layout/app-shell";
import { ErrorBoundary } from "@/components/common/error-boundary";
import { DashboardPage } from "@/pages/dashboard";
import { LeadsPage } from "@/pages/leads";
import { MyLeadsPage } from "@/pages/my-leads";
import { LettersPage } from "@/pages/letters";
import { ContractsPage } from "@/pages/contracts";
import { CountiesPage } from "@/pages/counties";
import { SettingsPage } from "@/pages/settings";
import { MarketingLandingPage } from "@/pages/marketing/landing";
import { CheckoutHandoffPage } from "@/pages/checkout";

function CheckoutRedirect() {
  const { pathname, search } = useLocation();
  const target = `${pathname}${search}`;
  return <RedirectToSignIn redirectUrl={target} />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <SignedOut>
        <Routes>
          <Route path="/" element={<MarketingLandingPage />} />
          <Route
            path="/sign-in/*"
            element={
              <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
                <SignIn routing="path" path="/sign-in" />
              </div>
            }
          />
          <Route
            path="/sign-up/*"
            element={
              <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
                <SignUp routing="path" path="/sign-up" />
              </div>
            }
          />
          <Route path="/checkout" element={<CheckoutRedirect />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
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
          <Route path="/checkout" element={<CheckoutHandoffPage />} />
          <Route path="/sign-in/*" element={<Navigate to="/" replace />} />
          <Route path="/sign-up/*" element={<Navigate to="/" replace />} />
        </Routes>
      </SignedIn>
    </ErrorBoundary>
  );
}

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@clerk/clerk-react", () => ({
  SignedIn: () => null,
  SignedOut: ({ children }: { children: React.ReactNode }) => children,
  SignIn: () => <div data-testid="clerk-sign-in" />,
  SignUp: () => <div data-testid="clerk-sign-up" />,
  RedirectToSignIn: ({ redirectUrl }: { redirectUrl?: string }) => (
    <div data-testid="redirect-to-sign-in" data-redirect={redirectUrl} />
  ),
  ClerkProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => ({ isSignedIn: false, userId: null, isLoaded: true }),
  useUser: () => ({ isLoaded: true, user: null }),
}));

const AppModulePromise = import("@/App");

async function renderAt(path: string) {
  const { default: App } = await AppModulePromise;
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("MarketingLandingPage (signed-out routing)", () => {
  it("renders marketing landing at /", async () => {
    await renderAt("/");
    expect(
      screen.getByRole("heading", {
        name: /Find the surplus funds/i,
      }),
    ).toBeInTheDocument();
  });

  it("renders Clerk SignIn at /sign-in", async () => {
    await renderAt("/sign-in");
    expect(screen.getByTestId("clerk-sign-in")).toBeInTheDocument();
  });

  it("renders Clerk SignUp at /sign-up", async () => {
    await renderAt("/sign-up");
    expect(screen.getByTestId("clerk-sign-up")).toBeInTheDocument();
  });

  it("redirects /checkout to sign-in while preserving redirect_url", async () => {
    await renderAt("/checkout?plan=pro&interval=annual#pricing");
    const redirect = screen.getByTestId("redirect-to-sign-in");
    expect(redirect).toBeInTheDocument();
    expect(redirect.getAttribute("data-redirect")).toBe(
      "/checkout?plan=pro&interval=annual#pricing",
    );
  });

  it("renders 3 how-it-works steps on /", async () => {
    await renderAt("/");
    expect(screen.getAllByTestId("how-it-works-step")).toHaveLength(3);
  });

  it("renders 3 audience tabs on /", async () => {
    await renderAt("/");
    expect(screen.getAllByTestId("audience-tab")).toHaveLength(3);
  });

  it("renders 3 pricing plans on /", async () => {
    await renderAt("/");
    expect(screen.getAllByTestId("pricing-plan")).toHaveLength(3);
  });

  it("renders 6 FAQ items on /", async () => {
    await renderAt("/");
    expect(screen.getAllByTestId("faq-item")).toHaveLength(6);
  });
});

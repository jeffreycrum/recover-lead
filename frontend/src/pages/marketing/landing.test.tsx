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

describe("MarketingLandingPage (signed-out routing)", () => {
  it("renders marketing landing at /", async () => {
    const { default: App } = await AppModulePromise;
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("heading", {
        name: /Find, qualify, and close surplus claims/i,
      }),
    ).toBeInTheDocument();
  });

  it("renders Clerk SignIn at /sign-in", async () => {
    const { default: App } = await AppModulePromise;
    render(
      <MemoryRouter initialEntries={["/sign-in"]}>
        <App />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("clerk-sign-in")).toBeInTheDocument();
  });

  it("renders Clerk SignUp at /sign-up", async () => {
    const { default: App } = await AppModulePromise;
    render(
      <MemoryRouter initialEntries={["/sign-up"]}>
        <App />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("clerk-sign-up")).toBeInTheDocument();
  });

  it("redirects /checkout to sign-in while preserving redirect_url", async () => {
    const { default: App } = await AppModulePromise;
    render(
      <MemoryRouter initialEntries={["/checkout?plan=pro&interval=annual"]}>
        <App />
      </MemoryRouter>,
    );
    const redirect = screen.getByTestId("redirect-to-sign-in");
    expect(redirect).toBeInTheDocument();
    expect(redirect.getAttribute("data-redirect")).toBe(
      "/checkout?plan=pro&interval=annual",
    );
  });
});

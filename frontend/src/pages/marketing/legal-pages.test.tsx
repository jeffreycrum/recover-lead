import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@clerk/clerk-react", () => ({
  SignedIn: () => null,
  SignedOut: ({ children }: { children: React.ReactNode }) => children,
  SignIn: () => <div data-testid="clerk-sign-in" />,
  SignUp: () => <div data-testid="clerk-sign-up" />,
  RedirectToSignIn: () => <div data-testid="redirect-to-sign-in" />,
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

describe("Legal marketing pages", () => {
  it("renders Privacy at /privacy", async () => {
    await renderAt("/privacy");
    expect(
      screen.getByRole("heading", { level: 1, name: /privacy policy/i }),
    ).toBeInTheDocument();
  });

  it("renders Terms at /terms", async () => {
    await renderAt("/terms");
    expect(
      screen.getByRole("heading", { level: 1, name: /terms of service/i }),
    ).toBeInTheDocument();
  });

  it("renders Security at /security", async () => {
    await renderAt("/security");
    expect(
      screen.getByRole("heading", { level: 1, name: /^security$/i }),
    ).toBeInTheDocument();
  });
});

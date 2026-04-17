import "@testing-library/jest-dom";
import { vi } from "vitest";

vi.mock("@clerk/clerk-react", () => ({
  useAuth: () => ({ isSignedIn: true, userId: "test-user-id", isLoaded: true }),
  useUser: () => ({
    isLoaded: true,
    user: { id: "test-user-id", fullName: "Test User", emailAddresses: [] },
  }),
  SignedIn: ({ children }: { children: React.ReactNode }) => children,
  SignedOut: () => null,
  ClerkProvider: ({ children }: { children: React.ReactNode }) => children,
  RedirectToSignIn: () => null,
}));

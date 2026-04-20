import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const trackMock = vi.fn();
vi.mock("@/lib/analytics", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/analytics")>("@/lib/analytics");
  return {
    ...actual,
    track: (event: string, props?: Record<string, unknown>) =>
      trackMock(event, props),
  };
});

import { SiteNav } from "./site-nav";

describe("SiteNav", () => {
  it("sign-in link fires marketing.nav_cta.click and marketing.signin_intent", async () => {
    const user = userEvent.setup();
    trackMock.mockClear();
    render(
      <MemoryRouter>
        <SiteNav />
      </MemoryRouter>,
    );
    const signInLink = screen.getByRole("button", { name: /^sign in$/i });
    expect(signInLink.getAttribute("href")).toBe("/sign-in");
    await user.click(signInLink);
    expect(trackMock).toHaveBeenCalledWith("marketing.nav_cta.click", {
      destination: "sign-in",
    });
    expect(trackMock).toHaveBeenCalledWith("marketing.signin_intent", {
      source: "nav",
    });
  });

  it("primary CTA fires marketing.nav_cta.click with destination=sign-up", async () => {
    const user = userEvent.setup();
    trackMock.mockClear();
    render(
      <MemoryRouter>
        <SiteNav />
      </MemoryRouter>,
    );
    const cta = screen.getByRole("button", { name: /start recovering/i });
    expect(cta.getAttribute("href")).toBe("/sign-up");
    await user.click(cta);
    expect(trackMock).toHaveBeenCalledWith("marketing.nav_cta.click", {
      destination: "sign-up",
    });
  });
});

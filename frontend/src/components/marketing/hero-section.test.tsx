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

import { HeroSection } from "./hero-section";

describe("HeroSection", () => {
  it("primary CTA links to /sign-up and fires marketing.hero_cta.click with variant=primary", async () => {
    const user = userEvent.setup();
    trackMock.mockClear();
    render(
      <MemoryRouter>
        <HeroSection />
      </MemoryRouter>,
    );
    const primary = screen.getByRole("link", { name: /start free/i });
    expect(primary.getAttribute("href")).toBe("/sign-up");
    await user.click(primary);
    expect(trackMock).toHaveBeenCalledWith("marketing.hero_cta.click", {
      variant: "primary",
      destination: "sign-up",
    });
  });

  it("secondary CTA links to /sign-in and fires marketing.hero_cta.click with variant=secondary", async () => {
    const user = userEvent.setup();
    trackMock.mockClear();
    render(
      <MemoryRouter>
        <HeroSection />
      </MemoryRouter>,
    );
    const secondary = screen.getByRole("link", { name: /^sign in$/i });
    expect(secondary.getAttribute("href")).toBe("/sign-in");
    await user.click(secondary);
    expect(trackMock).toHaveBeenCalledWith("marketing.hero_cta.click", {
      variant: "secondary",
      destination: "sign-in",
    });
  });
});

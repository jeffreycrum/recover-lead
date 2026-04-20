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

import { CtaButton } from "./cta-button";

describe("CtaButton", () => {
  it("fires analytics event with props on click", async () => {
    const user = userEvent.setup();
    trackMock.mockClear();
    render(
      <MemoryRouter>
        <CtaButton
          to="/sign-up"
          event="marketing.hero_cta.click"
          eventProps={{ variant: "primary" }}
        >
          Start free
        </CtaButton>
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("link", { name: /start free/i }));
    expect(trackMock).toHaveBeenCalledWith("marketing.hero_cta.click", {
      variant: "primary",
    });
  });

  it("does not fire when no event is provided", async () => {
    const user = userEvent.setup();
    trackMock.mockClear();
    render(
      <MemoryRouter>
        <CtaButton to="/somewhere">Click</CtaButton>
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("link", { name: /click/i }));
    expect(trackMock).not.toHaveBeenCalled();
  });
});

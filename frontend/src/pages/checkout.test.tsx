import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import * as CheckoutPageModule from "./checkout";

const createCheckoutMock = vi.fn();
const assignMock = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    createCheckout: (...args: unknown[]) => createCheckoutMock(...args),
  },
}));

const { CheckoutHandoffPage } = CheckoutPageModule;

describe("CheckoutHandoffPage", () => {
  beforeEach(() => {
    createCheckoutMock.mockReset();
    assignMock.mockReset();
    vi.spyOn(CheckoutPageModule.checkoutRedirect, "go").mockImplementation(assignMock);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a checkout session and redirects for valid params", async () => {
    createCheckoutMock.mockResolvedValue({
      checkout_url: "https://checkout.stripe.com/session/test",
    });

    render(
      <MemoryRouter initialEntries={["/checkout?plan=pro&interval=annual"]}>
        <CheckoutHandoffPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(createCheckoutMock).toHaveBeenCalledWith("pro", "annual");
    });
    await waitFor(() => {
      expect(assignMock).toHaveBeenCalledWith(
        "https://checkout.stripe.com/session/test",
      );
    });
  });

  it("shows a fallback path when checkout params are invalid", async () => {
    render(
      <MemoryRouter initialEntries={["/checkout?plan=free"]}>
        <CheckoutHandoffPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/select a paid plan before continuing to checkout/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /return to settings/i })).toHaveAttribute(
      "href",
      "/settings",
    );
    expect(createCheckoutMock).not.toHaveBeenCalled();
  });
});

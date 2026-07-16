import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Notice } from "./site";

it("renders the mandatory independence notice", () => {
  render(<Notice />);
  expect(screen.getByText(/not affiliated with, endorsed by or operated by/i)).toBeInTheDocument();
  expect(screen.getByText(/does not speak on his behalf/i)).toBeInTheDocument();
});

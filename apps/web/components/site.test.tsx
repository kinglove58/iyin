import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { Notice } from "./site";

it("renders the public learning-project notice", () => {
  render(<Notice />);
  expect(screen.getByText(/student-built learning platform/i)).toBeInTheDocument();
  expect(screen.getByText(/original conversation/i)).toBeInTheDocument();
});

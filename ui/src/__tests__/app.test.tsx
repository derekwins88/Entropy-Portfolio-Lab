import { it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import App from "../App";

it("renders header and status card", () => {
  render(<App />);
  expect(screen.getByText(/Entropy Portfolio Lab/i)).toBeInTheDocument();
  expect(screen.getByRole("status")).toBeInTheDocument();
});

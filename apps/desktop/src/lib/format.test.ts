import test from "node:test";
import assert from "node:assert/strict";

import { formatScore, formatSegmentDuration, formatSegmentRange, stringifyError } from "./format.ts";

test("format helpers produce review-safe strings", () => {
  assert.equal(formatSegmentRange(1.234, 4.567), "1.23s - 4.57s");
  assert.equal(formatSegmentDuration(1.234, 4.567), "3.33s");
  assert.equal(formatScore(0.876), "88");
});

test("stringifyError normalizes string and Error inputs", () => {
  assert.equal(stringifyError("bad"), "bad");
  assert.equal(stringifyError(new Error("worse")), "worse");
});

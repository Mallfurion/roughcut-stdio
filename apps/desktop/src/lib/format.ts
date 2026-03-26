export function formatSegmentRange(start: number, end: number) {
  return `${start.toFixed(2)}s - ${end.toFixed(2)}s`;
}

export function formatSegmentDuration(start: number, end: number) {
  return `${(end - start).toFixed(2)}s`;
}

export function formatScore(value: number) {
  return `${Math.round(value * 100)}`;
}

export function stringifyError(error: unknown) {
  if (typeof error === "string") {
    return error;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

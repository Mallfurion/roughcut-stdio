export function escapeHtml(value: string | undefined | null) {
  if (!value) {
    return "";
  }
  const str = String(value);
  return str
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

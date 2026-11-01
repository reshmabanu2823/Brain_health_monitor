export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    const result = await response
      .json()
      .catch(() => ({ detail: "Server unavailable" }));
    const message =
      typeof result.detail === "string"
        ? result.detail
        : result.detail?.map((v: { msg: string }) => v.msg).join("; ") ||
          "Request failed";
    throw new Error(message);
  }
  return response.json();
}
export const post = <T>(path: string, body: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const date = (value: string) =>
  new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
export const title = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (v) => v.toUpperCase());
export const number = (value: number | null | undefined, digits = 2) =>
  value == null
    ? "—"
    : value.toLocaleString(undefined, { maximumFractionDigits: digits });

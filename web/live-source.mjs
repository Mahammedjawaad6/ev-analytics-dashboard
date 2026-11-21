import { parseCsv } from "./data.mjs";

export function normalizeLiveCsvUrl(value) {
  let url;
  try {
    url = new URL(value.trim());
  } catch {
    throw new Error("Enter a valid public HTTPS CSV URL.");
  }

  if (url.protocol !== "https:") {
    throw new Error("Live CSV sources must use HTTPS.");
  }
  if (url.username || url.password) {
    throw new Error("Do not include credentials in a live CSV URL.");
  }
  return url.href;
}

export async function fetchLiveCsv(url, fetchImpl = globalThis.fetch) {
  let response;
  try {
    response = await fetchImpl(url, {
      cache: "no-store",
      headers: { Accept: "text/csv" },
    });
  } catch (error) {
    throw new Error(
      "Could not fetch the CSV. Check the URL, network, and whether its server allows cross-origin (CORS) access.",
      { cause: error },
    );
  }

  if (!response.ok) {
    throw new Error(`The CSV server returned HTTP ${response.status}.`);
  }
  return parseCsv(await response.text());
}

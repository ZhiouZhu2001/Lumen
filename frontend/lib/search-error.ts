export type SearchFailureKey = "rateLimited" | "dailyLimit" | "searchFailed";

// Only known status/code pairs select localized messages. Never display raw
// server exception text in the reader's interface.
export async function searchFailureKey(response: Response): Promise<SearchFailureKey> {
  if (response.status === 429) return "rateLimited";
  if (response.status === 503) {
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && "detail" in body) {
        const detail = body.detail;
        if (detail && typeof detail === "object" && "code" in detail && detail.code === "rate_limited") {
          return "dailyLimit";
        }
      }
    } catch {
      // HTML proxy errors and malformed bodies use the existing generic message.
    }
  }
  return "searchFailed";
}

export type SearchEvent = { event: string; data: unknown };

// A response chunk can split an event, a CRLF pair, or a UTF-8 character.
export async function readSearchEvents(
  response: Response,
  onEvent: (event: SearchEvent) => void,
) {
  if (!response.ok || !response.headers.get("content-type")?.includes("text/event-stream") || !response.body) {
    throw new Error("Search stream unavailable");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  let completed = false;
  function consume() {
    let separator: RegExpExecArray | null;
    while ((separator = /\r?\n\r?\n/.exec(pending)) !== null) {
      const block = pending.slice(0, separator.index);
      pending = pending.slice(separator.index + separator[0].length);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
      }
      if (data.length) {
        onEvent({ event, data: JSON.parse(data.join("\n")) });
        if (event === "done") completed = true;
      }
    }
    if (pending.length > 2_000_000) throw new Error("Search event exceeds size limit");
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += decoder.decode(value, { stream: !done });
      consume();
      if (done) break;
    }
    if (!completed) throw new Error("Search stream ended early");
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }
}

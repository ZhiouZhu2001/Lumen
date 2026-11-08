import test from "node:test";
import assert from "node:assert/strict";
import { readSearchEvents } from "../lib/sse.ts";

function response(text, chunkSize = 1) {
  const bytes = new TextEncoder().encode(text);
  return new Response(new ReadableStream({
    start(controller) {
      for (let i = 0; i < bytes.length; i += chunkSize) controller.enqueue(bytes.slice(i, i + chunkSize));
      controller.close();
    },
  }), { headers: { "Content-Type": "text/event-stream" } });
}

test("split UTF-8, CRLF, multiple events and comment frames", async () => {
  const events = [];
  await readSearchEvents(response(': heartbeat\r\n\r\nevent: book\r\ndata: {"title":"El océano"}\r\n\r\nevent: done\r\ndata: {"total":1}\r\n\r\n'), e => events.push(e));
  assert.deepEqual(events, [{event: "book", data: {title: "El océano"}}, {event: "done", data: {total: 1}}]);
});

test("data lines join and LF frames work", async () => {
  const events = [];
  await readSearchEvents(response('event: done\ndata: {\ndata: "total": 0}\n\n', 100), e => events.push(e));
  assert.deepEqual(events, [{event: "done", data: {total: 0}}]);
});

test("a stream that ends without done is an error", async () => {
  await assert.rejects(readSearchEvents(response('event: book\ndata: {}\n\n'), () => {}), /ended early/);
});

test("invalid JSON, non-SSE responses and HTTP failures are errors", async () => {
  await assert.rejects(readSearchEvents(response('event: done\ndata: invalid\n\n'), () => {}), SyntaxError);
  await assert.rejects(readSearchEvents(new Response('{}'), () => {}), /unavailable/);
  await assert.rejects(readSearchEvents(new Response('', {status: 503}), () => {}), /unavailable/);
});

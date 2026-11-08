import test from "node:test";
import assert from "node:assert/strict";
import { searchFailureKey } from "../lib/search-error.ts";

test("hourly denial and daily maintenance have separate messages", async () => {
  assert.equal(await searchFailureKey(new Response("", {status: 429})), "rateLimited");
  assert.equal(await searchFailureKey(Response.json({detail: {code: "rate_limited", message: "private data"}}, {status: 503})), "dailyLimit");
});

test("unrelated failures and malformed proxy bodies stay generic", async () => {
  for (const response of [new Response("bad", {status: 503}), Response.json({detail: {code: "upstream_unavailable"}}, {status: 503}), Response.json({detail: "private URL"}, {status: 500})]) {
    assert.equal(await searchFailureKey(response), "searchFailed");
  }
});

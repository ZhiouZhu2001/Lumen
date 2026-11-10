import test from "node:test";
import assert from "node:assert/strict";
import { createPreferencesStore, PREFERENCES_KEY } from "../stores/preferences-store.ts";

function memory(value) {
  const values = new Map(value === undefined ? [] : [[PREFERENCES_KEY, value]]);
  return {values, getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key)};
}

test("preferences hydrate explicitly and persist only the coupled language", async () => {
  const storage = memory(JSON.stringify({version: 1, state: {language: "es", query: "private", setLanguage: "bad"}}));
  const store = createPreferencesStore("en", () => storage);
  assert.equal(store.getState().language, "en");
  await store.persist.rehydrate();
  assert.equal(store.getState().language, "es");
  assert.equal(typeof store.getState().setLanguage, "function");
  store.getState().setLanguage("en");
  assert.deepEqual(JSON.parse(storage.values.get(PREFERENCES_KEY)), {state: {language: "en"}, version: 1});
  assert.equal(storage.values.size, 1);
  assert.deepEqual(Object.keys(store.getState()).sort(), ["language", "setLanguage"]);
});

test("malformed, unsupported and future preference data use the route language", async () => {
  for (const value of ["broken JSON", "null", JSON.stringify({version: 1, state: {language: "fr"}}), JSON.stringify({version: 2, state: {language: "es"}})]) {
    const storage = memory(value);
    const store = createPreferencesStore("en", () => storage);
    await store.persist.rehydrate();
    assert.equal(store.getState().language, "en");
    store.getState().setLanguage("en");
    assert.deepEqual(JSON.parse(storage.values.get(PREFERENCES_KEY)), {state: {language: "en"}, version: 1});
  }
});

test("blocked storage and independent requests cannot break or share preferences", async () => {
  const blocked = createPreferencesStore("en", () => {throw new Error("Storage unavailable");});
  await blocked.persist.rehydrate();
  blocked.getState().setLanguage("es");
  assert.equal(blocked.getState().language, "es");
  assert.equal(createPreferencesStore("en").getState().language, "en");
  const deniedWrite = createPreferencesStore("en", () => ({getItem: () => null, setItem: () => {throw new Error("Quota exceeded");}, removeItem: () => {throw new Error("Denied");}}));
  deniedWrite.getState().setLanguage("es");
  assert.equal(deniedWrite.getState().language, "es");
});

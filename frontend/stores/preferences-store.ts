import { createStore } from "zustand/vanilla";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

import type { Language } from "../lib/types.ts";

export const PREFERENCES_KEY = "lumen:preferences:v1";
type Preferences = {language: Language; setLanguage: (language: Language) => void};

// Storage restrictions must never prevent searching or choosing a language.
function safeStorage(getStorage: () => StateStorage): StateStorage {
  return {
    getItem: name => {try {return getStorage().getItem(name);} catch {return null;}},
    setItem: (name, value) => {try {getStorage().setItem(name, value);} catch {}},
    removeItem: name => {try {getStorage().removeItem(name);} catch {}},
  };
}

export function createPreferencesStore(language: Language, getStorage: () => StateStorage = () => window.localStorage) {
  return createStore<Preferences>()(persist(set => ({
    language,
    setLanguage: next => set({language: next}),
  }), {
    name: PREFERENCES_KEY, version: 1,
    storage: createJSONStorage(() => safeStorage(getStorage)),
    partialize: state => ({language: state.language}),
    skipHydration: true,
    migrate: () => ({language}),
    merge: (saved, current) => {
      const value = saved as {language?: unknown} | null;
      return {...current, language: value?.language === "en" || value?.language === "es" ? value.language : current.language};
    },
  }));
}

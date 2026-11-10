"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useStore } from "zustand";

import { createPreferencesStore } from "@/stores/preferences-store";
import type { Language } from "@/lib/types";

type PreferencesStore = ReturnType<typeof createPreferencesStore>;
const PreferencesContext = createContext<PreferencesStore | null>(null);

export default function PreferencesProvider({language, children}: {language: Language; children: ReactNode}) {
  const [store] = useState(() => createPreferencesStore(language));
  useEffect(() => {
    let current = true;
    void Promise.resolve(store.persist.rehydrate()).then(() => {
      // An explicit locale URL wins over an older browser preference.
      if (current) store.getState().setLanguage(language);
    });
    return () => {current = false;};
  }, [language, store]);
  return <PreferencesContext.Provider value={store}>{children}</PreferencesContext.Provider>;
}

export function usePreferences<T>(selector: (state: ReturnType<PreferencesStore["getState"]>) => T): T {
  const store = useContext(PreferencesContext);
  if (!store) throw new Error("PreferencesProvider is required");
  return useStore(store, selector);
}

"use client";

import { useEffect, useState } from "react";
import { useStore } from "zustand";

import { createSearchSession } from "@/stores/search-store";
import type { Language } from "@/lib/types";

export function useBookSearch(language: Language) {
  const [session] = useState(() => createSearchSession());
  const state = useStore(session.store);
  useEffect(() => () => session.reset(), [language, session]);
  return {...state, submit: () => session.submit(language), cancel: session.cancel, reset: session.reset};
}

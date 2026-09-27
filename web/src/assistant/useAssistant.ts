import { useCallback, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ChatAction, ChatCard, ChatState, ChatTurnRequest } from "../api/types";

// The conversation lives in the browser tab (sessionStorage): the server
// keeps none, and every turn sends the state back. Closing the tab ends it.

export type Surface = "citizen" | "admin";
export type Turn = Omit<ChatTurnRequest, "surface" | "state">;

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  cards?: ChatCard[];
  actions?: ChatAction[];
  /** Local preview of a photo the citizen attached - this page view only. */
  photo?: string;
  /** Set on a local failure notice; its only action retries the last turn. */
  failed?: boolean;
}

const OFFLINE = "The CivicFix service is temporarily unavailable. Your draft is still here; please try again.";
export const RETRY = "__retry";

interface Saved {
  messages: ChatMessage[];
  state: ChatState | null;
}

function key(surface: Surface) {
  return `civicfix-assistant-${surface}`;
}

function load(surface: Surface): Saved {
  try {
    return JSON.parse(sessionStorage.getItem(key(surface)) ?? "null") ?? { messages: [], state: null };
  } catch {
    return { messages: [], state: null };
  }
}

function save(surface: Surface, saved: Saved) {
  try {
    // Object URLs die with the page; don't store them.
    const messages = saved.messages.slice(-60).map(({ photo: _photo, ...m }) => m);
    sessionStorage.setItem(key(surface), JSON.stringify({ ...saved, messages }));
  } catch {
    /* storage blocked or full: the conversation still works for this page view */
  }
}

let seq = 0;
const nextId = () => `${Date.now().toString(36)}-${(seq++).toString(36)}`;

export function useAssistant(surface: Surface) {
  const [initial] = useState<Saved>(() => load(surface));
  const [messages, setMessages] = useState<ChatMessage[]>(initial.messages);
  const [lang, setLang] = useState(initial.state?.lang ?? "en");
  const [busy, setBusy] = useState(false);
  const stateRef = useRef<ChatState | null>(initial.state);
  const lastTurn = useRef<Turn | null>(null);

  const append = useCallback((msg: ChatMessage) => {
    setMessages((prev) => {
      const next = [...prev, msg];
      save(surface, { messages: next, state: stateRef.current });
      return next;
    });
  }, [surface]);

  /** One turn. `echo` is what the citizen sees as their own bubble. */
  const send = useCallback(async (turn: Turn, echo?: string, photo?: string): Promise<boolean> => {
    if (echo || photo) append({ id: nextId(), role: "user", text: echo ?? "", photo });
    lastTurn.current = turn;
    setBusy(true);
    try {
      const res = await api.chatTurn({ ...turn, surface, state: stateRef.current ?? undefined });
      stateRef.current = res.state;
      setLang(res.state.lang);
      append({ id: nextId(), role: "assistant", text: res.reply, cards: res.cards, actions: res.actions });
      return true;
    } catch (err) {
      const text = err instanceof ApiError && err.status === 429 ? `${err.message}.` : OFFLINE;
      append({
        id: nextId(), role: "assistant", text, failed: true,
        actions: [{ kind: "reply", label: "Try again", action: RETRY, value: null, href: null }],
      });
      return false;
    } finally {
      setBusy(false);
    }
  }, [append, surface]);

  const retry = useCallback(() => {
    if (lastTurn.current) void send(lastTurn.current);
  }, [send]);

  const reset = useCallback(() => {
    stateRef.current = null;
    setLang("en");
    setMessages([]);
    save(surface, { messages: [], state: null });
    void send({ action: "start" });
  }, [send, surface]);

  return { messages, busy, send, retry, reset, lang };
}

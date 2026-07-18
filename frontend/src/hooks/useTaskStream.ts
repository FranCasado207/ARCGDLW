import { useEffect, useRef } from "react";
import { openTaskStream } from "../api/client";
import type { TaskStreamMessage } from "../api/types";

/** Opens (and cleanly tears down) a WebSocket log/progress/status stream for
 * one task. Re-subscribes only when taskId changes; the handler is kept in a
 * ref so callers can pass a fresh closure every render without reconnecting. */
export function useTaskStream(taskId: string, onMessage: (msg: TaskStreamMessage) => void) {
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    let cancelled = false;
    let close: (() => void) | null = null;

    openTaskStream(taskId, (msg) => handlerRef.current(msg)).then((closer) => {
      if (cancelled) {
        closer();
      } else {
        close = closer;
      }
    });

    return () => {
      cancelled = true;
      close?.();
    };
  }, [taskId]);
}

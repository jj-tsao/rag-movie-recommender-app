import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";

export type StreamStatus = "idle" | "connecting" | "streaming" | "done" | "error" | "cancelled";

export interface StreamStatusState {
  status: StreamStatus;
  message?: string;
}

interface Props {
  state: StreamStatusState;
  onCancel?: () => void;
}

export default function StreamStatusBar({ state, onCancel }: Props) {
  const [visible, setVisible] = useState(state.status !== "idle");

  useEffect(() => {
    if (state.status === "idle") {
      setVisible(false);
      return;
    }
    setVisible(true);
    let timeoutId: number | undefined;
    if (state.status === "done" || state.status === "cancelled") {
      timeoutId = window.setTimeout(() => setVisible(false), 2500);
    } else if (state.status === "error") {
      timeoutId = window.setTimeout(() => setVisible(false), 4000);
    }
    return () => {
      if (timeoutId) window.clearTimeout(timeoutId);
    };
  }, [state.status]);

  const showCancel = typeof onCancel === "function" && (state.status === "connecting" || state.status === "streaming");
  const surfaceMessage = useMemo(() => formatMessage(state), [state]);

  if (!visible) return null;

  return (
    <div className="pointer-events-none fixed bottom-6 left-1/2 z-40 w-full max-w-xl -translate-x-1/2 px-4">
      <div className="pointer-events-auto flex items-center justify-between gap-3 rounded-full border border-border bg-background/95 px-5 py-2 shadow-lg shadow-black/10">
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <PulseDots active={state.status === "connecting" || state.status === "streaming"} />
          <span className="truncate text-foreground">{surfaceMessage}</span>
        </div>
        {showCancel && (
          <Button variant="ghost" size="sm" onClick={onCancel} className="h-8 px-3">
            Cancel
          </Button>
        )}
      </div>
    </div>
  );
}

function formatMessage(state: StreamStatusState): string {
  if (state.message) return state.message;
  switch (state.status) {
    case "connecting":
      return "Connecting to the discovery stream…";
    case "streaming":
      return "Streaming fresh insights…";
    case "done":
      return "Stream complete";
    case "cancelled":
      return "Stream cancelled";
    case "error":
      return "Stream interrupted";
    default:
      return "";
  }
}

function PulseDots({ active }: { active: boolean }) {
  const base = "w-2 h-2 rounded-full";
  const activeClass = active ? "bg-primary" : "bg-muted";
  return (
    <div className="flex items-center gap-1">
      <span className={`${base} ${activeClass} ${active ? "animate-[pulse_1.4s_ease-in-out_infinite]" : ""}`} />
      <span
        className={`${base} ${activeClass} ${active ? "animate-[pulse_1.4s_ease-in-out_infinite]" : ""}`}
        style={active ? { animationDelay: "0.2s" } : undefined}
      />
      <span
        className={`${base} ${activeClass} ${active ? "animate-[pulse_1.4s_ease-in-out_infinite]" : ""}`}
        style={active ? { animationDelay: "0.4s" } : undefined}
      />
    </div>
  );
}

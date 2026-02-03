import React, { useMemo, useState } from "react";
import { ToastContext, type ToastContextValue, type Toast } from "./useToast";

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const api = useMemo<ToastContextValue>(() => ({
    toast: ({ title, description, duration = 3500, variant = "default" }) => {
      const id = crypto.randomUUID();
      const item: Toast = { id, title, description, duration, variant };
      setToasts((t) => [...t, item]);
      if (duration !== null && duration! > 0) {
        window.setTimeout(() => {
          setToasts((t) => t.filter((x) => x.id !== id));
        }, duration);
      }
      return id;
    },
    dismiss: (id: string) => setToasts((t) => t.filter((x) => x.id !== id)),
  }), []);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed top-20 right-4 z-[100] flex w-full max-w-sm flex-col gap-3">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={[
              "relative rounded-xl border p-4 shadow-lg bg-background/95 backdrop-blur-sm text-foreground card-grain",
              t.variant === "success" && "border-gold/40",
              t.variant === "destructive" && "border-destructive/60",
              !t.variant || t.variant === "default" ? "border-gold/30" : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <div className="flex items-start gap-3">
              <div className="flex-1">
                {t.title ? <div className="text-sm font-semibold">{t.title}</div> : null}
                {t.description ? (
                  <div className="mt-1 text-sm text-muted-foreground">{t.description}</div>
                ) : null}
              </div>
              <button
                aria-label="Dismiss"
                className="text-muted-foreground hover:text-gold transition-colors"
                onClick={() => api.dismiss(t.id)}
              >
                <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                </svg>
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

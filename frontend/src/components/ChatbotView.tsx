import { useEffect, useState } from "react";
import { ArrowUp, MessageSquare, Plus } from "lucide-react";
import type { Machine } from "../types/dashboard";
type Citation = {
  chunk_id: string;
  document_id: string;
  version: string;
  page: number;
};
type Grounded = {
  model: string;
  instructions: { title: string; description: string; source: Citation }[];
  sources: Citation[];
};
type ChatEntry = {
  role: "user" | "assistant";
  text: string;
  grounded?: Grounded;
  error?: boolean;
};
type Session = {
  id: string;
  machineId: string;
  title: string;
  messages: ChatEntry[];
};
export function ChatbotView({
  machines,
}: {
  machines: Machine[];
  onOpenMachineAnalytics?: (machine: Machine) => void;
  onNavigateToDashboard?: () => void;
}) {
  const [machineId, setMachineId] = useState(machines[0]?.id || "");
  const [sessions, setSessions] = useState<Session[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("mistranics.chats.v2") || "[]");
    } catch {
      return [];
    }
  });
  const [active, setActive] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [storageError, setStorageError] = useState(false);
  const machine = machines.find((m) => m.id === machineId) || machines[0];
  const current = sessions.find(
    (s) => s.id === active && s.machineId === machine?.id,
  );
  // Report failures while synchronizing conversations with browser storage.
  useEffect(() => {
    try {
      localStorage.setItem(
        "mistranics.chats.v2",
        JSON.stringify(sessions.slice(0, 100)),
      );
      // eslint-disable-next-line react/set-state-in-effect
      setStorageError(false);
    } catch {
      // eslint-disable-next-line react/set-state-in-effect
      setStorageError(true);
    }
  }, [sessions]);
  async function send() {
    if (!input.trim() || !machine || busy) return;
    const text = input.trim(),
      id = current?.id || crypto.randomUUID();
    const next: Session = {
      id,
      machineId: machine.id,
      title: current?.title || text.slice(0, 55),
      messages: [
        ...(current?.messages || []),
        { role: "user" as const, text },
      ].slice(-99),
    };
    setSessions((prev) => [next, ...prev.filter((s) => s.id !== id)]);
    setActive(id);
    setInput("");
    setBusy(true);
    let entry: ChatEntry;
    try {
      if (machine.id === "simulation-01") {
        const response = await fetch("/api/industrial/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            machine_id: machine.id,
            text,
            history: (current?.messages || [])
              .slice(-10)
              .map((m) => ({ role: m.role, text: m.text })),
          }),
          signal: AbortSignal.timeout(380000),
        });
        const data = await response.json();
        if (!response.ok)
          throw new Error(
            typeof data.detail === "string"
              ? data.detail
              : "Industrial knowledge is unavailable. Check its backend configuration.",
          );
        entry = {
          role: "assistant",
          text: [
            data.condition_summary,
            ...data.possible_causes.map(
              (c: { cause: string }) => `Possible cause: ${c.cause}`,
            ),
          ].join("\n\n"),
          grounded: {
            model: data.model,
            instructions: data.instructions,
            sources: data.sources,
          },
        };
      } else {
        const last = machine.telemetry.at(-1);
        entry = {
          role: "assistant",
          text: `Workspace note for ${machine.name} (${machine.code}). ${last ? `The illustrative snapshot records ${last.temperature.toFixed(1)} °C and ${last.vibration.toFixed(2)} mm/s vibration.` : "There are no telemetry readings for this machine yet."} The simulation manuals and connected Ollama assistant are available for the Prototype motor.`,
        };
      }
    } catch (error) {
      entry = {
        role: "assistant",
        text:
          error instanceof Error
            ? error.message
            : "Unable to reach the Industrial assistant.",
        error: true,
      };
    }
    setSessions((prev) =>
      prev.map((s) =>
        s.id === id
          ? { ...s, messages: [...s.messages, entry].slice(-100) }
          : s,
      ),
    );
    setBusy(false);
  }
  return (
    <section className="chat-workspace">
      <aside className="chat-sidebar">
        <span className="eyebrow">MACHINE CONTEXT</span>
        <label className="sr-only" htmlFor="chat-machine">
          Target machine
        </label>
        <select
          id="chat-machine"
          value={machine?.id}
          onChange={(e) => {
            setMachineId(e.target.value);
            setActive(null);
            setInput("");
          }}
        >
          {machines.map((m) => (
            <option value={m.id} key={m.id}>
              {m.name}
            </option>
          ))}
        </select>
        <p>
          {machine?.code} · {machine?.location}
        </p>
        <button
          className="new-chat"
          onClick={() => {
            setActive(null);
            setInput("");
          }}
        >
          <Plus size={16} /> New conversation
        </button>
        <span className="eyebrow chat-history-title">
          PREVIOUS CONVERSATIONS
        </span>
        <div className="chat-history">
          {sessions
            .filter((s) => s.machineId === machine?.id)
            .map((s) => (
              <button
                key={s.id}
                aria-pressed={active === s.id}
                onClick={() => setActive(s.id)}
              >
                <MessageSquare size={15} />
                <span>{s.title}</span>
              </button>
            ))}
          {!sessions.some((s) => s.machineId === machine?.id) && (
            <p>Your conversations for this machine will appear here.</p>
          )}
        </div>
        <small>Conversations stay with their machine.</small>
      </aside>
      <div className={`chat-canvas ${current ? "has-messages" : ""}`}>
        {current ? (
          <div className="chat-messages" aria-live="polite">
            {current.messages.map((m, i) => (
              <div key={i} className={`chat-message ${m.role}`}>
                <span>
                  {m.role === "user" ? "You" : "Mistranics · prototype"}
                </span>
                <p
                  role={m.error ? "alert" : undefined}
                  style={{ whiteSpace: "pre-wrap" }}
                >
                  {m.text}
                </p>
                {m.grounded && (
                  <div className="grounded-answer">
                    <span className="eyebrow">
                      FICTIONAL SIMULATION MANUALS
                    </span>
                    {m.grounded.instructions.map((step, index) => (
                      <article key={index}>
                        <strong>{step.title}</strong>
                        <p>{step.description}</p>
                        <a
                          href={`/api/industrial/manuals/${step.source.document_id}/pdf#page=${step.source.page}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {step.source.document_id} ? {step.source.version} ?
                          page {step.source.page}
                        </a>
                      </article>
                    ))}
                    <div className="answer-sources">
                      {m.grounded.sources.map((source) => (
                        <a
                          key={source.chunk_id}
                          href={`/api/industrial/manuals/${source.document_id}/pdf#page=${source.page}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {source.document_id} / p. {source.page}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="chat-welcome">
            <div className="chat-mark">m.</div>
            <span className="eyebrow">{machine?.name}</span>
            <h1>
              A little context.
              <br />
              <em>A clearer next step.</em>
            </h1>
          </div>
        )}
        <form
          className="chat-composer"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <input
            aria-label="Message about the selected machine"
            placeholder={`Ask about ${machine?.name || "your machine"}…`}
            value={input}
            maxLength={2000}
            onChange={(e) => setInput(e.target.value)}
          />
          <button disabled={!input.trim() || busy} aria-label="Send message">
            <ArrowUp size={20} />
          </button>
        </form>
        <p className="chat-caption">
          Prototype assistant · Grounded in your selected machine’s workspace
        </p>
        {storageError && (
          <p role="alert">
            Browser storage is full. This conversation will last for this
            session only.
          </p>
        )}
      </div>
    </section>
  );
}

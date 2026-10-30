import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { askQuestion } from "./api";
import type { Turn } from "./types";

const EXAMPLES = [
  "What underwriting decision applies to a smoker with a BMI of 32?",
  "Am I covered for flood damage?",
  "How long do I have to submit a claim?",
];

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const busy = turns.some((turn) => turn.status === "loading");
  const selected = turns.find((turn) => turn.id === selectedId) ?? turns[turns.length - 1];

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;

    const id = Date.now();
    setTurns((current) => [...current, { id, question: text, status: "loading" }]);
    setSelectedId(id);
    setInput("");

    try {
      const { answer, chunks } = await askQuestion(text);
      setTurns((current) => current.map((t) => (t.id === id ? { ...t, status: "done", answer, chunks } : t)));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Something went wrong";
      setTurns((current) => current.map((t) => (t.id === id ? { ...t, status: "error", error: message } : t)));
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    ask(input);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      ask(input);
    }
  }

  return (
    <div className="app">
      <main className="chat">
        <header className="brand">&gt; policy-rag</header>

        <div className="transcript">
          {turns.length === 0 && (
            <div className="empty">
              <p>Ask a question about the insurance policy documents.</p>
              <div className="examples">
                {EXAMPLES.map((example) => (
                  <button key={example} className="example" onClick={() => ask(example)}>
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn) => (
            <section key={turn.id} className={turn.id === selected?.id ? "turn selected" : "turn"}>
              <button className="question" onClick={() => setSelectedId(turn.id)}>
                <span className="prompt">$</span> ask "{turn.question}"
              </button>
              {turn.status === "loading" && <div className="status">Searching the policy...</div>}
              {turn.status === "error" && <div className="card error">{turn.error}</div>}
              {turn.status === "done" && <div className="card answer">{turn.answer}</div>}
            </section>
          ))}
          <div ref={endRef} />
        </div>

        <form className="composer" onSubmit={onSubmit}>
          <span className="prompt" aria-hidden="true">
            $
          </span>
          <label htmlFor="question" className="sr-only">
            Ask a question about the policy
          </label>
          <textarea
            id="question"
            rows={2}
            value={input}
            placeholder="ask a question about the policy"
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onKeyDown}
          />
          <button type="submit" disabled={busy || !input.trim()}>
            Run
          </button>
        </form>
      </main>

      <aside className="inspector">
        <h2>Retrieved chunks</h2>
        {!selected?.chunks && <p className="hint">Chunks sent to the model appear here after you ask a question.</p>}
        {selected?.chunks?.map((chunk, index) => (
          <details key={`${chunk.source}-${chunk.page}-${index}`} className="chunk">
            <summary>
              <span className="meta">
                #{index + 1} · {chunk.source} · page {chunk.page}
              </span>
              <span className="title">{chunk.title}</span>
            </summary>
            <pre>{chunk.text}</pre>
          </details>
        ))}
      </aside>
    </div>
  );
}

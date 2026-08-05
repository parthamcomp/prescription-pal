import { CSSProperties, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AnswerPayload, ChatMessage, Prescription, prescriptionsApi } from "../api";
import Logo from "../components/Logo";
import { medTagSquareColor, sourceMeta } from "../lib/format";

type SourceType = "record" | "general" | null;

interface ProseSegment {
  type: SourceType;
  text: string;
}

// [[record]]/[[general]] are mode-switch markers, not a required open/close
// pair - deliberately lenient, because the model doesn't reliably close them
// (observed: reusing [[general]] itself as the "close", or dropping a marker
// entirely for one sentence in a mixed answer). Whatever follows a marker
// stays that type until the next marker, an explicit [[/record]]/[[/general]]
// (still honored if present), or the end of the text. Untagged text
// (including the plain-text fallback strings the backend returns when the
// LLM is unavailable or nothing was found) comes through as type: null and
// renders with no special styling - this must never throw on malformed or
// missing markers, only degrade to plain prose.
function parseSourceSegments(text: string): ProseSegment[] {
  const re = /\[\[(\/?)(record|general)\]\]/g;
  const segments: ProseSegment[] = [];
  let lastIndex = 0;
  let currentType: SourceType = null;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: currentType, text: text.slice(lastIndex, match.index) });
    }
    currentType = match[1] === "/" ? null : (match[2] as SourceType);
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    segments.push({ type: currentType, text: text.slice(lastIndex) });
  }
  return segments;
}

function renderBold(text: string, keyPrefix: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={`${keyPrefix}-${i}`}>{part.slice(2, -2)}</strong>
    ) : (
      <span key={`${keyPrefix}-${i}`}>{part}</span>
    )
  );
}

function BoldProse({ text }: { text: string }) {
  const segments = parseSourceSegments(text);
  return (
    <p>
      {segments.map((seg, i) =>
        seg.type ? (
          <span key={i} className={`source-span ${seg.type}`}>
            {renderBold(seg.text, `s${i}`)}
          </span>
        ) : (
          <span key={i}>{renderBold(seg.text, `s${i}`)}</span>
        )
      )}
    </p>
  );
}

function AnswerCard({ payload }: { payload: AnswerPayload }) {
  return (
    <div className="answercard">
      {payload.med && (
        <span className="med-tag">
          <span
            className="med-tag-square"
            style={{ background: medTagSquareColor(payload.med.color_key) }}
          />
          {payload.med.name}
        </span>
      )}
      {!payload.grounded && (
        <div className="grounding-note">
          Not based on your saved records — general information only.
        </div>
      )}
      <BoldProse text={payload.text} />
      {payload.facts && payload.facts.length >= 2 && (
        <div
          className="facts"
          style={{ "--fact-cols": payload.facts.length } as CSSProperties}
        >
          {payload.facts.map((f, i) => (
            <div key={i} className={`fact-cell ${f.emphasis ? "emphasis" : ""}`}>
              <div className="fact-label">{f.label}</div>
              <div className="fact-value">{f.value}</div>
            </div>
          ))}
        </div>
      )}
      {payload.safety_note && (
        <div className="safety-note">
          <span className="safety-icon">!</span>
          <p>{payload.safety_note}</p>
        </div>
      )}
    </div>
  );
}

interface AskViewProps {
  visible: boolean;
  prescriptions: Prescription[];
}

export default function AskView({ visible, prescriptions }: AskViewProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const questionInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatLoading]);

  // Other views (YOUR MEDS, Records "Ask about this", Upload CTA) navigate
  // here with a seed question in router state rather than sending directly,
  // matching the spec's "fills the composer, does not send" rule everywhere.
  useEffect(() => {
    const seed = (location.state as { seedQuestion?: string } | null)?.seedQuestion;
    if (visible && seed) {
      setQuestion(seed);
      questionInputRef.current?.focus();
      navigate(location.pathname, { replace: true, state: null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, location.state]);

  const askQuestion = async (override?: string) => {
    const q = (override ?? question).trim();
    if (!q || chatLoading) return;
    setMessages((m) => [...m, { role: "user", content: q }]);
    setQuestion("");
    setChatLoading(true);
    try {
      const payload = await prescriptionsApi.chat(q);
      setMessages((m) => [...m, { role: "assistant", content: "", payload }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: q, status: "error" }]);
    } finally {
      setChatLoading(false);
    }
  };

  const retryQuestion = (beforeIndex: number) => {
    for (let i = beforeIndex - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        const q = messages[i].content;
        setMessages((m) => m.slice(0, i));
        askQuestion(q);
        return;
      }
    }
  };

  const copyMessage = async (text: string, index: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex((v) => (v === index ? null : v)), 1500);
    } catch {
      // clipboard permission denied - nothing sensible to surface
    }
  };

  const newChat = () => {
    setMessages([]);
    setQuestion("");
  };

  const baselineSuggestions = [
    "All my dosages",
    "Any interactions?",
    "Doctor's advice",
    "Refills running out",
  ];

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const followUps = lastAssistant?.payload?.follow_ups ?? [];

  return (
    <div className="panel" style={{ display: visible ? undefined : "none" }}>
      <div className="panel-head">
        <h1>Ask anything</h1>
        <span className="privacy-pill">
          <span className="dot" />
          Only you can see this
        </span>
        <div className="panel-head-spacer" />
        <button className="ghost-btn newchat" onClick={newChat}>
          + New chat
        </button>
      </div>

      <div className="panel-scroll">
        <div className="thread">
          {messages.length === 0 && (
            <div className="empty">
              <Logo size={48} className="empty-mark" />
              <h3>Ask anything about your prescriptions</h3>
              <p>I only look at the records you&apos;ve uploaded.</p>
            </div>
          )}

          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="msg-row user">
                <div className="bubble">{m.content}</div>
              </div>
            ) : (
              <div key={i} className="msg-row assistant">
                <Logo size={32} className="msg-mark" />
                <div className="msg-col">
                  {m.status === "error" ? (
                    <div className="answercard error">
                      <p className="error-title">Couldn&apos;t reach your records</p>
                      <p className="error-body">
                        Something went wrong on our end. Your records are safe — try
                        asking again.
                      </p>
                      <button className="retry-btn" onClick={() => retryQuestion(i)}>
                        Try again
                      </button>
                    </div>
                  ) : m.payload ? (
                    <>
                      <AnswerCard payload={m.payload} />
                      {m.payload.sources.length > 0 && (
                        <div
                          className="sources"
                          style={
                            {
                              "--source-cols": Math.min(m.payload.sources.length, 2),
                            } as CSSProperties
                          }
                        >
                          {m.payload.sources.map((s) => (
                            <button
                              key={s.id}
                              type="button"
                              className="source-card"
                              data-record-id={s.id}
                              onClick={() => navigate(`/records/${s.id}`)}
                            >
                              <span
                                className={`source-tile ${s.kind === "note" ? "note" : ""}`}
                              >
                                {s.kind === "note" ? "✎" : "Rx"}
                              </span>
                              <span className="source-text">
                                <span className="title">{s.title}</span>
                                {sourceMeta(s) && (
                                  <span className="meta">{sourceMeta(s)}</span>
                                )}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                      <div className="actions">
                        <button
                          className="action-btn"
                          onClick={() => copyMessage(m.payload!.text, i)}
                        >
                          {copiedIndex === i ? "Copied!" : "Copy"}
                        </button>
                      </div>
                    </>
                  ) : null}
                </div>
              </div>
            )
          )}

          {chatLoading && (
            <div className="msg-row assistant">
              <Logo size={32} className="msg-mark" />
              <div className="msg-col">
                <div className="answercard loading">
                  <div className="skeleton-bar" />
                  <div className="skeleton-bar short" />
                  <div className="loading-label">Looking through your records…</div>
                </div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
      </div>

      <div className="composerwrap">
        <div className="composerwrap-inner">
          {prescriptions.length === 0 ? (
            <button className="no-records-cta" onClick={() => navigate("/upload")}>
              Upload a prescription
            </button>
          ) : (
            <div className="chips">
              {(followUps.length > 0
                ? followUps
                : baselineSuggestions.map((label) => ({ label, question: label }))
              ).map((c, i) => (
                <button
                  type="button"
                  key={i}
                  className="suggestion"
                  title={c.question}
                  aria-label={c.question}
                  onClick={() => setQuestion(c.question)}
                >
                  {c.label}
                </button>
              ))}
            </div>
          )}
          <div className="composer">
            <input
              ref={questionInputRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && askQuestion()}
              placeholder="Ask about a dose, a medication, or what your doctor said…"
            />
            <button
              type="button"
              className="attach-btn"
              onClick={() => navigate("/upload")}
              title="Add a prescription"
              aria-label="Add a prescription"
            >
              +
            </button>
            <button
              className="send-btn"
              onClick={() => askQuestion()}
              disabled={chatLoading || !question.trim()}
            >
              Ask
            </button>
          </div>
          <div className="composer-hint">Answers come only from your own records.</div>
        </div>
      </div>
    </div>
  );
}

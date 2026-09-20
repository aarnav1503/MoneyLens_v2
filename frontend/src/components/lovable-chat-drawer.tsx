import { useState, useRef, useEffect } from "react";
import { Bot, Send, X, Check, AlertCircle, Sparkles } from "lucide-react";
import { useChatbot } from "@/hooks/use-money-lens";
import { currency } from "@/lib/dashboard-data";
import { cn } from "@/lib/utils";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant" | "system";
  text: string;
  timestamp: string;
  action_payload?: {
    action_type: "UPDATE_PROFILE" | "CREATE_GOAL" | "NONE";
    title: string;
    description: string;
    data: Record<string, any>;
    confirmed?: boolean;
  };
  evidence?: string;
  suggested_followups?: string[];
}

export function LovableChatDrawer({
  isOpen,
  onClose,
  initialPrompt,
}: {
  isOpen: boolean;
  onClose: () => void;
  initialPrompt?: string;
}) {
  const { sendMessage, confirmAction } = useChatbot();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      sender: "assistant",
      text: "Hello. I am the Money Lens Assistant. Ask me about your surplus, simulate a purchase, explore spending trends, or update your profile via natural language.",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      suggested_followups: [
        "My salary increased to ₹95,000",
        "I want to save for a ₹5 lakh car",
        "What is my monthly surplus?",
        "Break down my spending",
      ],
    },
  ]);
  const [input, setInput] = useState(initialPrompt || "");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (initialPrompt) {
      setInput(initialPrompt);
    }
  }, [initialPrompt]);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || sendMessage.isPending) return;

    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      sender: "user",
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    try {
      const res = await sendMessage.mutateAsync({ message: text });
      const asstMsg: ChatMessage = {
        id: res.message_id || `asst_${Date.now()}`,
        sender: "assistant",
        text: res.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        action_payload: res.action_payload,
        evidence: res.evidence,
        suggested_followups: res.suggested_followups,
      };
      setMessages((prev) => [...prev, asstMsg]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          sender: "system",
          text: err.message || "Failed to reach intelligence layer.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    }
  };

  const handleConfirm = async (msgId: string, action: any) => {
    try {
      await confirmAction.mutateAsync({
        actionType: action.action_type,
        data: action.data,
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId && m.action_payload
            ? { ...m, action_payload: { ...m.action_payload, confirmed: true } }
            : m
        )
      );
    } catch (err: any) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          sender: "system",
          text: err.message || "Action failed. Please try again.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-foreground/20 backdrop-blur-xs">
      <div className="w-full max-w-md bg-surface-elevated border-l border-border h-full flex flex-col shadow-2xl animate-in slide-in-from-right">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-surface-muted/50">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Sparkles className="h-4 w-4" />
            </span>
            <div>
              <h2 className="text-sm font-medium">Money Lens Assistant</h2>
              <p className="text-[11px] text-subtle-foreground font-mono">Grounded Financial Reasoning</p>
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground cursor-pointer">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"} space-y-1.5`}
            >
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-4 py-3 text-xs leading-relaxed",
                  msg.sender === "user"
                    ? "bg-primary text-primary-foreground font-medium"
                    : msg.sender === "system"
                    ? "bg-risk-soft text-risk border border-border"
                    : "bg-surface-muted text-foreground border border-border"
                )}
              >
                <p className="whitespace-pre-wrap">{msg.text}</p>
                {msg.evidence && (
                  <div className="mt-2 pt-2 border-t border-border/60 text-[11px] text-subtle-foreground font-mono">
                    <span className="font-semibold text-foreground">Evidence: </span>
                    {msg.evidence}
                  </div>
                )}
              </div>

              {/* Action Confirmation Card */}
              {msg.action_payload && !msg.action_payload.confirmed && (
                <div className="w-full max-w-[90%] rounded-xl border border-primary/40 bg-primary-soft p-3.5 space-y-2.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider bg-primary text-primary-foreground px-1.5 py-0.5 rounded">
                    {msg.action_payload.title || "Action Detected"}
                  </span>
                  <p className="text-xs text-foreground font-medium">{msg.action_payload.description}</p>
                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={() => handleConfirm(msg.id, msg.action_payload)}
                      disabled={confirmAction.isPending}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1 text-xs font-medium cursor-pointer"
                    >
                      <Check className="h-3 w-3" />
                      <span>{confirmAction.isPending ? "Applying..." : "Confirm Update"}</span>
                    </button>
                    <button
                      onClick={() =>
                        setMessages((prev) =>
                          prev.map((m) => {
                            if (m.id === msg.id) {
                              const { action_payload, ...rest } = m;
                              return rest;
                            }
                            return m;
                          })
                        )
                      }
                      className="rounded-lg border border-border px-3 py-1 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {msg.action_payload?.confirmed && (
                <div className="flex items-center gap-1 text-[11px] text-positive font-medium px-1">
                  <Check className="h-3 w-3" />
                  <span>Action executed and engine recalibrated</span>
                </div>
              )}

              {msg.suggested_followups && msg.suggested_followups.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {msg.suggested_followups.map((chip, i) => (
                    <button
                      key={i}
                      onClick={() => handleSend(chip)}
                      className="px-2.5 py-1 text-[11px] rounded-lg bg-surface border border-border text-muted-foreground hover:text-foreground cursor-pointer text-left"
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              )}

              <span className="text-[10px] text-subtle-foreground font-mono">{msg.timestamp}</span>
            </div>
          ))}

          {sendMessage.isPending && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
              <div className="w-1.5 h-1.5 rounded-full bg-primary animate-ping" />
              <span>Synthesizing calculation telemetry...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Footer */}
        <div className="p-4 border-t border-border bg-surface-elevated">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything or update financial parameters..."
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium focus:outline-none focus:border-primary"
            />
            <button
              type="submit"
              disabled={sendMessage.isPending || !input.trim()}
              className="p-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-40 cursor-pointer"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

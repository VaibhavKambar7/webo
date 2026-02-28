"use client";

import { useState, useRef, useEffect } from "react";
import {
  Search,
  Loader,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Layers,
  Telescope,
  ArrowUp,
  StopCircle,
  Moon,
  Sun,
} from "lucide-react";
import ReactMarkdown from "react-markdown";

interface Source {
  title: string;
  url: string;
  favicon?: string;
}

interface ReActAction {
  tool: string;
  input?: string;
}

interface ReActStep {
  thought: string;
  action: ReActAction;
  observation?: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  thinkingSteps?: ReActStep[];
  subQueries?: string[];
  status?: string;
  error?: string;
  jobId?: string;
  isExpanded?: boolean;
}

interface ChatContainerProps {
  initialChatId: string | undefined;
}

const getFaviconUrl = (url: string) => {
  try {
    const hostname = new URL(url).hostname;
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=64`;
  } catch (e) {
    return "";
  }
};

export default function ChatContainer({ initialChatId }: ChatContainerProps) {
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [query, setQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [isAgentic, setIsAgentic] = useState<boolean>(false);

  const [currentChatId, setCurrentChatId] = useState<string | undefined>(
    initialChatId,
  );

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  };

  useEffect(() => {
    adjustHeight();
  }, [query]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const prevMessagesLengthRef = useRef(messages.length);
  useEffect(() => {
    const shouldScroll =
      messages.length !== prevMessagesLengthRef.current ||
      (loading && messages.length > 0);

    if (shouldScroll) {
      scrollToBottom();
    }

    prevMessagesLengthRef.current = messages.length;
  }, [messages, loading]);

  useEffect(() => {
    if (!loading && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [loading]);

  useEffect(() => {
    let value = localStorage.getItem("webo-theme");
    if (value === "light" || value === "dark") {
      setTheme(value);
    }

    if (initialChatId) {
      getChats();
    }
  }, []);

  const eventStreamer = async (jobId: string, assistantMessageId: string) => {
    try {
      const eventSource = new EventSource(`${apiBaseUrl}/stream/${jobId}`);

      eventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);

        setMessages((prevMessages) => {
          const updatedMessages = [...prevMessages];
          const currentAssistantMessageIndex = updatedMessages.findIndex(
            (msg) => msg.id === assistantMessageId,
          );

          if (currentAssistantMessageIndex === -1) return prevMessages;

          const currentAssistantMessage =
            updatedMessages[currentAssistantMessageIndex];

          currentAssistantMessage.status = data.status;
          currentAssistantMessage.thinkingSteps = data.memory || [];
          currentAssistantMessage.subQueries = data.sub_queries || [];
          currentAssistantMessage.sources = data.sources || [];

          if (data.final_answer && !currentAssistantMessage.content) {
            currentAssistantMessage.isExpanded = false;
          }

          if (data.final_answer) {
            currentAssistantMessage.content = data.final_answer;
          }

          return updatedMessages;
        });

        if (data.status === "COMPLETED" || data.status === "FAILED") {
          eventSource.close();
          setLoading(false);

          if (data.status === "COMPLETED") {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, isExpanded: false }
                  : msg,
              ),
            );
          }

          if (data.status === "FAILED") {
            setError("Job failed. Please try again.");
          }
        }
      };

      eventSource.onerror = (error) => {
        console.error("EventSource error:", error);
        eventSource.close();
        setError("Connection lost. Please try again.");
        setLoading(false);
      };
    } catch (err) {
      console.error("Streaming error:", err);
      setError("Failed to establish connection. Please try again.");
      setLoading(false);
    }
  };

  const getChats = async () => {
    try {
      if (!initialChatId) return;

      const response = await fetch(`${apiBaseUrl}/get-chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ chat_id: initialChatId }),
      });

      const messages = await response.json();
      setMessages(messages);
    } catch (err) {
      console.log("Get chats error:", err);
      setError("Failed to get chats. Please try again.");
    }
  };

  const handleSearch = async () => {
    if (!query.trim() || loading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString() + "-user",
      role: "user",
      content: query,
    };
    setMessages((prev) => [...prev, userMessage]);
    setQuery("");
    setError(null);
    setLoading(true);

    const assistantMessageId = Date.now().toString() + "-assistant";
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        thinkingSteps: [],
        status: "PENDING",
        sources: [],
        isExpanded: true,
      },
    ]);

    let finalChatId = currentChatId;

    if (!finalChatId) {
      const createIdResponse = await fetch(`${apiBaseUrl}/create-chatId`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });

      if (createIdResponse.ok) {
        const data = await createIdResponse.json();
        const newChatId = data.chat_id;

        if (newChatId) {
          finalChatId = newChatId;
          setCurrentChatId(newChatId);
          window.history.replaceState({}, "", `/c/${newChatId}`);
        } else {
          setError("Failed to start chat session.");
          setLoading(false);
          return;
        }
      } else {
        setError("Failed to start chat session.");
        setLoading(false);
        return;
      }
    }

    try {
      const response = await fetch(`${apiBaseUrl}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: userMessage.content,
          chat_id: finalChatId,
          is_agentic: isAgentic,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to submit query");
      }

      const { job_id } = await response.json();

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId ? { ...msg, jobId: job_id } : msg,
        ),
      );

      await eventStreamer(job_id, assistantMessageId);
    } catch (err) {
      setError("Failed to submit query. Please try again.");
      setLoading(false);
    }
  };

  const stopSearch = () => {
    setLoading(false);
    setMessages((prevMessages) => {
      const updatedMessages = [...prevMessages];
      const lastAssistantMessageIndex = updatedMessages.findLastIndex(
        (msg) => msg.role === "assistant",
      );
      if (lastAssistantMessageIndex !== -1) {
        updatedMessages[lastAssistantMessageIndex].status = "STOPPED";
        if (!updatedMessages[lastAssistantMessageIndex].content) {
          updatedMessages[lastAssistantMessageIndex].content =
            "Search was stopped.";
        }
      }
      return updatedMessages;
    });
  };

  const toggleExpansion = (messageId: string) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId ? { ...msg, isExpanded: !msg.isExpanded } : msg,
      ),
    );
  };

  const toggleTheme = () => {
    setTheme((prev) => {
      const next = prev === "light" ? "dark" : "light";
      localStorage.setItem("webo-theme", next);
      return next;
    });
  };

  const getStatusDisplay = (status?: string) => {
    if (!status) return null;

    const statusMap: Record<
      string,
      { label: string; icon: any; color: string }
    > = {
      PENDING: {
        label: "Initializing...",
        icon: Loader,
        color: theme === "dark" ? "text-neutral-400" : "text-slate-500",
      },
      DECOMPOSING: {
        label: "Breaking down request...",
        icon: Layers,
        color: theme === "dark" ? "text-neutral-300" : "text-slate-600",
      },
      WORKING: {
        label: "Searching internet...",
        icon: Search,
        color: theme === "dark" ? "text-neutral-200" : "text-slate-700",
      },
      SYNTHESIZING: {
        label: "Synthesizing answer...",
        icon: Loader,
        color: theme === "dark" ? "text-neutral-200" : "text-slate-700",
      },
      COMPLETED: { label: "Completed", icon: null, color: "text-emerald-600" },
      FAILED: { label: "Failed", icon: AlertCircle, color: "text-rose-600" },
      STOPPED: { label: "Stopped", icon: StopCircle, color: "text-amber-600" },
    };

    const statusInfo = statusMap[status] || {
      label: status,
      icon: Loader,
      color: theme === "dark" ? "text-neutral-400" : "text-slate-500",
    };
    const Icon = statusInfo.icon;

    return (
      <div
        className={`flex items-center gap-2 text-sm ${statusInfo.color} font-medium mb-4`}
      >
        {Icon && (
          <Icon
            className={`w-4 h-4 ${status === "PENDING" || status === "SYNTHESIZING" ? "animate-spin" : ""}`}
          />
        )}
        <span>{statusInfo.label}</span>
      </div>
    );
  };

  return (
    <>
      <style jsx global>{`
        .markdown-content > *:first-child {
          margin-top: 0;
        }
        .markdown-content > *:last-child {
          margin-bottom: 0;
        }
        .markdown-content p {
          margin-bottom: 1.25rem;
          line-height: 1.72;
          color: ${theme === "dark" ? "#ececec" : "#2f3a4a"};
        }
        .markdown-content h1,
        .markdown-content h2,
        .markdown-content h3,
        .markdown-content h4 {
          margin-top: 2rem;
          margin-bottom: 1rem;
          font-weight: 600;
          color: ${theme === "dark" ? "#ffffff" : "#162032"};
          line-height: 1.3;
        }
        .markdown-content h1 {
          font-size: 1.5rem;
        }
        .markdown-content h2 {
          font-size: 1.25rem;
        }
        .markdown-content h3 {
          font-size: 1.125rem;
        }
        .markdown-content ul,
        .markdown-content ol {
          margin-bottom: 1.25rem;
          padding-left: 1.5rem;
          color: ${theme === "dark" ? "#ececec" : "#2f3a4a"};
        }
        .markdown-content li {
          margin-bottom: 0.5rem;
          padding-left: 0.25rem;
        }
        .markdown-content li::marker {
          color: ${theme === "dark" ? "#666666" : "#8a9bb0"};
        }
        .markdown-content a {
          color: ${theme === "dark" ? "#a0a0a0" : "#374151"};
          text-decoration: none;
          cursor: pointer;
        }
        .markdown-content a:hover {
          text-decoration: underline;
        }
        .markdown-content code {
          background-color: ${theme === "dark" ? "#2f2f2f" : "#e8edf5"};
          color: ${theme === "dark" ? "#ffffff" : "#1f2d40"};
          padding: 0.2em 0.4em;
          border-radius: 0.25rem;
          font-size: 0.875em;
          font-family:
            ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        .markdown-content pre {
          background-color: ${theme === "dark" ? "#0d0d0d" : "#262626"};
          padding: 1rem;
          border-radius: 0.5rem;
          overflow-x: auto;
          margin-bottom: 1.5rem;
        }
        .markdown-content pre code {
          background-color: transparent;
          color: #e5e5e5;
          padding: 0;
          font-size: 0.875em;
        }
        .markdown-content blockquote {
          border-left: 4px solid ${theme === "dark" ? "#676767" : "#c7d4e5"};
          padding-left: 1rem;
          margin-bottom: 1.25rem;
          font-style: italic;
          color: ${theme === "dark" ? "#a0a0a0" : "#4e6078"};
        }
        .markdown-content strong {
          color: ${theme === "dark" ? "#ffffff" : "#162032"};
          font-weight: 600;
        }
      `}</style>

      <div
        className={`min-h-screen font-[family-name:var(--font-sans)] ${
          theme === "dark"
            ? "bg-[#212121] text-[#ececec]"
            : "bg-[radial-gradient(circle_at_top,#ffffff,#eef2f7_45%)] text-slate-900"
        }`}
      >
        <div className="fixed top-5 right-5 z-50">
          <button
            onClick={toggleTheme}
            className={`p-2.5 rounded-xl transition-colors border shadow-sm ${
              theme === "dark"
                ? "bg-[#2f2f2f] hover:bg-[#3a3a3a] text-[#ececec] border-[#424242]"
                : "bg-white/95 hover:bg-white text-slate-700 border-slate-200"
            }`}
          >
            {theme === "dark" ? (
              <Sun className="w-5 h-5 cursor-pointer" />
            ) : (
              <Moon className="w-5 h-5 cursor-pointer" />
            )}
          </button>
        </div>

        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-10">
          {messages.length === 0 && !currentChatId ? (
            <div className="flex flex-col items-center justify-center min-h-[60vh]">
              <div className="w-full max-w-3xl space-y-8">
                <div className="text-center space-y-3">
                  <h2
                    className={`text-4xl font-semibold tracking-tight ${
                      theme === "dark" ? "text-[#ececec]" : "text-slate-900"
                    }`}
                  >
                    WEBO
                  </h2>
                  <p
                    className={`text-lg ${
                      theme === "dark" ? "text-[#a0a0a0]" : "text-slate-600"
                    }`}
                  >
                    Analyze topics quickly with traceable sources and focused summaries.
                  </p>
                </div>

                <div className="relative">
                  <div
                    className={`relative rounded-2xl shadow-lg focus-within:ring-2 transition-all duration-200 ${
                      theme === "dark"
                        ? "bg-[#2f2f2f] border border-[#424242] focus-within:border-[#555555] focus-within:ring-[#3a3a3a]/40"
                        : "bg-white/95 border border-slate-200 focus-within:border-slate-400 focus-within:ring-slate-100"
                    }`}
                  >
                    <textarea
                      ref={textareaRef}
                      placeholder="What do you want to know?"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey && !loading) {
                          e.preventDefault();
                          handleSearch();
                        }
                      }}
                      rows={1}
                      className={`w-full px-5 py-4 pr-24 text-[15px] bg-transparent focus:outline-none rounded-2xl resize-none overflow-hidden min-h-[60px] leading-relaxed ${
                        theme === "dark"
                          ? "text-[#ececec] placeholder-[#666666]"
                          : "text-slate-900 placeholder-slate-400"
                      }`}
                      disabled={loading}
                    />
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
                      <button
                        onClick={() => setIsAgentic(!isAgentic)}
                        className={`h-9 w-9 rounded-full transition-all cursor-pointer border inline-flex items-center justify-center ${
                          isAgentic
                            ? "bg-[#2f2f2f] text-emerald-400 border-emerald-500/30"
                            : theme === "dark"
                              ? "text-[#888888] border-[#424242] hover:text-[#aaaaaa]"
                              : "text-slate-500 border-slate-200 hover:text-slate-700"
                        }`}
                        title="Deep Research uses an agentic workflow"
                        aria-label="Toggle deep research"
                      >
                        <Telescope
                          className={`w-4 h-4 ${isAgentic ? "animate-pulse" : ""}`}
                        />
                      </button>
                      <button
                        onClick={handleSearch}
                        disabled={!query.trim() || loading}
                        className={`h-9 w-9 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer inline-flex items-center justify-center ${
                          theme === "dark"
                            ? "bg-[#424242] text-white hover:bg-[#4f4f4f]"
                            : "bg-slate-900 text-white hover:bg-slate-800"
                        }`}
                        title="Send"
                        aria-label="Send message"
                      >
                        <ArrowUp className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>

                {error && (
                  <div
                    className={`p-3 rounded-lg flex items-center gap-3 text-sm ${
                      theme === "dark"
                        ? "bg-rose-900/20 border border-rose-800 text-rose-300"
                        : "bg-rose-50 border border-rose-200 text-rose-700"
                    }`}
                  >
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="pb-44 space-y-10">
              {messages.map((message) => (
                <div key={message.id} className="fade-in">
                  {message.role === "user" && (
                    <div className="flex justify-end mb-5">
                      <div
                        className={`max-w-[88%] rounded-2xl px-4 py-3 text-lg font-medium leading-relaxed ${
                          theme === "dark"
                            ? "bg-[#2f2f2f] text-[#ececec]"
                            : "bg-white text-slate-900 border border-slate-200"
                        }`}
                      >
                        {message.content}
                      </div>
                    </div>
                  )}

                  {message.role === "assistant" && (
                    <div className="flex gap-6">
                      <div
                        className={`flex-1 min-w-0 space-y-4 rounded-2xl p-5 ${
                          theme === "dark"
                            ? "bg-transparent"
                            : "bg-white/95 border border-slate-200"
                        }`}
                      >
                        <div>
                          {loading &&
                            message.status &&
                            message.status !== "COMPLETED" &&
                            getStatusDisplay(message.status)}

                          {((message.subQueries &&
                            message.subQueries.length > 0) ||
                            (message.sources &&
                              message.sources.length > 0)) && (
                            <div
                            className={`rounded-xl overflow-hidden shadow-sm mb-6 ${
                                theme === "dark"
                                  ? "border border-[#424242] bg-[#2a2a2a]"
                                  : "border border-slate-200 bg-slate-50/70"
                              }`}
                            >
                              <button
                                onClick={() => toggleExpansion(message.id)}
                                className={`w-full flex items-center justify-between px-4 py-3 transition-colors cursor-pointer ${
                                  theme === "dark"
                                    ? "bg-[#2a2a2a] hover:bg-[#333333] border-b border-[#424242]"
                                    : "bg-slate-100/70 hover:bg-slate-100 border-b border-slate-200"
                                }`}
                              >
                                <div
                                  className={`flex items-center gap-2 text-xs font-medium uppercase tracking-wide ${
                                    theme === "dark"
                                      ? "text-[#888888]"
                                      : "text-slate-600"
                                  }`}
                                >
                                  <Layers className="w-3.5 h-3.5" />
                                  <span>
                                    {message.sources?.length
                                      ? `${message.sources.length} Sources Analyzed`
                                      : "Processing Request"}
                                  </span>
                                </div>
                                {message.isExpanded ? (
                                  <ChevronUp
                                    className={`w-4 h-4 ${theme === "dark" ? "text-[#666666]" : "text-gray-400"}`}
                                  />
                                ) : (
                                  <ChevronDown
                                    className={`w-4 h-4 ${theme === "dark" ? "text-[#666666]" : "text-gray-400"}`}
                                  />
                                )}
                              </button>

                                {message.isExpanded && (
                                  <div
                                    className={`p-4 space-y-6 ${
                                      theme === "dark"
                                        ? "bg-[#262626]"
                                        : "bg-white"
                                    }`}
                                  >
                                    {message.subQueries &&
                                      message.subQueries.length > 0 && (
                                      <div className="space-y-2">
                                        <div
                                          className={`text-xs font-semibold uppercase ${
                                            theme === "dark"
                                              ? "text-[#888888]"
                                              : "text-slate-500"
                                          }`}
                                        >
                                          Research Steps
                                        </div>
                                        <div className="flex flex-col gap-2">
                                          {message.subQueries.map(
                                            (subQuery, idx) => (
                                              <div
                                                key={idx}
                                                className={`flex items-start gap-2.5 text-sm ${
                                                  theme === "dark"
                                                    ? "text-[#cccccc]"
                                                    : "text-slate-700"
                                                }`}
                                              >
                                                <div
                                                  className={`mt-0.5 ${
                                                    theme === "dark"
                                                      ? "text-[#666666]"
                                                      : "text-slate-400"
                                                  }`}
                                                >
                                                  <Search className="w-3.5 h-3.5" />
                                                </div>
                                                <span>{subQuery}</span>
                                              </div>
                                            ),
                                          )}
                                        </div>
                                      </div>
                                    )}

                                  {message.sources &&
                                    message.sources.length > 0 && (
                                      <div className="space-y-2">
                                        <div
                                          className={`text-xs font-semibold uppercase ${
                                            theme === "dark"
                                              ? "text-[#888888]"
                                              : "text-slate-500"
                                          }`}
                                        >
                                          References
                                        </div>
                                        <div className="flex flex-col gap-2">
                                          {message.sources.map(
                                            (source, idx) => {
                                              const hostname = new URL(
                                                source.url,
                                              ).hostname.replace("www.", "");
                                              return (
                                                <a
                                                  key={idx}
                                                  href={source.url}
                                                  target="_blank"
                                                  rel="noopener noreferrer"
                                                  className={`flex items-center gap-3 p-2.5 rounded-lg transition-all group cursor-pointer ${
                                                    theme === "dark"
                                                      ? "bg-[#2f2f2f] border border-[#424242] hover:border-[#555555] hover:bg-[#383838]"
                                                      : "bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                                                  }`}
                                                >
                                                  <div className="flex-shrink-0 w-4 h-4 rounded-sm overflow-hidden opacity-70">
                                                    <img
                                                      src={getFaviconUrl(
                                                        source.url,
                                                      )}
                                                      alt=""
                                                      className="w-full h-full object-cover"
                                                      onError={(e) => {
                                                        (
                                                          e.target as HTMLImageElement
                                                        ).style.display =
                                                          "none";
                                                      }}
                                                    />
                                                  </div>
                                                  <div className="flex-1 min-w-0">
                                                    <div
                                                      className={`text-sm font-medium truncate transition-colors ${
                                                        theme === "dark"
                                                          ? "text-[#cccccc] group-hover:text-[#ececec]"
                                                          : "text-slate-800 group-hover:text-slate-700"
                                                      }`}
                                                    >
                                                      {source.title || hostname}
                                                    </div>
                                                    <div
                                                      className={`text-xs truncate ${
                                                        theme === "dark"
                                                          ? "text-[#888888]"
                                                          : "text-slate-500"
                                                      }`}
                                                    >
                                                      {hostname}
                                                    </div>
                                                  </div>
                                                </a>
                                              );
                                            },
                                          )}
                                        </div>
                                      </div>
                                    )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>

                        <div className="markdown-content">
                          {message.content ? (
                            <ReactMarkdown>{message.content}</ReactMarkdown>
                          ) : (
                            loading &&
                            message.status !== "COMPLETED" && (
                              <div className="flex flex-col gap-2 animate-pulse mt-2">
                                <div
                                  className={`h-2 rounded w-1/3 ${theme === "dark" ? "bg-[#444444]" : "bg-gray-200"}`}
                                ></div>
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} className="h-2" />
            </div>
          )}
        </div>

        {(messages.length > 0 || currentChatId) && (
          <div
            className={`fixed bottom-0 left-0 right-0 z-20 backdrop-blur-md ${
              theme === "dark"
                ? "bg-[#212121]"
                : "bg-white/85 border-t border-slate-200"
            }`}
          >
            <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
              <div
                className={`relative rounded-2xl shadow-lg flex items-end transition-colors ${
                  theme === "dark"
                    ? "bg-[#2f2f2f] border border-[#424242] focus-within:border-[#555555]"
                    : "bg-white border border-slate-200 focus-within:border-slate-400"
                }`}
              >
                <textarea
                  ref={textareaRef}
                  placeholder="Ask a follow up..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && !loading) {
                      e.preventDefault();
                      handleSearch();
                    }
                  }}
                  rows={1}
                  className={`w-full px-4 py-3 pr-24 text-[15px] bg-transparent focus:outline-none resize-none overflow-hidden min-h-[56px] leading-relaxed ${
                    theme === "dark"
                      ? "text-[#ececec] placeholder-[#666666]"
                      : "text-slate-900 placeholder-slate-400"
                  }`}
                  disabled={loading}
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
                  {!loading && (
                    <button
                      onClick={() => setIsAgentic(!isAgentic)}
                      className={`h-9 w-9 rounded-full transition-all cursor-pointer border inline-flex items-center justify-center ${
                        isAgentic
                          ? "bg-[#2f2f2f] text-emerald-400 border-emerald-500/30"
                          : theme === "dark"
                            ? "text-[#888888] border-[#424242] hover:text-[#aaaaaa]"
                            : "text-slate-500 border-slate-200 hover:text-slate-700"
                      }`}
                      title="Deep Research uses an agentic workflow"
                      aria-label="Toggle deep research"
                    >
                      <Telescope
                        className={`w-4 h-4 ${isAgentic ? "animate-pulse" : ""}`}
                      />
                    </button>
                  )}
                  {loading ? (
                    <button
                      onClick={stopSearch}
                      className={`h-9 w-9 rounded-full transition-colors cursor-pointer inline-flex items-center justify-center ${
                        theme === "dark"
                          ? "bg-rose-900/30 text-rose-200 hover:bg-rose-900/45"
                          : "bg-rose-50 text-rose-700 hover:bg-rose-100"
                      }`}
                      title="Stop search"
                      aria-label="Stop search"
                    >
                      <StopCircle className="w-4 h-4" />
                    </button>
                  ) : (
                    <button
                      onClick={handleSearch}
                      disabled={!query.trim()}
                      className={`h-9 w-9 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer inline-flex items-center justify-center ${
                        theme === "dark"
                          ? "bg-[#424242] text-white hover:bg-[#4f4f4f]"
                          : "bg-slate-900 text-slate-100 hover:bg-slate-800"
                      }`}
                      title="Send"
                      aria-label="Send message"
                    >
                      <ArrowUp className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
              {error && (
                <div
                  className={`absolute -top-10 left-1/2 -translate-x-1/2 px-4 py-2 text-xs rounded-full flex items-center gap-2 shadow-sm ${
                    theme === "dark"
                      ? "bg-rose-900/20 text-rose-300 border border-rose-800"
                      : "bg-rose-50 text-rose-700 border border-rose-200"
                  }`}
                >
                  <AlertCircle className="w-3 h-3" /> {error}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

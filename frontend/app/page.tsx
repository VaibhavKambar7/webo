"use client";

import { useState, useRef, useEffect } from "react";
import {
  Search,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from "lucide-react";
import ReactMarkdown from "react-markdown";

interface Source {
  title: string;
  url: string;
  content?: string;
  summary?: string;
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
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [query, setQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSource, setExpandedSource] = useState<number | null>(null);
  const [showThinking, setShowThinking] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, showThinking]);

  const eventStreamer = async (jobId: string, assistantMessageId: string) => {
    try {
      const event = new EventSource(`http://localhost:8000/stream/${jobId}`);

      event.onmessage = (e) => {
        const data = JSON.parse(e.data);

        // if (!data.ok) {
        //   throw new Error("Failed to fetch data");
        // }

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

          if (data.final_answer) {
            currentAssistantMessage.content = data.final_answer;
          } else {
            currentAssistantMessage.content = `Status: ${data.status}...`;
          }

          return updatedMessages;
        });

        if (data.status === "COMPLETED") {
          event.close();
          setError("Job completed.");

          setLoading(false);

          if (data.status === "FAILED") {
            setError("Job failed. Please try again.");
          }
        }

        event.onerror = (error) => {
          console.error("EventSource error:", error);
          event.close();
          setError("Connection lost. Please try again.");
          setLoading(false);
        };
      };
    } catch (err) {
      console.error("Polling error:", err);
      setError("Failed to fetch status. Please try again.");
      setLoading(false);
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
    setShowThinking(true);

    const assistantMessageId = Date.now().toString() + "-assistant";
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "Submitting query...",
        thinkingSteps: [],
        status: "PENDING",
      },
    ]);

    try {
      const response = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: userMessage.content }),
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
      console.error("Search error:", err);
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
        updatedMessages[lastAssistantMessageIndex].status = "Search stopped.";
        updatedMessages[lastAssistantMessageIndex].content +=
          "\n\n**Search stopped.**";
      }
      return updatedMessages;
    });
  };

  const toggleSourceExpansion = (index: number) => {
    setExpandedSource(expandedSource === index ? null : index);
  };

  const formatThinkingStep = (step: ReActStep) => {
    return {
      title: `${step.action.tool}`,
      thought: step.thought,
      actionInput: step.action.input || "N/A",
      observation: step.observation || "Pending...",
    };
  };

  return (
    // Updated background color to pure black
    <div className="min-h-screen bg-black text-white">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <header className="pt-12 pb-8">
          <div className="flex items-center gap-2 justify-center">
            {/* Changed Sparkles icon color to a lighter gray for contrast on black */}
            <Sparkles className="w-7 h-7 text-gray-400" strokeWidth={2} />
            {/* Changed text color to white for better contrast */}
            <h1 className="text-2xl font-semibold text-white">Research</h1>
          </div>
        </header>

        {messages.length === 0 ? (
          <div className="mt-32">
            <div className="relative">
              <input
                ref={inputRef}
                type="text"
                placeholder="Ask anything..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" && !loading && handleSearch()
                }
                // Updated input styles for black theme, using gray-900 for background and gray-600 for border
                className="w-full px-5 py-4 text-base text-gray-50 placeholder-gray-400 bg-gray-900 border border-gray-600 rounded-full shadow-lg focus:outline-none focus:border-gray-400 focus:ring-1 focus:ring-gray-400 transition-all"
                disabled={loading}
              />
              <button
                onClick={handleSearch}
                disabled={!query.trim() || loading}
                // Changed button color to a subtle gray-700, with hover and disabled states
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-gray-700 text-white rounded-full hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500 disabled:cursor-not-allowed transition-colors"
              >
                <Search className="w-5 h-5" strokeWidth={2} />
              </button>
            </div>
            {error && (
              // Updated error styles for black theme, using red-950 for background and red-600 for border
              <div className="mt-4 p-3 bg-red-950/50 border border-red-600 rounded-lg flex items-start gap-2 text-sm text-red-300">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </div>
        ) : (
          <div className="pb-32">
            <div className="space-y-8">
              {messages.map((message, idx) => (
                <div key={message.id} className="space-y-4">
                  {message.role === "user" && (
                    <div className="flex items-start gap-3">
                      {/* Updated user message colors for black theme, using gray-800 background and gray-200 text */}
                      <div className="flex-shrink-0 w-8 h-8 bg-gray-800 rounded-full flex items-center justify-center">
                        <span className="text-sm font-medium text-gray-200">
                          U
                        </span>
                      </div>
                      <div className="flex-1 pt-1">
                        <p className="text-gray-100 text-base leading-relaxed">
                          {message.content}
                        </p>
                      </div>
                    </div>
                  )}

                  {message.role === "assistant" && (
                    <div className="flex items-start gap-3">
                      {/* Updated assistant message colors for black theme, using gray-900 background with a slight opacity and gray-400 for icon */}
                      <div className="flex-shrink-0 w-8 h-8 bg-gray-900/50 rounded-full flex items-center justify-center">
                        <Sparkles
                          className="w-4 h-4 text-gray-400"
                          strokeWidth={2}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        {loading && !message.content.includes("Status:") && (
                          <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span>Searching...</span>
                          </div>
                        )}

                        {message.subQueries &&
                          message.subQueries.length > 1 && (
                            <div className="mb-4 p-3 bg-gray-900/30 border border-gray-800 rounded-lg">
                              <div className="text-xs font-medium text-gray-400 mb-2">
                                Breaking down query into {message.subQueries.length} searches:
                              </div>
                              <div className="space-y-1">
                                {message.subQueries.map((subQuery, idx) => (
                                  <div
                                    key={idx}
                                    className="flex items-start gap-2 text-xs text-gray-300"
                                  >
                                    <span className="text-gray-500 flex-shrink-0">
                                      {idx + 1}.
                                    </span>
                                    <span>{subQuery}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                        {/* {message.thinkingSteps &&
                          message.thinkingSteps.length > 0 &&
                          showThinking && (
                            <div className="mb-4 space-y-2">
                              {message.thinkingSteps.map((step, stepIdx) => {
                                const formatted = formatThinkingStep(step);
                                return (
                                  <div
                                    key={stepIdx}
                                    className="flex items-start gap-2 text-xs text-gray-400"
                                  >
                                    <Loader2 className="w-3 h-3 mt-0.5 animate-spin flex-shrink-0" />
                                    <span>{formatted.title}</span>
                                  </div>
                                );
                              })}
                            </div>
                          )} */}

                        {message.sources && message.sources.length > 0 && (
                          <div className="mb-4">
                            <div className="flex items-center gap-2 flex-wrap">
                              {message.sources
                                .slice(0, 3)
                                .map((source, sourceIdx) => (
                                  <a
                                    key={sourceIdx}
                                    href={source.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    // Updated source pill styles for black theme, using gray-800 background and gray-600 border
                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-300 bg-gray-800 hover:bg-gray-700 rounded-full border border-gray-700 transition-colors"
                                  >
                                    <span className="w-4 h-4 bg-gray-900 rounded border border-gray-700 flex items-center justify-center text-[10px] font-medium text-gray-400">
                                      {sourceIdx + 1}
                                    </span>
                                    <span className="max-w-[200px] truncate">
                                      {source.title ||
                                        new URL(source.url).hostname}
                                    </span>
                                  </a>
                                ))}
                            </div>
                          </div>
                        )}

                        {/* Updated prose styles for black theme readability */}
                        <div className="prose prose-sm max-w-none prose-invert prose-headings:font-semibold prose-headings:text-white prose-p:text-gray-300 prose-p:leading-relaxed prose-a:text-gray-400 prose-a:no-underline hover:prose-a:underline prose-strong:text-white prose-strong:font-semibold prose-ul:text-gray-300 prose-ol:text-gray-300">
                          <ReactMarkdown>{message.content}</ReactMarkdown>
                        </div>

                        {message.sources && message.sources.length > 3 && (
                          <button
                            onClick={() => setShowThinking(!showThinking)}
                            className="mt-4 text-sm text-gray-400 hover:text-gray-300 flex items-center gap-1"
                          >
                            <span>
                              View all {message.sources.length} sources
                            </span>
                            {showThinking ? (
                              <ChevronUp className="w-4 h-4" />
                            ) : (
                              <ChevronDown className="w-4 h-4" />
                            )}
                          </button>
                        )}

                        {message.status && loading && (
                          <div className="mt-3 text-xs text-gray-400">
                            {message.status}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            <div
              // Updated fixed input area background for black theme, using black background with gradient to transparent
              className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-black via-black to-transparent pt-8 pb-6"
            >
              <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="relative">
                  <input
                    ref={inputRef}
                    type="text"
                    placeholder="Ask a follow up..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) =>
                      e.key === "Enter" && !loading && handleSearch()
                    }
                    // Updated input styles for black theme, using gray-900 for background and gray-600 for border
                    className="w-full px-5 py-4 pr-12 text-base text-gray-50 placeholder-gray-400 bg-gray-900 border border-gray-600 rounded-full shadow-lg focus:outline-none focus:border-gray-400 focus:ring-1 focus:ring-gray-400 transition-all"
                    disabled={loading}
                  />
                  {loading ? (
                    <button
                      onClick={stopSearch}
                      // Changed stop button color to a red-700
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-red-700 text-white rounded-full hover:bg-red-600 transition-colors"
                    >
                      <div className="w-4 h-4 border-2 border-white"></div>
                    </button>
                  ) : (
                    <button
                      onClick={handleSearch}
                      disabled={!query.trim()}
                      // Changed button color to a subtle gray-700, with hover and disabled states
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-gray-700 text-white rounded-full hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500 disabled:cursor-not-allowed transition-colors"
                    >
                      <Search className="w-5 h-5" strokeWidth={2} />
                    </button>
                  )}
                </div>
                {error && (
                  // Updated error styles for black theme
                  <div className="mt-3 p-3 bg-red-950/50 border border-red-600 rounded-lg flex items-start gap-2 text-sm text-red-300">
                    <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


// - each q has states etc , pending, decomposing etc
// - we break the q into subq, and show those qs to the FE, then fetch sites , and show the sources
// - then we list the summary
// - we also need to show the which content is coming from which source


// - first replace polling w server side events
// - send states , and memory steps


// when user sends a query we start this
// we show the states for me to understand
// and
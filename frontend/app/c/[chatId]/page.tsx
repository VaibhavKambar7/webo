import ChatContainer from "@/app/components/chat-container";

interface ChatIdPageProps {
  params: Promise<{
    chatId: string;
  }>;
}

export default async function ChatIdPage({ params }: ChatIdPageProps) {
  const { chatId } = await params;
  return <ChatContainer initialChatId={chatId} />;
}

import ChatContainer from "@/app/components/ChatContainer";

interface ChatIdPageProps {
  params: {
    chatId: string;
  };
}

export default function ChatIdPage({ params }: ChatIdPageProps) {
  return <ChatContainer initialChatId={params.chatId} />;
}

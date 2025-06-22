import { ref } from 'vue';

export interface Meta {
  tables: string[];
  activities: string[];
  query: string;
  result: Record<string, any>[];
  plotPath: string | undefined;
  plotBase64: string | undefined;
}

export type Role = 'system' | 'ai' | 'human';

export interface Message {
  id?: string;
  role: Role;
  content: string;
  meta?: Meta;
}

export function useChatWebSocket() {
  const socket = ref<WebSocket | null>(null);
  const messages = ref<Message[]>([]);
  const steps = ref<string[]>([]);
  const isConnected = ref(false);
  const onFinalResponse = ref<(() => void) | null>(null);
  const approvalRequest = ref<{ data: Record<string, any>[]; chat_id: string } | null>(null);
  const partialMessages = new Map<string, string>();

  const connect = () => {
    socket.value = new WebSocket('ws://localhost:8000/ws');

    socket.value.onopen = () => {
      isConnected.value = true;
    };

    socket.value.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'step') {
        steps.value = [data.node];
      } else if (data.type === 'approval') {
        steps.value = [];
        approvalRequest.value = {
          data: data.data,
          chat_id: data.chat_id
        };
      } else if (data.type === 'chunk') {
        const { id, content } = data;
        if (!partialMessages.has(id)) {
          const partialMessage: Message = {
            id,
            role: 'ai',
            content: content
          };
          messages.value.push(partialMessage);
          partialMessages.set(id, content);
        } else {
          partialMessages.set(id, content);
          const msgIndex = messages.value.findIndex((m) => m.id === id);
          if (msgIndex !== -1) {
            messages.value[msgIndex].content = content;
          }
        }
      } else if (data.role === 'ai') {
        const { id, content, additional_kwargs } = data;
        const msgIndex = messages.value.findIndex((m) => m.id === id);
        if (msgIndex !== -1) {
          messages.value[msgIndex] = {
            id,
            role: 'ai',
            content,
            meta: additional_kwargs?.meta
          };
        } else {
          messages.value.push({
            id,
            role: 'ai',
            content,
            meta: additional_kwargs?.meta
          });
        }
        partialMessages.delete(id);
        if (onFinalResponse.value) {
          onFinalResponse.value();
        }
        steps.value = [];
      }
    };

    socket.value.onclose = () => {
      isConnected.value = false;
    };
  };

  const send = (
    question: string,
    chatId: string,
    options?: { top_k?: number; autoApprove?: boolean }
  ) => {
    steps.value = [];
    messages.value.push({ role: 'human', content: question });
    socket.value?.send(
      JSON.stringify({
        question,
        chat_id: chatId,
        top_k: options?.top_k ?? 150,
        auto_approve: options?.autoApprove ?? false
      })
    );
  };
  return {
    connect,
    send,
    messages,
    steps,
    isConnected,
    onFinalResponse,
    approvalRequest
  };
}

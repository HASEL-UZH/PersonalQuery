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
  const interruptionMeta = ref<{
    query: string;
    data: Record<string, any>[];
    chat_id: string;
    reason: {
      auto_approve: boolean;
      auto_sql: boolean;
    };
  } | null>(null);
  const partialMessages = new Map<string, string>();

  const connect = () => {
    socket.value = new WebSocket('ws://localhost:8000/ws');

    socket.value.onopen = () => {
      isConnected.value = true;
    };

    socket.value.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type != 'chunk'){
        console.log("data received:", data);
      }


      if (data.type === 'step') {
        steps.value = [data.node];
      } else if (data.type === 'interruption') {
        steps.value = [];
        interruptionMeta.value = {
          query: data.query,
          data: data.data,
          chat_id: data.chat_id,
          reason: {
            auto_approve: data.reason.auto_approve,
            auto_sql: data.reason.auto_sql
          }
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
    options?: {
      top_k?: number;
      autoApprove?: boolean;
      autoSQL?: boolean;
      answerDetail?: string;
      wantsPlot?: string;
    }
  ) => {
    steps.value = [];
    messages.value.push({ role: 'human', content: question });

    const payload = JSON.stringify({
      question,
      chat_id: chatId,
      top_k: options?.top_k ?? 150,
      auto_approve: options?.autoApprove ?? false,
      auto_sql: options?.autoSQL ?? true,
      answer_detail: options?.answerDetail ?? 'auto',
      wants_plot: options?.wantsPlot ?? 'auto'
    });

    if (!socket.value || socket.value.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket is not open. Reconnecting...');
      connect();
      setTimeout(() => {
        if (socket.value?.readyState === WebSocket.OPEN) {
          socket.value.send(payload);
        } else {
          console.error('WebSocket still not open after reconnect.');
        }
      }, 300);
    } else {
      socket.value.send(payload);
    }
  };

  const disconnect = () => {
    if (socket.value) {
      socket.value.close();
      socket.value = null;
    }
  };


  return {
    connect,
    send,
    disconnect,
    messages,
    steps,
    isConnected,
    onFinalResponse,
    interruptionMeta: interruptionMeta
  };
}

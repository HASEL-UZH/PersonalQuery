<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { marked } from 'marked';
import { Message, Meta, useChatWebSocket } from '../utils/WebSocketHandler';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import markedKatex from 'marked-katex-extension';
import { FilterMatchMode } from '@primevue/core/api';
import ApprovalRequestBox from '../components/ApprovalRequestBox.vue';
import SQLReviewBox from '../components/SQLReviewBox.vue';

const route = useRoute();
const chatId = ref(route.params.chatId as string);
const input = ref('');
const isOpen = ref(true);

const enlargedImage = ref<string | null>(null);
const showImageModal = ref(false);

function openImageModal(base64: string) {
  enlargedImage.value = base64;
  showImageModal.value = true;
}

function closeImageModal() {
  showImageModal.value = false;
  enlargedImage.value = null;
}

const {
  connect,
  send,
  disconnect,
  messages: wsMessages,
  steps,
  onFinalResponse,
  interruptionMeta
} = useChatWebSocket();

const mainGreetings = [
  'Hello there. Want to know how your time was spent?',
  'Welcome back. Let me know what you want to find out.',
  'Hi there 👋 What would you like to explore in your data today?',
  "I'm ready to help you reflect on your digital activity — just ask.",
  'Greetings. How can I assist with your PersonalAnalytics data?',
  'PersonalAnalytics observed 👀. PersonalQuery speaks 🗣️.',
  'I know what you did last session (spoiler: you sat heroically 🪑).',
  'Thanks for joining the study! What’s on your mind?',
  'Visuals take extra time, but they might be worth it 📊.'
];

const greetingDisplayed = ref(true);
const greetingChunks = ref<string[]>([]);
const fullGreeting = ref('');

interface Review {
  chat_id: string;
  data: Record<string, any>[];
  query: string;
}

marked.use(markedKatex());

function formatMessage(message: string) {
  return marked.parse(message);
}

const filters = ref<{ global: { value: string | null; matchMode: string } }>({
  global: { value: null, matchMode: FilterMatchMode.CONTAINS }
});

const globalSearch = ref('');

watch(globalSearch, (newVal) => {
  filters.value.global.value = newVal;
});

const metaDialog = ref<HTMLDialogElement | null>(null);
const currentMeta = ref<Meta>({
  tables: [],
  activities: [],
  query: '',
  result: [],
  plotPath: '',
  plotBase64: ''
});
const bottomAnchor = ref<HTMLElement | null>(null);
const autoApprove = ref(false);
const autoSQL = ref(false);
const answerDetail = ref('auto');
const wantsPlot = ref('auto');
const topK = ref(150);
const loadingResult = ref(false);
const loadingQuery = ref(false);
const sqlError = ref<string | null>(null);
const STORAGE_KEY = 'chat_settings';

function openMetaModal(meta: Meta) {
  currentMeta.value = meta;
  metaDialog.value?.showModal();
}

function closeMetaModal() {
  metaDialog.value?.close();
}

const handleNewChatGreeting = () => {
  greetingDisplayed.value = true;
  fullGreeting.value = mainGreetings[Math.floor(Math.random() * mainGreetings.length)];
  simulateGreetingStream(fullGreeting.value);
};

function simulateGreetingStream(text: string) {
  greetingChunks.value = [];
  const words = text.split(' ');
  let i = 0;
  const interval = setInterval(() => {
    if (i < words.length) {
      greetingChunks.value.push(words[i]);
      i++;
    } else {
      clearInterval(interval);
    }
  }, 50); // word speed
}

async function fetchChatHistory() {
  const res = await fetch(`http://localhost:8000/chats/${chatId.value}`);
  if (!res.ok) return;

  const data = await res.json();
  const fetchedMessages: Message[] = data.messages
    .filter((msg: Message) => msg.role !== 'system')
    .map((msg: any) => ({
      role: msg.role,
      content: msg.content,
      meta: msg.meta || msg.additional_kwargs?.meta
    }));

  wsMessages.value.push(...fetchedMessages);

  if (fetchedMessages.length > 0) {
    greetingDisplayed.value = false;
  }
}

onMounted(() => {
  connect();
  fetchChatHistory();
  window.addEventListener('newChatCreated', handleNewChatGreeting);
});

onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      if (typeof parsed.autoApprove === 'boolean') autoApprove.value = parsed.autoApprove;
      if (typeof parsed.topK === 'number') topK.value = parsed.topK;
      if (typeof parsed.autoSQL === 'boolean') autoSQL.value = parsed.autoSQL;
      if (typeof parsed.answerDetail === 'string') answerDetail.value = parsed.answerDetail;
      if (typeof parsed.wantsPlot === 'string') wantsPlot.value = parsed.wantsPlot;
    } catch (e) {
      console.warn('Invalid chat_settings in localStorage');
    }
  }
});

onBeforeUnmount(() => {
  disconnect();
  window.removeEventListener('newChatCreated', handleNewChatGreeting);
});

watch([autoApprove, topK, autoSQL, answerDetail, wantsPlot], () => {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      autoApprove: autoApprove.value,
      topK: topK.value,
      autoSQL: autoSQL.value,
      answerDetail: answerDetail.value,
      wantsPlot: wantsPlot.value
    })
  );
});

const needsApproval = ref(false);
const needsSQLReview = ref(false);
const reviewMeta = ref<Review | null>(null);

watch(interruptionMeta, () => {
  console.log('interruptionMeta:', interruptionMeta);
  if (interruptionMeta.value) {
    needsApproval.value = !interruptionMeta.value.reason.auto_approve;
    needsSQLReview.value = !interruptionMeta.value.reason.auto_sql;
    reviewMeta.value = {
      chat_id: interruptionMeta.value.chat_id,
      data: interruptionMeta.value.data,
      query: interruptionMeta.value.query
    };
    console.log('reviewMeta.value', reviewMeta.value);
  }
});

watch(
  () => route.params.chatId,
  (newChatId) => {
    chatId.value = newChatId as string;
    wsMessages.value = [];
    fetchChatHistory();
  }
);

watch(
  wsMessages,
  async () => {
    await nextTick();
    bottomAnchor.value?.scrollIntoView({ behavior: 'smooth' });
  },
  { deep: true }
);

watch(
  steps,
  async () => {
    await nextTick();
    bottomAnchor.value?.scrollIntoView({ behavior: 'smooth' });
  },
  { deep: true }
);

function sendMessage() {
  if (!input.value.trim()) return;
  greetingDisplayed.value = false;
  const userMessage = input.value;
  input.value = '';
  send(userMessage, chatId.value, {
    top_k: topK.value,
    autoApprove: autoApprove.value,
    autoSQL: autoSQL.value,
    answerDetail: answerDetail.value,
    wantsPlot: wantsPlot.value
  });
}

function cleanQuery(query: string): string {
  return query
    .split('\n')
    .map((line) => line.trimStart())
    .join('\n')
    .trim();
}

onFinalResponse.value = async () => {
  await fetch(`http://localhost:8000/chats`)
    .then((res) => res.json())
    .then((data) => {
      window.dispatchEvent(new CustomEvent('refreshSidebar', { detail: data.chats }));
    });
};

const sendApproval = async (chatId: string, approval: boolean, data: any) => {
  try {
    const res = await fetch('http://localhost:8000/approval', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chatId,
        approval,
        data: data
      })
    });

    const result = await res.json();

    if (result && result.role === 'ai' && result.content) {
      wsMessages.value.push({
        role: result.role,
        content: result.content,
        meta: result.additional_kwargs?.meta
      });
    }
  } catch (err) {
    console.error('Failed to send approval:', err);
  }
};

function respondToApproval(approval: boolean) {
  if (reviewMeta.value?.chat_id) {
    sendApproval(reviewMeta.value.chat_id, approval, reviewMeta.value.data);
  }
  needsApproval.value = false;
  reviewMeta.value = null;
}

const resultData = computed(() => {
  return Array.isArray(currentMeta.value.result) ? currentMeta.value.result : [];
});

const resultColumns = computed(() => {
  const firstRow = resultData.value[0];
  if (!firstRow) return [];
  return Object.keys(firstRow).map((key) => ({
    field: key,
    header: formatHeader(key)
  }));
});

const approvalColumns = computed(() => {
  const firstRow = reviewMeta.value?.data?.[0];
  if (!firstRow) return [];
  return Object.keys(firstRow).map((key) => ({
    field: key,
    header: formatHeader(key)
  }));
});

function formatHeader(key: string): string {
  return key.replace(/([A-Z])/g, ' $1').replace(/^./, (str) => str.toUpperCase());
}

const onCellEditComplete = (event: any) => {
  const { data, newValue, field } = event;

  if (newValue?.trim?.() === '') {
    event.preventDefault();
    return;
  }

  data[field] = newValue;
};

async function executeQuery(finalQuery: string) {
  if (!chatId.value) return;
  sqlError.value = null;
  loadingResult.value = true;
  try {
    const res = await fetch('http://localhost:8000/execute-query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chatId.value,
        query: finalQuery
      })
    });
    const result = await res.json();
    if (result) {
      if (result.error) {
        sqlError.value = result.error;
      }

      else if (reviewMeta.value) {
        reviewMeta.value.data = result;
      }
    }
    steps.value = [];
  } catch (error) {
    console.error('Failed to execute SQL:', error);
  } finally {
    loadingResult.value = false;
  }
}

function resetQuery() {
  console.log("resetting:", reviewMeta.value?.query)
  console.log("with:", interruptionMeta.value?.query)
  if (reviewMeta.value) {
    reviewMeta.value.query = interruptionMeta.value!.query;
  }
}

async function handleLLMCorrection(instruction: string, query: string) {
  if (!interruptionMeta.value) return;
  loadingQuery.value = true;
  const { chat_id } = interruptionMeta.value;

  try {
    const res = await fetch('http://localhost:8000/correct-query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id,
        query,
        instruction
      })
    });

    const result = await res.json();

    if (result) {
      reviewMeta.value!.query = result;
      loadingQuery.value = false;
    } else {
      console.warn('No corrected query returned from server');
    }
  } catch (err) {
    console.error('Failed to request query correction:', err);
  }
}

async function handleProceedAfterSQL() {
  if (!reviewMeta.value) return;
  needsSQLReview.value = false;

  const { chat_id, query, data } = reviewMeta.value;

  try {
    const res = await fetch('http://localhost:8000/confirm-query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id,
        query,
        data
      })
    });

    const result = await res.json();
    if (result && result.role === 'ai' && result.content) {
      console.log("IM IN HEREEEE")
      wsMessages.value.push({
        role: result.role,
        content: result.content,
        meta: result.additional_kwargs?.meta
      });
      reviewMeta.value = null;
    }


  } catch (err) {
    console.error('Failed to confirm SQL with backend:', err);
  }
}
</script>

<template>
  <div class="flex h-screen flex-col bg-base-100 p-4">
    <div class="scrollable flex-1 space-y-4 overflow-y-auto pr-1">
      <div
        v-if="greetingDisplayed"
        class="flex h-[80%] items-center justify-center px-4 text-center"
      >
        <div class="max-w-4xl text-3xl font-semibold leading-relaxed text-base-content">
          <span v-html="greetingChunks.join(' ')" />
        </div>
      </div>

      <div v-for="(msg, index) in wsMessages" :key="index" class="w-full">
        <!-- User message -->
        <div v-if="msg.role === 'human'" class="chat chat-end mb-4">
          <div class="chat-bubble chat-bubble-primary max-w-[80%] px-4 py-2 text-base">
            <div class="prose prose-base text-black" v-html="formatMessage(msg.content)" />
          </div>
        </div>
        <!-- Loading steps appear directly after the last user message -->
        <div
          v-if="index === wsMessages.length - 1 && msg.role === 'human' && steps.length"
          class="mb-4 flex w-full justify-center px-4"
        >
          <div class="prose prose-sm mx-auto w-full max-w-4xl px-2 text-left text-gray-400">
            <p v-if="steps.length" class="flex items-center gap-2">
              <span class="loading loading-spinner loading-sm"></span>
              {{ steps[steps.length - 1].replaceAll('_', ' ') }}
            </p>
          </div>
        </div>
        <!-- AI message -->
        <div v-else-if="msg.role === 'ai'" class="mb-4 flex w-full justify-center px-4">
          <div
            class="prose mx-auto w-full max-w-4xl rounded-lg border border-white/10 px-6 py-5 text-left leading-tight text-base-content"
          >
            <!-- Render message text -->
            <div v-html="formatMessage(msg.content)" />

            <!-- Render plot if present -->
            <img
              v-if="msg.meta?.plotBase64"
              :src="msg.meta.plotBase64"
              alt="Generated plot"
              class="mt-4 max-h-[500px] w-full cursor-pointer rounded-lg border border-white/20 object-contain shadow transition"
              @click="openImageModal(msg.meta.plotBase64)"
            />

            <!-- Optional metadata info button -->
            <button
              v-if="msg.meta"
              class="btn btn-circle btn-ghost btn-xs float-right mt-2 text-info"
              title="View details"
              @click="openMetaModal(msg.meta)"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                class="size-6 text-primary"
              >
                <path
                  fill-rule="evenodd"
                  d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm8.706-1.442c1.146-.573 2.437.463 2.126 1.706l-.709 2.836.042-.02a.75.75 0 0 1 .67 1.34l-.04.022c-1.147.573-2.438-.463-2.127-1.706l.71-2.836-.042.02a.75.75 0 1 1-.671-1.34l.041-.022ZM12 9a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Z"
                  clip-rule="evenodd"
                />
              </svg>
            </button>
          </div>
        </div>
        <div class="mb-4 flex w-full justify-center px-4">
          <SQLReviewBox
            v-if="needsSQLReview && index === wsMessages.length - 1"
            :query="reviewMeta?.query"
            :original-query="interruptionMeta?.query"
            :result="reviewMeta?.data"
            :columns="approvalColumns"
            :filters="filters"
            :loading-query="loadingQuery"
            :loading-result="loadingResult"
            :sql-error="sqlError"
            @reset-query="resetQuery"
            @execute-query="executeQuery"
            @correct-query="handleLLMCorrection"
            @proceed="handleProceedAfterSQL"
          />
          <ApprovalRequestBox
            v-if="needsApproval && !needsSQLReview && index === wsMessages.length - 1"
            :data="reviewMeta?.data"
            @approve="respondToApproval"
            @cell-edit-complete="onCellEditComplete"
          />
        </div>
      </div>

      <div ref="bottomAnchor"></div>
    </div>

    <form class="w-full" @submit.prevent="sendMessage">
      <div class="space-y-2 rounded border border-base-300 bg-base-200 p-3">
        <div class="flex w-full">
          <input
            v-model="input"
            class="input input-bordered w-full rounded-r-none focus:outline-none focus:ring-0"
            placeholder="Type your message..."
          />
          <button class="btn btn-primary rounded-l-none" type="submit">Send</button>
        </div>

        <button class="btn btn-sm mt-0 flex items-center p-1" @click="isOpen = !isOpen">
          <span>Options</span>
          <svg
            v-if="isOpen"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            class="size-6"
          >
            <path
              fill-rule="evenodd"
              d="M11.47 7.72a.75.75 0 0 1 1.06 0l7.5 7.5a.75.75 0 1 1-1.06 1.06L12 9.31l-6.97 6.97a.75.75 0 0 1-1.06-1.06l7.5-7.5Z"
              clip-rule="evenodd"
            />
          </svg>
          <svg
            v-else
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            class="size-6"
          >
            <path
              fill-rule="evenodd"
              d="M12.53 16.28a.75.75 0 0 1-1.06 0l-7.5-7.5a.75.75 0 0 1 1.06-1.06L12 14.69l6.97-6.97a.75.75 0 1 1 1.06 1.06l-7.5 7.5Z"
              clip-rule="evenodd"
            />
          </svg>
        </button>

        <div v-if="isOpen" class="flex w-full flex-wrap items-start gap-6">
          <!-- Privacy Container -->
          <div class="flex w-fit items-start gap-4 rounded-lg border border-white/10 p-2">
            <div class="flex items-center gap-1">
              <!-- Privacy icon -->
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="lucide lucide-shield-check-icon lucide-shield-check h-5 w-5"
              >
                <path
                  d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"
                />
                <path d="m9 12 2 2 4-4" />
              </svg>
              <span class="text-sm font-medium">Consent</span>
            </div>
            <div class="flex flex-col items-start">
              <input v-model="autoApprove" type="checkbox" class="toggle toggle-primary" />
              <div
                class="tooltip"
                data-tip="Allow the system to automatically approve and send sensitive data."
              >
                <span class="label-text mt-1 text-xs">Auto Approve</span>
              </div>
            </div>
          </div>

          <!-- SQL Options Container -->
          <div class="flex w-fit items-start gap-4 rounded-lg border border-white/10 p-2">
            <div class="flex items-center gap-1">
              <!-- SQL icon -->
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="lucide lucide-database-icon lucide-database h-5 w-5"
              >
                <ellipse cx="12" cy="5" rx="9" ry="3" />
                <path d="M3 5V19A9 3 0 0 0 21 19V5" />
                <path d="M3 12A9 3 0 0 0 21 12" />
              </svg>
              <span class="text-sm font-medium">SQL</span>
            </div>
            <div class="flex flex-row items-start">
              <div class="flex flex-col items-start">
                <input
                  id="top_k"
                  v-model.number="topK"
                  type="range"
                  min="0"
                  max="500"
                  step="10"
                  class="range"
                  style="width: 250px"
                />
                <div class="mt-1 flex items-center gap-2 text-xs">
                  <label for="top_k">Limit Results:</label>
                  <input
                    v-model.number="topK"
                    type="number"
                    min="0"
                    max="500"
                    class="input input-xs w-min focus:outline-none focus:ring-0"
                  />
                </div>
              </div>

              <!-- Optional: Add SQL Auto-Approve toggle here -->
              <div class="ml-4 flex flex-col items-start">
                <input v-model="autoSQL" type="checkbox" class="toggle toggle-primary" />
                <div
                  class="tooltip"
                  data-tip="Automatically approve and run generated SQL queries without manual review."
                >
                  <span class="label-text mt-1 text-xs">Auto SQL</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Answer Style Container -->
          <div class="flex w-fit items-start gap-4 rounded-lg border border-white/10 p-2">
            <div class="flex items-center gap-1">
              <!-- Icon -->
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="lucide lucide-message-square-text h-5 w-5"
              >
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                <line x1="9" y1="9" x2="15" y2="9" />
                <line x1="9" y1="13" x2="13" y2="13" />
              </svg>
              <span class="text-sm font-medium">Response Style</span>
            </div>
            <div class="flex flex-row gap-4">
              <!-- Granularity -->
              <div class="form-control">
                <div class="flex flex-col">
                  <div class="join">
                    <div class="tooltip" data-tip="Minimally detailed">
                      <label
                        class="btn join-item btn-sm px-3 text-xs"
                        :class="[
                          answerDetail === 'low'
                            ? 'btn-primary'
                            : 'btn-outline border border-white/20 hover:bg-transparent hover:text-inherit'
                        ]"
                      >
                        <input v-model="answerDetail" type="radio" value="low" class="hidden" />
                        Low
                      </label>
                    </div>
                    <div class="tooltip" data-tip="System decides">
                      <label
                        class="btn join-item btn-sm px-3 text-xs"
                        :class="[
                          answerDetail === 'auto'
                            ? 'btn-primary'
                            : 'btn-outline border border-white/20 hover:bg-transparent hover:text-inherit'
                        ]"
                      >
                        <input v-model="answerDetail" type="radio" value="auto" class="hidden" />
                        Auto
                      </label>
                    </div>
                    <div class="tooltip" data-tip="Highly detailed">
                      <label
                        class="btn join-item btn-sm px-3 text-xs"
                        :class="[
                          answerDetail === 'high'
                            ? 'btn-primary'
                            : 'btn-outline border border-white/20 hover:bg-transparent hover:text-inherit'
                        ]"
                      >
                        <input v-model="answerDetail" type="radio" value="high" class="hidden" />
                        High
                      </label>
                    </div>
                  </div>
                  <span class="label-text mt-1 self-center text-xs">Granularity</span>
                </div>
              </div>

              <!-- Visualization -->
              <div class="form-control">
                <div class="flex flex-col">
                  <div class="join">
                    <div class="tooltip" data-tip="No visualizations">
                      <label
                        class="btn join-item btn-sm px-3 text-xs"
                        :class="[
                          wantsPlot === 'no'
                            ? 'btn-primary'
                            : 'btn-outline border border-white/20 hover:bg-transparent hover:text-inherit'
                        ]"
                      >
                        <input v-model="wantsPlot" type="radio" value="no" class="hidden" />
                        Never
                      </label>
                    </div>
                    <div class="tooltip" data-tip="System decides">
                      <label
                        class="btn join-item btn-sm px-3 text-xs"
                        :class="[
                          wantsPlot === 'auto'
                            ? 'btn-primary'
                            : 'btn-outline border border-white/20 hover:bg-transparent hover:text-inherit'
                        ]"
                      >
                        <input v-model="wantsPlot" type="radio" value="auto" class="hidden" />
                        Auto
                      </label>
                    </div>
                    <div class="tooltip" data-tip="Always create visualizations">
                      <label
                        class="btn join-item btn-sm px-3 text-xs"
                        :class="[
                          wantsPlot === 'yes'
                            ? 'btn-primary'
                            : 'btn-outline border border-white/20 hover:bg-transparent hover:text-inherit'
                        ]"
                      >
                        <input v-model="wantsPlot" type="radio" value="yes" class="hidden" />
                        Always
                      </label>
                    </div>
                  </div>
                  <span class="label-text mt-1 self-center text-xs">Visualizations</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </form>

    <!-- Plot Modal -->
    <dialog v-if="showImageModal" class="modal modal-open" @click.self="closeImageModal">
      <div class="modal-box w-11/12 max-w-5xl p-4">
        <img
          v-if="enlargedImage"
          :src="enlargedImage"
          alt="Enlarged plot"
          class="max-h-[80vh] w-full rounded-lg object-contain"
        />
        <div class="modal-action">
          <button class="btn btn-outline btn-sm" @click="closeImageModal">Close</button>
        </div>
      </div>
    </dialog>

    <!-- Info Modal -->
    <dialog ref="metaDialog" class="modal">
      <div class="modal-box flex h-[90vh] w-[90vw] max-w-[80%] flex-col p-0">
        <!-- Sticky Header -->
        <div class="sticky top-0 z-10 flex items-start justify-between px-6 py-4">
          <h3 class="text-lg font-bold">Details</h3>
          <button class="btn btn-circle btn-ghost btn-sm" title="Close" @click="closeMetaModal">
            ✕
          </button>
        </div>

        <div v-if="currentMeta" class="flex-1 space-y-4 overflow-y-auto px-6 py-4">
          <div>
            <p class="font-semibold">Tables:</p>
            <p class="text-sm">{{ currentMeta.tables?.join(', ') ?? '' }}</p>
          </div>
          <div>
            <p class="font-semibold">Activities:</p>
            <p class="text-sm">{{ currentMeta.activities?.join(', ') ?? '' }}</p>
          </div>
          <div>
            <p class="font-semibold">Query:</p>
            <pre class="overflow-x-auto whitespace-pre-wrap rounded bg-base-200 p-2 text-sm"
              >{{ cleanQuery(currentMeta.query) ?? '' }}
</pre
            >
          </div>
          <div v-if="resultData.length > 0" class="inline-block max-w-[100%]">
            <p class="font-semibold">Result:</p>
            <DataTable
              :value="resultData"
              scrollable
              scroll-height="400px"
              striped-rows
              removable-sort
              :filters="filters"
              :global-filter-fields="resultColumns.map((c) => c.field)"
              class="!w-auto pt-1"
            >
              <template #header>
                <div
                  class="custom-datatable-header flex items-center justify-between gap-4 p-2 pr-0"
                >
                  <span class="ml-auto">
                    <input
                      v-model="globalSearch"
                      type="text"
                      placeholder="Search for values..."
                      class="input input-sm input-bordered w-full max-w-xs"
                    />
                  </span>
                </div>
              </template>

              <Column header="#" :style="{ whiteSpace: 'nowrap', width: '0.1%' }">
                <template #body="{ index }">
                  {{ index + 1 }}
                </template>
              </Column>
              <Column
                v-for="col in resultColumns"
                :key="col.field"
                :field="col.field"
                :header="col.header"
                sortable
                :style="{ whiteSpace: 'nowrap', width: '1%' }"
              >
                <template #body="slotProps">
                  <span
                    :title="slotProps.data[col.field]"
                    style="
                      display: inline-block;
                      max-width: 200px;
                      overflow: hidden;
                      text-overflow: ellipsis;
                      white-space: nowrap;
                      vertical-align: bottom;
                    "
                  >
                    {{ slotProps.data[col.field] }}
                  </span>
                </template>
              </Column>
            </DataTable>
          </div>
        </div>
      </div>
    </dialog>
  </div>
</template>

<style scoped lang="less">
.chat-bubble h1,
.chat-bubble h2,
.chat-bubble h3 {
  font-weight: bold;
  margin: 1rem 0 0.5rem;
  font-size: 1.125rem;
}

.chat-bubble p {
  margin-bottom: 0.5rem;
  line-height: 1.5;
}

.chat-bubble ul {
  padding-left: 1.2rem;
  list-style: disc;
  margin-bottom: 0.5rem;
}

::v-deep(.katex .katex-html) {
  display: none !important;
}

::v-deep(.p-datatable td),
::v-deep(.p-datatable tr),
::v-deep(.p-datatable tr),
::v-deep(.p-datatable th) {
  border-color: var(--bc); /* Example: Tailwind gray-300 */
}
::v-deep(.p-datatable-header) {
  padding-bottom: 0;
  border-bottom: var(--bc); /* Tailwind gray-300 or your custom color */
}

input[type='number']::-webkit-outer-spin-button,
input[type='number']::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

input[type='number'] {
  -moz-appearance: textfield;
}
</style>

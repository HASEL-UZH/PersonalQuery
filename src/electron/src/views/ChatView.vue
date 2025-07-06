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
import typedIpcRenderer from '../utils/typedIpcRenderer';
import VueDatePicker from '@vuepic/vue-datepicker';
import '@vuepic/vue-datepicker/dist/main.css';
import { data } from 'autoprefixer';

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

interface Feedback {
  messageId: string;
  dataCorrect: 'yes' | 'no' | null;
  questionAnswered: 'yes' | 'no' | null;
  comment: string;
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
  plotBase64: '',
  fbSubmitted: false
});
const bottomAnchor = ref<HTMLElement | null>(null);
const autoApprove = ref(false);
const autoSQL = ref(true);
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
  if (wsMessages.value.length === 0) {
    greetingDisplayed.value = true;
    fullGreeting.value = mainGreetings[Math.floor(Math.random() * mainGreetings.length)];
    randomSuggestedQuestions.value = suggestedQuestions.sort(() => Math.random() - 0.5).slice(0, 3);
    simulateGreetingStream(fullGreeting.value);
  }
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
      id: msg.id,
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
      data: JSON.parse(JSON.stringify(interruptionMeta.value.data)),
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

const feedbackStates = ref<Record<string, Feedback>>({});
const submittedFeedbacks = ref<Set<string>>(new Set());

function getFeedbackState(messageId: string): Feedback {
  if (!feedbackStates.value[messageId]) {
    feedbackStates.value[messageId] = {
      messageId,
      dataCorrect: null,
      questionAnswered: null,
      comment: ''
    };
  }
  return feedbackStates.value[messageId];
}

const submitFeedback = async (chatId: string, feedback: Feedback) => {
  try {
    const res = await fetch('http://localhost:8000/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chatId,
        message_id: feedback.messageId,
        data_correct: feedback.dataCorrect === 'yes' ? 1 : 0,
        question_answered: feedback.questionAnswered === 'yes' ? 1 : 0,
        comment: feedback.comment || ''
      })
    });

    const result = await res.json();
    console.log('Feedback submitted:', result);
    console.log('Adding msg to submitted feedbacks:', feedback.messageId);
    submittedFeedbacks.value.add(feedback.messageId);
  } catch (err) {
    console.error('Failed to send feedback:', err);
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
      } else if (reviewMeta.value) {
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
  console.log('resetting:', reviewMeta.value?.query);
  console.log('with:', interruptionMeta.value?.query);
  if (reviewMeta.value) {
    reviewMeta.value.query = interruptionMeta.value!.query;
  }
}
function resetData() {
  console.log('resetting:', reviewMeta.value?.data);
  console.log('with:', interruptionMeta.value?.data);
  if (reviewMeta.value) {
    reviewMeta.value.data = interruptionMeta.value!.data;
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
      console.log('IM IN HEREEEE');
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

const selectedQuestion = ref<string | null>(null);
const showDatePicker = ref(false);
const selectedDate = ref<Date | [Date, Date] | null>(null);
const coverageScores = ref<Record<string, number>>({});

const suggestedQuestions = [
  'How many times do I switch between apps?',
  'How much time do I spend coding?',
  'How much time do I spend in the browser?',
  'Which activities do I spend the most time on?',
  'On which day of the week do I code the most?',
  'Which activities are associated with high mouse activity?',
  'How does my perceived productivity compare across different activities?',
  'How often do I switch from work to non-work activities?',
  'How has my productivity changed?',
  'Which activities have the longest total focus time?',
  'What patterns exist in my typing activity?',
  'Which applications do I type in the most?',
  'Which activities generate the most user input?',
  'How does my input relate to my self-perceived productivity ratings?',
  'How does time spent on activities relate to feeling productive?'
];

const randomSuggestedQuestions = ref<string[]>([]);

function onSelectQuestion(q: string) {
  selectedQuestion.value = q;
  showDatePicker.value = true;
}

function getDayClass(date: Date) {
  const iso = date.toISOString().slice(0, 10);
  const score = coverageScores.value[iso] || 0;
  if (score >= 50) return 'high-activity';
  if (score >= 20) return 'medium-activity';
  if (score > 0) return 'low-activity';
  return '';
}

function onConfirmSelection() {
  let dateString = '';

  if (Array.isArray(selectedDate.value)) {
    const [start, end] = selectedDate.value;
    if (start && end) {
      dateString = `${formatDate(start)} to ${formatDate(end)}`;
    } else if (start) {
      dateString = formatDate(start);
    } else {
      dateString = 'No date selected';
    }
  } else if (selectedDate.value instanceof Date) {
    dateString = formatDate(selectedDate.value);
  } else {
    dateString = 'No date selected';
  }

  input.value = `${selectedQuestion.value}, ${dateString}`;
  showDatePicker.value = false;
}

function formatDate(d: unknown): string {
  if (d instanceof Date) {
    const parts = d.toDateString().split(' ');
    return `${parts[1]} ${parts[2]} ${parts[3]}`;
  }
  return 'Invalid date';
}

onMounted(async () => {
  const data = await typedIpcRenderer.invoke('getDataCoverageScore');
  coverageScores.value = Object.fromEntries(data.map((d) => [d.day, d.score]));
  console.log('coverageScores loaded:', coverageScores.value);
});
</script>

<template>
  <div class="flex h-screen flex-col bg-base-100 p-4">
    <div class="scrollable flex flex-1 flex-col space-y-4 overflow-y-auto pr-1">
      <div
        v-if="greetingDisplayed"
        class="flex flex-grow items-center justify-center px-4 text-center"
      >
        <div class="max-w-4xl text-3xl font-semibold leading-relaxed text-base-content">
          <span v-html="greetingChunks.join(' ')" />
        </div>
      </div>
      <div
        v-if="greetingDisplayed"
        class="flex flex-col items-center justify-center px-4 text-center"
      >
        <h3 class="mb-4 text-lg font-semibold">Quick Start</h3>
        <ul class="flex flex-wrap gap-2">
          <li v-for="q in randomSuggestedQuestions" :key="q">
            <button
              :key="q"
              :class="[
                'btn',
                'w-auto',
                'px-3',
                'text-sm',
                selectedQuestion === q ? 'btn-primary' : 'btn-outline'
              ]"
              @click="onSelectQuestion(q)"
            >
              {{ q }}
            </button>
          </li>
        </ul>
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
        <!-- Error message -->
        <div
          v-else-if="msg.role === 'system' && msg.error"
          class="mb-4 flex w-full justify-center px-4"
        >
          <div
            class="prose mx-auto w-full max-w-4xl rounded-lg border border-white/10 px-6 py-5 text-left leading-tight text-base-content text-error"
            v-html="msg.content"
          />
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

            <div
              v-if="msg.meta && msg.id"
              class="mt-4 flex flex-col border-t border-white/10 pt-4 text-sm"
            >
              <div
                v-if="submittedFeedbacks.has(msg.id) || msg.meta.fbSubmitted"
                class="mt-2 font-semibold text-success"
              >
                Feedback saved!
              </div>
              <div v-else class="flex flex-row gap-4">
                <div>
                  <span class="font-semibold">Was the correct data retrieved?</span>
                  <div class="mt-1 flex gap-2">
                    <button
                      class="btn btn-xs"
                      :class="{ 'btn-success': getFeedbackState(msg.id).dataCorrect === 'yes' }"
                      @click="getFeedbackState(msg.id).dataCorrect = 'yes'"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 16 16"
                        fill="currentColor"
                        class="size-4"
                      >
                        <path
                          d="M2.09 15a1 1 0 0 0 1-1V8a1 1 0 1 0-2 0v6a1 1 0 0 0 1 1ZM5.765 13H4.09V8c.663 0 1.218-.466 1.556-1.037a4.02 4.02 0 0 1 1.358-1.377c.478-.292.907-.706.989-1.26V4.32a9.03 9.03 0 0 0 0-2.642c-.028-.194.048-.394.224-.479A2 2 0 0 1 11.09 3c0 .812-.08 1.605-.235 2.371a.521.521 0 0 0 .502.629h1.733c1.104 0 2.01.898 1.901 1.997a19.831 19.831 0 0 1-1.081 4.788c-.27.747-.998 1.215-1.793 1.215H9.414c-.215 0-.428-.035-.632-.103l-2.384-.794A2.002 2.002 0 0 0 5.765 13Z"
                        />
                      </svg>
                    </button>
                    <button
                      class="btn btn-xs"
                      :class="{ 'btn-error': getFeedbackState(msg.id).dataCorrect === 'no' }"
                      @click="getFeedbackState(msg.id).dataCorrect = 'no'"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 16 16"
                        fill="currentColor"
                        class="size-4"
                      >
                        <path
                          d="M10.325 3H12v5c-.663 0-1.219.466-1.557 1.037a4.02 4.02 0 0 1-1.357 1.377c-.478.292-.907.706-.989 1.26v.005a9.031 9.031 0 0 0 0 2.642c.028.194-.048.394-.224.479A2 2 0 0 1 5 13c0-.812.08-1.605.234-2.371a.521.521 0 0 0-.5-.629H3C1.896 10 .99 9.102 1.1 8.003A19.827 19.827 0 0 1 2.18 3.215C2.45 2.469 3.178 2 3.973 2h2.703a2 2 0 0 1 .632.103l2.384.794a2 2 0 0 0 .633.103ZM14 2a1 1 0 0 0-1 1v6a1 1 0 1 0 2 0V3a1 1 0 0 0-1-1Z"
                        />
                      </svg>
                    </button>
                  </div>
                </div>

                <div>
                  <span class="font-semibold">Did this answer your question?</span>
                  <div class="mt-1 flex gap-2">
                    <button
                      class="btn btn-xs"
                      :class="{
                        'btn-success': getFeedbackState(msg.id).questionAnswered === 'yes'
                      }"
                      @click="getFeedbackState(msg.id).questionAnswered = 'yes'"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 16 16"
                        fill="currentColor"
                        class="size-4"
                      >
                        <path
                          d="M2.09 15a1 1 0 0 0 1-1V8a1 1 0 1 0-2 0v6a1 1 0 0 0 1 1ZM5.765 13H4.09V8c.663 0 1.218-.466 1.556-1.037a4.02 4.02 0 0 1 1.358-1.377c.478-.292.907-.706.989-1.26V4.32a9.03 9.03 0 0 0 0-2.642c-.028-.194.048-.394.224-.479A2 2 0 0 1 11.09 3c0 .812-.08 1.605-.235 2.371a.521.521 0 0 0 .502.629h1.733c1.104 0 2.01.898 1.901 1.997a19.831 19.831 0 0 1-1.081 4.788c-.27.747-.998 1.215-1.793 1.215H9.414c-.215 0-.428-.035-.632-.103l-2.384-.794A2.002 2.002 0 0 0 5.765 13Z"
                        />
                      </svg>
                    </button>
                    <button
                      class="btn btn-xs"
                      :class="{ 'btn-error': getFeedbackState(msg.id).questionAnswered === 'no' }"
                      @click="getFeedbackState(msg.id).questionAnswered = 'no'"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 16 16"
                        fill="currentColor"
                        class="size-4"
                      >
                        <path
                          d="M10.325 3H12v5c-.663 0-1.219.466-1.557 1.037a4.02 4.02 0 0 1-1.357 1.377c-.478.292-.907.706-.989 1.26v.005a9.031 9.031 0 0 0 0 2.642c.028.194-.048.394-.224.479A2 2 0 0 1 5 13c0-.812.08-1.605.234-2.371a.521.521 0 0 0-.5-.629H3C1.896 10 .99 9.102 1.1 8.003A19.827 19.827 0 0 1 2.18 3.215C2.45 2.469 3.178 2 3.973 2h2.703a2 2 0 0 1 .632.103l2.384.794a2 2 0 0 0 .633.103ZM14 2a1 1 0 0 0-1 1v6a1 1 0 1 0 2 0V3a1 1 0 0 0-1-1Z"
                        />
                      </svg>
                    </button>
                  </div>
                </div>

                <div>
                  <textarea
                    v-model="getFeedbackState(msg.id).comment"
                    class="textarea textarea-bordered mt-2 w-full"
                    placeholder="Additional comments (optional)"
                    rows="2"
                  ></textarea>
                </div>

                <button
                  class="btn btn-primary btn-sm mt-2 self-start"
                  :disabled="
                    !getFeedbackState(msg.id).dataCorrect ||
                    !getFeedbackState(msg.id).questionAnswered
                  "
                  @click="submitFeedback(chatId, getFeedbackState(msg.id))"
                >
                  Submit Feedback
                </button>
              </div>
            </div>

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
            :query="reviewMeta?.query ?? ''"
            :original-query="interruptionMeta?.query ?? ''"
            :result="reviewMeta?.data"
            :columns="approvalColumns"
            :filters="filters"
            :loading-query="loadingQuery"
            :loading-result="loadingResult"
            :sql-error="sqlError ?? undefined"
            @reset-query="resetQuery"
            @execute-query="executeQuery"
            @correct-query="handleLLMCorrection"
            @proceed="handleProceedAfterSQL"
          />
          <ApprovalRequestBox
            v-if="needsApproval && !needsSQLReview && index === wsMessages.length - 1"
            :data="reviewMeta?.data ?? []"
            @approve="respondToApproval"
            @cell-edit-complete="onCellEditComplete"
            @reset="resetData"
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

    <dialog
      v-if="showDatePicker"
      class="modal modal-open"
      @click.self="() => (showDatePicker = false)"
    >
      <div
        class="modal-box flex flex-col justify-between p-6"
        style="height: 600px; max-width: 32rem"
      >
        <div>
          <!-- Modal Title -->
          <h2 class="mb-2 text-lg font-semibold">Select a Time Scope for the question:</h2>
          <p class="mb-2">'{{ selectedQuestion }}'</p>

          <div class="mt-6">
            <label class="mb-1 block text-sm font-semibold"> Data Richness </label>
            <!-- Gradient bar -->
            <div
              class="h-4 w-full rounded"
              style="background: linear-gradient(to right, white, #22c55e)"
            ></div>
            <!-- Labels -->
            <div class="mt-1 flex justify-between text-xs text-gray-600">
              <span>No Data</span>
              <span>High Coverage</span>
            </div>
          </div>

          <!-- Date Picker -->
          <VueDatePicker
            v-if="showDatePicker"
            v-model="selectedDate"
            :day-class="getDayClass"
            :enable-time-picker="false"
            range
            class="mb-6 mt-2 w-full flex-grow"
          />
        </div>

        <!-- Confirm Button fixed at the bottom -->
        <div class="mt-4 text-right">
          <button :disabled="!selectedDate" class="btn btn-primary" @click="onConfirmSelection">
            Confirm
          </button>
        </div>
      </div>
    </dialog>

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
/* Heatmap backgrounds (always apply) */
:deep(.dp__cell_inner.low-activity) {
  background-color: rgba(34, 197, 94, 0.2);
}
:deep(.dp__cell_inner.medium-activity) {
  background-color: rgba(34, 197, 94, 0.5);
  color: white;
}
:deep(.dp__cell_inner.high-activity) {
  background-color: rgba(34, 197, 94, 0.9);
  color: white;
}

/* Selection styles when NO heatmap class is present */
:deep(.dp__cell_inner.dp__active_date:not(.low-activity):not(.medium-activity):not(.high-activity)),
:deep(.dp__cell_inner.dp__range_start:not(.low-activity):not(.medium-activity):not(.high-activity)),
:deep(.dp__cell_inner.dp__range_end:not(.low-activity):not(.medium-activity):not(.high-activity)) {
  background-color: transparent !important;
}

/* Border always applied on selection, regardless of heatmap */
:deep(.dp__cell_inner.dp__active_date),
:deep(.dp__cell_inner.dp__range_start),
:deep(.dp__cell_inner.dp__range_end) {
  border: 2px solid #4b99ff;
  border-radius: 4px;
  color: inherit;
}
</style>

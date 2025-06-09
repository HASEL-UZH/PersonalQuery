<script setup lang="ts">
import { ref, onMounted, watch, nextTick, computed } from 'vue';
import { useRoute } from 'vue-router';
import { marked } from 'marked';
import { Meta, Message, useChatWebSocket } from '../utils/WebSocketHandler';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import markedKatex from 'marked-katex-extension';
import { FilterMatchMode } from '@primevue/core/api';
import InputText from 'primevue/inputtext';

const route = useRoute();
const chatId = ref(route.params.chatId as string);
const input = ref('');

const {
  connect,
  send,
  messages: wsMessages,
  steps,
  onFinalResponse,
  approvalRequest
} = useChatWebSocket();

interface Approval {
  chat_id: string;
  data: Record<string, any>[];
}

marked.use(markedKatex({ throwOnError: false }));

function formatMessage(message: string) {
  console.log(message);
  return marked.parse(message);
}

const filters = ref({
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
  result: []
});
const bottomAnchor = ref<HTMLElement | null>(null);
const autoApprove = ref(false);
const topK = ref(150);
const STORAGE_KEY = 'chat_settings';

function openMetaModal(meta: Meta) {
  currentMeta.value = meta;
  metaDialog.value?.showModal();
}

function closeMetaModal() {
  metaDialog.value?.close();
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
}

onMounted(() => {
  connect();
  fetchChatHistory();
});

onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      if (typeof parsed.autoApprove === 'boolean') autoApprove.value = parsed.autoApprove;
      if (typeof parsed.topK === 'number') topK.value = parsed.topK;
    } catch (e) {
      console.warn('Invalid chat_settings in localStorage');
    }
  }
});

watch([autoApprove, topK], () => {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      autoApprove: autoApprove.value,
      topK: topK.value
    })
  );
});

const needsApproval = ref(false);
const approvalData = ref<Approval | null>(null);

watch(approvalRequest, () => {
  if (approvalRequest.value) {
    needsApproval.value = true;
    approvalData.value = approvalRequest.value;
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
  const userMessage = input.value;
  input.value = '';
  send(userMessage, chatId.value, {
    top_k: topK.value,
    autoApprove: autoApprove.value
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

const sendApproval = async (chatId: string, approval: boolean) => {
  try {
    const res = await fetch('http://localhost:8000/approval', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, approval })
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
  if (approvalData.value?.chat_id) {
    sendApproval(approvalData.value.chat_id, approval);
  }
  needsApproval.value = false;
  approvalData.value = null;
  if (approval) {
    steps.value = ['generate answer'];
  }
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
  const firstRow = approvalData.value?.data?.[0];
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
</script>

<template>
  <div class="flex h-screen flex-col bg-base-100 p-4">
    <div class="scrollable flex-1 space-y-4 overflow-y-auto pr-1">
      <div v-for="(msg, index) in wsMessages" :key="index" class="w-full">
        <!-- User message -->
        <div v-if="msg.role === 'human'" class="chat chat-end mb-4">
          <div class="chat-bubble chat-bubble-primary max-w-[80%] px-4 py-2 text-base">
            <div v-html="formatMessage(msg.content)" class="prose prose-base text-black" />
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
            <div v-html="formatMessage(msg.content)" />
            <button
              v-if="msg.meta"
              class="btn btn-circle btn-ghost btn-xs float-right mt-2 text-info"
              @click="openMetaModal(msg.meta)"
              title="View details"
            >
              ℹ️
            </button>
          </div>
        </div>
        <!-- Approval Request -->
        <div
          v-if="needsApproval && index === wsMessages.length - 1"
          class="mb-4 flex w-full justify-center px-4"
        >
          <div
            class="prose prose-base mx-auto w-full max-w-4xl rounded-lg border border-warning bg-warning/10 px-6 py-5 text-left text-base-content"
          >
            <p class="mb-2 font-semibold">
              Do you approve to send this to OpenAI for further processing?
            </p>

            <div
              v-if="approvalData && approvalData.data && approvalData.data.length"
              class="overflow-y-auto rounded bg-base-200 p-4 text-sm"
            >
              <div>
                <DataTable
                  :value="resultData"
                  scrollable
                  scrollHeight="400px"
                  striped-rows
                  removableSort
                  :filters="filters"
                  :globalFilterFields="resultColumns.map((c) => c.field)"
                  class="!w-auto pt-0"
                  edit-mode="cell"
                  @cell-edit-complete="onCellEditComplete"
                  :pt="{
                    table: { style: 'min-width: 50rem' },
                    column: {
                      bodycell: ({ state }) => ({
                        class: [{ '!py-0': state['d_editing'] }]
                      })
                    }
                  }"
                >
                  <template #header>
                    <div
                      class="custom-datatable-header flex items-center justify-between gap-4 pr-0"
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
                    :editable="true"
                  >
                    <template #editor="{ data, field }">
                      <InputText v-model="data[field]" :autofocus="true" fluid />
                    </template>
                  </Column>
                </DataTable>
              </div>
            </div>

            <div v-else class="p-4 text-sm text-gray-500">No preview available.</div>

            <div class="mt-4 flex justify-end gap-4">
              <button class="btn btn-outline btn-sm" @click="respondToApproval(false)">No</button>
              <button class="btn btn-primary btn-sm" @click="respondToApproval(true)">Yes</button>
            </div>
          </div>
        </div>
      </div>

      <div ref="bottomAnchor"></div>
    </div>

    <form @submit.prevent="sendMessage" class="w-full">
      <div class="space-y-4 rounded border border-base-300 bg-base-200 p-4">
        <input
          v-model="input"
          class="input input-bordered w-full"
          placeholder="Type your message..."
        />

        <div class="flex w-full flex-wrap items-start gap-6">
          <div class="flex items-start gap-6">
            <div class="flex flex-col items-start">
              <input type="checkbox" class="toggle toggle-primary" v-model="autoApprove" />
              <span class="label-text mt-1 text-xs">Auto Approve</span>
            </div>

            <div class="flex flex-col items-start">
              <input
                id="top_k"
                type="range"
                min="0"
                max="1500"
                step="50"
                v-model.number="topK"
                class="range"
                style="width: 250px"
              />
              <span class="label-text mt-1 text-xs">Limit Results to: {{ topK }}</span>
            </div>
          </div>

          <div class="ml-auto self-start">
            <button class="btn btn-primary" type="submit">Send</button>
          </div>
        </div>
      </div>
    </form>

    <!-- Info Modal -->
    <dialog ref="metaDialog" class="modal">
      <div class="modal-box h-[90vh] w-[90vw] max-w-none">
        <div class="mb-4 flex items-start justify-between">
          <h3 class="text-lg font-bold">Details</h3>
          <button class="btn btn-circle btn-ghost btn-sm" @click="closeMetaModal" title="Close">
            ✕
          </button>
        </div>

        <div v-if="currentMeta" class="space-y-4">
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
          <div v-if="resultData.length > 0" class="inline-block min-w-[500px]">
            <p class="font-semibold">Result:</p>
            <DataTable
              :value="resultData"
              scrollable
              scrollHeight="400px"
              striped-rows
              removableSort
              :filters="filters"
              :globalFilterFields="resultColumns.map((c) => c.field)"
              class="!w-auto min-w-max pt-1"
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
                :style="{ whiteSpace: 'nowrap', padding: '0.75rem 1rem', width: '1%' }"
              />
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
</style>

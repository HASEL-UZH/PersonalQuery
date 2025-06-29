<script setup lang="ts">
import { ref, watch, type PropType } from 'vue';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';

interface ColumnDef {
  field: string;
  header: string;
}

const props = defineProps({
  query: { type: String, required: true },
  originalQuery: { type: String, required: true },
  result: { type: Array as PropType<Record<string, any>[]>, default: () => [] },
  columns: {
    type: Array as PropType<ColumnDef[]>,
    default: () => []
  },
  filters: { type: Object as PropType<Record<string, any>>, default: () => ({}) },
  loadingQuery: { type: Boolean, default: false },
  loadingResult: { type: Boolean, default: false },
  sqlError: { type: String, required: false, default: null }
});

const emits = defineEmits(['reset-query', 'execute-query', 'correct-query', 'proceed']);

const editableQuery = ref(props.query);
const correctionPrompt = ref('');
const globalSearch = ref('');

console.log('editableQuery:', editableQuery.value);

watch(
  () => props.query,
  (newQuery) => {
    editableQuery.value = newQuery;
  }
);

function emitCorrection() {
  emits('correct-query', correctionPrompt.value, editableQuery.value);
  correctionPrompt.value = '';
}

function handleExecute() {
  emits('execute-query', editableQuery.value);
}

function tableBodyCell({ state }: { state: Record<string, any> }) {
  return {
    class: [{ '!py-0': state['d_editing'] }]
  };
}
</script>

<template>
  <div class="flex w-full flex-col gap-6 px-4 md:flex-row">
    <!-- Left Box: SQL Query -->
    <div class="flex flex-1 flex-col gap-2 rounded-xl bg-base-200 p-6">
      <h2 class="text-xl font-semibold">SQL Query</h2>

      <div v-if="loadingQuery">
        <p class="flex items-center gap-2">
          <span class="loading loading-spinner loading-sm"></span>
          generating new query...
        </p>
      </div>

      <div v-else>
        <textarea
          v-model="editableQuery"
          rows="16"
          class="textarea textarea-bordered w-full font-mono"
        />
      </div>

      <div class="flex gap-4">
        <button
          class="btn btn-outline btn-sm tooltip"
          @click="() => (editableQuery = originalQuery)"
          data-tip="Reset Query"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.5"
            stroke="currentColor"
            class="size-5"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"
            />
          </svg>
        </button>

        <button class="btn btn-primary btn-sm tooltip" @click="handleExecute" data-tip="Execute">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.5"
            stroke="currentColor"
            class="size-6"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M3 8.689c0-.864.933-1.406 1.683-.977l7.108 4.061a1.125 1.125 0 0 1 0 1.954l-7.108 4.061A1.125 1.125 0 0 1 3 16.811V8.69ZM12.75 8.689c0-.864.933-1.406 1.683-.977l7.108 4.061a1.125 1.125 0 0 1 0 1.954l-7.108 4.061a1.125 1.125 0 0 1-1.683-.977V8.69Z"
            />
          </svg>
        </button>
      </div>

      <!-- Spacer to push correction section to bottom (optional for layout control) -->
      <div class="flex-1" />

      <!-- Correction Section -->
      <div class="mt-4">
        <h3 class="mb-1 text-sm text-gray-500">
          Want to improve or fix the query? Describe what you’d like to change:
        </h3>
        <div class="flex w-full">
          <input
            v-model="correctionPrompt"
            type="text"
            placeholder="e.g. remove sessions with zero duration"
            class="input input-sm input-bordered w-full rounded-r-none focus:outline-none focus:ring-0"
            @keydown.enter.prevent="emitCorrection"
          />
          <button class="btn btn-primary btn-sm rounded-l-none border" @click="emitCorrection">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke-width="1.5"
              stroke="currentColor"
              class="size-5"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Right Box: Result -->
    <div class="flex max-w-4xl flex-1 flex-col gap-4 rounded-xl bg-base-200 p-6">
      <h2 class="text-xl font-semibold">Current Data</h2>

      <div class="min-h-[12rem] rounded bg-base-100 p-4 text-sm">
        <p v-if="loadingResult" class="flex items-center gap-2">
          <span class="loading loading-spinner loading-sm"></span>
          executing query...
        </p>
        <p
          v-else-if="sqlError"
          class="rounded-md border border-error-content bg-error p-4 text-sm text-error-content"
        >
          <strong class="mb-1 block font-medium">SQL Error:</strong>
          {{ sqlError }}
        </p>
        <div v-else-if="result && result.length">
          <DataTable
            :value="result"
            scrollable
            scrollHeight="500px"
            striped-rows
            removableSort
            :filters="filters"
            :globalFilterFields="columns.map((c) => c.field)"
            class="!w-auto pt-0"
            edit-mode="cell"
            :pt="{
              table: { style: 'min-width: 50rem' },
              column: {
                bodycell: tableBodyCell
              }
            }"
          >
            <template #header>
              <div
                class="custom-datatable-header mb-4 flex items-center justify-between gap-4 pr-0"
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
              v-for="col in columns"
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
        <div v-else class="text-center text-gray-500">No data yet</div>
      </div>

      <div class="mt-auto flex justify-end">
        <button class="btn btn-primary btn-block text-lg" @click="$emit('proceed')">
          Accept Query
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="less"></style>

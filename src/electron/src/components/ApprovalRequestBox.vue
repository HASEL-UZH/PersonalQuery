<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { FilterMatchMode } from '@primevue/core/api';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import InputText from 'primevue/inputtext';

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  }
});

const globalSearch = ref('');
const searchTerms = ref('');

function handleObfuscate() {
  const terms = searchTerms.value
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);

  if (!terms.length) return;

  props.data.forEach((row) => {
    for (const key in row) {
      const cell = row[key];
      if (typeof cell === 'string') {
        let obfuscated = cell;
        terms.forEach((term) => {
          const mask = '*'.repeat(term.length);
          obfuscated = obfuscated.split(term).join(mask);
        });
        row[key] = obfuscated;
      }
    }
  });

  // Clear input
  searchTerms.value = '';
}

watch(globalSearch, (newVal) => {
  filters.value.global.value = newVal;
});

const filters = ref<{ global: { value: string | null; matchMode: string } }>({
  global: { value: null, matchMode: FilterMatchMode.CONTAINS }
});

function formatHeader(key: string): string {
  return key.replace(/([A-Z])/g, ' $1').replace(/^./, (str) => str.toUpperCase());
}

const columns = computed(() => {
  const firstRow = props.data?.[0];
  if (!firstRow) return [];
  return Object.keys(firstRow).map((key) => ({
    field: key,
    header: formatHeader(key)
  }));
});

function tableBodyCell({ state }: { state: Record<string, any> }) {
  return {
    class: [{ '!py-0': state['d_editing'] }]
  };
}
</script>

<template>
  <div
    class="prose prose-base w-full max-w-4xl rounded-lg border border-warning bg-warning/10 px-6 py-5 text-left text-base-content"
  >
    <p class="mb-2 font-semibold">Do you approve to send this to OpenAI for further processing?</p>

    <div v-if="data && data.length" class="overflow-y-auto rounded bg-base-100 p-4 text-sm">
      <DataTable
        :value="data"
        scrollable
        scrollHeight="400px"
        striped-rows
        removableSort
        :filters="filters"
        :globalFilterFields="columns.map((c) => c.field)"
        class="!w-auto pt-0"
        edit-mode="cell"
        @cell-edit-complete="$emit('cell-edit-complete', $event)"
        :pt="{
          table: { style: 'min-width: 50rem' },
          column: {
            bodycell: tableBodyCell
          }
        }"
      >
        <template #header>
          <div class="custom-datatable-header flex items-center justify-between gap-4 pr-0">
            <span class="ml-auto">
              <input
                v-model="globalSearch"
                type="text"
                placeholder="Search for values..."
                class="input input-sm input-bordered w-full max-w-xs"
              />
            </span>

            <span class="flex gap-2">
              <input
                v-model="searchTerms"
                type="text"
                placeholder="Terms to obfuscate (comma-separated)"
                class="input input-sm input-bordered w-64"
              />
              <button @click="handleObfuscate" class="btn btn-secondary btn-sm">Obfuscate</button>
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
          :editable="true"
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
          <template #editor="{ data, field }">
            <InputText v-model="data[field]" :autofocus="true" fluid class="w-full" />
          </template>
        </Column>
      </DataTable>
    </div>

    <div v-else class="p-4 text-sm text-gray-500">No data found.</div>

    <div class="mt-4 flex justify-end gap-4">
      <button class="btn btn-outline btn-sm" @click="$emit('approve', false)">No</button>
      <button class="btn btn-primary btn-sm" @click="$emit('approve', true)">Yes</button>
    </div>
  </div>
</template>

<style scoped lang="less">
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

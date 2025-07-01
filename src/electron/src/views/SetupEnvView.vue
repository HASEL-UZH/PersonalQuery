<script setup lang="ts">
import { ref } from 'vue';
import typedIpcRenderer from '../utils/typedIpcRenderer';

const apiKey = ref('');

async function saveKey() {
  if (!apiKey.value.trim()) {
    alert('Please enter your API key.');
    return;
  }

  const envContent = `
OPENAI_API_KEY=${apiKey.value}
LANGSMITH_TRACING=false
LANGSMITH_PROJECT=personalQuery
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=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
  `.trim();

  await typedIpcRenderer.invoke('saveEnvFile', envContent);
  window.close();
}

async function pasteFromClipboard() {
  try {
    apiKey.value = await navigator.clipboard.readText();
  } catch (err) {
    console.error('Failed to read clipboard:', err);
  }
}
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center px-4">
    <h2 class="mb-4 text-2xl font-semibold">Enter OpenAI API Key</h2>
    <p class="mb-4 max-w-xl text-sm">
      Please enter the API key sent to you by email. It will be saved locally, and the application
      will restart. This may take a moment the first time.
    </p>
    <div class="flex w-full">
      <input
        v-model="apiKey"
        class="input input-bordered w-full rounded-r-none focus:outline-none focus:ring-0"
        placeholder="Enter your API Key..."
      />
      <button
        class="btn tooltip mt-0 flex rounded-l-none bg-gray-200 px-4 hover:bg-gray-300"
        @click="pasteFromClipboard"
        title="Paste from clipboard"
        data-tip="Paste"
      >
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
            d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25ZM6.75 12h.008v.008H6.75V12Zm0 3h.008v.008H6.75V15Zm0 3h.008v.008H6.75V18Z"
          />
        </svg>
      </button>
    </div>

    <div class="mt-4 flex w-full max-w-md justify-end">
      <button class="btn btn-primary btn-sm" @click="saveKey">Save and Restart</button>
    </div>
  </div>
</template>

<style scoped lang="less"></style>

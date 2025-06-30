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
</script>

<template>
  <div class="setup-env">
    <h2>Set up OpenAI API Key</h2>
    <input
      v-model="apiKey"
      class="input input-md"
      type="password"
      placeholder="Enter your OpenAI API Key"
    />
    <button class="btn btn-primary btn-sm" @click="saveKey">Save and Restart</button>
  </div>
</template>

<style scoped lang="less">
.setup-env {
  padding: 1em;
}
button {
  margin-top: 1em;
  padding: 0.5em 1em;
}
</style>

<script setup lang="ts">
import ChatSidebar from '../components/ChatSideBar.vue';
import DailyGoal from '../components/DailyGoal.vue';
</script>

<template>
  <div class="flex h-screen">
    <ChatSidebar />
    <router-view class="flex-1" />
    <DailyGoal />
  </div>
</template>
<style scoped lang="less"></style>

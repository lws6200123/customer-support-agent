<script setup lang="ts">
defineProps<{ title: string; description?: string }>()
</script>

<template>
  <a-empty :description="title" class="empty-state">
    <p v-if="description" class="muted">{{ description }}</p>
    <slot />
  </a-empty>
</template>

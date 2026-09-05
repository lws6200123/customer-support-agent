<script setup lang="ts">
import { computed } from 'vue'
import { displayDecision } from '../utils/display'

const props = defineProps<{ decision: string | null | undefined; technical?: boolean }>()
const color = computed(() => ({ AUTO_RESOLVE: 'green', NEED_MORE_INFO: 'gold', ESCALATE_TO_HUMAN: 'red' }[props.decision || ''] || 'default'))
const label = computed(() => {
  if (!props.decision) return '尚未决策'
  const display = displayDecision(props.decision)
  return props.technical && display !== props.decision ? `${display} (${props.decision})` : display
})
</script>

<template><a-tag :color="color">{{ label }}</a-tag></template>

<script setup lang="ts">
import { computed } from 'vue'
import { displayExecutionStatus, displayOrderStatus, displayTicketStatus } from '../utils/display'
const props = withDefaults(defineProps<{ status: string | null | undefined; kind?: 'ticket' | 'order' | 'execution' }>(), { kind: 'ticket' })
const color = computed(() => ({ open: 'blue', awaiting_customer: 'gold', under_review: 'red', resolved: 'green', closed: 'default', SUCCESS: 'green', FAILED: 'red', FALLBACK: 'orange', SKIPPED: 'default' }[props.status || ''] || 'blue'))
const label = computed(() => props.kind === 'order' ? displayOrderStatus(props.status) : props.kind === 'execution' ? displayExecutionStatus(props.status) : displayTicketStatus(props.status))
</script>

<template><a-tag :color="color" class="status-tag">{{ label }}</a-tag></template>

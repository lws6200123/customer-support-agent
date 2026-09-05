<script setup lang="ts">
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import AppLayout from './components/AppLayout.vue'
</script>

<template>
  <a-config-provider :locale="zhCN">
    <AppLayout />
  </a-config-provider>
</template>

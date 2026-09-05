<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DashboardOutlined, InboxOutlined, RobotOutlined, SafetyCertificateOutlined, MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons-vue'

const collapsed = ref(false)
const route = useRoute()
const router = useRouter()
const selected = computed(() => [route.path.startsWith('/tickets') ? '/tickets' : route.path])
const items = [
  { key: '/', icon: () => h(DashboardOutlined), label: '数据看板' },
  { key: '/tickets', icon: () => h(InboxOutlined), label: '工单管理' },
  { key: '/human-reviews', icon: () => h(SafetyCertificateOutlined), label: '人工审核' },
  { key: '/demo', icon: () => h(RobotOutlined), label: 'Agent 演示' },
]
function navigate({ key }: { key: string }) { void router.push(key) }
</script>

<template>
  <a-layout class="app-shell">
    <a-layout-sider v-model:collapsed="collapsed" collapsible :trigger="null" width="232" class="app-sider">
      <div class="brand"><div class="brand-mark">DS</div><div v-if="!collapsed"><strong>DemoShop</strong><small>客服运营控制台</small></div></div>
      <a-menu mode="inline" theme="dark" :selected-keys="selected" :items="items" @click="navigate" />
      <div v-if="!collapsed" class="sider-note"><span class="status-dot" /> 演示环境</div>
    </a-layout-sider>
    <a-layout>
      <a-layout-header class="topbar">
        <a-button type="text" class="collapse-button" aria-label="展开或收起导航" @click="collapsed = !collapsed">
          <MenuUnfoldOutlined v-if="collapsed" /><MenuFoldOutlined v-else />
        </a-button>
        <div class="topbar-title"><strong>DemoShop 智能客服 Agent</strong><span>运营控制台</span></div>
        <div class="environment-badges"><a-tag color="blue">演示环境</a-tag><a-tag color="orange">演示系统：未配置生产级身份认证</a-tag></div>
      </a-layout-header>
      <a-layout-content class="page-content"><router-view /></a-layout-content>
    </a-layout>
  </a-layout>
</template>

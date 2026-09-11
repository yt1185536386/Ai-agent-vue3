<template>
  <!-- Element Plus 按需引入后,全局配置(中文语言包)通过 ConfigProvider 提供 -->
  <el-config-provider :locale="zhCn">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import zhCn from 'element-plus/es/locale/lang/zh-cn'
</script>

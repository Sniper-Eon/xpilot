<script setup lang="ts">
import { onMounted, ref } from "vue";
const status = ref<Record<string, unknown> | null>(null);
const error = ref("");
const result = ref("");
const recording = ref('{"frames":[]}');
const profile = ref("standard_party");
const busA = ref(0);
const busB = ref(1);
const onroad = ref(true);
const features = ref<string[]>([]);
async function request(path: string, body?: unknown) {
  const response = await fetch('/api/tcan/' + path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
  return value;
}
async function refresh() {
  error.value = '';
  try { status.value = await request('status'); }
  catch (e) { error.value = String(e); }
}
async function preview() {
  try {
    const frames = JSON.parse(recording.value).frames;
    result.value = JSON.stringify(await request('preview', {frames, profile: profile.value,
      bus_map: {A: busA.value, B: busB.value}, sp_onroad: onroad.value, features: features.value}), null, 2);
  } catch (e) { result.value = String(e); }
}
onMounted(refresh);
</script>

<template>
  <section class="mx-auto max-w-4xl space-y-5 p-6 text-sl-text-1" data-testid="tcan-panel">
    <h1 class="text-xl font-semibold">T-CAN 观察与离线影子预览</h1>
    <p class="text-sm text-sl-text-2">无 CAN 发送能力，物理 CAN 映射未验证。候选帧不代表车辆功能已启用。</p>
    <p v-if="error" role="alert" class="text-sl-danger">{{ error }}</p>
    <div class="flex flex-wrap gap-4">
      <button class="rounded bg-sl-surface-3 p-3" @click="refresh">刷新状态</button>
      <a class="rounded bg-sl-surface-3 p-3" href="/api/tcan/capture" download="tcan-capture.json">导出最近最多 1000 帧</a>
    </div>
    <pre class="overflow-auto rounded bg-sl-surface p-4 text-xs">{{ JSON.stringify(status, null, 2) }}</pre>
    <p class="text-sm">R79 仅 mux1 位变换；ISA 是无发送计数器／校验和的中间态；Country US 仅 0x238。不是完整 T2CAN 功能移植。</p>
    <label class="block">离线录包 JSON（最多 1000 帧、仅 11 位 ID）
      <textarea v-model="recording" class="mt-2 min-h-40 w-full rounded bg-sl-surface p-3 font-mono text-sm" />
    </label>
    <div class="flex flex-wrap gap-4">
      <label>离线车型 <select v-model="profile" class="bg-sl-surface p-2"><option>standard_party</option><option>standard_body</option><option>yl</option></select></label>
      <label>A <select v-model="busA" class="bg-sl-surface p-2"><option v-for="b in [0,1,2]" :key="b" :value="b">{{ b }}</option></select></label>
      <label>B <select v-model="busB" class="bg-sl-surface p-2"><option v-for="b in [0,1,2]" :key="b" :value="b">{{ b }}</option></select></label>
    </div>
    <p class="text-sm text-sl-text-2">A/B 只是输入录包的声明，不是已验证的 C3 物理接线。预览不会修改实时配置。</p>
    <label class="block"><input v-model="onroad" type="checkbox"> 模拟 SP onroad（阻止候选）</label>
    <div class="flex flex-wrap gap-4"><label v-for="feature in ['r79','isa','country_us']" :key="feature"><input v-model="features" type="checkbox" :value="feature"> {{ feature }}</label></div>
    <button class="rounded bg-sl-surface-3 p-3" @click="preview">运行离线影子预览</button>
    <pre class="overflow-auto whitespace-pre-wrap break-all rounded bg-sl-surface p-4 text-xs">{{ result }}</pre>
  </section>
</template>

/**
 * 语音输入(composable):
 * 点击麦克风开启/关闭。开启后分段录音(MediaRecorder 每 ~3s 轮换一次,
 * 每段都是完整 webm 文件),解码重采样为 16kHz mono WAV 后上传后端 ASR,
 * 识别文本实时追加到输入框;关闭后文本保留可编辑再发送。
 *
 * 链路:浏览器 → NestJS /v1/asr/transcribe(JWT)→ ai-service(X-Service-Key)
 *       → 百炼 Paraformer。
 */
import { ref, nextTick, onBeforeUnmount } from "vue";
import { post } from "../../axios";
import { extractErrorMessage } from "../../axios/utils";

// 分段时长:过短识别上下文不足,过长文字出现延迟大
const SEGMENT_MS = 3000;
// 上传 WAV 参数:与 ai-service ASR 端点(format=wav, sample_rate=16000)对齐
const TARGET_SAMPLE_RATE = 16000;

/** 把 Float32 PCM(单声道,TARGET_SAMPLE_RATE)编码为 16bit PCM WAV Blob */
function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buf);
  const writeStr = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true); // PCM 块大小
  view.setUint16(20, 1, true); // PCM 编码
  view.setUint16(22, 1, true); // 单声道
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // 字节率
  view.setUint16(32, 2, true); // 块对齐
  view.setUint16(34, 16, true); // 位深
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buf], { type: "audio/wav" });
}

/** webm/opus 片段 → 16kHz mono WAV Blob(OfflineAudioContext 顺便完成重采样) */
async function webmToWav(blob: Blob): Promise<Blob> {
  const raw = await blob.arrayBuffer();
  const probe = new AudioContext();
  const decoded = await probe.decodeAudioData(raw);
  await probe.close();
  const offline = new OfflineAudioContext(
    1,
    Math.ceil(decoded.duration * TARGET_SAMPLE_RATE),
    TARGET_SAMPLE_RATE,
  );
  const src = offline.createBufferSource();
  src.buffer = decoded;
  src.connect(offline.destination);
  src.start();
  const rendered = await offline.startRendering();
  return encodeWav(rendered.getChannelData(0), TARGET_SAMPLE_RATE);
}

export function useVoiceInput({
  userInput,
  autoResize,
}: {
  userInput: { value: string };
  autoResize: () => void;
}) {
  const voiceRecording = ref(false);
  const voiceHint = ref("");

  let stream: MediaStream | null = null;
  let recorder: MediaRecorder | null = null;
  let segTimer: ReturnType<typeof setTimeout> | null = null;
  // 识别请求串行队列:保证多段文本按录音顺序追加
  let queue: Promise<void> = Promise.resolve();
  let stopping = false;

  /** 追加识别文本到输入框并重算高度 */
  const appendText = (text: string) => {
    userInput.value += text;
    nextTick(() => autoResize());
  };

  /** 单段:转 WAV → 上传 → 追加文本;失败只告警一次(由调用方决定) */
  const transcribeSegment = async (webm: Blob) => {
    if (!webm.size) return;
    const wav = await webmToWav(webm);
    const fd = new FormData();
    fd.append("file", wav, "voice.wav");
    const { text } = await post<{ text?: string }>("/v1/asr/transcribe", fd);
    if (text) appendText(text);
  };

  const enqueue = (webm: Blob) => {
    queue = queue
      .then(() => transcribeSegment(webm))
      .catch((e) => {
        // 某段失败不阻塞后续段,也不打断录音
        console.error("语音转写失败", e);
        voiceHint.value = `转写失败: ${extractErrorMessage(e)}`;
      });
  };

  /** 停掉当前 recorder(触发 ondataavailable 拿到完整片段),并立即开下一段 */
  const rotateSegment = () => {
    if (!voiceRecording.value) return;
    recorder?.stop();
  };

  const startSegment = () => {
    if (!stream || !voiceRecording.value) return;
    const rec = new MediaRecorder(stream);
    recorder = rec;
    rec.ondataavailable = (e) => {
      if (e.data?.size) enqueue(e.data);
    };
    rec.onstop = () => {
      if (voiceRecording.value && !stopping) startSegment();
    };
    rec.start();
    segTimer = setTimeout(rotateSegment, SEGMENT_MS);
  };

  const release = () => {
    if (segTimer) {
      clearTimeout(segTimer);
      segTimer = null;
    }
    stream?.getTracks().forEach((t) => t.stop());
    stream = null;
    recorder = null;
  };

  const startVoice = async () => {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      alert(`无法使用麦克风: ${extractErrorMessage(e)}`);
      return;
    }
    voiceRecording.value = true;
    voiceHint.value = "正在聆听…";
    stopping = false;
    startSegment();
  };

  const stopVoice = () => {
    if (!voiceRecording.value) return;
    stopping = true;
    voiceRecording.value = false;
    voiceHint.value = "";
    if (recorder && recorder.state !== "inactive") recorder.stop();
    release();
  };

  const toggleVoice = () => {
    if (voiceRecording.value) stopVoice();
    else startVoice();
  };

  onBeforeUnmount(stopVoice);

  return { voiceRecording, voiceHint, toggleVoice, stopVoice };
}

/**
 * 转写文本解析：会议录音转写工具的导出格式五花八门，这里做一层宽松解析。
 * 支持形态：
 *   [00:12:30] 孟嘉祺：文本        /  00:12 孟嘉祺: 文本
 *   孟嘉祺：文本                   /  孟嘉祺 说：文本
 * 完全没有说话人时，按句号/问号切段，说话人留空（后端会兜底成「发言人 1」）。
 */
export interface ParsedSegment {
  idx: number;
  speaker: string;
  start_ms: number;
  end_ms: number;
  text: string;
}

const TIME = /^\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\]?\s*/;
const SPEAKER = /^([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9·\s]{0,11})\s*[:：]\s*/;

export function parseTranscript(raw: string): ParsedSegment[] {
  const lines = raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  const out: ParsedSegment[] = [];
  for (const line of lines) {
    let rest = line;
    let start = 0;
    const t = rest.match(TIME);
    if (t) {
      // TIME 有两种可能：mm:ss（t[3] 为空）或 hh:mm:ss
      start = t[3] !== undefined
        ? (Number(t[1]) * 3600 + Number(t[2]) * 60 + Number(t[3])) * 1000
        : (Number(t[1]) * 60 + Number(t[2])) * 1000;
      rest = rest.slice(t[0].length);
    }
    let speaker = '';
    const s = rest.match(SPEAKER);
    if (s) {
      speaker = s[1].trim();
      rest = rest.slice(s[0].length);
    }
    if (!rest.trim()) continue;
    out.push({ idx: out.length + 1, speaker, start_ms: start, end_ms: start, text: rest.trim() });
  }

  // 没有识别出任何换行结构时，按句子聚合，每 2 句一段，保证后续切块有语义边界
  if (out.length <= 1 && raw.length > 120) {
    const sentences = raw.split(/(?<=[。！？!?])/).map((x) => x.trim()).filter(Boolean);
    const merged: ParsedSegment[] = [];
    for (let i = 0; i < sentences.length; i += 2) {
      merged.push({
        idx: merged.length + 1,
        speaker: '',
        start_ms: 0,
        end_ms: 0,
        text: sentences.slice(i, i + 2).join(''),
      });
    }
    return merged;
  }

  // 补齐结束时间：下一段开始时间即本段结束，最后一段按字数估算（每秒 4 字）
  const est = (txt: string) => Math.max(4000, Math.round((txt.length / 4) * 1000));
  for (let i = 0; i < out.length; i += 1) {
    const next = out[i + 1];
    out[i].end_ms = next && next.start_ms > out[i].start_ms ? next.start_ms : out[i].start_ms + est(out[i].text);
  }
  return out;
}

export function transcriptToPlain(segments: { speaker: string; text: string }[]): string {
  return segments.map((s) => `${s.speaker || '发言人'}：${s.text}`).join('\n');
}

export const DEMO_TRANSCRIPT = `[00:00] 孟嘉祺：今天主要对齐两件事，纪要多 Agent 流水线的验收口径，还有九月上线前的演示环境资源。
[00:48] 杜春晓：前端这边证据链面板已经能跑，但决议卡片在移动端会换行错位，我打算改成上下布局。
[01:35] 孟嘉祺：移动端先不做全量适配，演示用桌面端，但卡片换行这个 bug 要修，今天下班前能给我一版吗？
[02:02] 杜春晓：可以，改完顺手把引用高亮也调一下，弱证据用灰色描边，强证据用实线。
[02:40] 赵鹏：后端有个问题，转写超过 3000 字的时候，decider 的输入会被截断，导致最后几条决议缺失。
[03:15] 孟嘉祺：那就先做分段摘要，每段控制在 1200 字以内，段间用会议主题做锚点，不要整篇重构。
[03:52] 赵鹏：明白，我评估一下，大概两天，也就是 9 月 2 号能给到可测版本。
[04:20] 杜春晓：引用校验的阈值现在是 0.55，我问了几个人，误留率偏高，要不要下调到 0.45？
[04:55] 孟嘉祺：下调，但要做回归集，别让准确率掉太多。这个数据下周周会上给我。
[05:30] 赵鹏：还有个风险，演示环境只申请到一台 4 核 8G 的机器，并发一高 SSE 会断。`;

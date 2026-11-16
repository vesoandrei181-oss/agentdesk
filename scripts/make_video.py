"""录制 1080p 演示视频：脚本驱动浏览器 + edge-tts 旁白 + ffmpeg 合成。

流程：
1. 每段旁白先用 edge-tts 生成语音，用 ffprobe 量出真实时长；
2. 按这些时长录制浏览器操作（画面跟着旁白走，不会出现"讲完了画面还在动"）；
3. 语音按场景顺序拼成一条音轨（场景之间补 0.5 秒静音），与视频等长；
4. webm 转 mp4，烧入字幕，输出 1920x1080。

跑法：python scripts/make_video.py
前置：后端在 127.0.0.1:8000 运行、系统装有 Chrome、ffmpeg 在 PATH 里。
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import edge_tts
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "docs" / "video"
TTS_DIR = WORK / "tts"
CLIPS = WORK / "clips"
BASE = "http://127.0.0.1:8000"
VOICE = "zh-CN-XiaoxiaoNeural"
GAP = 0.5  # 场景之间留白，给画面切换一点呼吸


@dataclass
class Scene:
    key: str
    text: str
    action: str
    duration: float = 0.0
    audio: Path | None = None
    extra: dict = field(default_factory=dict)


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def synth(scene: Scene) -> None:
    mp3 = TTS_DIR / f"{scene.key}.mp3"
    if not mp3.exists() or mp3.stat().st_size < 1000:
        async def run() -> None:
            await edge_tts.Communicate(scene.text, VOICE, rate="-4%").save(str(mp3))
        asyncio.run(run())
    scene.audio = mp3
    scene.duration = ffprobe_duration(mp3)
    print(f"  {scene.key:<10} {scene.duration:5.1f}s  {scene.text[:26]}…")


SCENES = [
    Scene("s01_problem",
          "开完会之后的事，往往比开会更耗人。一场一小时的评审会，散会后要有一个人回听录音、整理纪要、"
          "把结论摘出来、把待办派下去，再在周报里复述一遍。更麻烦的是三个副作用：结论被顺得走了样，"
          "先看看变成已决定；待办落到文档里只剩一句跟进相关工作，没有责任人；三个月后新人问，"
          "我们当时的阈值是怎么定的，没人答得上来。这是智协台 AgentDesk 想做的事："
          "让 AI 的每一句输出，都能点回原始证据。",
          "login"),
    Scene("s02_dashboard",
          "这是登录后的工作台。左边是六个模块，右边是这周整体情况：累计会议、沉淀决议、证据覆盖率、"
          "节省的整理工时。下面这条曲线是最近十四天的分析任务量，右边是八个 Agent 的调用分布。"
          "请注意，这里所有数字都来自真实运行记录，不是写死的假数据。",
          "dashboard"),
    Scene("s03_meetings",
          "进入会议纪要。新建一场会只要两步：贴上带时间戳的转写，或者直接贴对话文本。"
          "左边是实时解析预览，它会识别时间戳和说话人前缀。分析走后台任务，页面轮询状态，"
          "用户不用干等，一场十二段的会大概三十秒出结果。",
          "meetings"),
    Scene("s04_evidence",
          "打开第一场会。上面这排是统计：五条决议、四条待办、证据覆盖四比五。重点看第二个页签，证据链。"
          "每条决议下面都挂着原始引文、说话人、时间点，右边是置信度。这条决议的引文来自一分十二秒的原话，"
          "重合度百分之九十四，所以标为有据。下面这条是未决问题，它没有引文。系统在落库前会把引文回查到转写原文，"
          "重合度低于零点五五的直接丢弃，丢弃后没有证据的条目就降级成未决，提示需要人确认。"
          "可信的 AI 不是更会编，而是编不出来的时候敢承认。",
          "evidence"),
    Scene("s05_trace",
          "第四个页签是执行链。六个 Agent 依次做了什么、输入输出摘要、token 数、耗时，都在这里。"
          "这一页不只是给评委看的，调优时我们就是靠它发现复核 Agent 花了十二秒这种问题的。",
          "trace"),
    Scene("s06_writer",
          "智能写作。这里有一个刻意的设计：我们不让模型重写整篇文档，而是要求它输出补丁，"
          "改哪一句、改成什么、为什么改。后端拿到补丁后在原文里定位并应用，再算出逐行差异。"
          "生成之后右边出现文本体检和修改建议，每条都带理由，再往下是差异确认，每一块都可以单独取消勾选。"
          "用户接受的是这几处改动，不是整篇被换掉。实测四条常用指令，补丁定位成功率百分之百。",
          "writer"),
    Scene("s07_kb",
          "知识库。资料会被切成五百二十字一段、重叠八十，同时建 BM25 索引和向量索引。"
          "问一个具体问题，它不是等七秒才出结果，而是先把召回的片段显示出来，再逐字输出正文。"
          "回答里每个编号都能点开看原文，引用卡片标着强支撑和弱支撑：弱支撑提示这句可能是模型自己的总结，"
          "你需要自己回查。这个标注比单纯显示来源有用，因为它告诉你能不能直接引用。",
          "kb"),
    Scene("s08_tasks",
          "任务看板，四列状态。卡片上的进度条不是普通进度，是 P50 和 P90：大概率三天干完，"
          "拖到五天的可能性也不小。描述里出现调研、梳理这类模糊动词时，区间会自动拉宽，"
          "因为这种任务本来就不该给一个确定数字。",
          "tasks"),
    Scene("s09_weekly",
          "周报页做成两段：左边的数据面板本地聚合，秒出；右边正文点一下才生成，数据没变就不重复花钱。"
          "这个设计是被一次事故逼出来的，最初同步生成，用户打开页面要等三十到六十秒，看起来就是白屏。",
          "weekly"),
    Scene("s10_insights",
          "运行观测和设置。累计三十一次运行、十万出头的 token、不到八美分，缓存命中二十六次。"
          "设置里可以切四档模型路由。默认这档全部走快模型并关闭思维链，这是实测出来的结论："
          "同一个抽取任务，快模型抽得比大模型更多、快十倍；大模型开着思维链，四千 token 预算内一条都产不出来，"
          "因为预算全花在思考上。这个项目真正花时间的不是页面，是这些看不见的东西："
          "让输出可校验，让失败能降级，让成本看得见。谢谢观看。",
          "insights"),
]


# ------------------------------------------------------------------ 浏览器动作
CURSOR_JS = """
window.__cursor = document.createElement('div');
Object.assign(window.__cursor.style, {
  position: 'fixed', width: '16px', height: '16px', borderRadius: '50%',
  background: 'rgba(79,70,229,.85)', boxShadow: '0 0 0 6px rgba(79,70,229,.18)',
  pointerEvents: 'none', zIndex: 999999, transition: 'transform .06s linear',
  transform: 'translate(-100px,-100px)'
});
document.body.appendChild(window.__cursor);
document.addEventListener('mousemove', e => {
  window.__cursor.style.transform = `translate(${e.clientX - 8}px, ${e.clientY - 8}px)`;
}, true);
"""


def glide(page: Page, x: float, y: float, steps: int = 22) -> None:
    page.mouse.move(x, y, steps=steps)
    page.wait_for_timeout(120)


def click_text(page: Page, text: str, exact: bool = False) -> bool:
    """按可见文字点击。只在可交互元素里找，并优先选文字最短的那个——
    否则容易点到包住整页的 div，看起来"点了"，其实什么都没发生。"""
    box = page.evaluate(
        """([text, exact]) => {
            const sel = 'button, a, [role=tab], [role=button], input[type=submit]';
            const hits = [...document.querySelectorAll(sel)]
              .map(e => ({e, t: (e.textContent || '').trim()}))
              .filter(x => x.t && (exact ? x.t === text : x.t.includes(text)))
              .sort((a, b) => a.t.length - b.t.length);
            if (!hits.length) return null;
            const e = hits[0].e;
            e.scrollIntoView({block: 'center'});
            const r = e.getBoundingClientRect();
            if (!r.width || !r.height) return null;
            return {x: r.x + r.width / 2, y: r.y + r.height / 2};
        }""",
        [text, exact],
    )
    if not box:
        return False
    glide(page, box["x"], box["y"])
    page.mouse.click(box["x"], box["y"])
    return True


def ensure_login(page: Page) -> None:
    """登录并确认真的进了工作区；没进去就直接抛错，别录一整段登录页。"""
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.wait_for_timeout(600)
    if "/login" not in page.url:
        return
    page.fill("form input:not([type=password])", "demo@agentdesk.dev")
    page.fill("form input[type=password]", "Demo@2026")
    page.wait_for_timeout(200)
    page.click("form button.btn-primary")
    page.wait_for_url("**/dashboard", timeout=15000)
    page.wait_for_timeout(1200)


def slow_scroll(page: Page, total: int, ms: int = 1200, steps: int = 12) -> None:
    for _ in range(steps):
        page.mouse.wheel(0, total // steps)
        page.wait_for_timeout(max(40, ms // steps))


def fill_until(page: Page, remaining: float) -> None:
    """把当前场景剩余的时间"演"完：轻微滚动，避免画面完全静止。"""
    spent = 0.0
    while spent < remaining - 0.4:
        page.wait_for_timeout(400)
        spent += 0.4
        if int(spent * 2) % 8 == 0:
            page.mouse.wheel(0, 60)


def act(page: Page, key: str, seconds: float) -> None:
    """每个场景的动作：先导航/点击，剩下的时间用滚动或停留填满。"""
    t0 = time.time()
    try:
        if key == "login":
            page.goto(f"{BASE}/login", wait_until="networkidle")
            page.wait_for_timeout(800)
            fill_until(page, seconds - (time.time() - t0))
            ensure_login(page)
            fill_until(page, seconds - (time.time() - t0))
        elif key == "dashboard":
            page.goto(f"{BASE}/dashboard", wait_until="networkidle")
            page.wait_for_timeout(1200)
            slow_scroll(page, 520, 1600)
            fill_until(page, seconds - (time.time() - t0))
            page.mouse.wheel(0, -600)
        elif key == "meetings":
            page.goto(f"{BASE}/meetings", wait_until="networkidle")
            page.wait_for_timeout(1000)
            click_text(page, "新建会议")
            page.wait_for_timeout(1200)
            fill_until(page, seconds * 0.55 - (time.time() - t0))
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
            fill_until(page, seconds - (time.time() - t0))
        elif key == "evidence":
            page.goto(f"{BASE}/meetings/1", wait_until="networkidle")
            page.wait_for_timeout(1500)
            slow_scroll(page, 420, 1800)
            click_text(page, "证据链")
            page.wait_for_timeout(1200)
            slow_scroll(page, 700, 2600)
            fill_until(page, seconds - (time.time() - t0))
        elif key == "trace":
            click_text(page, "Agent Trace")
            page.wait_for_timeout(1500)
            slow_scroll(page, 460, 2000)
            fill_until(page, seconds - (time.time() - t0))
        elif key == "writer":
            page.goto(f"{BASE}/docs/1", wait_until="networkidle")
            page.wait_for_timeout(1200)
            click_text(page, "生成修改建议")
            page.wait_for_timeout(14000)
            slow_scroll(page, 900, 2400)
            fill_until(page, seconds - (time.time() - t0))
        elif key == "kb":
            page.goto(f"{BASE}/kb", wait_until="networkidle")
            # 上一轮录制的问答会留在历史里，先清空，画面才是「一次干净的提问」
            page.evaluate(
                """async () => {
                    const t = localStorage.getItem('agentdesk.token');
                    await fetch('/api/kb/chat/history', {method: 'DELETE', headers: {Authorization: 'Bearer ' + t}});
                }"""
            )
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(1200)
            page.fill('input[placeholder*="提问"]', "引用校验阈值是多少")
            page.wait_for_timeout(400)
            page.click("form button.btn-primary")
            page.wait_for_timeout(11000)
            slow_scroll(page, 700, 2000)
            fill_until(page, seconds - (time.time() - t0))
        elif key == "tasks":
            page.goto(f"{BASE}/tasks", wait_until="networkidle")
            page.wait_for_timeout(1400)
            slow_scroll(page, 560, 2200)
            fill_until(page, seconds - (time.time() - t0))
        elif key == "weekly":
            page.goto(f"{BASE}/weekly", wait_until="networkidle")
            page.wait_for_timeout(1500)
            if not page.evaluate("document.body.innerText.includes('本周进展')"):
                click_text(page, "生成本周周报")
                page.wait_for_timeout(9000)
            slow_scroll(page, 420, 1800)
            fill_until(page, seconds - (time.time() - t0))
        elif key == "insights":
            page.goto(f"{BASE}/insights", wait_until="networkidle")
            page.wait_for_timeout(1400)
            slow_scroll(page, 700, 2400)
            page.goto(f"{BASE}/settings", wait_until="networkidle")
            page.wait_for_timeout(1500)
            slow_scroll(page, 380, 1800)
            fill_until(page, seconds - (time.time() - t0))
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] {key} 动作异常：{exc}")
        page.wait_for_timeout(500)
    finally:
        if "/login" in page.url:
            print(f"  [warn] {key} 结束时仍停在登录页，画面可能无效")


# ------------------------------------------------------------------ 字幕
def ass_time(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Microsoft YaHei,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2.4,0,2,110,110,58,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_subtitles(scenes: list[Scene]) -> Path:
    """直接生成 ASS：PlayRes 固定 1920x1080，字号才是像素级可控的。

    用 SRT + force_style 时 libass 默认按 288 行高换算，字号会被放大三四倍，
    字幕占掉半个屏幕——踩过这个坑，所以这里自己写 ASS 头部。
    """
    lines: list[str] = []
    clock = 0.0
    for sc in scenes:
        parts = [p for p in re.split(r"(?<=[。，；：！？])", sc.text) if p.strip()]
        # 长句按 22 字切开；过短的碎句并回上一句，避免屏幕上闪一个"0"这种碎片
        pieces: list[str] = []
        for p in parts:
            while len(p) > 22:
                pieces.append(p[:22])
                p = p[22:]
            if not p:
                continue
            if pieces and len(p) < 8:
                pieces[-1] += p
            else:
                pieces.append(p)
        total_chars = sum(len(p) for p in pieces) or 1
        cursor = clock
        for p in pieces:
            dur = sc.duration * len(p) / total_chars
            lines.append(
                f"Dialogue: 0,{ass_time(cursor)},{ass_time(cursor + dur)},Main,,0,0,0,,{p}"
            )
            cursor += dur
        clock += sc.duration + GAP
    out = WORK / "subtitles.ass"
    out.write_text(ASS_HEAD + "\n".join(lines) + "\n", encoding="utf-8")
    return out


def build_audio(scenes: list[Scene]) -> Path:
    silence = WORK / "silence.mp3"
    if not silence.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono",
             "-t", str(GAP), "-q:a", "9", str(silence)],
            check=True, capture_output=True,
        )
    listfile = WORK / "audio_list.txt"
    rows = []
    for sc in scenes:
        rows.append(f"file '{sc.audio.as_posix()}'")
        rows.append(f"file '{silence.as_posix()}'")
    listfile.write_text("\n".join(rows), encoding="utf-8")
    out = WORK / "narration.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
         "-c:a", "libmp3lame", "-q:a", "3", str(out)],
        check=True, capture_output=True,
    )
    return out


def main() -> None:
    for d in (TTS_DIR, CLIPS):
        d.mkdir(parents=True, exist_ok=True)

    print("1/4 生成旁白")
    for sc in SCENES:
        synth(sc)
    total = sum(s.duration + GAP for s in SCENES)
    print(f"    预计视频长度 {total / 60:.1f} 分钟")

    print("2/4 录制画面")
    with sync_playwright() as p:
        browser = None
        for channel in ("chrome", "msedge"):
            try:
                browser = p.chromium.launch(channel=channel)
                break
            except Exception:  # noqa: BLE001
                continue
        if browser is None:
            browser = p.chromium.launch()

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(CLIPS),
            record_video_size={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        page = context.new_page()
        page.add_init_script(CURSOR_JS)
        page.goto(f"{BASE}/login", wait_until="networkidle")
        try:
            page.evaluate("localStorage.setItem('agentdesk.token', ''); localStorage.clear();")
        except Exception:  # noqa: BLE001
            pass

        start = time.time()
        for sc in SCENES:
            print(f"    {sc.key}  {sc.duration:.1f}s")
            act(page, sc.action, sc.duration + GAP)
        elapsed = time.time() - start
        video_path = page.video.path()
        context.close()
        browser.close()

    raw = WORK / "raw.webm"
    shutil.move(video_path, raw)
    print(f"    录制完成 {elapsed:.0f}s → {raw.name}")

    print("3/4 合成音轨与字幕")
    audio = build_audio(SCENES)
    srt = build_subtitles(SCENES)

    print("4/4 转码 1080p MP4")
    out = ROOT / "docs" / "演示视频-智协台AgentDesk.mp4"
    # 在视频工作目录里跑，字幕路径写成裸文件名：Windows 盘符里的冒号会被 ffmpeg 当成滤镜参数分隔符
    subprocess.run(
        ["ffmpeg", "-y", "-i", "raw.webm", "-i", "narration.mp3",
         "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                "subtitles=subtitles.ass",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
         str(out)],
        check=True,
        cwd=str(WORK),
    )
    print(f"完成：{out}（{out.stat().st_size / 1024 / 1024:.1f} MB）")


def mux_only() -> None:
    """已有 raw.webm 与 narration.mp3 时，只重做声音拼接、字幕与转码。"""
    for sc in SCENES:
        sc.audio = TTS_DIR / f"{sc.key}.mp3"
        sc.duration = ffprobe_duration(sc.audio)
    print("重做字幕与合成（不重新录制）")
    build_audio(SCENES)
    build_subtitles(SCENES)
    out = ROOT / "docs" / "演示视频-智协台AgentDesk.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-i", "raw.webm", "-i", "narration.mp3",
         "-vf", "subtitles=subtitles.ass",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
         str(out)],
        check=True,
        cwd=str(WORK),
    )
    print(f"完成：{out}（{out.stat().st_size / 1024 / 1024:.1f} MB）")


if __name__ == "__main__":
    if "--mux-only" in sys.argv:
        mux_only()
    else:
        main()

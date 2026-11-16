import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Sparkles, Loader2 } from 'lucide-react';
import { api, auth } from '@/lib/api';

const DEMO = { email: 'demo@agentdesk.dev', password: 'Demo@2026' };

export function LoginPage() {
  const nav = useNavigate();
  const [email, setEmail] = useState(DEMO.email);
  const [password, setPassword] = useState(DEMO.password);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const resp = await api.login(email.trim(), password);
      auth.save(resp);
      nav('/dashboard', { replace: true });
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : '登录失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden bg-ink-900 lg:block">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,#4338ca55,transparent_55%),radial-gradient(circle_at_75%_70%,#0ea5e955,transparent_50%)]" />
        <div className="relative flex h-full flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-2 text-sm">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/15 font-bold">智</span>
            智协台 AgentDesk
          </div>
          <div>
            <h1 className="max-w-[21rem] text-[26px] font-semibold leading-snug">
              让会议记录、文档撰写
              <br />
              与任务跟进
              <br />
              在同一条链路上自动流转
            </h1>
            <p className="mt-4 max-w-md text-sm leading-6 text-white/70">
              六个专职 Agent 协同完成会议理解与文档生产，每一条结论都能回指原始语句，
              模型档位与成本在界面上可见、可控。
            </p>
            <div className="mt-8 grid max-w-md grid-cols-3 gap-3 text-center">
              {[
                ['6', '协同 Agent'],
                ['4', '模型路由档'],
                ['100%', '结论可溯源'],
              ].map(([v, k]) => (
                <div key={k} className="rounded-lg bg-white/10 px-3 py-3 backdrop-blur-sm">
                  <p className="text-lg font-semibold">{v}</p>
                  <p className="mt-0.5 text-[11px] text-white/60">{k}</p>
                </div>
              ))}
            </div>
          </div>
          <p className="text-[11px] text-white/40">哈尔滨信息工程学院 · 孟嘉祺 / 杜春晓</p>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-16">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="mb-6 flex items-center gap-2 lg:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 font-bold text-white">智</span>
            <span className="text-sm font-semibold">智协台 AgentDesk</span>
          </div>
          <h2 className="text-xl font-semibold text-ink-900">登录工作区</h2>
          <p className="mt-1 text-xs text-ink-500">演示账号已预填，可直接进入。</p>

          <div className="mt-6 space-y-3.5">
            <div>
              <label className="label">邮箱</label>
              <input
                className="input"
                value={email}
                autoComplete="username"
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
              />
            </div>
            <div>
              <label className="label">密码</label>
              <input
                className="input"
                type="password"
                value={password}
                autoComplete="current-password"
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
          </div>

          {err && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-600">{err}</p>}

          <button className="btn-primary mt-5 w-full" disabled={busy}>
            {busy ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
            {busy ? '正在进入…' : '进入工作区'}
          </button>

          <button
            type="button"
            className="btn-ghost mt-2 w-full text-xs"
            onClick={() => {
              setEmail(DEMO.email);
              setPassword(DEMO.password);
            }}
          >
            <Sparkles size={13} /> 使用评审演示账号
          </button>

          <p className="mt-6 text-center text-[11px] leading-5 text-ink-400">
            评审专用账号 demo@agentdesk.dev / Demo@2026
          </p>
        </form>
      </div>
    </div>
  );
}

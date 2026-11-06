import { useEffect, useState, type ReactNode } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Mic, PenLine, Library, KanbanSquare, CalendarRange, Activity, Settings,
  Cpu, LogOut, Search, Command,
} from 'lucide-react';
import { clsx } from 'clsx';
import { api, auth } from '@/lib/api';
import { Avatar } from '@/components/ui';

const NAV = [
  { to: '/dashboard', label: '工作台', icon: LayoutDashboard, hint: '全局概览与今日待办' },
  { to: '/meetings', label: '会议纪要', icon: Mic, hint: '转写 → 决议 → 待办' },
  { to: '/docs', label: '智能写作', icon: PenLine, hint: '模板生成与逐句改写' },
  { to: '/kb', label: '知识库', icon: Library, hint: '检索增强问答与引用' },
  { to: '/tasks', label: '任务看板', icon: KanbanSquare, hint: '工时预测与风险' },
  { to: '/weekly', label: '智能周报', icon: CalendarRange, hint: '自动汇总团队产出' },
  { to: '/insights', label: '运行观测', icon: Activity, hint: 'Agent Trace 与成本' },
  { to: '/settings', label: '设置', icon: Settings, hint: '模型路由与脱敏' },
];

const TITLES: Record<string, string> = {
  '/dashboard': '工作台',
  '/meetings': '会议纪要',
  '/docs': '智能写作',
  '/kb': '知识库',
  '/tasks': '任务看板',
  '/weekly': '智能周报',
  '/insights': '运行观测',
  '/settings': '设置',
};

export function AppShell({ children }: { children: ReactNode }) {
  const nav = useNavigate();
  const loc = useLocation();
  const [provider, setProvider] = useState<{ name: string; mock: boolean } | null>(null);
  const user = auth.user;

  useEffect(() => {
    api
      .health()
      .then((h) => setProvider({ name: h.provider, mock: h.mock }))
      .catch(() => setProvider(null));
  }, []);

  const title = TITLES[Object.keys(TITLES).find((k) => loc.pathname.startsWith(k)) || ''] || '智协台';

  return (
    <div className="flex h-full min-h-screen bg-ink-50">
      <aside className="fixed inset-y-0 left-0 z-30 flex w-[228px] flex-col border-r border-ink-200/70 bg-white">
        <div className="flex h-14 items-center gap-2 px-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white shadow-sm">
            智
          </div>
          <div className="leading-tight">
            <p className="text-[13px] font-semibold text-ink-900">智协台</p>
            <p className="text-[10px] tracking-wide text-ink-400">AgentDesk</p>
          </div>
        </div>

        <nav className="mt-1 flex-1 space-y-0.5 px-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition',
                  isActive ? 'bg-brand-50 font-medium text-brand-700' : 'text-ink-600 hover:bg-ink-50 hover:text-ink-900',
                )
              }
              title={item.hint}
            >
              <item.icon size={16} className="shrink-0 opacity-80" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="mx-2 mb-2 rounded-lg border border-ink-100 bg-ink-50/60 p-2.5">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-ink-600">
            <Cpu size={12} />
            推理服务
            <span
              className={clsx(
                'ml-auto rounded px-1.5 py-0.5 text-[10px]',
                provider?.mock ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700',
              )}
            >
              {provider ? (provider.mock ? '离线演示' : '在线') : '检测中'}
            </span>
          </div>
          <p className="mt-1 truncate text-[10px] text-ink-400">{provider?.name || '—'}</p>
        </div>

        <div className="flex items-center gap-2 border-t border-ink-100 px-3 py-2.5">
          <Avatar name={user?.name} size={28} />
          <div className="min-w-0 flex-1 leading-tight">
            <p className="truncate text-[12px] font-medium text-ink-800">{user?.name || '未登录'}</p>
            <p className="truncate text-[10px] text-ink-400">{user?.title || '演示账号'}</p>
          </div>
          <button
            className="btn-ghost h-7 w-7 !p-0"
            title="退出登录"
            onClick={() => {
              auth.clear();
              nav('/login');
            }}
          >
            <LogOut size={14} />
          </button>
        </div>
      </aside>

      <div className="ml-[228px] flex min-h-screen flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-ink-200/70 bg-white/85 px-6 backdrop-blur">
          <h1 className="text-[15px] font-semibold text-ink-900">{title}</h1>
          <span className="chip bg-ink-100 text-ink-500">
            智协实验室 · 演示工作区
          </span>
          <div className="ml-auto flex items-center gap-2 text-xs text-ink-400">
            <kbd className="hidden items-center gap-1 rounded border border-ink-200 bg-white px-1.5 py-0.5 text-[10px] text-ink-400 md:inline-flex">
              <Command size={10} /> K
            </kbd>
            <span className="hidden md:inline">快速跳转</span>
            <button className="btn-ghost btn-sm" onClick={() => nav('/kb')} title="去知识库检索">
              <Search size={14} />
            </button>
          </div>
        </header>
        <main className="flex-1 px-6 py-5">{children}</main>
      </div>
    </div>
  );
}

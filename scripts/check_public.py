import json, sys, time
import httpx

BASE = "https://agentdesk.2007116.xyz"
c = httpx.Client(trust_env=False, timeout=120)

r = c.post(f"{BASE}/api/auth/login", json={"email": "demo@agentdesk.dev", "password": "Demo@2026"})
print("login", r.status_code)
tok = r.json()["token"]
H = {"Authorization": f"Bearer {tok}"}

ov = c.get(f"{BASE}/api/insights/overview", headers=H).json()
print("kpi", json.dumps(ov["kpi"], ensure_ascii=False)[:220])

t0 = time.time()
a = c.post(f"{BASE}/api/kb/ask_sync", headers=H, json={"question": "引用校验的阈值是多少？"}).json()
print(f"kb {time.time()-t0:.1f}s len={len(a['answer'])} cites={len(a['citations'])}")
print("answer:", a["answer"][:140].replace("\n", " "))
for ct in a["citations"][:2]:
    print("cite:", ct.get("doc"), "p", ct.get("page"), ct.get("status"))

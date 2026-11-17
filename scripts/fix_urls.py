import io, pathlib, re

ROOT = pathlib.Path(r"D:\cluaudestudy\agentdesk")
NEW = "https://agentdesk.2007116.xyz"
OLD_TUNNEL = "https://applying-left-rehabilitation-poems.trycloudflare.com"

targets = [
    ROOT / "README.md",
    ROOT / "deploy" / "README.md",
    ROOT / "docs" / "交付清单.md",
]

for p in targets:
    text = p.read_text(encoding="utf-8")
    before = text
    text = text.replace(OLD_TUNNEL, NEW)
    text = text.replace("SITE_ADDRESS=durkmo.eu.cc", "SITE_ADDRESS=agentdesk.2007116.xyz")
    if text != before:
        p.write_text(text, encoding="utf-8")
        print("updated", p.name)
    else:
        print("unchanged", p.name)

# 校验是否还有残留
for p in targets:
    t = p.read_text(encoding="utf-8")
    left = [ln for ln in t.splitlines() if "trycloudflare" in ln or "durkmo" in ln]
    print(p.name, "left:", len(left))
    for ln in left[:3]:
        print("   ", ln.strip()[:110])

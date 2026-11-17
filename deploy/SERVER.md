# 閮ㄧ讲鍒版湇鍔″櫒锛堝煙鍚?agentdesk.2007116.xyz锛?
> 鐩爣锛氳瘎瀹℃湡闂寸數鑴戝叧鏈恒€佹柇缃戯紝`https://agentdesk.2007116.xyz` 渚濈劧鑳芥墦寮€銆?> 鍚庣鏄崟杩涚▼ FastAPI + SQLite锛? 鏍?1G / 20G 鐩樺鐢ㄣ€?
## 鍏堝垽鏂湇鍔″櫒鏄笉鏄湡姝ｃ€屾湁鍏綉 IP銆?
`172.16.29.50` 灞炰簬绉佺綉娈碉紙172.16.0.0/12锛夛紝澶栫綉鍒颁笉浜嗐€備袱绉嶆儏鍐碉細

| 鎯呭喌 | 鍒ゆ柇鏂规硶锛堟湇鍔″櫒涓婃墽琛岋級 | 璧板摢涓柟妗?|
|---|---|---|
| 浜戜富鏈鸿嚜甯﹀叕缃?IP锛堥樋閲?鑵捐/鍗庝负绛夛級 | `curl -4 ifconfig.me` 杩斿洖涓€涓叕缃?IP | **鏂规 A**锛欳addy 鐩存帴绛捐瘉涔︼紝闇€瑕?80/443 鏀捐 |
| 鍙湁鍐呯綉 IP锛屾垨浣嶄簬鍏徃/瀛︽牎 NAT 涔嬪悗 | 鍚屼笂杩斿洖鐨勪粛鏄?172./10./192.168. 娈?| **鏂规 C**锛欳loudflare Tunnel锛屼笉闇€瑕佸叕缃?IP銆佷笉鐢ㄥ紑绔彛 |

澧冨唴涓绘満鐨勯澶栭檺鍒讹細`.xyz` 鏈妗?+ 80/443 缁戝煙鍚嶈繘鍑哄彲鑳借鎷︺€?*鏂规 C 涓嶅彈杩欐潯褰卞搷**锛屽洜涓烘祦閲忔槸鏈嶅姟鍣ㄤ富鍔ㄥ杩?Cloudflare锛屽啀鍥炴簮鍒版湰鏈?HTTP銆?
## 鏂规 C锛欳loudflare Tunnel锛堝唴缃戞湇鍔″櫒棣栭€夛級

闇€瑕侊細鍩熷悕 `2007116.xyz` 宸插湪 Cloudflare 璐﹀彿閲岋紙宸茬‘璁ゅ湪锛孨S 涓?`betty/evan.ns.cloudflare.com`锛夈€?
### C-1 寤洪毀閬擄紙娴忚鍣?1 鍒嗛挓锛?
Cloudflare 鎺у埗鍙?鈫?**Zero Trust** 鈫?**Networks 鈫?Tunnels** 鈫?**Create a tunnel** 鈫?閫?**Cloudflared** 鈫?鍚嶅瓧濉?`agentdesk` 鈫?淇濆瓨鍚庨〉闈㈢粰鍑轰竴涓?token锛坄eyJh...`锛夈€?
鍚屼竴椤靛垏鍒?**Public Hostname** 鏍囩 鈫?**Add a public hostname**锛?
| 瀛楁 | 鍊?|
|---|---|
| Subdomain | `agentdesk` |
| Domain | `2007116.xyz` |
| Type | `HTTP` |
| URL | `localhost:8000` |

淇濆瓨鍚?Cloudflare 鑷姩寤?CNAME锛屼笉闇€瑕佹墜鍔ㄥ姞 A 璁板綍銆?
### C-2 鏈嶅姟鍣ㄤ笂璺戯紙涓€鏉″懡浠わ級

```bash
MODE=tunnel \
SITE_ADDRESS=agentdesk.2007116.xyz \
LLM_API_KEY=sk-浣犵殑key \
CLOUDFLARE_TUNNEL_TOKEN=eyJh...浣犲垰澶嶅埗鐨則oken \
NPM_REGISTRY=https://registry.npmmirror.com \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/vesoandrei181-oss/agentdesk/main/deploy/deploy.sh)"
```

鑴氭湰浼氾細瑁?Docker 鈫?鎷変唬鐮?鈫?鍐?`deploy/.env` 鈫?鏋勫缓闀滃儚锛堝墠绔湪闀滃儚鍐呮瀯寤猴級鈫?鐏屾紨绀烘暟鎹?鈫?`docker-compose.tunnel.yml` 璧?api锛堝彧缁?`127.0.0.1:8000`锛夆啋 瑁?cloudflared 骞舵敞鍐?systemd 鏈嶅姟銆?
### C-3 楠屾敹

```bash
curl -s http://127.0.0.1:8000/api/health      # 鏈満
curl -s https://agentdesk.2007116.xyz/api/health   # 鍏綉
systemctl status cloudflared --no-pager        # 闅ч亾甯搁┗
```

娴忚鍣ㄦ墦寮€ `https://agentdesk.2007116.xyz`锛宍demo@agentdesk.dev` / `Demo@2026` 鐧诲綍銆備箣鍚庢湇鍔″櫒鍏虫満/閲嶅惎閮戒細鑷姩鎭㈠锛坄restart: unless-stopped` + `systemctl enable`锛夈€?
## 鏂规 A锛氭湇鍔″櫒鏈夊叕缃?IP锛孋addy 鐩存帴绛捐瘉涔?
瑙佹枃鏈€屾墜鍔ㄩ儴缃层€嶏紝鎴栵細

```bash
SITE_ADDRESS=agentdesk.2007116.xyz LLM_API_KEY=sk-浣犵殑key bash deploy/deploy.sh
```

鍓嶆彁锛欴NS 閲?`agentdesk` 鐨?A 璁板綍鎸囧悜璇ュ叕缃?IP锛堢伆浜?/ DNS only锛夛紝浜戝巶鍟嗗畨鍏ㄧ粍鏀捐 80/443銆?
## 鎵嬪姩閮ㄧ讲锛堜笉鐢ㄨ剼鏈級

```bash
curl -fsSL https://get.docker.com | sh
git clone https://github.com/vesoandrei181-oss/agentdesk.git /opt/agentdesk
cd /opt/agentdesk
cp deploy/.env.example deploy/.env && nano deploy/.env   # 濉?LLM_API_KEY / SECRET_KEY / SITE_ADDRESS

# 鏈夊叕缃?IP
docker compose -f deploy/docker-compose.yml up -d --build
# 鍐呯綉 / 璧伴毀閬?docker compose -f deploy/docker-compose.tunnel.yml up -d --build

docker compose -f deploy/docker-compose.yml run --rm --entrypoint python api apps/api/seed/demo.py --force
```

## 4. 涓嶇敤 Docker 鐨勮８鏈烘柟妗堬紙鍙€夛級

```bash
apt-get update && apt-get install -y python3.12-venv python3-pip caddy
cd /opt/agentdesk
python3 -m venv .venv && .venv/bin/pip install -r apps/api/requirements.txt
mkdir -p apps/web/dist && cp -r <鏈湴鏋勫缓濂界殑 dist>/* apps/web/dist/   # 鎴?scp -r 涓婁紶
PYTHONPATH=apps/api .venv/bin/python apps/api/seed/demo.py --force
```

systemd 鍗曞厓 `/etc/systemd/system/agentdesk.service`锛?
```ini
[Unit]
Description=AgentDesk
After=network.target

[Service]
WorkingDirectory=/opt/agentdesk
Environment=PYTHONPATH=/opt/agentdesk/apps/api
Environment=LLM_API_KEY=sk-浣犵殑key
Environment=SECRET_KEY=鎹㈡垚闅忔満涓?ExecStart=/opt/agentdesk/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
```

`/etc/caddy/Caddyfile`锛?
```
agentdesk.2007116.xyz {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8000
}
```

```bash
systemctl daemon-reload && systemctl enable --now agentdesk caddy
```

## 5. 涓婄嚎鍚庤鏀圭殑鏂囦欢

鍩熷悕鐢熸晥鍚庯紝鎶婅繖涓夊 URL 浠?`*.trycloudflare.com` 鎹㈡垚 `https://agentdesk.2007116.xyz`锛岀劧鍚庢彁浜わ細

- `README.md` 椤堕儴銆屽湪绾挎紨绀恒€?- `deploy/README.md` 椤堕儴銆屽綋鍓嶅湪绾挎紨绀恒€?- `docs/浜や粯娓呭崟.md` 绗?13 琛?
## 6. 甯歌闂

| 鐜拌薄 | 鍘熷洜 | 澶勭悊 |
|---|---|---|
| 璇佷功鐢宠澶辫触 | 80/443 娌℃斁琛岋紝鎴?DNS 杩樻病鐢熸晥 | 瀹夊叏缁勬斁琛?+ `dig agentdesk.2007116.xyz` 纭 |
| 502 | api 瀹瑰櫒娌¤捣鏉?| `docker compose logs api`锛屽鍗婃槸 `LLM_API_KEY` 涓虹┖ |
| 椤甸潰 404 鐧藉睆 | 鏋勫缓浜х墿璺緞涓嶅 | 纭闀滃儚閲?`/app/apps/web/dist/index.html` 瀛樺湪 |
| 鐧诲綍鎶?401 鍙嶅璺宠浆 | `SECRET_KEY` 鍙樹簡瀵艰嚧鏃?token 澶辨晥 | 閲嶆柊鐧诲綍鍗冲彲 |
| 涓枃瀵煎嚭 Word 涔辩爜 | 闀滃儚缂哄瓧浣?| Dockerfile 閲屽凡瑁?`fonts-noto-cjk`锛岃８鏈烘柟妗堣 `apt install fonts-noto-cjk` |

"""Instagram: Reels e métricas. Dois modos:
- "facebook": login do Facebook + Página ligada ao Instagram (graph.facebook.com, token da Página não vence).
- "instagram": login do Instagram (graph.instagram.com, token de 60 dias renovado a cada 7)."""
import time
import requests
from comum import segredo, app_id, checar, agora

G_IG = "https://graph.instagram.com/v23.0"
G_FB = "https://graph.facebook.com/v23.0"


def _g(ig):
    return G_FB if ig.get("modo") == "facebook" else G_IG
ESCOPOS = "instagram_business_basic,instagram_business_content_publish,instagram_business_manage_insights,instagram_business_manage_comments"


def trocar_codigo(codigo, redirect):
    codigo = codigo.split("#")[0]
    if _modo_app() == "facebook":
        return _trocar_fb(codigo, redirect)
    curto = checar(requests.post("https://api.instagram.com/oauth/access_token", data={
        "client_id": app_id("instagram"), "client_secret": segredo("IG_APP_SECRET"),
        "grant_type": "authorization_code", "redirect_uri": redirect, "code": codigo}, timeout=60)).json()
    longo = checar(requests.get("https://graph.instagram.com/access_token", params={
        "grant_type": "ig_exchange_token", "client_secret": segredo("IG_APP_SECRET"),
        "access_token": curto["access_token"]}, timeout=60)).json()
    return {"token": longo["access_token"], "user_id": str(curto["user_id"]), "renovado": agora().isoformat()}


def _modo_app():
    import json
    from comum import APPS
    try:
        return json.loads(APPS.read_text()).get("instagram_modo", "instagram")
    except Exception:
        return "instagram"


def _trocar_fb(codigo, redirect):
    curto = checar(requests.get(f"{G_FB}/oauth/access_token", params={
        "client_id": app_id("instagram"), "client_secret": segredo("IG_APP_SECRET"),
        "redirect_uri": redirect, "code": codigo}, timeout=60)).json()
    longo = checar(requests.get(f"{G_FB}/oauth/access_token", params={
        "grant_type": "fb_exchange_token", "client_id": app_id("instagram"), "client_secret": segredo("IG_APP_SECRET"),
        "fb_exchange_token": curto["access_token"]}, timeout=60)).json()
    pags = checar(requests.get(f"{G_FB}/me/accounts", params={
        "fields": "id,name,access_token,instagram_business_account{id,username}", "access_token": longo["access_token"]},
        timeout=60)).json().get("data", [])
    for p in pags:
        ig = p.get("instagram_business_account")
        if ig:
            print(f"Página {p['name']} -> Instagram @{ig.get('username')}")
            return {"modo": "facebook", "token": p["access_token"], "user_id": ig["id"],
                    "pagina": p["name"], "renovado": agora().isoformat()}
    raise RuntimeError("Nenhuma Página com Instagram ligado foi autorizada. Ligue o Instagram do Nino na Página e conecte de novo.")


def renovar(cofre):
    """O token dura 60 dias; renovamos a cada 7 para nunca vencer."""
    from datetime import datetime
    ig = cofre["instagram"]
    if ig.get("modo") == "facebook":
        return False  # token de Página não vence
    if (agora() - datetime.fromisoformat(ig["renovado"])).days < 7:
        return False
    r = checar(requests.get("https://graph.instagram.com/refresh_access_token", params={
        "grant_type": "ig_refresh_token", "access_token": ig["token"]}, timeout=60)).json()
    ig["token"], ig["renovado"] = r["access_token"], agora().isoformat()
    return True


def _ja_postado(G, uid, tk, legenda):
    import datetime
    r = requests.get(f"{G}/{uid}/media", params={"fields": "id,caption,timestamp,permalink", "limit": 15, "access_token": tk}, timeout=60)
    if not r.ok:
        return None
    agora = datetime.datetime.now(datetime.timezone.utc)
    for m in r.json().get("data", []):
        try:
            quando = datetime.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        except Exception:
            continue
        if (m.get("caption") or "").strip() == legenda.strip() and agora - quando < datetime.timedelta(hours=24):
            print("   Instagram: essa legenda já foi postada, não vou repetir:", m.get("permalink"))
            return {"id": m["id"], "link": m.get("permalink", ""), "obs": "já estava postado (trava contra duplicado)"}
    return None


def postar(cofre, post, arquivo, cfg):
    ig = cofre["instagram"]
    tk, uid = ig["token"], ig["user_id"]
    G = _g(ig)
    # Trava contra post duplicado: se a mesma legenda já saiu nas últimas 24 h, não posta de novo.
    ja = _ja_postado(G, uid, tk, post["legenda"])
    if ja:
        return ja
    c = checar(requests.post(f"{G}/{uid}/media", data={
        "media_type": "REELS", "video_url": post["video"], "caption": post["legenda"],
        "share_to_feed": "true", "access_token": tk}, timeout=120)).json()
    cid = c["id"]
    for _ in range(60):  # até 10 minutos processando
        time.sleep(10)
        s = checar(requests.get(f"{G}/{cid}", params={"fields": "status_code,status", "access_token": tk}, timeout=60)).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram recusou o vídeo: {s}")
    else:
        raise RuntimeError("Instagram demorou demais para processar o vídeo.")
    m = checar(requests.post(f"{G}/{uid}/media_publish", data={"creation_id": cid, "access_token": tk}, timeout=120)).json()
    mid = m["id"]
    info = requests.get(f"{G}/{mid}", params={"fields": "permalink", "access_token": tk}, timeout=60).json()
    saida = {"id": mid, "link": info.get("permalink", "")}
    if post.get("comentario"):
        try:
            checar(requests.post(f"{G}/{mid}/comments", data={"message": post["comentario"], "access_token": tk}, timeout=60))
            saida["comentario"] = "feito (fixar no app)"
        except Exception as e:
            saida["comentario"] = f"falhou: {e}"
    return saida


NOMES_IG = {"saved": "salvos", "shares": "compartilhamentos", "reach": "alcance", "follows": "seguidores_ganhos",
            "profile_visits": "visitas_perfil", "total_interactions": "interacoes",
            "ig_reels_avg_watch_time": "tempo_medio_ms", "ig_reels_video_view_total_time": "tempo_total_ms",
            "reels_skip_rate": "pularam_pct"}
METRICAS_REEL = ["views", "reach", "saved", "shares", "total_interactions", "ig_reels_avg_watch_time",
                 "ig_reels_video_view_total_time", "follows", "profile_visits", "reels_skip_rate"]


def _insights_midia(G, mid, tk, tipo):
    """Pede tudo de uma vez; se a Meta recusar alguma métrica, pede uma por uma e pula as que não existem."""
    lista = METRICAS_REEL if tipo == "REELS" else ["views", "reach", "saved", "shares", "total_interactions"]
    out = {}
    r = requests.get(f"{G}/{mid}/insights", params={"metric": ",".join(lista), "access_token": tk}, timeout=60)
    dados = r.json().get("data", []) if r.ok else []
    if not r.ok:
        for m in lista:
            r1 = requests.get(f"{G}/{mid}/insights", params={"metric": m, "access_token": tk}, timeout=60)
            if r1.ok:
                dados += r1.json().get("data", [])
    for d in dados:
        vals = d.get("values") or [{}]
        out[NOMES_IG.get(d["name"], d["name"])] = vals[0].get("value", d.get("total_value", {}).get("value"))
    return out


def _seguidores_por_dia(G, uid, tk):
    """Seguidores novos por dia nos últimos 30 dias (a Meta só dá isso para contas com 100+ seguidores)."""
    import time
    fim = int(time.time()); ini = fim - 29 * 86400
    r = requests.get(f"{G}/{uid}/insights", params={"metric": "follower_count", "period": "day",
                                                    "since": ini, "until": fim, "access_token": tk}, timeout=60)
    if not r.ok:
        return []
    vals = (r.json().get("data") or [{}])[0].get("values", [])
    return [{"data": v["end_time"][:10], "novos": v.get("value", 0)} for v in vals]


def metricas(cofre):
    ig = cofre["instagram"]
    tk, G, uid = ig["token"], _g(ig), ig["user_id"]
    eu = checar(requests.get(f"{G}/{uid}", params={"fields": "username,followers_count,media_count", "access_token": tk}, timeout=60)).json()
    lista = checar(requests.get(f"{G}/{uid}/media", params={
        "fields": "id,caption,timestamp,permalink,like_count,comments_count,media_product_type",
        "limit": 50, "access_token": tk}, timeout=60)).json().get("data", [])
    videos = []
    for m in lista:
        v = {"id": m["id"], "titulo": (m.get("caption") or "")[:60], "data": m.get("timestamp"),
             "link": m.get("permalink"), "likes": m.get("like_count", 0), "comentarios": m.get("comments_count", 0)}
        v.update(_insights_midia(G, m["id"], tk, m.get("media_product_type")))
        for k in ("tempo_medio_ms", "tempo_total_ms"):
            if isinstance(v.get(k), (int, float)):
                v[k.replace("_ms", "_s")] = round(v.pop(k) / 1000, 1)
        videos.append(v)
    return {"conta": eu.get("username"), "seguidores": eu.get("followers_count", 0), "videos": videos,
            "seguidores_por_dia": _seguidores_por_dia(G, uid, tk)}

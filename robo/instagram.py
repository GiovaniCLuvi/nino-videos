"""Instagram: Reels e métricas pela "Instagram API com login do Instagram" (sem página do Facebook)."""
import time
import requests
from comum import segredo, app_id, checar, agora

G = "https://graph.instagram.com/v23.0"
ESCOPOS = "instagram_business_basic,instagram_business_content_publish,instagram_business_manage_insights,instagram_business_manage_comments"


def trocar_codigo(codigo, redirect):
    codigo = codigo.split("#")[0]
    curto = checar(requests.post("https://api.instagram.com/oauth/access_token", data={
        "client_id": app_id("instagram"), "client_secret": segredo("IG_APP_SECRET"),
        "grant_type": "authorization_code", "redirect_uri": redirect, "code": codigo}, timeout=60)).json()
    longo = checar(requests.get("https://graph.instagram.com/access_token", params={
        "grant_type": "ig_exchange_token", "client_secret": segredo("IG_APP_SECRET"),
        "access_token": curto["access_token"]}, timeout=60)).json()
    return {"token": longo["access_token"], "user_id": str(curto["user_id"]), "renovado": agora().isoformat()}


def renovar(cofre):
    """O token dura 60 dias; renovamos a cada 7 para nunca vencer."""
    from datetime import datetime
    ig = cofre["instagram"]
    if (agora() - datetime.fromisoformat(ig["renovado"])).days < 7:
        return False
    r = checar(requests.get("https://graph.instagram.com/refresh_access_token", params={
        "grant_type": "ig_refresh_token", "access_token": ig["token"]}, timeout=60)).json()
    ig["token"], ig["renovado"] = r["access_token"], agora().isoformat()
    return True


def postar(cofre, post, arquivo, cfg):
    ig = cofre["instagram"]
    tk, uid = ig["token"], ig["user_id"]
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


def metricas(cofre):
    ig = cofre["instagram"]
    tk = ig["token"]
    eu = checar(requests.get(f"{G}/me", params={"fields": "username,followers_count,media_count", "access_token": tk}, timeout=60)).json()
    lista = checar(requests.get(f"{G}/me/media", params={
        "fields": "id,caption,timestamp,permalink,like_count,comments_count,media_product_type",
        "limit": 50, "access_token": tk}, timeout=60)).json().get("data", [])
    videos = []
    for m in lista:
        v = {"id": m["id"], "titulo": (m.get("caption") or "")[:60], "data": m.get("timestamp"),
             "link": m.get("permalink"), "likes": m.get("like_count", 0), "comentarios": m.get("comments_count", 0)}
        for metr in ("views,reach,saved,shares", "reach,saved,shares"):
            r = requests.get(f"{G}/{m['id']}/insights", params={"metric": metr, "access_token": tk}, timeout=60)
            if r.ok:
                for d in r.json().get("data", []):
                    v[{"saved": "salvos", "shares": "compartilhamentos", "reach": "alcance"}.get(d["name"], d["name"])] = d["values"][0]["value"]
                break
        videos.append(v)
    return {"conta": eu.get("username"), "seguidores": eu.get("followers_count", 0), "videos": videos}

"""TikTok: Content Posting API. Modo "rascunho" (vai para a caixa de entrada do app, você toca em Publicar)
ou "direto" (posta sozinho; antes da auditoria do TikTok só sai como privado)."""
import os, time
import requests
from comum import segredo, app_id, checar

API = "https://open.tiktokapis.com/v2"
ESCOPOS = "user.info.basic,user.info.stats,video.list,video.upload,video.publish"


def trocar_codigo(codigo, redirect):
    r = checar(requests.post(f"{API}/oauth/token/", data={
        "client_key": app_id("tiktok"), "client_secret": segredo("TT_CLIENT_SECRET"),
        "code": codigo, "grant_type": "authorization_code", "redirect_uri": redirect}, timeout=60)).json()
    if "access_token" not in r:
        raise RuntimeError(f"TikTok recusou o código: {r}")
    return {"access": r["access_token"], "refresh": r["refresh_token"],
            "vence": time.time() + r["expires_in"] - 300, "escopos": r.get("scope", "")}


def renovar(cofre):
    tt = cofre["tiktok"]
    if time.time() < tt["vence"]:
        return False
    r = checar(requests.post(f"{API}/oauth/token/", data={
        "client_key": app_id("tiktok"), "client_secret": segredo("TT_CLIENT_SECRET"),
        "grant_type": "refresh_token", "refresh_token": tt["refresh"]}, timeout=60)).json()
    tt.update(access=r["access_token"], refresh=r.get("refresh_token", tt["refresh"]), vence=time.time() + r["expires_in"] - 300)
    return True


def _h(cofre):
    return {"Authorization": f"Bearer {cofre['tiktok']['access']}", "Content-Type": "application/json; charset=UTF-8"}


def postar(cofre, post, arquivo, cfg):
    renovar(cofre)
    tam = os.path.getsize(arquivo)
    pedaco = tam if tam <= 64_000_000 else 10_000_000
    n = 1 if pedaco == tam else tam // pedaco
    fonte = {"source": "FILE_UPLOAD", "video_size": tam, "chunk_size": pedaco, "total_chunk_count": n}
    modo = cfg.get("tiktok_modo", "rascunho")
    if modo == "direto":
        corpo = {"post_info": {"title": post["legenda"][:2200], "privacy_level": cfg.get("tiktok_privacidade", "SELF_ONLY"),
                               "is_aigc": True, "disable_comment": False, "disable_duet": False, "disable_stitch": False},
                 "source_info": fonte}
        url = f"{API}/post/publish/video/init/"
    else:
        corpo, url = {"source_info": fonte}, f"{API}/post/publish/inbox/video/init/"
    r = checar(requests.post(url, headers=_h(cofre), json=corpo, timeout=60)).json()
    if r.get("error", {}).get("code", "ok") != "ok":
        raise RuntimeError(f"TikTok: {r['error']}")
    up, pid = r["data"]["upload_url"], r["data"]["publish_id"]
    with open(arquivo, "rb") as f:
        for i in range(n):
            ini = i * pedaco
            fim = tam - 1 if i == n - 1 else ini + pedaco - 1
            f.seek(ini)
            dados = f.read(fim - ini + 1)
            checar(requests.put(up, data=dados, timeout=900, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(dados)),
                "Content-Range": f"bytes {ini}-{fim}/{tam}"}))
    estado = "?"
    for _ in range(30):
        time.sleep(10)
        s = requests.post(f"{API}/post/publish/status/fetch/", headers=_h(cofre), json={"publish_id": pid}, timeout=60).json()
        estado = s.get("data", {}).get("status", "?")
        if estado in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            break
        if estado == "FAILED":
            raise RuntimeError(f"TikTok falhou: {s.get('data', {}).get('fail_reason')}")
    return {"id": pid, "estado": estado, "modo": modo}


def metricas(cofre):
    renovar(cofre)
    u = checar(requests.get(f"{API}/user/info/", headers=_h(cofre), params={
        "fields": "display_name,follower_count,likes_count,video_count"}, timeout=60)).json()["data"]["user"]
    vids = checar(requests.post(f"{API}/video/list/", headers=_h(cofre), params={
        "fields": "id,title,create_time,share_url,view_count,like_count,comment_count,share_count"},
        json={"max_count": 20}, timeout=60)).json().get("data", {}).get("videos", [])
    return {"conta": u.get("display_name"), "seguidores": u.get("follower_count", 0), "curtidas_total": u.get("likes_count", 0),
            "videos": [{"id": v["id"], "titulo": (v.get("title") or "")[:60], "data": v.get("create_time"), "link": v.get("share_url"),
                        "views": v.get("view_count", 0), "likes": v.get("like_count", 0),
                        "comentarios": v.get("comment_count", 0), "compartilhamentos": v.get("share_count", 0)} for v in vids]}

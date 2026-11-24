"""YouTube: envio de Shorts e métricas pela YouTube Data API v3."""
import os
import requests
from comum import segredo, app_id, checar

ESCOPOS = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/yt-analytics.readonly"


def trocar_codigo(codigo, redirect):
    r = checar(requests.post("https://oauth2.googleapis.com/token", data={
        "code": codigo, "client_id": app_id("youtube"), "client_secret": segredo("YT_CLIENT_SECRET"),
        "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=60)).json()
    if "refresh_token" not in r:
        raise RuntimeError("O Google não mandou refresh_token. Tire o acesso do app em myaccount.google.com/permissions e conecte de novo.")
    return {"refresh_token": r["refresh_token"]}


def _token(cofre):
    r = checar(requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": app_id("youtube"), "client_secret": segredo("YT_CLIENT_SECRET"),
        "refresh_token": cofre["youtube"]["refresh_token"], "grant_type": "refresh_token"}, timeout=60)).json()
    return r["access_token"]


def postar(cofre, post, arquivo, cfg):
    tk = _token(cofre)
    titulo = (post.get("titulo") or post["legenda"])[:95]
    if "#shorts" not in titulo.lower() and len(titulo) < 88:
        titulo += " #shorts"
    corpo = {
        "snippet": {"title": titulo, "description": post.get("descricao_youtube", post["legenda"]),
                    "categoryId": "1", "defaultLanguage": "pt-BR", "defaultAudioLanguage": "pt-BR",
                    "tags": [t.strip("#") for t in post["legenda"].split() if t.startswith("#")]},
        "status": {"privacyStatus": cfg.get("youtube_privacidade", "public"),
                   "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    tam = os.path.getsize(arquivo)
    ini = checar(requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {tk}", "X-Upload-Content-Type": "video/mp4",
                 "X-Upload-Content-Length": str(tam)}, json=corpo, timeout=60))
    with open(arquivo, "rb") as f:
        r = checar(requests.put(ini.headers["Location"], data=f,
                                headers={"Content-Type": "video/mp4", "Content-Length": str(tam)}, timeout=1800)).json()
    return {"id": r["id"], "link": f"https://youtube.com/shorts/{r['id']}",
            "privacidade": r.get("status", {}).get("privacyStatus")}


def metricas(cofre):
    tk = _token(cofre)
    h = {"Authorization": f"Bearer {tk}"}
    canal = checar(requests.get("https://www.googleapis.com/youtube/v3/channels",
                                params={"part": "statistics,contentDetails,snippet", "mine": "true"}, headers=h, timeout=60)).json()["items"][0]
    lista = canal["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = []
    pl = checar(requests.get("https://www.googleapis.com/youtube/v3/playlistItems",
                             params={"part": "contentDetails", "playlistId": lista, "maxResults": 50}, headers=h, timeout=60)).json()
    ids = [i["contentDetails"]["videoId"] for i in pl.get("items", [])]
    videos = []
    if ids:
        vs = checar(requests.get("https://www.googleapis.com/youtube/v3/videos",
                                 params={"part": "statistics,snippet,status", "id": ",".join(ids)}, headers=h, timeout=60)).json()
        for v in vs.get("items", []):
            s = v["statistics"]
            videos.append({"id": v["id"], "titulo": v["snippet"]["title"], "data": v["snippet"]["publishedAt"],
                           "privacidade": v["status"]["privacyStatus"], "link": f"https://youtube.com/shorts/{v['id']}",
                           "views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                           "comentarios": int(s.get("commentCount", 0))})
    st = canal["statistics"]
    saida = {"conta": canal["snippet"]["title"], "seguidores": int(st.get("subscriberCount", 0)),
             "views_total": int(st.get("viewCount", 0)), "videos": videos}
    try:
        _analytics(h, videos, saida)
    except Exception as e:  # sem a permissão de Analytics ainda: segue só com o básico
        saida["aviso_analytics"] = str(e)[:200]
    return saida


def _analytics(h, videos, saida):
    """YouTube Analytics: tempo assistido, % assistido e inscritos ganhos por vídeo, mais inscritos por dia."""
    import datetime
    hoje = datetime.date.today()
    base = {"ids": "channel==MINE", "startDate": "2026-11-01", "endDate": hoje.isoformat()}
    U = "https://youtubeanalytics.googleapis.com/v2/reports"
    r = checar(requests.get(U, headers=h, timeout=60, params={**base, "dimensions": "video", "sort": "-views", "maxResults": 200,
        "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,shares"})).json()
    cols = [c["name"] for c in r.get("columnHeaders", [])]
    por_id = {l[0]: dict(zip(cols, l)) for l in r.get("rows", [])}
    for v in videos:
        a = por_id.get(v["id"])
        if a:
            v.update({"tempo_medio_s": a.get("averageViewDuration"), "assistido_pct": round(a.get("averageViewPercentage") or 0, 1),
                      "seguidores_ganhos": a.get("subscribersGained"), "compartilhamentos": a.get("shares"),
                      "tempo_total_s": round((a.get("estimatedMinutesWatched") or 0) * 60)})
    d = checar(requests.get(U, headers=h, timeout=60, params={**base, "startDate": (hoje - datetime.timedelta(days=29)).isoformat(),
        "dimensions": "day", "metrics": "subscribersGained,subscribersLost"})).json()
    saida["seguidores_por_dia"] = [{"data": l[0], "novos": (l[1] or 0) - (l[2] or 0)} for l in d.get("rows", [])]

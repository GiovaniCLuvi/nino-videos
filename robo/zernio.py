"""TikTok via Zernio (app já aprovado pelo TikTok): publica direto, público, sozinho.
Precisa do secret ZERNIO_API_KEY e da conta TikTok conectada no painel do Zernio."""
import os, time
import requests

API = "https://zernio.com/api/v1"


def _h():
    chave = os.environ.get("ZERNIO_API_KEY")
    if not chave:
        raise RuntimeError("falta o secret ZERNIO_API_KEY")
    return {"Authorization": f"Bearer {chave}", "Content-Type": "application/json"}


def conta_tiktok():
    r = requests.get(f"{API}/accounts", headers=_h(), timeout=60)
    r.raise_for_status()
    contas = r.json().get("accounts", [])
    tk = [c for c in contas if c.get("platform") == "tiktok"]
    if not tk:
        raise RuntimeError("nenhuma conta TikTok conectada no Zernio")
    return tk[0]["_id"], tk[0].get("username") or tk[0].get("displayName")


def postar(post, cfg):
    conta, nome = conta_tiktok()
    corpo = {
        "content": post["legenda"][:2200],
        "mediaItems": [{"type": "video", "url": post["video"]}],
        "platforms": [{"platform": "tiktok", "accountId": conta}],
        "tiktokSettings": {
            "privacy_level": cfg.get("tiktok_privacidade_zernio", "PUBLIC_TO_EVERYONE"),
            "allow_comment": True, "allow_duet": True, "allow_stitch": True,
            "videoMadeWithAi": True,
            "content_preview_confirmed": True, "express_consent_given": True,
        },
        "publishNow": True,
    }
    r = requests.post(f"{API}/posts", headers={**_h(), "Idempotency-Key": post["id"] + "-tiktok"}, json=corpo, timeout=120)
    if r.status_code >= 300:
        raise RuntimeError(f"Zernio {r.status_code}: {r.text[:300]}")
    p = r.json().get("post") or r.json()
    pid = p.get("_id") or p.get("id")
    estado, link = p.get("status", "?"), None
    for _ in range(30):
        if estado in ("published", "failed", "partial", "cancelled"):
            break
        time.sleep(10)
        p = requests.get(f"{API}/posts/{pid}", headers=_h(), timeout=60).json().get("post", {})
        estado = p.get("status", "?")
    for pl in p.get("platforms", []):
        link = pl.get("platformPostUrl") or link
        if pl.get("status") == "failed":
            raise RuntimeError(f"Zernio/TikTok falhou: {str(pl.get('error') or pl.get('errorMessage') or pl)[:300]}")
    if estado == "failed":
        raise RuntimeError(f"Zernio falhou: {str(p)[:300]}")
    return {"id": pid, "estado": estado, "modo": "zernio", "conta": nome, "link": link}

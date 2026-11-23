"""Peças comuns do robô: cofre de senhas, agenda, horário de Brasília."""
import base64, hashlib, json, os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RAIZ = Path(__file__).resolve().parent.parent
COFRE = RAIZ / "robo" / "cofre.json"      # tokens criptografados (o repositório é público)
FILA = RAIZ / "agenda" / "fila.json"
APPS = RAIZ / "docs" / "apps.json"        # ids públicos dos apps (não são segredo)
BRT = timezone(timedelta(hours=-3))
REDIRECT = "https://giovanicluvi.github.io/nino-videos/conectar.html"


def agora():
    return datetime.now(BRT)


def _chave():
    senha = os.environ.get("COFRE_CHAVE", "")
    if len(senha) < 12:
        raise SystemExit("Falta o segredo COFRE_CHAVE (mínimo 12 caracteres) no GitHub.")
    return hashlib.sha256(senha.encode()).digest()


def ler_cofre():
    if not COFRE.exists():
        return {}
    pacote = json.loads(COFRE.read_text())
    bruto = AESGCM(_chave()).decrypt(base64.b64decode(pacote["n"]), base64.b64decode(pacote["d"]), None)
    return json.loads(bruto)


def gravar_cofre(dados):
    n = os.urandom(12)
    d = AESGCM(_chave()).encrypt(n, json.dumps(dados).encode(), None)
    COFRE.write_text(json.dumps({"n": base64.b64encode(n).decode(), "d": base64.b64encode(d).decode()}) + "\n")


def segredo(nome):
    v = os.environ.get(nome, "").strip()
    if not v:
        raise RuntimeError(f"Falta o segredo {nome} no GitHub (Settings > Secrets > Actions).")
    return v


def app_id(rede):
    """Id público do app (client id). Vem do segredo ou do apps.json."""
    nomes = {"youtube": "YT_CLIENT_ID", "instagram": "IG_APP_ID", "tiktok": "TT_CLIENT_KEY"}
    v = os.environ.get(nomes[rede], "").strip()
    if v:
        return v
    if APPS.exists():
        v = json.loads(APPS.read_text()).get(rede, "")
    if not v:
        raise RuntimeError(f"Falta o id do app de {rede} ({nomes[rede]}).")
    return v


def ler_fila():
    return json.loads(FILA.read_text()) if FILA.exists() else {"posts": []}


def gravar_fila(fila):
    FILA.write_text(json.dumps(fila, ensure_ascii=False, indent=2) + "\n")


def baixar(url, destino):
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for parte in r.iter_content(1 << 20):
                f.write(parte)
    return destino


def checar(r):
    if r.status_code >= 400:
        raise RuntimeError(f"{r.request.method} {r.url.split('?')[0]} -> {r.status_code}: {r.text[:500]}")
    return r

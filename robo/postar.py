"""Roda a cada 15 minutos no GitHub Actions: posta o que estiver na hora em agenda/fila.json."""
import os, sys, tempfile, traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import requests
from comum import agora, ler_cofre, gravar_cofre, ler_fila, gravar_fila, baixar
import youtube, instagram, tiktok, zernio

REDES = {"youtube": youtube, "instagram": instagram, "tiktok": tiktok}
MAX_TENTATIVAS = 3


def aviso_tiktok(post, res):
    """No modo rascunho o TikTok não recebe legenda: abre um aviso (issue) com o texto pronto pra copiar."""
    tk, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (tk and repo):
        return
    corpo = ("O vídeo já está nos **rascunhos / caixa de entrada do TikTok** (abra o app, toque no aviso de vídeo novo).\n\n"
             "Ao publicar: cole a legenda abaixo e marque **Conteúdo gerado por IA**.\n\n"
             f"**Legenda:**\n```\n{post['legenda']}\n```\n")
    if post.get("comentario"):
        corpo += f"\n**Comentário para fixar:**\n```\n{post['comentario']}\n```\n"
    corpo += "\nDepois de publicar, pode fechar este aviso."
    requests.post(f"https://api.github.com/repos/{repo}/issues", timeout=60,
                  headers={"Authorization": f"Bearer {tk}", "Accept": "application/vnd.github+json"},
                  json={"title": f"TikTok: publicar \"{post.get('titulo') or post['id']}\"", "body": corpo})


def main():
    simular = os.environ.get("SIMULAR") == "1"
    fila = ler_fila()
    cfg = fila.get("config", {})
    atraso_max = timedelta(hours=cfg.get("atraso_max_horas", 6))
    cofre = ler_cofre()
    mudou_fila = mudou_cofre = False
    agora_ = agora()

    for post in fila.get("posts", []):
        quando = datetime.fromisoformat(post["quando"])
        if quando > agora_:
            continue
        arquivo = None
        for rede, st in post.get("redes", {}).items():
            if st.get("status") not in ("pendente", "erro") or st.get("tentativas", 0) >= MAX_TENTATIVAS:
                continue
            if rede in cfg.get("redes_pausadas", []):
                if st.get("status") != "pausada":
                    st.update(status="pausada", motivo="rede pausada em config.redes_pausadas")
                    mudou_fila = True
                continue
            if agora_ - quando > atraso_max:
                st.update(status="perdido", motivo=f"passou mais de {atraso_max} do horário sem conseguir postar")
                mudou_fila = True
                continue
            via_zernio = rede == "tiktok" and cfg.get("tiktok_modo") == "zernio"
            if rede not in cofre and not via_zernio:
                if st.get("motivo") != "rede ainda não conectada":
                    st["motivo"] = "rede ainda não conectada"
                    mudou_fila = True
                continue
            print(f"[{agora_:%d/%m %H:%M}] {post['id']} -> {rede}")
            if simular:
                print("   (simulação: não postei)")
                continue
            try:
                if via_zernio:
                    res = zernio.postar(post, cfg)
                    st.clear()
                    st.update(status="postado", em=agora().isoformat(timespec="minutes"), **res)
                    print("   ok:", res)
                    mudou_fila = True
                    continue
                if arquivo is None and rede != "instagram":
                    arquivo = baixar(post["video"], os.path.join(tempfile.gettempdir(), "video.mp4"))
                if rede == "instagram":
                    instagram.renovar(cofre)
                res = REDES[rede].postar(cofre, post, arquivo, cfg)
                st.clear()
                st.update(status="postado", em=agora().isoformat(timespec="minutes"), **res)
                if rede == "tiktok" and res.get("modo") == "rascunho":
                    st["status"] = "rascunho_no_tiktok"
                    aviso_tiktok(post, res)
                print("   ok:", res)
            except Exception as e:
                traceback.print_exc()
                st.update(status="erro", tentativas=st.get("tentativas", 0) + 1, motivo=str(e)[:400],
                          em=agora().isoformat(timespec="minutes"))
            mudou_fila = mudou_cofre = True

    if mudou_cofre and cofre:
        gravar_cofre(cofre)
    if mudou_fila:
        gravar_fila(fila)
    print("Fim do ciclo.", "Mudou a agenda." if mudou_fila else "Nada pra postar agora.")


if __name__ == "__main__":
    main()

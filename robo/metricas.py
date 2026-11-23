"""Roda 1 vez por dia: puxa as métricas das 3 redes e renova os acessos que estão perto de vencer."""
import csv, json, sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from comum import RAIZ, agora, ler_cofre, gravar_cofre
import youtube, instagram, tiktok

REDES = {"youtube": youtube, "instagram": instagram, "tiktok": tiktok}

if __name__ == "__main__":
    cofre = ler_cofre()
    mudou = False
    if "instagram" in cofre:
        mudou |= instagram.renovar(cofre)
    if "tiktok" in cofre:
        mudou |= tiktok.renovar(cofre)
    saida = {"atualizado": agora().isoformat(timespec="minutes"), "redes": {}}
    for nome, mod in REDES.items():
        if nome not in cofre:
            saida["redes"][nome] = {"erro": "rede ainda não conectada"}
            continue
        try:
            saida["redes"][nome] = mod.metricas(cofre)
        except Exception as e:
            traceback.print_exc()
            saida["redes"][nome] = {"erro": str(e)[:300]}
    if mudou:
        gravar_cofre(cofre)
    dados = RAIZ / "dados"
    dados.mkdir(exist_ok=True)
    (dados / "metricas.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n")
    hist = dados / "historico.csv"
    novo = not hist.exists()
    with open(hist, "a", newline="") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(["data", "rede", "seguidores", "views_somadas", "videos"])
        for nome, r in saida["redes"].items():
            if "erro" in r:
                continue
            w.writerow([agora().date().isoformat(), nome, r.get("seguidores", 0),
                        sum(v.get("views", 0) or 0 for v in r.get("videos", [])), len(r.get("videos", []))])
    for nome, r in saida["redes"].items():
        print(nome, r.get("erro") or f"{r.get('seguidores')} seguidores, {len(r.get('videos', []))} vídeos")

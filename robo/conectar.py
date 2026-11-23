"""Guarda no cofre o acesso de uma rede, a partir do código que aparece em conectar.html."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from comum import ler_cofre, gravar_cofre, REDIRECT
import youtube, instagram, tiktok

REDES = {"youtube": youtube, "instagram": instagram, "tiktok": tiktok}

if __name__ == "__main__":
    rede, codigo = sys.argv[1].strip().lower(), sys.argv[2].strip()
    cofre = ler_cofre()
    cofre[rede] = REDES[rede].trocar_codigo(codigo, REDIRECT)
    m = REDES[rede].metricas(cofre)  # testa o acesso na hora
    gravar_cofre(cofre)
    print(f"Conectado: {rede} -> conta {m.get('conta')} ({m.get('seguidores')} seguidores)")

# nino-videos

Vídeos do Nino e o **robô de postagem** próprio (sem Metricool, sem limite de posts).

## Como funciona

- `agenda/fila.json`: a agenda. Cada post tem horário (Brasília), vídeo, título, legenda, comentário e o estado em cada rede.
- **Postar vídeos** (`.github/workflows/postar.yml`): roda a cada 15 minutos e posta o que estiver na hora.
  - Instagram: Reels direto.
  - YouTube: Shorts direto (fica privado até o Google aprovar a auditoria da API).
  - TikTok: vai para os rascunhos/caixa de entrada do app e abre um aviso (issue) com a legenda pronta. Depois da auditoria do TikTok, muda `tiktok_modo` para `direto`.
- **Métricas do dia** (`metricas.yml`): 7h todo dia grava `dados/metricas.json` e `dados/historico.csv`, e renova os acessos.
- **Conectar uma rede** (`conectar.yml`): troca o código da página https://giovanicluvi.github.io/nino-videos/ pelo acesso, guardado criptografado em `robo/cofre.json`.

## Segredos (Settings > Secrets and variables > Actions)

`COFRE_CHAVE`, `IG_APP_ID`, `IG_APP_SECRET`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `TT_CLIENT_KEY`, `TT_CLIENT_SECRET`.
Nenhuma senha fica no código. Os acessos ficam em `robo/cofre.json`, criptografados com a `COFRE_CHAVE`.

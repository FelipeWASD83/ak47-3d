# CLAUDE.md: ak47-3d

Modelo 3D de uma AK-47 (no padrão AKM, que é a AK-47 do CS2), gerado por código no Blender, com as animações de
tiro em rajada e de recarga. Criado em 16/10/2026, junto com outras cinco armas feitas em paralelo (metralhadora,
escopeta 12, M4A4, M4A1-S e sniper), cada uma no seu projeto. A arma vai para o mod `revolver-minecraft`; quem faz a
integração (munição, dano, Java, exportador) é a sessão do mod, depois. Repositório público (escolha dele). O
`CLAUDE.md` da raiz vale aqui também, e o `README.md` explica o projeto para ele.

## Como gerar e conferir

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python gerar.py -- --leve
```

O `gerar.bat` faz o mesmo. As opções depois de `--` são as do `deagle-3d`:

- `--sem-render` pula as imagens (uns 8 s);
- `--rapido` faz as imagens em meia resolução;
- `--leve` faz quatro vistas (lado direito, três quartos, `anim-tiro` e `anim-recarga`), com 4 núcleos e
  prioridade mínima;
- `--vistas a,b` escolhe as imagens do modo leve. Os nomes estão no fim de `renderizar`.

**Ele joga no mesmo PC: sem ele pedir render cheio, conferir sempre com `--leve`.**

Conferir no `modelo/relatorio.txt`:

- todas as peças têm que sair `fechada`;
- não pode haver linha `ATENÇÃO` (contorno que se cruza ao arredondar a borda);
- a conferência das animações tem que dizer "nada novo" em todos os momentos. Em repouso nenhum par conferido se
  toca (a linha "No repouso:" sai vazia).

## Referência medida

- **Foto de lado da arma real:** Wikimedia Commons, `AK-47 type II Part DM-ST-89-01131.jpg` (foto do Departamento
  de Defesa dos EUA, 2365 × 854 px, lado esquerdo, fundo branco). A silhueta foi medida coluna a coluna no
  navegador. A escala é **2,59 px por mm**, tirada do comprimento total (870 mm com a coronha fixa), e confere com o
  cano: da boca à frente da caixa dá 369 mm, mais os ~32 mm dentro da caixa, perto dos 415 mm do cano real. A foto
  está girada 0,8° (boca para cima); as medidas foram corrigidas por isso.
- **Imagem do CS2:** `CS2_AK-47_Inventory.png` em counterstrike.fandom.com. Dela vieram o padrão AKM (caixa
  estampada com a covinha em cima do poço, compensador inclinado na boca, guarda-mão de baixo com barriga), a
  madeira alaranjada laqueada na coronha e nos guarda-mãos, o punho marrom-avermelhado mais escuro e o pente
  escuro com nervuras. A foto é de uma Type II (caixa fresada); as medidas externas da AKM são praticamente as
  mesmas, e a forma dos detalhes segue o CS2.
- **Medidas que saíram da foto** (X a partir da frente da caixa, Z a partir do eixo do cano):
  - massa de mira em torre de X 332 a 353, topo em Z 51; bloco de gás de X 225 a 263, com a frente inclinada
    subindo de Z 11 a 34; tubo de gás com o eixo em Z 25;
  - guarda-mão de cima de X 46 a 150 (Z 15 a 42); o de baixo de X 12 a 174, fundo de Z -18 na frente a -25 atrás;
  - bloco da alça de X 0 a 45; alça tangente até Z 44;
  - caixa de X 0 a -264, de Z 18 (a tampa até 37,6) a -30;
  - pente curvo: arco com centro em (137,9; 1,7) e raio de 218 mm na linha do meio, ajustado aos pontos da borda de
    trás; 59 mm de fundo em cima, 52 embaixo, 195 mm de comprimento; a base do pente desce até Z -205;
  - guarda-mato de X -121 a -184, fundo em Z -67; gatilho em X -126 a -138;
  - punho inclinado ~20°, de X -181/-234 em cima a -222/-257 embaixo, fundo em Z -139;
  - coronha de X -262 a -501: em cima de Z 5 a -23, embaixo de Z -38 a -130 (cai ~23°), soleira inclinada.

  O comprimento total saiu 889 mm (870 da arma real mais o compensador da AKM, que a Type II da foto não tem).

## Contrato com o mod (não mudar sem a sessão do mod)

- **Empty raiz `ak47`** em `RECUO = (-212, 0, -78)`, no meio do punho, onde a mão segura: o coice gira em volta
  dele. Todas as peças são filhas dele; `estojo_topo` e `bala_topo` são filhos do `pente`.
- **Peças que mexem:** `ferrolho` (transportador, cabeça do ferrolho e a alavanca de manejo à direita, num objeto
  só), `gatilho`, `botao_pente` (a alavanca do retém atrás do poço), `pente` (origem no centro do fundo, embaixo da
  base), `estojo_topo` e `bala_topo` (o cartucho de cima, deitado em cima do pente), `clarao` (escala 0 em repouso,
  origem na boca) e `estojo_ejetado` (escala 0 em repouso, na câmara; usa a mesma malha do `estojo_topo`). O resto
  fica parado.
- **Faixas de NLA:** `repouso` (HOLD, quadros 1 e 2), `tiro` (quadros 1 a 4 da cena, **exatamente 4 quadros**) e
  `recarregar` (quadros 10 a 84, 75 quadros). Cada faixa começa e termina em repouso; o tiro repete sem pulo.
- **`modelo/animacoes.json`** traz a raiz, o fps (30), início, quadros e eventos de cada faixa e a lista das peças
  que mexem. Eventos (quadro da faixa, 1 = primeiro):
  - `tiro`: `disparo` 2 (clarão cheio, ferrolho no meio, estojo na janela);
  - `recarregar`: `pente_sai` 18, `troca` 35 (o velho já sumiu e o novo não apareceu), `pente_entra` 54 (trava),
    `ferrolho` 64 (o ferrolho bate na frente depois de puxado).
- Os quadros e eventos moram em `TIRO_INICIO`, `TIRO_FIM`, `REC_INICIO`, `REC_FIM` e `EVENTOS`, no `gerar.py`.
  Mudou algum, avisar o mod: o exportador de lá depende deles.

## Decisões que não se desfazem sem motivo

- **Os utilitários de geometria são cópia dos do `deagle-3d`** (`almofada`, `tornear`, `cabo_solido`, `varrer`,
  `booleano`, `acabar` com normais pela área, `_juntar` recebendo o material, `Faixa`, `conferir_movimento`,
  `relatorio`, `renderizar` com `--leve`, `exportar`). Os projetos são independentes. Acrescentados aqui:
  `reamostrar` (linha com pontos igualmente espaçados, para as fatias da coronha e do punho), `no_arco` (pontos
  do arco do pente), `girar_malha` (o seletor parado na posição de rajada), `uv_ao_longo` e a `textura_madeira`
  com as cores como parâmetro.
- **Eixos e unidade:** 1 unidade = 1 mm, boca em +X, o lado direito de quem atira (janela de ejeção, alavanca de
  manejo, seletor) em -Y, Z para cima, eixo do cano em Z = 0, X = 0 na frente da caixa da culatra.
- **Madeira com forma de verdade**, não chapa: coronha, punho e guarda-mão de baixo são sólidos de fatias ovais
  (`cabo_solido`), com a largura crescendo para a soleira e a barriga no guarda-mão. O guarda-mão de cima é uma
  seção arredondada em volta do tubo de gás.
- **Cores:** aço 0,20 (acetinado, metálico 0,65), peças pequenas 0,14, pente 0,17, madeira laqueada alaranjada e o punho
  marrom-avermelhado. Nada preto puro (no Minecraft vira borrão). Sem logo nem escrita.
- **A caixa é oca onde precisa:** canal do ferrolho por dentro (aberto em cima, embaixo da tampa, que também é
  oca), poço do pente aberto até Z -13 (o topo do pente segue o arco e a frente dele sobe mais que a de trás), janela
  de ejeção e fenda da alavanca à direita. Assim o ferrolho corre 85 mm sem atravessar nada.
- **O pente gira em volta do dente da frente** (`PIVO_PENTE`, X -50, Z -30), como numa AK de verdade: sai girando a
  boca para a frente e o novo engata o dente e gira para trás. Como a origem tem que ficar no fundo, a rotação em
  volta do dente vira posição e rotação em cada chave, com chaves a cada 2 quadros nos giros para seguir o arco.
- **Tiro em 4 quadros:** 1 parada, 2 disparo (gatilho, clarão cheio, ferrolho a 55%, estojo saindo pela janela),
  3 ferrolho todo atrás, estojo uns centímetros para fora e para cima, clarão menor, 4 parada (o estojo some). Coice
  de 2,2°. Chaves `LINEAR` e `CONSTANT`: o mod lê quadro inteiro.
- **Seletor parado na posição de rajada** (5° para baixo): não é peça do contrato.

## O que não tem (de propósito, não foi pedido)

Sem baioneta, sem bandoleira, sem vídeo das animações, sem fumaça, sem LOD e sem render cheio no commit (só os do
`--leve`).

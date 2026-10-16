# AK-47 3D

Uma AK-47 no padrão AKM (a mesma arma da AK-47 do CS2), feita por código no Blender, do mesmo jeito que o
`deagle-3d`. Mede uns 89 cm de comprimento e 25 cm de altura com o pente, e tem uns 54 mil triângulos. As
proporções foram medidas numa foto de lado da arma real e conferidas com a imagem do CS2.

As peças ficam separadas:

- **Cano e frente:** o cano, o quebra-chamas inclinado na boca, a massa de mira em torre, o bloco de gás com a
  frente inclinada, o tubo de gás com os furos de respiro e a vareta de limpeza embaixo do cano.
- **Madeira:** o guarda-mão de cima (em volta do tubo de gás), o de baixo (com a barriga para a palma), o punho
  inclinado e a coronha caída, com a soleira de aço no fim.
- **Caixa da culatra:** a caixa estampada com a covinha em cima do poço, os rebites, a tampa por cima, o bloco da
  alça com a alça tangente, o seletor grande à direita e o guarda-mato.
- **Peças que mexem:** o ferrolho (com a alavanca de manejo à direita), o gatilho, o retém do pente (a alavanca
  atrás do poço), o pente curvo de 30 com o cartucho 7,62x39 de cima, o estojo que voa no tiro e o clarão.

O metal é aço cinza acetinado, a madeira é alaranjada e laqueada, o punho é marrom-avermelhado e o pente é de aço
escuro com nervuras. Não tem logo nem escrita.

## Animações

São duas:

| Nome | Duração | O que faz |
|---|---|---|
| `tiro` | 4 quadros | Um tiro da rajada: gatilho, clarão, o ferrolho vai e volta, o estojo salta da janela e some, coice pequeno. O mod repete a faixa enquanto o gatilho estiver apertado. |
| `recarregar` | 2,5 s | A arma deita, o retém é apertado, o pente velho gira para a frente e cai, o novo engata pela frente e gira para trás até travar, e a alavanca do ferrolho é puxada e solta. |

No `ak47.blend` elas ficam em sequência na linha do tempo, com marcadores (tiro no quadro 1, recarregar no 10). No
`ak47.glb` cada uma vira uma animação com nome. O `.obj` sai parado e carregado. O `modelo/animacoes.json` diz
onde cada animação começa, quantos quadros tem e em que quadro acontece cada coisa (o disparo, o pente saindo, a
troca, o pente entrando e o ferrolho batendo), para o mod.

## Onde estão os arquivos

| Arquivo | Para quê |
|---|---|
| `modelo/ak47.blend` | Abrir no Blender e mexer. Um objeto por peça. |
| `modelo/ak47.glb` | Visualizadores de web, Unity, Godot, Windows 3D Viewer. Em metros, com as animações. |
| `modelo/ak47.obj` (+ `.mtl`, `madeira.png` e `madeira_punho.png`) | GameMaker e a maioria dos programas 3D. 1 unidade = 1 mm. |
| `modelo/animacoes.json` | Quadros e eventos das animações, para o mod. |
| `render/*.png` | Imagens do modo leve: lado direito, três quartos e um quadro de cada animação (`anim-*`). |
| `modelo/relatorio.txt` | Medidas e contagem de triângulos de cada peça, e a conferência das animações. |

## Como gerar de novo

Dois cliques no `gerar.bat` (precisa do Blender 5.2 em `C:\Program Files\Blender Foundation`). Faz todas as
imagens em qualidade cheia, leva alguns minutos e ocupa o processador inteiro. Com o PC ocupado, use
`gerar.bat --leve` (quatro imagens pequenas em prioridade mínima). Com `gerar.bat --sem-render`, leva segundos.

## Como mudar uma coisa

Tudo está no `gerar.py`, em milímetros:

- **Quanto o ferrolho recua no tiro:** troque `CURSO = 85.0` no começo do arquivo.
- **Cor do aço:** em `construir()`, procure `material("aco", (0.20, 0.205, 0.20)` e mude os três números
  (vermelho, verde e azul, de 0 a 1).
- **Cor da madeira:** em `construir()`, procure `textura_madeira("madeira", (0.20, 0.075, 0.025), (0.46, 0.20, 0.07)`:
  o primeiro grupo é o tom escuro do veio e o segundo o claro.
- **Duração das animações:** `TIRO_FIM` e `REC_FIM`, junto com os quadros dentro de `animar()`. Mudou isso, avise o
  mod: ele lê os quadros do `animacoes.json`.

O mod de Minecraft (`revolver-minecraft`) vai usar este modelo. Mudou alguma coisa aqui, rode também o exportador de
lá.

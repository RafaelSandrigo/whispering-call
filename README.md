# whispering-call

Automatiza o pós-reunião: **gravação → transcrição → documento**.

1. Lê as gravações de uma pasta local (ex.: pasta do Google Drive sincronizada).
2. Transcreve cada gravação nova com [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
   na GPU NVIDIA (ou na CPU, se não houver), **direto do vídeo** (sem etapa de extração de áudio).
3. Salva a transcrição em Markdown com timestamps.
4. Abre o **Claude Code** com um prompt inicial que aponta para o prompt de
   geração da doc (`prompts/doc_prompt.md`) e para a transcrição. O Claude gera
   `doc.md` na pasta da reunião.

Funciona em **Linux e Windows**.

```
recordings/kickoff.mp4
        │  faster-whisper (GPU ou CPU)
        ▼
output/kickoff_mp4/transcript.md   ← transcrição com timestamps
output/kickoff_mp4/doc_prompt.md   ← cópia do prompt usado
        │  claude "<prompt inicial com os caminhos>"
        ▼
output/kickoff_mp4/doc.md          ← documento gerado pelo Claude
```

## Requisitos

| Item | Observação |
|---|---|
| [uv](https://docs.astral.sh/uv/) | Gerencia Python 3.12 e dependências (não mexe no Python do sistema). |
| [Claude Code](https://docs.claude.com/en/docs/claude-code) | Comando `claude` no `PATH`, já autenticado. |
| GPU NVIDIA + driver | Opcional (acelera bastante). cuBLAS/cuDNN vêm via pip com `uv sync --extra gpu`; **não** é preciso instalar o CUDA Toolkit. |

**Qual hardware roda o quê:** só GPUs **NVIDIA** aceleram a transcrição. Intel
integrada (UHD/Iris/Arc) e AMD (Radeon) **não** são usadas e rodam em **CPU**,
sem nenhuma configuração extra: com `device = "auto"` (padrão) o programa
detecta a ausência de CUDA, avisa no terminal e usa a CPU. Windows 10/11 x64
e Linux x64; ARM não é suportado.

FFmpeg **não** precisa estar instalado: o faster-whisper decodifica o vídeo via
PyAV, que já traz o FFmpeg embutido.

## Instalação

**Linux**

```sh
# Arch/CachyOS: sudo pacman -S uv   |   outros: curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync                 # com GPU NVIDIA: uv sync --extra gpu
cp config.example.toml config.toml
```

**Windows (PowerShell)**

```powershell
winget install --id=astral-sh.uv -e
uv sync                 # com GPU NVIDIA: uv sync --extra gpu
copy config.example.toml config.toml
```

> **Com GPU NVIDIA, sempre use `--extra gpu`.** O `uv sync` sem o extra
> **remove** os pacotes `nvidia-*` já instalados, e o programa passa a usar a CPU
> (o terminal avisa). Rode `uv sync --extra gpu` de novo para voltar à GPU.

Edite o `config.toml`, principalmente `[recordings].folder`. Todas as opções
estão comentadas no próprio [config.example.toml](config.example.toml).

## Passo a passo: processar uma gravação nova

Com a instalação e o `config.toml` prontos:

1. **Coloque o vídeo na pasta de gravações** (`[recordings].folder` do seu
   `config.toml`). Se for uma pasta do Google Drive sincronizada, espere o
   arquivo terminar de baixar/sincronizar antes de rodar.
   - A extensão precisa estar em `[recordings].extensions` (padrão: `.mp4`,
     `.mkv`, `.webm`, `.mov`, `.m4a`, `.mp3`, `.wav`).
   - Se o vídeo está numa subpasta, ligue `recursive = true`.
2. **Abra um terminal na pasta do projeto** e rode:

   ```sh
   uv run whispering-call run
   ```

   Havendo mais de uma gravação pendente, o programa lista todas e **pergunta
   quantas processar** nesta execução (Enter = todas). Para pular a pergunta,
   use `--limit N` ou `--all` (ver [Quantas gravações processar](#quantas-gravações-processar)).

3. **Acompanhe a transcrição.** O terminal mostra qual dispositivo foi usado
   (GPU ou CPU, e o modelo) e o percentual de progresso de cada gravação. Na primeira
   vez o modelo é baixado antes (ver [Primeira execução](#primeira-execução)).
4. **Converse com o Claude.** Quando a transcrição termina, o Claude Code abre
   no mesmo terminal já com o prompt inicial, e gera o `doc.md`. Revise, peça
   ajustes se quiser e saia com `/exit` (ou Ctrl+D). Se houver outras reuniões
   pendentes, a próxima sessão abre em seguida.
5. **Pegue o resultado** em `output/<nome_do_video>/` (a pasta leva o nome do
   arquivo, ex.: `kickoff.mp4` → `output/kickoff_mp4/`):

   | Arquivo | Conteúdo |
   |---|---|
   | `transcript.md` | Transcrição com timestamps. |
   | `doc_prompt.md` | Cópia do prompt usado. |
   | `doc.md` | Documento gerado pelo Claude. |

Se algo falhar, o terminal indica a gravação e a etapa; os detalhes ficam em
`output/whispering-call.log` (ver [Logs](#logs) e
[Solução de problemas](#solução-de-problemas)). Rodar o comando de novo
retoma de onde parou, sem retranscrever o que já foi transcrito.

Para **refazer** o doc de uma reunião, apague o `doc.md` da pasta dela. Para
**retranscrever** (ex.: depois de trocar o modelo), apague também o
`transcript.md`. Detalhes na seção abaixo.

## Uso

```sh
uv run whispering-call run                     # usa ./config.toml
uv run whispering-call run --config outro.toml
```

Cada execução processa **apenas o que falta**, conforme os arquivos na pasta da reunião:

| Situação na pasta `output/<reunião>/` | O que acontece |
|---|---|
| Nada existe | Transcreve e abre o Claude |
| Já existe `transcript.md`, mas não `doc.md` | Só abre o Claude (não retranscreve) |
| Já existe `doc.md` | Pula |

Para **regerar** a doc, apague `doc.md`. Para **retranscrever**, apague também
`transcript.md`.

Primeiro todas as gravações novas são transcritas e só depois o Claude é aberto,
uma vez por reunião. Assim você não precisa esperar uma transcrição entre uma
sessão e outra.

### Quantas gravações processar

Uma gravação "pendente" é a que ainda não tem `doc.md`. Cada uma consome uma
transcrição (se ainda não houver `transcript.md`) e uma sessão do Claude. Para
controlar quantas entram em uma execução:

| Como | Efeito |
|---|---|
| (nada, terminal interativo) | Lista as pendentes e pergunta quantas processar; Enter = todas. |
| `--limit N` ou `-n N` | Processa no máximo as **N mais recentes** pendentes e não pergunta. |
| `--all` | Processa todas, sem perguntar. |
| (nada, sem terminal: cron, pipe, CI) | Processa todas, sem perguntar. |

```sh
uv run whispering-call run --limit 2
uv run whispering-call run --all
```

A ordem é da gravação **mais nova para a mais antiga**, pela data de modificação
do arquivo (empate: ordem do caminho). Isso vale também para a ordem em que as
transcrições e as sessões do Claude acontecem. Arquivos copiados de outro lugar
podem ganhar a data da cópia; confira a data no Explorer se a ordem surpreender.

As que ficaram de fora aparecem no resumo final como "Pendentes (ficaram para a
próxima execução)" e são retomadas na execução seguinte. Com uma só pendente a
pergunta é pulada. `--limit` e `--all` não podem ser usados juntos.

### Modos de abertura do Claude (`[claude].launch_mode`)

- `same_terminal` (padrão): o Claude abre no terminal atual. Ao sair dele
  (`/exit` ou Ctrl+D), segue para a próxima reunião. Ctrl+C dentro do Claude
  continua funcionando normalmente.
- `new_window`: abre uma janela de terminal por reunião e termina na hora. O
  terminal é configurável em `[claude].new_window_command` (padrão: `konsole`
  no Linux e `cmd /c start` no Windows).

### Prompt da doc

Edite [prompts/doc_prompt.md](prompts/doc_prompt.md), que vem com um exemplo de
ata (resumo, decisões, itens de ação). A cada sessão ele é copiado para a pasta
da reunião, o que registra qual versão do prompt gerou cada doc.

## Primeira execução

- O modelo (`small` por padrão, ~500 MB; `large-v3` tem ~3 GB) é baixado do
  Hugging Face na primeira transcrição e fica em cache (`~/.cache/huggingface`, ou `%USERPROFILE%\.cache\huggingface`).
- Troque o modelo em `[transcription].model` (`tiny`, `base`, `small`, `medium`,
  `large-v3-turbo`, `large-v3`). Em CPU, `small`/`medium` são o equilíbrio entre
  velocidade e qualidade; `large-v3` só vale a pena com GPU NVIDIA.
- Na RTX 2060 Super (8 GB), `large-v3` com `int8_float16` usa ~3 GB de VRAM.

## Logs

A saída no terminal é texto simples. Os detalhes para depuração ficam em JSON,
um objeto por linha, em `output/whispering-call.log`:

```json
{"timestamp": "...", "level": "ERROR", "event": "pipeline_stage_failed", "recording": "a.mp4", "stage": "transcription", "error": "...", "exception": "Traceback ..."}
```

## Solução de problemas

| Sintoma | Causa provável / solução |
|---|---|
| `Could not load library libcudnn_ops.so.9` / `cudnn64_9.dll` | Libs CUDA não encontradas. Rode `uv sync --extra gpu` de novo; veja o log (`cuda_libraries_not_loaded`). Como alternativa, use `device = "cpu"`. |
| Terminal diz "GPU CUDA indisponível" mas você tem NVIDIA | Atualize o driver e rode `uv sync --extra gpu` (no Windows os pacotes `nvidia-*` são obrigatórios). |
| Transcrição lenta na CPU | Use um modelo menor (`base`, `small`). O CTranslate2 usa só 4 threads por padrão; expor `cpu_threads` está no [roadmap](docs/roadmap.md). |
| `CUDA out of memory` | Use `compute_type = "int8_float16"` ou um modelo menor (`large-v3-turbo`, `medium`). |
| `Executável do Claude Code não encontrado` | Instale o Claude Code ou aponte `[claude].executable` para o caminho absoluto. |
| Nova janela não abre | Ajuste `[claude].new_window_command` para o seu terminal (exemplos no `config.example.toml`). |
| Windows + `new_window` recusa caminho com `&`, `%`, `^`... | Limitação do `cmd.exe`. Renomeie a pasta ou use `same_terminal`. |

## Desenvolvimento

O `uv.lock` é versionado de propósito: ele fixa o `av<19` (ver
[docs/architecture.md](docs/architecture.md)) e as versões do CTranslate2.
Commite-o junto de qualquer mudança em `pyproject.toml`.

```sh
uv run pytest            # testes (comando único)
uv run mypy              # tipos (strict)
uv run black src tests   # formatação
```

- Arquitetura e decisões: [docs/architecture.md](docs/architecture.md)
- Melhorias planejadas (ex.: integração com o Google Drive): [docs/roadmap.md](docs/roadmap.md)
- Regras de código do projeto: [CLAUDE.md](CLAUDE.md)

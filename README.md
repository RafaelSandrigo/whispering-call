# whispering-call

Automatiza o pós-reunião: **gravação → transcrição → documento**.

1. Lê as gravações de uma pasta local (ex.: pasta do Google Drive sincronizada).
2. Transcreve cada gravação nova com [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
   na GPU, **direto do vídeo** (sem etapa de extração de áudio).
3. Salva a transcrição em Markdown com timestamps.
4. Abre o **Claude Code** com um prompt inicial que aponta para o prompt de
   geração da doc (`prompts/doc_prompt.md`) e para a transcrição. O Claude gera
   `doc.md` na pasta da reunião.

Funciona em **Linux e Windows**.

```
recordings/kickoff.mp4
        │  faster-whisper (GPU)
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
| GPU NVIDIA + driver | Opcional, mas muito recomendado. cuBLAS/cuDNN vêm via pip; **não** é preciso instalar o CUDA Toolkit. Sem GPU, use `device = "cpu"`. |

FFmpeg **não** precisa estar instalado: o faster-whisper decodifica o vídeo via
PyAV, que já traz o FFmpeg embutido.

## Instalação

**Linux**

```sh
# Arch/CachyOS: sudo pacman -S uv   |   outros: curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
cp config.example.toml config.toml
```

**Windows (PowerShell)**

```powershell
winget install --id=astral-sh.uv -e
uv sync
copy config.example.toml config.toml
```

Edite o `config.toml`, principalmente `[recordings].folder`. Todas as opções
estão comentadas no próprio [config.example.toml](config.example.toml).

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

- O modelo `large-v3` (~3 GB) é baixado do Hugging Face na primeira transcrição
  e fica em cache (`~/.cache/huggingface`, ou `%USERPROFILE%\.cache\huggingface`).
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
| `Could not load library libcudnn_ops.so.9` / `cudnn64_9.dll` | Libs CUDA não encontradas. Rode `uv sync` de novo; veja o log (`cuda_libraries_not_loaded`). Como alternativa, use `device = "cpu"`. |
| `CUDA out of memory` | Use `compute_type = "int8_float16"` ou um modelo menor (`large-v3-turbo`, `medium`). |
| `Executável do Claude Code não encontrado` | Instale o Claude Code ou aponte `[claude].executable` para o caminho absoluto. |
| Nova janela não abre | Ajuste `[claude].new_window_command` para o seu terminal (exemplos no `config.example.toml`). |
| Windows + `new_window` recusa caminho com `&`, `%`, `^`... | Limitação do `cmd.exe`. Renomeie a pasta ou use `same_terminal`. |

## Desenvolvimento

```sh
uv run pytest            # testes (comando único)
uv run mypy              # tipos (strict)
uv run black src tests   # formatação
```

- Arquitetura e decisões: [docs/architecture.md](docs/architecture.md)
- Melhorias planejadas (ex.: integração com o Google Drive): [docs/roadmap.md](docs/roadmap.md)
- Regras de código do projeto: [CLAUDE.md](CLAUDE.md)

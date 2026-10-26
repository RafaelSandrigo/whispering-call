# Arquitetura

## Fluxo

```
cli.main
  └─ load_config(config.toml)
  └─ build_pipeline(config)            ← raiz de composição (único lugar com implementações reais)
       └─ MeetingDocPipeline.run()
            1. read_prompt_template()               falha cedo se o prompt não existir
            2. RecordingSource.list_recordings()
            3. para cada gravação sem doc.md:
                 se não há transcript.md → Transcriber.transcribe() → save_transcript()
            4. para cada gravação transcrita:
                 save_prompt_copy() → build_initial_prompt() → ClaudeLauncher.launch()
```

## Módulos (`src/whispering_call/`)

| Módulo | Responsabilidade |
|---|---|
| `cli.py` | Argumentos, tratamento de erros esperados e composição das dependências. |
| `config.py` | Lê e valida o `config.toml` em dataclasses tipadas; os erros citam chave, valor e formato esperado. |
| `errors.py` | Hierarquia de erros acionáveis pelo usuário (`WhisperingCallError`). |
| `recordings.py` | `Recording`, contrato `RecordingSource` e `LocalFolderRecordingSource`. |
| `meeting_workspace.py` | Pasta de saída por reunião, nomes válidos em Windows/Linux, escrita atômica. |
| `transcription.py` | Contrato `Transcriber` e `TranscriptSegment`, independentes do motor. |
| `faster_whisper_transcriber.py` | Adaptador do faster-whisper (import tardio, modelo carregado uma vez). |
| `cuda_runtime.py` | Torna cuBLAS/cuDNN dos wheels `nvidia-*` visíveis ao CTranslate2. |
| `transcript_markdown.py` | Renderiza a transcrição como `- [HH:MM:SS] texto`. |
| `claude_prompt.py` | Monta o prompt inicial com os três caminhos. |
| `claude_launcher.py` | Launchers `same_terminal` e `new_window` e montagem do comando. |
| `process_runner.py` | Wrapper do `subprocess`, com o tratamento de Ctrl+C. |
| `pipeline.py` | Orquestração e resumo da execução (`RunSummary`). |
| `console_reporter.py` | Saída de texto simples para o usuário. |
| `json_logging.py` | Logs estruturados em JSON no arquivo de log. |

Toda dependência externa (filesystem de gravações, Whisper, processos, libs
nativas) fica atrás de um `Protocol` próprio e é injetada pelo construtor. Os
testes usam fakes nomeados de `tests/fakes.py`.

## Decisões

### Transcrever direto do vídeo
O faster-whisper decodifica via PyAV (FFmpeg embutido no wheel). Por isso não
há etapa de extração de áudio nem dependência do `ffmpeg` do sistema, o que
simplifica bastante a instalação no Windows.

### Estado derivado dos arquivos, sem banco de estado
"Processado" significa que `doc.md` existe, e "transcrito" significa que
`transcript.md` existe. Vantagens: a execução é idempotente e retomável (uma
queda no meio não deixa estado inconsistente), o reprocessamento se faz
apagando um arquivo, e o modo `new_window` funciona igual, já que não temos
como saber quando aquela janela termina. A transcrição é gravada de forma
atômica (`.partial` seguido de rename) para que um arquivo pela metade nunca
pareça completo.

### Transcrever tudo antes de abrir o Claude
A transcrição é longa e não exige interação. Fazê-la toda primeiro deixa as
sessões interativas do Claude em sequência, sem espera entre elas.

### Prompt copiado para a pasta da reunião
O Claude roda com `cwd = output/<reunião>/`. Com o prompt copiado para lá, tudo
que ele precisa ler está dentro do diretório de trabalho, sem pedidos de
permissão para ler fora dele e sem `--add-dir`. O `--add-dir` é variádico e
engoliria o prompt posicional. A cópia também registra qual versão do prompt
gerou cada doc.

### Prompt inicial curto, em linha única e sem aspas
O conteúdo fica nos arquivos e o prompt inicial só aponta para eles. No Windows
em `new_window`, o texto passa pelo `cmd /c start`, que quebra em quebras de
linha e reinterpreta `& | < > ^ % "`. Por isso esses caracteres são recusados
com erro explícito (`ensure_safe_for_cmd`).

### Comando: `claude <prompt> <extra_args>`
O prompt vem logo após o executável, porque opções variádicas colocadas antes
dele o consumiriam como valor.

### Ctrl+C no modo `same_terminal`
O SIGINT chega a todo o grupo de processos do terminal. Enquanto o Claude roda,
o Python instala um handler *no-op* (e não `SIG_IGN`, que seria herdado pelo
filho no `exec`) para não morrer com `KeyboardInterrupt` e derrubar a sessão.

### cuBLAS/cuDNN via pip
Os wheels `nvidia-cublas-cu12`/`nvidia-cudnn-cu12` evitam instalar o CUDA
Toolkit. No Linux, cada `.so` é pré-carregado com `RTLD_GLOBAL`, repetindo as
que falham enquanto houver progresso, porque as sub-libs do cuDNN dependem
umas das outras. No Windows, a pasta `bin` é registrada com
`os.add_dll_directory` e no `PATH`.

### Python 3.12
O CTranslate2 (motor do faster-whisper) ainda não tem wheels estáveis para o
3.14. O uv provisiona o 3.12 isolado (`.python-version`).

## Compatibilidade Windows/Linux

- Todos os arquivos são lidos e gravados com `encoding="utf-8"` explícito (o padrão no Windows é cp1252).
- `Recording.key` usa separador POSIX, e os nomes de pasta removem caracteres proibidos no Windows.
- O executável é resolvido com `shutil.which` (`claude` vira `claude.exe` no Windows).
- O template de nova janela tem um padrão por SO e pode ser trocado na config.

# Arquitetura

## Fluxo

```
cli.main
  └─ load_config(config.toml)
  └─ build_pipeline(config)            ← raiz de composição (único lugar com implementações reais)
       └─ MeetingDocPipeline.run()
            1. read_prompt_template()               falha cedo se o prompt não existir
            2. RecordingSource.list_recordings()
               RunLimitPolicy.choose(pendentes) → processa só as N primeiras
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
| `cuda_runtime.py` | Torna cuBLAS/cuDNN dos wheels `nvidia-*` visíveis ao CTranslate2 e sonda se há GPU NVIDIA utilizável (`SystemCudaProbe`). |
| `device_selection.py` | Resolve `device`/`compute_type` `auto` em valores reais (GPU ou CPU) a partir da sondagem. |
| `transcript_markdown.py` | Renderiza a transcrição como `- [HH:MM:SS] texto`. |
| `claude_prompt.py` | Monta o prompt inicial com os três caminhos. |
| `claude_launcher.py` | Launchers `same_terminal` e `new_window` e montagem do comando. |
| `process_runner.py` | Wrapper do `subprocess`, com o tratamento de Ctrl+C. |
| `pipeline.py` | Orquestração e resumo da execução (`RunSummary`). |
| `run_limit.py` | `RunLimitPolicy`: quantas pendentes processar (`AllPending`, `FixedLimit` de `--limit`, `AskUserLimit` interativa). |
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

### Limite por execução e pergunta interativa
A fonte local ordena as gravações da mais nova para a mais antiga (`st_mtime_ns`, desempate pelo caminho), então o limite pega as mais recentes. O critério é a data de modificação porque é a única portátil entre Windows e Linux (data de criação não é).
O pipeline não conhece teclado nem argparse: depois de listar as pendentes ele
consulta uma `RunLimitPolicy` injetada. A CLI escolhe a política em
`choose_limit_policy`: `--limit` > `--all` > (sem terminal) todas > perguntar.
Sem TTY nunca se pergunta, para que cron/CI não travem esperando entrada. O
limite conta gravações pendentes (sem `doc.md`), não só as que precisam de
transcrição, porque cada uma abre uma sessão do Claude, que é a etapa interativa.

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

### GPU opcional com fallback para CPU
Só o CUDA acelera o CTranslate2; Intel integrada e AMD não têm backend. Por isso
`device = "auto"` (padrão) sonda a GPU na primeira transcrição
(`ResolvingModelFactory`, preguiçosa para não custar nada sem gravações novas) e
cai para CPU com `int8`, avisando o motivo. `device = "cuda"` também cai para
CPU em vez de falhar. No Windows os wheels `nvidia-*` são exigidos para contar a
GPU como disponível, porque sem eles o CTranslate2 acharia a placa e falharia só
na primeira inferência. Esses wheels ficam no extra `gpu` (`uv sync --extra gpu`)
para não baixar centenas de MB em máquinas sem NVIDIA.

### Modelo padrão `small`
`large-v3` é inviável em CPU. O padrão leve funciona em qualquer máquina; quem
tem GPU troca `[transcription].model` na config.

### `uv.lock` versionado
O lock fixa o `av<19` e as versões do CTranslate2 (que definem a compatibilidade com cuDNN 9 e com GPUs novas, como a Blackwell). Reproduzir o ambiente exige commitá-lo.

### `av<19`
O PyAV 19 removeu o argumento `metadata_errors` usado pelo faster-whisper 1.2.x
(`TypeError` ao abrir qualquer mídia). A versão fica limitada em `pyproject.toml`.

### Python 3.12
O CTranslate2 (motor do faster-whisper) ainda não tem wheels estáveis para o
3.14. O uv provisiona o 3.12 isolado (`.python-version`).

### Atalho do Windows (`scripts/create-desktop-shortcut.ps1`)
O atalho roda `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command
"... uv run whispering-call run --all ..."` com a pasta do projeto como
diretório de trabalho.

- `--all`: o atalho é o fluxo "processar tudo que está pendente", sem a pergunta
  de quantas. Quem quiser limitar usa o terminal (`--limit N`).
- O caminho absoluto do `uv` é resolvido na criação (`Get-Command uv`) e gravado
  no atalho. Um atalho não herda o PATH de um terminal já aberto, e o winget às
  vezes só atualiza o PATH em sessões novas.
- `-ExecutionPolicy Bypass` vale só para esse processo e não muda a política da
  máquina. Ele é necessário porque a política padrão do Windows bloqueia `.ps1`.
- A janela termina com `Read-Host` para o resumo não sumir quando o processo sai.
  No modo `same_terminal`, o Claude abre na própria janela do atalho.
- O `.ps1` é salvo em UTF-8 **com BOM** e CRLF. O Windows PowerShell 5.1 lê
  arquivos sem BOM como ANSI e corrompe os acentos das mensagens.
- Os caminhos entram no comando entre aspas simples, com `'` dobrado, para que
  pastas com espaço, `$` ou `'` não quebrem o comando.
- `assets/whispering-call.ico` é um arquivo estático (16 a 256 px), gerado uma
  vez com Pillow e versionado. O gerador não faz parte do projeto.

## Compatibilidade Windows/Linux

- Todos os arquivos são lidos e gravados com `encoding="utf-8"` explícito (o padrão no Windows é cp1252).
- `Recording.key` usa separador POSIX, e os nomes de pasta removem caracteres proibidos no Windows.
- O executável é resolvido com `shutil.which` (`claude` vira `claude.exe` no Windows).
- O template de nova janela tem um padrão por SO e pode ser trocado na config.
- O atalho de Área de Trabalho existe só no Windows (`scripts/create-desktop-shortcut.ps1`). No Linux, rode `uv run whispering-call run --all` ou crie um `.desktop` manualmente.

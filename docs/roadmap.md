# Roadmap / melhorias

## 1. Integração direta com o Google Drive (prioridade)

**Hoje:** o whispering-call lê uma pasta local, então o Drive precisa estar
sincronizado no disco (Google Drive para desktop, rclone, Insync...).

**Proposta:** uma nova fonte `GoogleDriveRecordingSource`, que implementa o
contrato `RecordingSource` (`src/whispering_call/recordings.py`). O pipeline não
muda; só a raiz de composição (`cli.build_pipeline`) escolhe a fonte pela config.

Esboço:

```toml
[recordings]
source = "google_drive"            # "local_folder" (padrão) | "google_drive"

[recordings.google_drive]
folder_id = "1AbC..."              # ID da pasta (ex.: "Meet Recordings")
credentials_file = "credentials.json"
token_file = "token.json"          # gerado no primeiro login OAuth
download_folder = "recordings"     # cache local dos vídeos baixados
```

Pontos a decidir antes de implementar:
- **Autenticação:** OAuth de usuário (login no navegador na primeira vez, token
  salvo) ou Service Account (a pasta é compartilhada com a conta de serviço).
- **Biblioteca:** `google-api-python-client` + `google-auth-oauthlib`, atrás de
  uma interface própria (ex.: `DriveFilesClient`) para permitir um fake nos testes.
- **Download:** em streaming (`MediaIoBaseDownload`), porque as gravações têm
  centenas de MB. Gravar em `.partial` e renomear, igual à transcrição.
- **Chave estável:** usar o `fileId` do Drive (ou `nome + fileId`) em
  `Recording.key`, já que nomes podem se repetir.
- **Arquivos ainda sendo gerados:** o Meet publica a gravação minutos depois da
  reunião; pular arquivos sem `md5Checksum`/tamanho final.

## 2. Outras ideias

- **Gravação ainda sendo copiada/sincronizada:** ignorar arquivos modificados há
  menos de N segundos (`[recordings].min_age_seconds`).
- **Diarização (quem falou):** pyannote/WhisperX para rotular os falantes na transcrição.
- **Modo headless:** `launch_mode = "headless"` com `claude -p`, para rodar via
  cron/systemd sem interação.
- **Execução agendada:** documentar timer systemd (Linux) e Agendador de Tarefas (Windows).
- **Prompt por tipo de reunião:** escolher o prompt pela subpasta ou pelo padrão do nome.
- **Comando `status`:** listar gravações e o estado de cada uma sem processar.

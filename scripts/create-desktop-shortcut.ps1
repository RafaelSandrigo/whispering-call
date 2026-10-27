<#
.SYNOPSIS
    Cria na Área de Trabalho um atalho que processa todas as gravações pendentes.

.DESCRIPTION
    O atalho abre uma janela do PowerShell na pasta do projeto e roda
    `uv run whispering-call run --all` (fluxo padrão, sem a pergunta de quantas
    processar). O Claude Code abre nessa mesma janela quando
    [claude].launch_mode = "same_terminal". No fim, a janela espera um Enter
    para fechar, para dar tempo de ler o resumo.

    O caminho do uv é resolvido agora e gravado no atalho: um atalho não carrega
    o PATH de um terminal já aberto, e assim ele funciona mesmo se o uv só
    estiver no PATH desta sessão.

.PARAMETER ShortcutName
    Nome do atalho (sem .lnk). Padrão: "Whispering Call".

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\create-desktop-shortcut.ps1
#>
[CmdletBinding()]
param(
    [string]$ShortcutName = "Whispering Call"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$iconPath = Join-Path $projectRoot "assets\whispering-call.ico"
$configPath = Join-Path $projectRoot "config.toml"

$uvCommand = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $uvCommand) {
    throw "uv não encontrado no PATH. Instale com: winget install --id=astral-sh.uv -e"
}
if (-not (Test-Path -LiteralPath $iconPath)) {
    throw "Ícone não encontrado em '$iconPath'. Esperado: assets\whispering-call.ico na raiz do projeto."
}
if (-not (Test-Path -LiteralPath $configPath)) {
    Write-Warning "config.toml não existe em '$projectRoot'. Copie o config.example.toml antes de usar o atalho."
}

# Aspas simples no PowerShell escapam dobrando: caminhos com ' não quebram o comando.
function ConvertTo-PSLiteral([string]$Text) {
    return "'" + $Text.Replace("'", "''") + "'"
}

$runCommand = @(
    "Set-Location -LiteralPath $(ConvertTo-PSLiteral $projectRoot)"
    "& $(ConvertTo-PSLiteral $uvCommand.Source) run whispering-call run --all"
    "Write-Host ''"
    "Read-Host 'Pressione Enter para fechar'"
) -join "; "

$powershellExe = Join-Path $PSHOME "powershell.exe"
if (-not (Test-Path -LiteralPath $powershellExe)) {
    # PowerShell 7 (pwsh) rodando o script: usa o executável dele.
    $powershellExe = (Get-Process -Id $PID).Path
}

# GetFolderPath respeita a Área de Trabalho redirecionada pelo OneDrive.
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "$ShortcutName.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $powershellExe
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -Command `"$runCommand`""
$shortcut.WorkingDirectory = $projectRoot
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Description = "Transcreve as gravações pendentes e gera as docs com o Claude Code"
$shortcut.Save()

Write-Host "Atalho criado: $shortcutPath"

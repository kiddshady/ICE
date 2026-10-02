<#
.SYNOPSIS
    Hace que DE4DC0DEX arranque solo al iniciar sesión en Windows, sin ventana.

.DESCRIPTION
    Pone un acceso directo en la carpeta de Inicio de Windows que corre
    `pythonw -m de4dc0dex.tg` en esta carpeta. No hace falta ser administrador.
    Sin ventana, lo que DE4DC0DEX cuenta en la consola va a data\de4dc0dex.log.

.EXAMPLE
    .\autoarranque.ps1             # que arranque solo desde el próximo inicio
.EXAMPLE
    .\autoarranque.ps1 -Iniciar    # prenderlo ya, sin ventana
.EXAMPLE
    .\autoarranque.ps1 -Detener    # apagar el que está corriendo
.EXAMPLE
    .\autoarranque.ps1 -Estado     # si arranca solo, si está corriendo y lo último del registro
.EXAMPLE
    .\autoarranque.ps1 -Quitar     # que deje de arrancar solo
#>
param(
    [switch]$Iniciar,
    [switch]$Detener,
    [switch]$Estado,
    [switch]$Quitar
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$link = Join-Path ([Environment]::GetFolderPath('Startup')) 'DE4DC0DEX.lnk'
$logFile = Join-Path $root 'data\de4dc0dex.log'

function Find-Pythonw {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $python) { throw 'No encontré Python. ¿Está instalado y en el PATH?' }
    $pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
    if (-not (Test-Path $pythonw)) { throw "No encontré pythonw.exe al lado de $python." }
    $pythonw
}

# Los DE4DC0DEX que están corriendo: con ventana (python) o sin ella (pythonw).
function Get-Bot {
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" |
        Where-Object { $_.CommandLine -match '-m\s+de4dc0dex\.tg\b' }
}

if ($Detener) {
    $running = @(Get-Bot)
    if (-not $running) { 'DE4DC0DEX no está corriendo.'; return }
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    'DE4DC0DEX apagado.'
    return
}

if ($Estado) {
    $auto = if (Test-Path $link) { 'sí' } else { 'no' }
    $running = @(Get-Bot)
    $now = if ($running) { "sí (proceso $($running.ProcessId -join ', '))" } else { 'no' }
    "Arranca solo con Windows: $auto"
    "Corriendo ahora:          $now"
    if (Test-Path $logFile) {
        ''
        'Lo último del registro (data\de4dc0dex.log):'
        Get-Content $logFile -Tail 10 -Encoding utf8
    }
    return
}

if ($Quitar) {
    if (Test-Path $link) { Remove-Item $link; 'DE4DC0DEX ya no arranca solo con Windows.' }
    else { 'DE4DC0DEX no estaba puesto para arrancar solo.' }
    'Si está corriendo, sigue hasta que lo apagues: .\autoarranque.ps1 -Detener'
    return
}

if ($Iniciar) {
    if (Get-Bot) { 'DE4DC0DEX ya está corriendo.'; return }
    Start-Process (Find-Pythonw) -ArgumentList '-m', 'de4dc0dex.tg' -WorkingDirectory $root
    'DE4DC0DEX arrancó sin ventana. Lo que hace va a data\de4dc0dex.log.'
    return
}

# Sin opciones: instalar el arranque automático.
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = Find-Pythonw
$shortcut.Arguments = '-m de4dc0dex.tg'
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'DE4DC0DEX, bot moderador de Telegram'
$shortcut.Save()
'Listo: DE4DC0DEX arranca solo cada vez que inicies sesión en Windows.'
'Para prenderlo ya, sin esperar al próximo inicio: .\autoarranque.ps1 -Iniciar'

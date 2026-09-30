<#
.SYNOPSIS
    Hace que ICE arranque solo al iniciar sesión en Windows, sin ventana.

.DESCRIPTION
    Pone un acceso directo en la carpeta de Inicio de Windows que corre
    `pythonw -m ice.tg` en esta carpeta. No hace falta ser administrador.
    Sin ventana, lo que ICE cuenta en la consola va a data\ice.log.

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
$link = Join-Path ([Environment]::GetFolderPath('Startup')) 'ICE.lnk'
$logFile = Join-Path $root 'data\ice.log'

function Find-Pythonw {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $python) { throw 'No encontré Python. ¿Está instalado y en el PATH?' }
    $pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
    if (-not (Test-Path $pythonw)) { throw "No encontré pythonw.exe al lado de $python." }
    $pythonw
}

# Los ICE que están corriendo: con ventana (python) o sin ella (pythonw).
function Get-Ice {
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" |
        Where-Object { $_.CommandLine -match '-m\s+ice\.tg\b' }
}

if ($Detener) {
    $running = @(Get-Ice)
    if (-not $running) { 'ICE no está corriendo.'; return }
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    'ICE apagado.'
    return
}

if ($Estado) {
    $auto = if (Test-Path $link) { 'sí' } else { 'no' }
    $running = @(Get-Ice)
    $now = if ($running) { "sí (proceso $($running.ProcessId -join ', '))" } else { 'no' }
    "Arranca solo con Windows: $auto"
    "Corriendo ahora:          $now"
    if (Test-Path $logFile) {
        ''
        'Lo último del registro (data\ice.log):'
        Get-Content $logFile -Tail 10 -Encoding utf8
    }
    return
}

if ($Quitar) {
    if (Test-Path $link) { Remove-Item $link; 'ICE ya no arranca solo con Windows.' }
    else { 'ICE no estaba puesto para arrancar solo.' }
    'Si está corriendo, sigue hasta que lo apagues: .\autoarranque.ps1 -Detener'
    return
}

if ($Iniciar) {
    if (Get-Ice) { 'ICE ya está corriendo.'; return }
    Start-Process (Find-Pythonw) -ArgumentList '-m', 'ice.tg' -WorkingDirectory $root
    'ICE arrancó sin ventana. Lo que hace va a data\ice.log.'
    return
}

# Sin opciones: instalar el arranque automático.
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = Find-Pythonw
$shortcut.Arguments = '-m ice.tg'
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'ICE, bot moderador de Telegram'
$shortcut.Save()
'Listo: ICE arranca solo cada vez que inicies sesión en Windows.'
'Para prenderlo ya, sin esperar al próximo inicio: .\autoarranque.ps1 -Iniciar'

param(
    [string]$SerialPort = 'COM5',
    [int]$Baud = 9600,
    [string]$BrokerHost = '',
    [int]$BrokerPort = 0
)

$ErrorActionPreference = 'Stop'
$prototypeRoot = $PSScriptRoot
$prototypePython = Join-Path $prototypeRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $prototypePython)) {
    throw 'Install the repository virtual environment and backend/requirements-hardware.txt first.'
}

# The backend and bridge must load the same .env from the repository root.
Push-Location -LiteralPath $prototypeRoot
try {
    $existingBridge = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'python.exe' -and
        $_.CommandLine -like '*-m backend.examples.serial_sensor*' -and
        $_.CommandLine -match ('--port\s+"?' + [regex]::Escape($SerialPort) + '(?:\s|"|$)')
    }
    if ($existingBridge) {
        Write-Host "The USB-to-MQTT bridge for $SerialPort is already running."
        Write-Host 'Open http://127.0.0.1:5173 and choose Hands-on Mode.'
        return
    }
    if ($BrokerHost) { $env:MQTT_HOST = $BrokerHost }
    if ($BrokerPort) { $env:MQTT_PORT = [string]$BrokerPort }
    Write-Host "Reading ESP32 on $SerialPort at $Baud baud. Keep this terminal running."
    Write-Host 'Close Arduino Serial Monitor so the bridge can access the USB port.'
    Write-Host 'Uses the same MQTT settings as the backend; Ctrl+C stops the bridge.'
    & $prototypePython -m backend.examples.serial_sensor --port $SerialPort --baud $Baud
    if ($LASTEXITCODE -ne 0) { throw "Serial bridge exited with code $LASTEXITCODE" }
}
finally {
    Pop-Location
}

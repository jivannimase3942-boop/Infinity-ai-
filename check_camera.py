import subprocess
import sys

ps = """
try {
    Add-Type -AssemblyName System.Drawing
    [Windows.Media.Capture.MediaCapture, Windows.Media.Capture, ContentType = WindowsRuntime] | Out-Null
    [Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType = WindowsRuntime] | Out-Null
    $op = [Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync([Windows.Devices.Enumeration.DeviceClass]::VideoCapture)
    $task = [System.WindowsRuntimeSystemExtensions]::AsTask($op)
    $task.Wait()
    $devs = $task.Result
    Write-Output "COUNT:$($devs.Count)"
    foreach ($d in $devs) {
        Write-Output "NAME:$($d.Name)"
    }
} catch {
    Write-Output "ERR:$($_.Exception.Message)"
}
"""

res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
print("STDOUT:", res.stdout.strip())
print("STDERR:", res.stderr.strip())

# CPU paneli için GGUF modellerini indirir ve SHA-256 ile doğrular (Windows PowerShell).
# Kullanım:  powershell -ExecutionPolicy Bypass -File scripts\download_cpu_models.ps1 -Keys qwen,aya -Dest D:\modeller
param([string[]]$Keys = @("qwen","gemma","llama","aya"), [string]$Dest = "C:\modeller")
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$rows = Import-Csv -Delimiter "`t" -Path (Join-Path $PSScriptRoot "cpu_models.tsv")
foreach ($r in $rows | Where-Object { $Keys -contains $_.key }) {
  $out = Join-Path $Dest $r.file
  if (-not (Test-Path $out)) {
    $url = "https://huggingface.co/$($r.hf_repo)/resolve/main/$($r.file)"
    Write-Host "İndiriliyor: $url"
    curl.exe -L --fail -o $out $url
  }
  $h = (Get-FileHash -Algorithm SHA256 $out).Hash.ToLower()
  if ($h -ne $r.sha256) { Write-Error "SHA-256 UYUŞMUYOR: $($r.file) ($h)"; exit 1 }
  Write-Host "Doğrulandı: $($r.file)"
}

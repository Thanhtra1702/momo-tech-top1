# Tạo file .zip mã nguồn để nộp và kiểm tra không lộ khóa API.
# Chạy từ thư mục gốc dự án:  pwsh scripts/make_submission_zip.ps1
param([string]$Out = "momo-travel-assistant-source.zip")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$excludeDirs = @(".git", ".venv", "node_modules", "dist", "__pycache__", ".pytest_cache", "frontend_dist", "results")
$excludeFiles = @("*.db", "*.sqlite3", "*.pyc", ".env", "*.zip")

$files = Get-ChildItem -Recurse -File -Force | Where-Object {
    $rel = $_.FullName.Substring($root.Length + 1)
    $parts = $rel.Split([IO.Path]::DirectorySeparatorChar)
    if ($parts | Where-Object { $excludeDirs -contains $_ }) { return $false }
    if ($_.Name -like ".env.*" -and $_.Name -ne ".env.example") { return $false }
    foreach ($p in $excludeFiles) { if ($_.Name -like $p) { return $false } }
    return $true
}

# Quét khóa: chuỗi giống khóa sk-..., hoặc LLM_API_KEY được gán giá trị khác rỗng.
$leaks = @()
foreach ($f in $files) {
    if ($f.Length -gt 2MB) { continue }
    $text = Get-Content -Raw -LiteralPath $f.FullName -ErrorAction SilentlyContinue
    if (-not $text) { continue }
    if ($text -cmatch "sk-[A-Za-z0-9]{20,}") { $leaks += "$($f.FullName): chuỗi giống khóa sk-..." }
    if ($text -cmatch "(?m)^[ \t]*LLM_API_KEY[ \t]*=[ \t]*[^\s#]+") { $leaks += "$($f.FullName): LLM_API_KEY có giá trị" }
}
if ($leaks.Count -gt 0) {
    $leaks | ForEach-Object { Write-Error $_ -ErrorAction Continue }
    throw "Phát hiện khả năng lộ khóa, không tạo zip."
}

if (Test-Path $Out) { Remove-Item -LiteralPath $Out }
$staging = Join-Path ([IO.Path]::GetTempPath()) ("momo-src-" + [guid]::NewGuid())
try {
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($root.Length + 1)
        $dest = Join-Path $staging $rel
        New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
        Copy-Item -LiteralPath $f.FullName -Destination $dest
    }
    Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $Out
} finally {
    if (Test-Path $staging) { Remove-Item -Recurse -Force -LiteralPath $staging }
}
$size = [math]::Round((Get-Item $Out).Length / 1KB)
Write-Output "Đã tạo $Out ($($files.Count) tệp, $size KB). Không phát hiện khóa."

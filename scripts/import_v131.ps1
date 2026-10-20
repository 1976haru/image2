# Import existing LOCAL V1.3.1 Python files into local image2 checkout.
# Explicit opt-in: copies source+tests only. No model weights or user creative material.
# Examples may be copied for LOCAL tests only, but are gitignored and NEVER pushed.
[CmdletBinding(SupportsShouldProcess=$true)]
param(
  [Parameter(Mandatory=$true)][string]$Source,
  [Parameter(Mandatory=$true)][string]$Target,
  [switch]$LocalExamples
)
$ErrorActionPreference = 'Stop'
$src = (Resolve-Path -LiteralPath $Source).Path
$dest = (Resolve-Path -LiteralPath $Target).Path
if (-not (Test-Path -LiteralPath (Join-Path $src 'story_image_studio\app.py'))) {
  throw "V1.3.1 소스 폴더를 찾지 못했습니다. story_image_studio\app.py 가 있는 폴더를 -Source로 지정하세요."
}
if (-not (Test-Path -LiteralPath (Join-Path $dest '.git'))) {
  throw "Target은 GitHub image2 clone 폴더여야 합니다 (.git 없음)."
}
$items = @(
  'story_image_studio', 'tests', 'run_studio.py',
  'requirements.txt', 'requirements-dev.txt',
  '실행_설치.bat', '빠른실행.bat', '테스트_실행.bat', 'EXE_빌드_선택.bat'
)
foreach ($relative in $items) {
  $origin=Join-Path $src $relative
  $destination=Join-Path $dest $relative
  if (-not (Test-Path -LiteralPath $origin)) { Write-Warning "없음: $origin"; continue }
  if ($PSCmdlet.ShouldProcess($destination, "Copy from $origin")) {
    if ((Get-Item -LiteralPath $origin).PSIsContainer) {
      New-Item -ItemType Directory -Force -Path $destination | Out-Null
      Get-ChildItem -LiteralPath $origin -File -Recurse |
        Where-Object { $_.Extension -eq '.py' } |
        ForEach-Object {
          $sub=$_.FullName.Substring($origin.Length).TrimStart('\')
          $out=Join-Path $destination $sub
          New-Item -ItemType Directory -Force -Path (Split-Path $out -Parent) | Out-Null
          Copy-Item -LiteralPath $_.FullName -Destination $out -Force
        }
    } else {
      Copy-Item -LiteralPath $origin -Destination $destination -Force
    }
  }
}
if ($LocalExamples) {
  $examples = Join-Path $src 'examples'
  if (Test-Path -LiteralPath $examples) {
    if ($PSCmdlet.ShouldProcess((Join-Path $dest 'examples'), 'Copy private fixtures locally (gitignored)')) {
      Copy-Item -LiteralPath $examples -Destination (Join-Path $dest 'examples') -Recurse -Force
    }
  }
}
Write-Host "LOCAL import step done. Check git status: NO private examples/images/lyrics should be staged." -ForegroundColor Yellow
Write-Host "Next: python -m pip install -r requirements.txt; python -m pip install -r requirements-dev.txt; python -m pytest -q" -ForegroundColor Cyan
Write-Host "Never run git add -f on examples or image/model files." -ForegroundColor Yellow
# ============================================================================
# RUN_NOW.PS1 - Executa TUDO em paralelo AGORA
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "EXECUTANDO GOOGOLPLEX-BOOKS - PARALELO" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Encontra Python
$pythonPaths = @(
    "python",
    "python3",
    "py",
    "C:\Python311\python.exe",
    "C:\Python310\python.exe",
    "C:\Python39\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python39\python.exe"
)

$python = $null
foreach ($path in $pythonPaths) {
    try {
        $result = & $path --version 2>&1
        if ($LASTEXITCODE -eq 0 -or $result -match "Python") {
            $python = $path
            Write-Host "√ Python encontrado: $path" -ForegroundColor Green
            Write-Host "  Versao: $result" -ForegroundColor Gray
            break
        }
    }
    catch {
        continue
    }
}

if (-not $python) {
    Write-Host "X Python nao encontrado!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Por favor, instale Python de: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Durante instalacao, marque 'Add Python to PATH'" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Pressione Enter para sair"
    exit 1
}

# Muda para diretório do script
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "FASE 1: Verificando Ollama" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Verifica se Ollama está rodando
try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    Write-Host "√ Ollama esta rodando" -ForegroundColor Green
}
catch {
    Write-Host "! Ollama nao esta rodando" -ForegroundColor Yellow
    Write-Host "Tentando iniciar Ollama..." -ForegroundColor Yellow

    try {
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden -PassThru
        Write-Host "Aguardando Ollama iniciar..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5

        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        Write-Host "√ Ollama iniciado com sucesso" -ForegroundColor Green
    }
    catch {
        Write-Host "X Nao foi possivel iniciar Ollama" -ForegroundColor Red
        Write-Host ""
        Write-Host "Por favor, inicie Ollama manualmente:" -ForegroundColor Yellow
        Write-Host "  ollama serve" -ForegroundColor White
        Write-Host ""
        Read-Host "Pressione Enter para sair"
        exit 1
    }
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "FASE 2: Executando pipeline em PARALELO" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Executando: python run_all.py --languages en es --limit 20" -ForegroundColor White
Write-Host ""

# Executa run_all.py
& $python run_all.py --languages en es --limit 20

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================================================" -ForegroundColor Green
    Write-Host "√ SUCESSO! Pipeline completado" -ForegroundColor Green
    Write-Host "============================================================================" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host "X Erro ao executar pipeline (codigo: $LASTEXITCODE)" -ForegroundColor Red
    Write-Host "============================================================================" -ForegroundColor Red
}

Write-Host ""
Read-Host "Pressione Enter para sair"

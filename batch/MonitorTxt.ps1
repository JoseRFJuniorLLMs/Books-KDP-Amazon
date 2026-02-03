# MonitorTxt.ps1
# Script para monitorar a pasta 'txt' e fazer git add/commit/push automaticamente

$folder = "$PSScriptRoot\txt"
$syncCount = 0

function Show-Header {
    Clear-Host
    Write-Host "============================" -ForegroundColor Cyan
    Write-Host "   MONITOR DE SINCRONIA     " -ForegroundColor Yellow
    Write-Host "   Obs: Ctrl+C para sair    " -ForegroundColor Cyan
    Write-Host "============================" -ForegroundColor Cyan
    Write-Host "Pasta monitorada: " -NoNewline -ForegroundColor White
    Write-Host "$folder" -ForegroundColor Green
    Write-Host "Arquivos sincronizados nesta sessão: " -NoNewline -ForegroundColor White
    Write-Host "$syncCount" -ForegroundColor Magenta
    Write-Host ""
}

Show-Header

# Loop infinito
while ($true) {
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] Monitorando... " -NoNewline -ForegroundColor DarkGray
    
    # Verifica o status do git na pasta txt
    $status = git status --porcelain "$folder"
    
    if ($status) {
        Write-Host "ALTERAÇÕES DETECTADAS!" -ForegroundColor Red
        Write-Host "Iniciando processo de upload..." -ForegroundColor Yellow
        
        try {
            # Adiciona todos os arquivos (não apenas em txt, para garantir consistência do repo, conforme pedido 'git add .')
            # Adiciona todos os arquivos, excluindo explicitamente o arquivo bugado 'nul'
            git add . ":(exclude)nul"
            
            # Verifica se há algo para commitar depois do add
            $status_after_add = git status --porcelain
            if ($status_after_add) {
                $commit_time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
                $commit_msg = "Auto-sync: Novos arquivos detectados em $commit_time"
                
                git commit -m "$commit_msg" | Out-Null
                
                Write-Host "Enviando para o repositório remoto (PUSH)..." -ForegroundColor Yellow
                git push origin main
                
                if ($?) {
                    $syncCount++
                    Show-Header
                    Write-Host "[$timestamp] SUCESSO! Arquivos enviados para o GitHub." -ForegroundColor Green
                } else {
                    Write-Host "ERRO no push. Verifique sua conexão." -ForegroundColor Red
                }
            } else {
                Write-Host "Nada novo para commitar." -ForegroundColor Gray
            }
        }
        catch {
            Write-Error "Ocorreu um erro durante o processo git: $_"
        }
    } else {
        # Se não houve alterações, apenas sobrescreve a linha de status (simples efeito visual)
        Write-Host "OK" -ForegroundColor Green
    }
    
    # Aguarda 5 segundos antes da próxima verificação
    Start-Sleep -Seconds 5
}

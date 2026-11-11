# Verifica se algum processo do Editor continua aberto antes da atualizacao.
# Retorna 0 se livre, 3 se existe processo, 2 em falha de verificacao.
param(
    [string]$ScriptPath = 'D:\OFFline\Videos\@ensaio\_sistema\app\revisao_web.py'
)
try {
    $wanted = [System.IO.Path]::GetFullPath($ScriptPath)
    $active = @(Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine.IndexOf($wanted, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
            ($_.Name -ieq 'pythonw.exe' -or $_.Name -ieq 'python.exe')
        })
    if ($active.Count -gt 0) {
        Write-Host ''
        Write-Host 'ATENCAO: o Editor ainda esta em execucao.' -ForegroundColor Yellow
        foreach ($p in $active) {
            Write-Host ('  PID ' + $p.ProcessId + ' - ' + $p.Name)
        }
        Write-Host 'Encerre pelo botao Encerrar e execute a atualizacao novamente.'
        Write-Host 'Fechar a aba do navegador nao encerra o servidor.'
        exit 3
    }
    Write-Host 'Nenhum processo do Editor em execucao.'
    exit 0
} catch {
    Write-Host ('ERRO: nao foi possivel verificar os processos: ' + $_.Exception.Message)
    exit 2
}

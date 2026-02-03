# 👁️ Watchdog Auto-Restart

Sistema de monitoramento que **reinicia automaticamente** o daemon se ele cair.

## 🎯 O que faz

O Watchdog:
- ✅ Monitora o daemon a cada 30 segundos
- ✅ Reinicia automaticamente se o daemon cair
- ✅ Registra todos os restarts em log
- ✅ Mantém estatísticas de crashes
- ✅ Tenta reiniciar até 3 vezes antes de aguardar mais tempo
- ✅ Roda 24/7 sem supervisão

## 🚀 Como usar

### Método 1: Script Simples (Recomendado)

**Windows:**
```bash
# Clique duplo em:
INICIAR_WATCHDOG.bat

# Ou execute no terminal:
INICIAR_WATCHDOG.bat
```

**Linux/Mac:**
```bash
python watchdog_daemon.py
```

### Método 2: Personalizado

```bash
# Com configuração customizada
python watchdog_daemon.py \
  --languages en es ru \
  --batch-size 100 \
  --model qwen2.5:7b \
  --check-interval 15

# Verificação mais frequente (a cada 15s)
python watchdog_daemon.py --check-interval 15
```

## ⚙️ Parâmetros

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `--languages` | en es | Idiomas do daemon |
| `--batch-size` | 50 | Livros por ciclo |
| `--model` | bigllama/mistralv01-7b:latest | Modelo de tradução |
| `--cycle-delay` | 600 | Delay entre ciclos (10 min) |
| `--max-cycles` | 0 | Máximo de ciclos (0 = ∞) |
| `--check-interval` | 30 | Intervalo de verificação (segundos) |

## 🔄 Como funciona

```
[WATCHDOG INICIA]
├─ Inicia daemon
├─ Aguarda 30s
├─ Verifica se daemon está rodando
│  ├─ ✅ Rodando → Aguarda mais 30s
│  └─ ❌ Caiu → Reinicia automaticamente
└─ Repete indefinidamente
```

### Exemplo de execução

```
[10:00:00] 🚀 Iniciando daemon...
[10:00:05] ✅ Daemon iniciado (PID: 12345)
[10:00:35] ✅ Watchdog ativo | Restarts: 0
[10:05:00] ⚠️ DAEMON CAIU!
[10:05:10] 🚀 Reiniciando daemon...
[10:05:15] ✅ Daemon reiniciado (PID: 12456)
[10:05:45] ✅ Watchdog ativo | Restarts: 1
```

## 📊 Estatísticas

O watchdog salva estatísticas em `data/watchdog_stats.json`:

```json
{
  "total_restarts": 5,
  "daemon_crashes": 3,
  "start_time": "2026-01-27T10:00:00",
  "last_restart": "2026-01-27T15:30:00"
}
```

### Ver estatísticas

```bash
# Ver arquivo de estatísticas
cat data/watchdog_stats.json

# Ver logs do watchdog
tail -f logs/watchdog_20260127.log
```

## 🛑 Parar o Watchdog

```bash
# Método 1: Ctrl+C (recomendado)
Ctrl+C

# Isso irá:
# 1. Parar o watchdog
# 2. Parar o daemon com segurança
# 3. Salvar estatísticas
```

## 🔧 Comportamento em Falhas

### Falhas Consecutivas

```
Falha #1 → Aguarda 10s → Reinicia
Falha #2 → Aguarda 10s → Reinicia
Falha #3 → Aguarda 60s → Reinicia
Falha #4 → Aguarda 60s → Reinicia
...
```

Após 3 falhas consecutivas, o watchdog aguarda 1 minuto antes de tentar reiniciar.

### Auto-recuperação

O watchdog nunca desiste:
- ✅ Continua tentando reiniciar indefinidamente
- ✅ Registra todas as tentativas em log
- ✅ Mantém histórico de crashes
- ✅ Aguarda mais tempo após falhas consecutivas

## 📝 Logs

### Ver logs em tempo real

```bash
# Logs do watchdog
tail -f logs/watchdog_20260127.log

# Logs do daemon
tail -f logs/daemon_20260127.log

# Ambos
tail -f logs/*.log
```

### Buscar crashes

```bash
# Windows (PowerShell)
Select-String "DAEMON CAIU" logs/watchdog_*.log

# Linux/Mac
grep "DAEMON CAIU" logs/watchdog_*.log
```

## 🎯 Quando usar

### Use o Watchdog quando:

✅ Quer garantir que daemon roda 24/7
✅ Daemon ocasionalmente cai por erros externos
✅ Quer monitoramento automático
✅ Precisa de alta disponibilidade
✅ Vai deixar rodando por dias/semanas

### Não precisa de Watchdog quando:

❌ Vai executar apenas alguns ciclos
❌ Está testando o daemon
❌ Daemon é estável e nunca cai
❌ Você está presente para monitorar

## 💡 Dicas

### 1. Deixar rodando 24/7

```bash
# Windows - Inicie INICIAR_WATCHDOG.bat
# Minimize a janela
# Daemon + Watchdog rodarão continuamente
```

### 2. Rodar como Serviço (Windows)

Use NSSM (Non-Sucking Service Manager):

```bash
# Baixe NSSM: https://nssm.cc/download

# Instale como serviço
nssm install GoogolplexWatchdog "C:\Path\To\Python\python.exe" "D:\DEV\Googolplex-Books\watchdog_daemon.py"

# Inicie serviço
nssm start GoogolplexWatchdog
```

### 3. Verificação mais frequente

Para ambientes críticos:

```bash
# Verifica a cada 10 segundos
python watchdog_daemon.py --check-interval 10
```

### 4. Monitoramento remoto

```bash
# Monitore via SSH/Remote Desktop
tail -f logs/watchdog_*.log

# Ou use o arquivo de estatísticas
cat data/watchdog_stats.json
```

## 📁 Estrutura

```
Googolplex-Books/
├── watchdog_daemon.py        # Script watchdog principal
├── INICIAR_WATCHDOG.bat      # Atalho Windows
├── run_daemon.py             # Daemon que é monitorado
├── logs/
│   ├── watchdog_20260127.log # Logs do watchdog
│   └── daemon_20260127.log   # Logs do daemon
└── data/
    ├── watchdog_stats.json   # Estatísticas watchdog
    └── daemon_stats.json     # Estatísticas daemon
```

## ✅ Fluxo Completo

```
1. Você inicia: INICIAR_WATCHDOG.bat
2. Watchdog inicia
3. Watchdog inicia o daemon
4. Daemon processa livros (Hunter + Translator)
5. Watchdog verifica a cada 30s
6. Se daemon cair → Watchdog reinicia
7. Repete indefinidamente
8. Ctrl+C → Para watchdog e daemon
```

## 🎉 Pronto!

Agora você tem:
- ✅ Daemon rodando 24/7
- ✅ Auto-restart em caso de crash
- ✅ Logs detalhados
- ✅ Estatísticas de crashes
- ✅ Zero supervisão necessária

---

**Próximos passos:**

1. Execute `INICIAR_WATCHDOG.bat`
2. Minimize a janela
3. Deixe rodando
4. Verifique logs periodicamente
5. Daemon processará livros continuamente com auto-restart! 🚀

# 🔄 Auto Git Commit/Push

Sistema automático que faz **commit e push** de cada livro novo traduzido.

## 🎯 O que faz

O Auto-Git monitora continuamente a pasta `translated/` e:
- ✅ Detecta novos livros traduzidos (*_pt.txt)
- ✅ Faz `git add .` automaticamente
- ✅ Cria commit com mensagem descritiva
- ✅ Faz `git push` para o repositório
- ✅ Registra estatísticas de commits/pushes
- ✅ Roda 24/7 em background

## 🚀 Como usar

### Método 1: Script Simples (Recomendado)

**Windows:**
```bash
# Clique duplo em:
INICIAR_AUTO_GIT.bat

# Ou execute no terminal:
INICIAR_AUTO_GIT.bat
```

**Linux/Mac:**
```bash
python auto_git_push.py
```

### Método 2: Personalizado

```bash
# Verifica a cada 60 segundos
python auto_git_push.py --check-interval 60

# Verifica a cada 2 minutos
python auto_git_push.py --check-interval 120
```

## ⚙️ Parâmetros

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `--check-interval` | 30 | Intervalo de verificação (segundos) |

## 🔄 Como funciona

```
[AUTO-GIT INICIA]
├─ Escaneia arquivos existentes em translated/
├─ Aguarda 30s
├─ Verifica se há novos arquivos
│  ├─ ❌ Sem novos → Aguarda mais 30s
│  └─ ✅ Novos detectados:
│      ├─ git add .
│      ├─ git commit -m "Adicionar tradução: [Nome do Livro]"
│      └─ git push
└─ Repete indefinidamente
```

### Exemplo de execução

```
[14:00:00] 🔄 AUTO GIT COMMIT/PUSH - INICIADO
[14:00:00] 📂 Arquivos conhecidos: 125
[14:00:30] ✅ Auto-git ativo | Commits: 0
[14:01:00] 📝 Novos arquivos detectados: 1
[14:01:00]   • translated/Chess/Chess_pt.txt
[14:01:01] ✅ git add
[14:01:02] ✅ git commit
[14:01:05] ✅ git push
[14:01:05] ✅ COMMIT E PUSH CONCLUÍDOS
[14:01:05]    Arquivos: 1
[14:01:05]    Total de commits: 1
[14:01:05]    Total de pushes: 1
```

## 📝 Mensagens de Commit

### Um livro novo
```
Adicionar tradução: Chess

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Múltiplos livros
```
Adicionar 5 novas traduções

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## 📊 Estatísticas

O auto-git salva estatísticas em `data/auto_git_stats.json`:

```json
{
  "total_commits": 10,
  "total_pushes": 10,
  "total_files": 15,
  "start_time": "2026-01-27T14:00:00",
  "last_commit": "2026-01-27T15:30:00"
}
```

### Ver estatísticas

```bash
# Ver arquivo de estatísticas
cat data/auto_git_stats.json

# Ver logs do auto-git
tail -f logs/auto_git_20260127.log
```

## 🛑 Parar o Auto-Git

```bash
# Método 1: Ctrl+C (recomendado)
Ctrl+C

# Isso irá:
# 1. Parar o monitoramento
# 2. Salvar estatísticas
```

## 🔧 Integração com Daemon e Watchdog

### Usar os 3 juntos (Recomendado)

Execute em janelas separadas:

**Janela 1: Watchdog + Daemon**
```bash
INICIAR_WATCHDOG.bat
```

**Janela 2: Auto-Git**
```bash
INICIAR_AUTO_GIT.bat
```

### O que cada um faz

```
Watchdog → Monitora e reinicia o daemon
    ↓
Daemon → Baixa e traduz livros
    ↓
Auto-Git → Faz commit/push de cada livro novo
```

### Fluxo completo

```
1. Watchdog inicia daemon
2. Daemon baixa livros (Hunter)
3. Daemon traduz livros (Translator)
4. Auto-git detecta novo livro traduzido
5. Auto-git faz commit + push
6. Repete indefinidamente
```

## 📝 Logs

### Ver logs em tempo real

```bash
# Logs do auto-git
tail -f logs/auto_git_20260127.log

# Ver tudo junto
tail -f logs/auto_git_*.log logs/daemon_*.log logs/watchdog_*.log
```

### Buscar commits

```bash
# Windows (PowerShell)
Select-String "COMMIT E PUSH" logs/auto_git_*.log

# Linux/Mac
grep "COMMIT E PUSH" logs/auto_git_*.log
```

## 💡 Dicas

### 1. Monitoramento mais frequente

Para commits mais rápidos:

```bash
# Verifica a cada 10 segundos
python auto_git_push.py --check-interval 10
```

### 2. Background em Linux/Mac

```bash
# Roda em background
nohup python auto_git_push.py &

# Ver logs
tail -f nohup.out
```

### 3. Sistema completo 24/7

Para deixar tudo rodando:

```bash
# Terminal 1: Watchdog
python watchdog_daemon.py &

# Terminal 2: Auto-git
python auto_git_push.py &

# Agora está tudo rodando em background!
```

### 4. Evitar conflitos de push

Se múltiplas máquinas fazem push:

```bash
# Antes de cada commit, o auto-git faz:
# git add .
# git commit
# git push

# Se houver conflito, o push falha mas o commit fica local
# Você pode fazer git pull manual depois
```

## 🛡️ Segurança

### O que o auto-git NÃO faz

❌ Não faz force push
❌ Não sobrescreve commits existentes
❌ Não comita arquivos sensíveis (.env, credentials, etc)
❌ Não faz rebase ou merge automático

### O que ele FAZ

✅ Apenas `git add .`, `git commit`, `git push`
✅ Se push falhar, apenas registra o erro
✅ Commits sempre com mensagem descritiva
✅ Respeita .gitignore

## 📁 Estrutura

```
Googolplex-Books/
├── auto_git_push.py          # Script principal
├── INICIAR_AUTO_GIT.bat      # Atalho Windows
├── logs/
│   └── auto_git_20260127.log # Logs do auto-git
├── data/
│   └── auto_git_stats.json   # Estatísticas
└── translated/               # Pasta monitorada
    ├── Chess/
    │   └── Chess_pt.txt     # Auto-git detecta isso
    └── ...
```

## ⚠️ Avisos

### Quando NÃO usar

❌ Se você quer revisar traduções antes de commitar
❌ Se múltiplas pessoas editam o mesmo repositório ao mesmo tempo
❌ Se você quer fazer commits em lotes (batch)

### Quando usar

✅ Tradução automática 24/7
✅ Você é o único editando o repositório
✅ Quer backup automático de cada tradução
✅ Quer histórico detalhado (1 commit por livro)

## 🎉 Pronto!

Agora você tem:
- ✅ Commit automático de cada livro novo
- ✅ Push automático para GitHub
- ✅ Histórico completo de traduções
- ✅ Backup contínuo
- ✅ Zero intervenção manual

---

**Sistema completo:**

```
👁️ Watchdog → 🤖 Daemon → 🔄 Auto-Git → 📦 GitHub
   (monitora)  (traduz)   (commit)    (backup)
```

**Execute tudo:**
1. `INICIAR_WATCHDOG.bat` (terminal 1)
2. `INICIAR_AUTO_GIT.bat` (terminal 2)
3. Deixe rodando 24/7
4. Todos os livros traduzidos vão automaticamente para o GitHub! 🚀

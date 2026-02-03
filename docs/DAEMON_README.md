# 🤖 Daemon Autônomo 24/7

Sistema que roda **continuamente o dia todo** sem precisar da sua presença.

## 🎯 O que faz

O daemon executa um **loop infinito** com 4 etapas:

```
LOOP INFINITO:
  1. Baixa livros (Hunter)          ← 📥
  2. Traduz livros (Translator)     ← 🌍
  3. Aguarda N segundos             ← ⏳
  4. Volta para 1                   ← 🔄
```

## 🚀 Iniciar Daemon

### Windows
```bash
# Clique duplo ou execute:
start_daemon.bat

# Ou personalizado:
python run_daemon.py --languages en es --batch-size 50
```

### Linux/Mac
```bash
chmod +x start_daemon.sh
./start_daemon.sh

# Ou personalizado:
python run_daemon.py --languages en es --batch-size 50
```

## ⚙️ Configurações

### Básico
```bash
# Roda indefinidamente (padrão)
python run_daemon.py --languages en es

# Processa 100 livros por idioma a cada ciclo
python run_daemon.py --languages en es ru --batch-size 100

# Usa modelo mais rápido
python run_daemon.py --languages en --batch-size 50 --model gemma2:2b
```

### Avançado
```bash
# Aguarda apenas 5 minutos entre ciclos
python run_daemon.py --languages en es --cycle-delay 300

# Executa apenas 10 ciclos e para
python run_daemon.py --languages en --batch-size 50 --max-cycles 10

# Ciclo ultra-rápido
python run_daemon.py --languages en --batch-size 10 --cycle-delay 60
```

## 📊 Parâmetros

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `--languages` | en es | Idiomas para processar |
| `--batch-size` | 50 | Livros por idioma em cada ciclo |
| `--model` | qwen2.5:7b | Modelo Ollama para tradução |
| `--cycle-delay` | 600 | Segundos entre ciclos (600 = 10 min) |
| `--max-cycles` | 0 | Máximo de ciclos (0 = infinito) |

## 🔄 Ciclo de Execução

```
[CICLO 1]
├─ Baixa 50 livros em EN (Hunter)
├─ Baixa 50 livros em ES (Hunter)
├─ Traduz todos os livros baixados (Translator)
└─ Aguarda 10 minutos

[CICLO 2]
├─ Baixa mais 50 livros em EN
├─ Baixa mais 50 livros em ES
├─ Traduz novos livros
└─ Aguarda 10 minutos

[CICLO 3]
...
```

## 📈 Estatísticas

O daemon salva estatísticas em `data/daemon_stats.json`:

```json
{
  "total_books_downloaded": 500,
  "total_books_translated": 450,
  "total_cycles": 10,
  "total_errors": 2,
  "start_time": "2026-01-27T10:00:00",
  "last_cycle": "2026-01-27T15:30:00"
}
```

### Ver estatísticas
```bash
cat data/daemon_stats.json

# Ou veja os logs
tail -f logs/daemon_20260127.log
```

## 📝 Logs

Logs são salvos em `logs/daemon_YYYYMMDD.log`:

```bash
# Ver logs em tempo real
tail -f logs/daemon_20260127.log

# Ver últimas 100 linhas
tail -n 100 logs/daemon_20260127.log

# Buscar erros
grep ERROR logs/daemon_20260127.log
```

## 🛑 Parar Daemon

```bash
# Método 1: Ctrl+C (recomendado - para com segurança)
Ctrl+C

# Método 2: Fechar terminal (funciona, mas menos elegante)
```

O daemon **sempre salva estatísticas** antes de parar, mesmo com Ctrl+C.

## ⏱️ Exemplos de Uso

### Caso 1: Deixar rodando o dia todo
```bash
# Roda 24h sem parar
python run_daemon.py --languages en es --batch-size 50

# Deixa rodando e vai fazer outra coisa
# Daemon continuará processando automaticamente
```

### Caso 2: Processar tudo rapidamente
```bash
# Lotes grandes, delay curto
python run_daemon.py --languages en es ru --batch-size 200 --cycle-delay 60
```

### Caso 3: Processar durante a noite
```bash
# Inicia antes de dormir, processa a noite toda
python run_daemon.py --languages en es --batch-size 100 --cycle-delay 300
```

### Caso 4: Teste rápido (3 ciclos)
```bash
# Roda apenas 3 ciclos e para
python run_daemon.py --languages en --batch-size 10 --max-cycles 3
```

## 🔧 Recursos

### Auto-recuperação
- ✅ Se Hunter falha, continua para Translator
- ✅ Se Translator falha, continua para próximo ciclo
- ✅ Retry automático após erros
- ✅ Nunca trava

### Gerenciamento
- ✅ Inicia Ollama automaticamente
- ✅ Verifica se modelo existe (baixa se necessário)
- ✅ Salva estatísticas a cada ciclo
- ✅ Logs detalhados

### Controle
- ✅ Para com segurança (Ctrl+C)
- ✅ Pode limitar número de ciclos
- ✅ Configurável via CLI

## 🎯 Recomendações

### Para deixar rodando 24/7
```bash
# Configuração balanceada
python run_daemon.py \
  --languages en es \
  --batch-size 50 \
  --model qwen2.5:7b \
  --cycle-delay 600
```

**Isso vai:**
- Processar 100 livros por ciclo (50 en + 50 es)
- Executar ~6 ciclos por hora (10 min entre ciclos)
- Processar ~600 livros por hora
- Usar modelo de boa qualidade

### Para processamento rápido
```bash
# Máxima velocidade
python run_daemon.py \
  --languages en \
  --batch-size 200 \
  --model gemma2:2b \
  --cycle-delay 60
```

**Isso vai:**
- Processar 200 livros por ciclo
- Executar ~60 ciclos por hora (1 min entre ciclos)
- Usar modelo mais rápido (menor qualidade)

## 📁 Estrutura

```
Googolplex-Books/
├── run_daemon.py          # Script daemon principal
├── start_daemon.bat       # Atalho Windows
├── start_daemon.sh        # Atalho Linux/Mac
├── logs/
│   └── daemon_20260127.log   # Logs do dia
├── data/
│   └── daemon_stats.json     # Estatísticas
├── txt/                   # Livros baixados
└── translated/            # Livros traduzidos
```

## ✅ Resumo

| Comando | Uso |
|---------|-----|
| `python run_daemon.py` | Inicia daemon (padrão) |
| `start_daemon.bat` | Atalho Windows |
| `./start_daemon.sh` | Atalho Linux/Mac |
| `Ctrl+C` | Para daemon |
| `tail -f logs/daemon_*.log` | Ver logs |
| `cat data/daemon_stats.json` | Ver estatísticas |

---

## 🎉 Pronto!

Agora você pode:
1. ✅ Iniciar o daemon com um comando
2. ✅ Deixar rodando 24/7 sem supervisão
3. ✅ Processar centenas/milhares de livros automaticamente
4. ✅ Ver estatísticas e logs em tempo real
5. ✅ Parar com segurança a qualquer momento

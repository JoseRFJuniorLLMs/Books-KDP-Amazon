# 🚀 Como Executar o Googolplex-Books

## 📋 Pré-requisitos

### 1. Instalar Ollama (modelo LOCAL)
```bash
# Windows: Baixe em https://ollama.ai
# Linux/Mac:
curl -fsSL https://ollama.com/install.sh | sh

# Inicie o Ollama
ollama serve
```

### 2. Baixar modelo rápido
```bash
# Modelo RECOMENDADO (rápido e melhor qualidade):
ollama pull qwen2.5:7b

# Outras opções:
ollama pull gemma2:2b      # Mais rápido (menor qualidade)
ollama pull llama3.2:3b    # Rápido e boa qualidade
```

### 3. Instalar dependências Python
```bash
pip install requests tqdm langdetect python-dotenv
```

---

## 🎯 Executar os Módulos Separadamente

### **1️⃣ HUNTER - Baixar Livros (Sequencial)**

Baixa livros do Project Gutenberg:

```bash
# Baixar livros em inglês e espanhol (50 de cada)
python run_hunter.py --languages en es --limit 50

# Baixar livros em português
python run_hunter.py --languages pt --limit 100

# Baixar livros de um autor específico
python run_hunter.py --author "Machado de Assis" --limit 20

# Apenas atualizar catálogo
python run_hunter.py --init
```

**Opções:**
- `--languages` / `-L`: Idiomas (en, es, ru, fr, de, pt, it)
- `--limit` / `-l`: Quantos livros por idioma
- `--author` / `-a`: Baixar de um autor específico
- `--init`: Apenas baixar/atualizar catálogo

**Saída:** Livros salvos em `txt/autor/titulo.txt`

---

### **2️⃣ TRANSLATOR - Traduzir Livros (LOCAL, Ollama)**

Traduz livros usando modelo LOCAL (sem API):

```bash
# Traduzir livros em inglês e espanhol (modelo RECOMENDADO)
python run_translator.py --languages en es

# Traduzir 10 livros
python run_translator.py --languages en --limit 10

# Usar modelo mais rápido (menor qualidade)
python run_translator.py --languages ru --model gemma2:2b
```

**Opções:**
- `--languages` / `-l`: Idiomas para traduzir (en, es, ru, fr, de, it)
- `--limit` / `-n`: Limite de livros (0 = todos)
- `--model` / `-m`: Modelo Ollama (padrão: gemma2:2b, o mais rápido)

**Modelos disponíveis (do mais rápido ao mais lento):**
| Modelo | Velocidade | Qualidade | Uso de RAM | Recomendação |
|--------|------------|-----------|------------|--------------|
| `qwen2.5:7b` | ⚡⚡ Rápido | ⭐⭐⭐⭐ Excelente | ~6 GB | ✅ **RECOMENDADO** |
| `gemma2:2b` | ⚡⚡⚡ Muito rápido | ⭐⭐ Boa | ~2 GB | RAM limitada |
| `llama3.2:3b` | ⚡⚡ Rápido | ⭐⭐⭐ Muito boa | ~3 GB | Alternativa |
| `qwen2.5:14b` | 🐌 Lento | ⭐⭐⭐⭐⭐ Perfeito | ~12 GB | Máxima qualidade |

**Saída:** Traduções em `translated/autor/titulo_pt.txt`

---

## 📊 Exemplo de Fluxo Completo

### Opção 1: **AUTOMÁTICO** (tudo em paralelo) ✨

```bash
# Executa TUDO automaticamente (Hunter + Translator em PARALELO)
python run_all.py --languages en es --limit 20

# Windows
run_all.bat en es 20

# Linux/Mac
chmod +x run_all.sh
./run_all.sh en es 20
```

O script automático:
- ✅ Inicia Ollama automaticamente
- ✅ Baixa modelo + livros **EM PARALELO**
- ✅ Traduz livros automaticamente

### Opção 2: Manual (passo a passo)

```bash
# 1. Certifique-se que Ollama está rodando
ollama serve

# 2. Baixe o modelo RECOMENDADO
ollama pull qwen2.5:7b

# 3. Baixe livros em inglês e espanhol
python run_hunter.py --languages en es --limit 20

# 4. Traduza os livros baixados (usa qwen2.5:7b por padrão)
python run_translator.py --languages en es

# 5. Veja as traduções
ls translated/
```

---

## 🔧 Troubleshooting

### Ollama não conecta
```bash
# Verifique se está rodando
curl http://localhost:11434/api/tags

# Se não estiver, inicie:
ollama serve
```

### Modelo não encontrado
```bash
# Liste modelos instalados
ollama list

# Baixe o modelo
ollama pull gemma2:2b
```

### Tradução muito lenta
```bash
# Use modelo mais rápido (menor qualidade)
python run_translator.py --model gemma2:2b

# Ou limite os livros
python run_translator.py --limit 5

# Ou use qwen2.5:3b se tiver pouca RAM
ollama pull qwen2.5:3b
python run_translator.py --model qwen2.5:3b
```

---

## 📁 Estrutura de Pastas

```
Googolplex-Books/
├── txt/                    # Livros baixados pelo Hunter
│   └── Autor/
│       └── titulo.txt
├── translated/             # Livros traduzidos
│   └── Autor/
│       └── titulo_pt.txt
├── data/
│   ├── books.db           # Banco de livros
│   └── translation_cache.db  # Cache de traduções
├── run_hunter.py          # Script para baixar livros
└── run_translator.py      # Script para traduzir livros
```

---

## ⚙️ Configurações Avançadas

### Alterar configurações padrão

Edite `config/settings.py`:

```python
# URL do Ollama (se rodando em outra máquina)
OLLAMA_BASE_URL = "http://192.168.1.100:11434"

# Modelo padrão
OLLAMA_MODEL = "qwen2.5:7b"
```

### Usar .env

Crie `.env` na raiz:

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

---

## 🎯 Resumo dos Comandos

| Ação | Comando |
|------|---------|
| **TUDO AUTOMÁTICO** ✨ | `python run_all.py --languages en es --limit 20` |
| Baixar livros | `python run_hunter.py --languages en es --limit 50` |
| Traduzir livros | `python run_translator.py --languages en es` |
| Listar modelos | `ollama list` |
| Baixar modelo | `ollama pull qwen2.5:7b` |
| Iniciar Ollama | `ollama serve` |

### Exemplos de uso do run_all.py

```bash
# Básico (en + es, 20 livros cada)
python run_all.py

# Customizado
python run_all.py --languages en es ru --limit 50 --model qwen2.5:7b

# Só baixar (não traduzir)
python run_all.py --languages en es --limit 100 --skip-translate

# Só traduzir (não baixar)
python run_all.py --languages en es --skip-download
```

---

## 🤖 Modo Daemon (Autônomo 24/7)

Para deixar rodando **o dia todo** sem supervisão:

```bash
# Windows
start_daemon.bat

# Linux/Mac
./start_daemon.sh

# Ou manualmente:
python run_daemon.py --languages en es --batch-size 50
```

O daemon:
- ✅ Roda **continuamente** (loop infinito)
- ✅ Baixa + traduz automaticamente
- ✅ Salva estatísticas e logs
- ✅ Auto-recuperação de erros
- ✅ Para com Ctrl+C

Ver [DAEMON_README.md](DAEMON_README.md) para detalhes.

---

## ✅ Pronto!

Agora você pode:
1. ✅ Baixar livros com `run_hunter.py` (sequencial)
2. ✅ Traduzir com `run_translator.py` (usando Ollama LOCAL, modelo **qwen2.5:7b**)
3. ✅ Executar tudo automático com `run_all.py` (paralelo)
4. ✅ **Deixar rodando 24/7 com `run_daemon.py`** (autônomo)
5. ✅ Sem usar APIs externas
6. ✅ Tudo local e gratuito

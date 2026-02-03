# 📚 Hunter2 - Archive.org Book Downloader

Sistema que baixa livros do **Internet Archive** (archive.org), expandindo suas fontes além do Project Gutenberg.

## 🎯 O que é o Archive.org?

O **Internet Archive** é uma biblioteca digital sem fins lucrativos que:
- ✅ Contém **40+ milhões de livros**
- ✅ Inclui livros de domínio público
- ✅ Tem coleções em **100+ idiomas**
- ✅ Oferece acesso gratuito
- ✅ API pública para busca e download

## 🆚 Hunter1 vs Hunter2

| Característica | Hunter1 (Gutenberg) | Hunter2 (Archive.org) |
|----------------|---------------------|----------------------|
| **Fonte** | Project Gutenberg | Internet Archive |
| **Total de livros** | ~70.000 | ~40 milhões |
| **Idiomas** | 60+ | 100+ |
| **Formatos** | TXT, EPUB, PDF | TXT, PDF, EPUB, DJVU, MOBI |
| **Foco** | Clássicos literários | Diversidade total |
| **Qualidade** | Alta (curadoria) | Variável |

## 🚀 Como usar

### Método 1: Script Interativo (Recomendado)

**Windows:**
```bash
# Clique duplo em:
EXECUTAR_HUNTER2.bat

# Vai perguntar:
# - Idiomas (en, es, pt, etc.)
# - Quantidade de livros
```

### Método 2: Linha de comando

```bash
# Baixar 50 livros em inglês
python run_hunter2.py --languages en --limit 50

# Múltiplos idiomas
python run_hunter2.py --languages en es pt --limit 100

# Apenas português
python run_hunter2.py --languages pt --limit 200
```

### Método 3: Dual Hunter (Recomendado!)

Baixa de **ambas as fontes** para maximizar variedade:

```bash
# Windows - Clique duplo em:
EXECUTAR_DUAL_HUNTER.bat

# Ou via linha de comando:
python run_dual_hunter.py --languages en es --limit 50
```

## ⚙️ Parâmetros

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `--languages` | en | Idiomas para buscar |
| `--limit` | 50 | Livros por idioma |

## 🌐 Idiomas Suportados

```
en = Inglês          pt = Português
es = Espanhol        fr = Francês
de = Alemão          it = Italiano
ru = Russo
```

## 📖 Tipos de livros

O Archive.org tem **muito mais variedade** que o Gutenberg:

### Gutenberg (Hunter1)
- Clássicos da literatura
- Obras antigas (>70 anos)
- Curadoria rigorosa
- Qualidade uniforme

### Archive.org (Hunter2)
- **Tudo do Gutenberg** +
- Livros técnicos e acadêmicos
- Revistas e periódicos
- Documentos históricos
- Livros modernos digitalizados
- Coleções especializadas
- Qualidade variável

## 🔄 Como funciona

```
1. Hunter2 consulta API do Archive.org
   ↓
2. Busca por:
   • mediatype:texts (livros)
   • language:[idioma]
   • format:txt (preferência)
   ↓
3. Ordena por downloads (mais populares primeiro)
   ↓
4. Baixa metadados de cada livro
   ↓
5. Procura arquivo .txt
   ↓
6. Download e salva em txt/[Autor]/[Título].txt
```

## 📊 Estatísticas

### Ver estatísticas

```bash
# Logs do Hunter2
tail -f logs/hunter2_20260127.log

# Logs do Dual Hunter
tail -f logs/dual_hunter_20260127.log
```

### Exemplo de output

```
============================================================
HUNTER2 - Archive.org
Idiomas: ['en', 'es']
Limite por idioma: 50
============================================================

--- Idioma: EN ---
Buscando livros em EN no Archive.org...
Encontrados 50 livros em EN
Baixando EN: 100%|████████████| 50/50 [02:15<00:00]

--- Idioma: ES ---
Buscando livros em ES no Archive.org...
Encontrados 50 livros em ES
Baixando ES: 100%|████████████| 50/50 [02:30<00:00]

============================================================
RESUMO
Encontrados: 100
Baixados: 45
Pulados (já existem): 55
Falhas: 0
Pasta: D:\DEV\Googolplex-Books\txt
============================================================
```

## 🎯 Estratégias de Download

### 1. Máxima Variedade (Dual Hunter)

Use ambas as fontes:

```bash
python run_dual_hunter.py --languages en es pt --limit 100
```

**Resultado:** ~200-300 livros de fontes diferentes

### 2. Apenas Archive.org

Para coleções específicas:

```bash
python run_hunter2.py --languages pt --limit 500
```

**Resultado:** Livros em português do Archive.org

### 3. Download Massivo

Para construir grande biblioteca:

```bash
# Gutenberg
python run_hunter.py --languages en es pt fr de --limit 200

# Archive.org
python run_hunter2.py --languages en es pt fr de --limit 200
```

**Resultado:** ~1000-2000 livros de múltiplas fontes

## 🔧 Integração com Daemon

### Atualizar daemon para usar Hunter2

O daemon pode usar o Dual Hunter para baixar de ambas as fontes.

**Edite run_daemon.py** (linha ~315):

```python
# ANTES:
hunter_cmd = [
    sys.executable,
    'run_hunter.py',
    '--languages'] + self.languages + [
    '--limit', str(self.batch_size)
]

# DEPOIS (usar dual hunter):
hunter_cmd = [
    sys.executable,
    'run_dual_hunter.py',
    '--languages'] + self.languages + [
    '--limit', str(self.batch_size)
]
```

Agora o daemon baixará de **ambas as fontes** automaticamente!

## 📁 Estrutura de arquivos

```
Googolplex-Books/
├── src/
│   ├── hunter.py           # Hunter1 (Gutenberg)
│   └── hunter2.py          # Hunter2 (Archive.org)
├── run_hunter.py           # Executa Hunter1
├── run_hunter2.py          # Executa Hunter2
├── run_dual_hunter.py      # Executa ambos
├── EXECUTAR_HUNTER2.bat    # Atalho Hunter2
├── EXECUTAR_DUAL_HUNTER.bat # Atalho Dual
├── logs/
│   ├── hunter_*.log        # Logs Hunter1
│   ├── hunter2_*.log       # Logs Hunter2
│   └── dual_hunter_*.log   # Logs Dual
└── txt/                    # Livros baixados
    ├── [Autor]/
    │   └── [Título].txt
```

## 🛠️ Troubleshooting

### Erro: "No module named 'bs4'"

```bash
pip install beautifulsoup4
```

### Erro: "No module named 'fitz'"

```bash
pip install PyMuPDF
```

### Erro: "No module named 'ebooklib'"

```bash
pip install ebooklib
```

### Poucos livros baixados

Alguns livros podem não ter formato TXT disponível. O Hunter2 prioriza TXT e pula outros formatos por enquanto.

**Solução:** Aumentar o limit:

```bash
python run_hunter2.py --languages en --limit 200
```

### Livros duplicados

O Hunter2 verifica se o livro já existe antes de baixar. Se mesmo assim houver duplicatas, é porque são edições diferentes.

## 💡 Dicas

### 1. Começar com Dual Hunter

```bash
# Baixe de ambas as fontes
EXECUTAR_DUAL_HUNTER.bat
```

Isso garante máxima variedade logo de cara.

### 2. Idiomas menos comuns

Archive.org tem ótima cobertura de idiomas raros:

```bash
python run_hunter2.py --languages ru it --limit 100
```

### 3. Download em lote

Para construir biblioteca grande rapidamente:

```bash
# Loop de downloads
for /L %i in (1,1,10) do (
    python run_dual_hunter.py --languages en es pt --limit 100
    timeout /t 60
)
```

### 4. Monitorar progresso

```bash
# Em outro terminal
tail -f logs/hunter2_*.log
```

## 📈 Performance

### Velocidade

- **Hunter1 (Gutenberg):** ~1-2 livros/segundo
- **Hunter2 (Archive.org):** ~0.5-1 livro/segundo (mais lento devido a API)
- **Dual Hunter:** ~1 livro/segundo (executa sequencial)

### Rate Limiting

Hunter2 tem delay de 0.5s entre downloads para não sobrecarregar o Archive.org.

## ⚠️ Avisos

### Legal

✅ Archive.org fornece acesso legal a:
- Livros de domínio público
- Livros com permissão de distribuição
- Coleções com licenças abertas

❌ Respeite os termos de uso do Archive.org

### Qualidade

Archive.org tem **qualidade variável**:
- Alguns livros são scans de alta qualidade
- Outros podem ter erros de OCR
- Metadados podem estar incompletos

**Recomendação:** Use Dual Hunter para ter mix de qualidade (Gutenberg) + variedade (Archive.org)

## 🎉 Pronto!

Agora você tem:
- ✅ Acesso a 40+ milhões de livros
- ✅ Hunter2 para Archive.org
- ✅ Dual Hunter para ambas as fontes
- ✅ Máxima variedade de conteúdo

---

**Próximos passos:**

1. Execute `EXECUTAR_DUAL_HUNTER.bat`
2. Escolha idiomas e quantidade
3. Aguarde downloads
4. Livros vão para `txt/`
5. Daemon traduzirá automaticamente!
6. Auto-git fará commit/push! 🚀

**Sistema completo:**
```
Hunter1 (Gutenberg) + Hunter2 (Archive.org)
            ↓
        Dual Hunter
            ↓
        txt/ (livros)
            ↓
        Daemon (traduz)
            ↓
    translated/ (PT)
            ↓
      Auto-Git (commit)
            ↓
        GitHub (backup)
```

**Biblioteca infinita em piloto automático! 📚✨**

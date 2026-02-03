# 🎨 Cover Generator - Gerador de Capas com IA

Sistema que gera capas profissionais de livros usando múltiplas APIs de IA.

## 🎯 O que faz?

O Cover Generator:
1. ✅ Lê autor e título do livro
2. ✅ Analisa o tema do livro usando IA local (Ollama)
3. ✅ Gera prompts otimizados seguindo **padrões KDP/Amazon**
4. ✅ Cria capas usando múltiplas APIs de IA
5. ✅ Salva as imagens junto com o arquivo DOCX

## 📐 Padrões KDP (Kindle Direct Publishing)

As capas são geradas seguindo as especificações da Amazon KDP:

**Proporções:**
- **Ideal KDP:** 1.6:1 (altura:largura) - ex: 1600x2560px
- **DALL-E 3:** 1024x1792px (1.75:1) - próximo do ideal
- **Gemini:** Proporção 5:8 (1.6:1) - **EXATO ao padrão KDP** ⭐
- **Grok:** 1024x1792px (1.75:1) - próximo do ideal

**Especificações técnicas:**
- ✅ Alta resolução (equivalente a 300 DPI)
- ✅ Orientação vertical (portrait)
- ✅ Cores vibrantes e alto contraste
- ✅ Legível em thumbnail (200x300px)
- ✅ Pronto para impressão e ebook

**Design profissional:**
- ✅ Margens de segurança (0.125")
- ✅ Espaço para título (topo 20%)
- ✅ Foco visual central (meio 60%)
- ✅ Espaço para autor (base 20%)
- ✅ Sem texto na imagem (será adicionado depois)
- ✅ Composição pela regra dos terços

## 🤖 APIs Suportadas (Os 3)

### 1. OpenAI DALL-E 3

**Qualidade:** ⭐⭐⭐⭐⭐
**Custo:** $0.040 por imagem (1024x1792)
**Velocidade:** ~30-40 segundos

**Como configurar:**
```bash
# Windows PowerShell
$env:OPENAI_API_KEY="sk-..."

# Windows CMD
set OPENAI_API_KEY=sk-...

# Ou adicione ao .env
OPENAI_API_KEY=sk-...
```

**Obter API key:**
1. Acesse https://platform.openai.com/api-keys
2. Crie uma nova chave
3. Configure no ambiente

### 2. Google Gemini Imagen 3.0

**Qualidade:** ⭐⭐⭐⭐⭐
**Custo:** Consultar pricing do Google AI Studio
**Velocidade:** ~20-30 segundos

**Como configurar:**
```bash
# Windows
set GOOGLE_API_KEY=...

# .env
GOOGLE_API_KEY=...
```

**Obter API key:**
1. Acesse https://aistudio.google.com/app/apikey
2. Crie uma API key
3. Configure no ambiente

### 3. xAI Grok

**Qualidade:** ⭐⭐⭐⭐⭐
**Custo:** Consultar pricing do xAI
**Velocidade:** ~25-35 segundos

**Como configurar:**
```bash
# Windows
set XAI_API_KEY=...

# .env
XAI_API_KEY=...
```

**Obter API key:**
1. Acesse https://console.x.ai
2. Crie uma conta xAI
3. Gere uma API key
4. Configure no ambiente

## 🎨 Prompt Profissional Otimizado

O sistema usa um **prompt avançado** que instrui as IAs a seguir:

### Especificações Técnicas KDP
- Proporção 1.6:1 (altura:largura)
- Alta resolução (300 DPI equivalente)
- Cores vibrantes e alto contraste
- Legível em thumbnail

### Composição Profissional
- **Topo 20%:** Espaço para título (imagery sutil)
- **Meio 60%:** Foco visual principal (imagem forte)
- **Base 20%:** Espaço para nome do autor (área limpa)

### Elementos Visuais
- Focal point central claro
- Regra dos terços
- Margens de segurança 0.125"
- Hierarquia visual definida

### Marketability
- Atrativo para o gênero específico
- Competitivo com bestsellers
- Funciona em thumbnail pequeno (200x300px)
- Qualidade de impressão profissional

## 🚀 Como usar

### Método 1: Script Interativo (Windows)

**Clique duplo em:**
```bash
EXECUTAR_COVER_GENERATOR.bat
```

Escolha:
- Opção 1: Gerar capa para um livro específico
- Opção 2: Gerar capas para todos os livros traduzidos

### Método 2: Linha de comando

**Um livro específico:**
```bash
python src\cover_generator.py --input "translated\Chess\Nezhmetdinov_pt.txt"
```

**Todos os livros (batch):**
```bash
python src\cover_generator.py --batch
```

**Com DOCX específico:**
```bash
python src\cover_generator.py --input "translated\Chess\Nezhmetdinov_pt.txt" --docx "docx\Chess\Nezhmetdinov_Final.docx"
```

## 📁 Estrutura de arquivos

Após gerar capas, a estrutura fica:

```
translated/
├── Chess/
│   ├── Nezhmetdinov_pt.txt
│   ├── cover_abc12345_dalle_3.png      # DALL-E 3
│   ├── cover_abc12345_stability_ai.png # Stability AI
│   └── ...

docx/
├── Chess/
│   ├── Nezhmetdinov_Final.docx
│   ├── cover_abc12345_dalle_3.png      # Também aqui se especificado
│   └── ...
```

## 🎨 Como funciona?

### 1. Análise do Livro

O sistema usa Ollama (IA local) para analisar:
- **Gênero literário** (ficção, romance, técnico, etc.)
- **Temas principais** (tecnologia, amor, guerra, etc.)
- **Estilo visual** (minimalista, épico, sombrio, etc.)
- **Atmosfera** (contemplativo, energético, misterioso, etc.)

**Exemplo de análise:**
```json
{
  "genre": "ficção científica",
  "themes": ["tecnologia", "futuro", "distopia"],
  "style": "futurista, sombrio",
  "mood": "misterioso",
  "summary": "Obra sobre o impacto da tecnologia na sociedade"
}
```

### 2. Geração de Prompt

Baseado na análise, cria prompts otimizados:

```
Book cover design for "Neuromancer" by William Gibson.

Genre: ficção científica
Themes: tecnologia, futuro, distopia
Style: futurista, sombrio, misterioso

Visual requirements:
- Professional book cover design
- Clean typography with title and author name
- Evocative imagery that captures the book's essence
- High contrast and readability
- Suitable for print and digital
- No text or words in the image
```

### 3. Geração de Imagem

Cada API recebe o prompt e gera uma imagem:
- **DALL-E 3:** 1024x1792px (proporção de capa)
- **Stability AI:** 1024x1792px
- **Gemini:** (em desenvolvimento)

### 4. Salvamento

As imagens são salvas com nomes únicos:
- `cover_abc12345_dalle_3.png`
- `cover_abc12345_stability_ai.png`

O hash `abc12345` é baseado em autor+título para evitar duplicatas.

## 📊 Resultados Esperados

**Por livro:**
- 3 capas (uma de cada API: DALL-E 3, Gemini, Grok)
- Tempo total: ~1.5-2 minutos
- Custo: ~$0.04-0.10 (dependendo das APIs)

**Batch (27 livros traduzidos):**
- 81 capas (27 x 3 APIs)
- Tempo total: ~40-60 minutos
- Custo: ~$1.08-2.70 (dependendo das APIs)

## 🔧 Integração com Daemon

O daemon **automaticamente** gera capas após traduzir livros:

```
FLUXO COMPLETO DO DAEMON:
┌─────────────────────────────────┐
│  1. Dual Hunter (download)      │
│     ↓                            │
│  2. Translator (traduz)         │
│     ↓                            │
│  3. Processor (DOCX)   🆕       │
│     ↓                            │
│  4. Cover Generator   🆕        │
│     ↓                            │
│  5. Auto-Git (commit)           │
└─────────────────────────────────┘
```

O daemon agora tem **4 fases** por ciclo:
1. Download de livros (Gutenberg + Archive.org)
2. Tradução para português
3. Geração de DOCX formatado
4. Geração de capas com IA

## ⚙️ Configuração Avançada

### Variáveis de ambiente (.env)

```bash
# APIs de Imagem (Os 3)
OPENAI_API_KEY=sk-...         # DALL-E 3
GOOGLE_API_KEY=...            # Gemini Imagen
XAI_API_KEY=...               # Grok (xAI)

# Ollama (análise do livro)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

### Requisitos

```bash
pip install openai
pip install google-generativeai
pip install requests
pip install python-dotenv
```

## 🎯 Exemplo de Prompt Completo Gerado

### Para "1984" de George Orwell (Ficção Científica):

```
Professional book cover design for Amazon KDP/Kindle Direct Publishing.

BOOK DETAILS:
- Title: "1984"
- Author: George Orwell
- Genre: distopia
- Themes: vigilância, controle, totalitarismo
- Mood: sombrio, opressivo

TECHNICAL SPECIFICATIONS (KDP Standards):
- Aspect ratio: 1.6:1 (height to width) - CRITICAL for KDP
- Orientation: Portrait/vertical
- Resolution: High-quality, print-ready (300 DPI equivalent)
- Format considerations: Suitable for both ebook thumbnail and print cover
- Color space: RGB for digital, but with CMYK-safe colors

DESIGN REQUIREMENTS:

1. COMPOSITION:
   - Central focal point that captures the book's essence
   - Clear visual hierarchy with strong focal area
   - Safe margins: Keep important imagery 0.125" from edges
   - Rule of thirds composition for balanced layout
   - Leave ample space at top (for title) and bottom (for author name)

2. VISUAL STYLE:
   - Genre-appropriate imagery (distopia style)
   - Professional, publishable quality
   - Commercial book cover aesthetics
   - Evocative and thematic: vigilância, controle, totalitarismo
   - Mood: sombrio, opressivo

3. COLOR & CONTRAST:
   - High contrast for thumbnail visibility
   - Bold, eye-catching color palette
   - Colors that stand out in search results
   - Readable at small sizes (important for Amazon thumbnails)

4. IMAGE CONTENT:
   - NO text, letters, or words in the image
   - NO typography or font elements
   - Clear, recognizable imagery even at thumbnail size
   - Symbolism related to: vigilância, controle, totalitarismo
   - Professional photography/illustration quality

5. MARKETABILITY:
   - Should attract target audience for distopia
   - Competitive with bestsellers in category
   - Thumbnail-friendly (legible at 200x300 pixels)
   - Print-ready quality for paperback

6. LAYOUT ZONES:
   - Top 20%: Reserved for title placement (keep imagery subtle here)
   - Middle 60%: Main visual focus, strongest imagery
   - Bottom 20%: Reserved for author name (keep clear)

STYLE DIRECTION: sombrio, opressivo, professional, bestseller-quality, commercial, print-ready

Create a stunning, professional book cover background that will make this book
stand out on Amazon and in bookstores. The cover should be immediately
eye-catching and genre-appropriate.
```

### Resultado Esperado:
- ✅ Imagem distópica com paleta sombria (cinzas, azuis escuros, vermelhos)
- ✅ Simbolismo visual (câmeras, olho, cidade opressiva)
- ✅ Alto contraste para legibilidade
- ✅ Espaço limpo no topo e base para texto
- ✅ Impacto visual mesmo em thumbnail
- ✅ Qualidade profissional de bestseller

## 📈 Performance

### Velocidade por API

| API | Tempo médio | Qualidade | Custo estimado |
|-----|-------------|-----------|----------------|
| DALL-E 3 | 35s | ⭐⭐⭐⭐⭐ | $0.040 |
| Gemini Imagen | 25s | ⭐⭐⭐⭐⭐ | ~$0.02-0.04 |
| Grok (xAI) | 30s | ⭐⭐⭐⭐⭐ | ~$0.03-0.05 |

### Batch Processing

Para 27 livros:
- Análise: ~10 min (Ollama local)
- Geração: ~40-60 min (3 APIs x 27 livros)
- Total: ~50-70 min

## 🛠️ Troubleshooting

### "Nenhum gerador disponível"

**Problema:** Nenhuma API key configurada

**Solução:**
```bash
# Configure as 3 APIs:
set OPENAI_API_KEY=sk-...      # DALL-E 3
set GOOGLE_API_KEY=...         # Gemini
set XAI_API_KEY=...            # Grok
```

### "Ollama não disponível"

**Problema:** Ollama não está rodando

**Solução:**
```bash
# Inicie o Ollama
ollama serve

# Em outro terminal
ollama pull qwen2.5:7b
```

### "API retornou erro 401"

**Problema:** API key inválida ou expirada

**Solução:**
1. Verifique se a chave está correta
2. Verifique se tem créditos disponíveis
3. Regenere a chave se necessário

### "Timeout ao gerar imagem"

**Problema:** API demorou muito

**Solução:**
- Normal em horários de pico
- Tente novamente
- Aumente timeout no código se necessário

## 📦 Preparando para KDP/Amazon

Após gerar as capas, você precisa adicionar o texto (título e autor):

### Opção 1: Usar Canva (Recomendado)
1. Acesse [Canva.com](https://canva.com)
2. Crie design personalizado: 1600x2560px
3. Faça upload da capa gerada como fundo
4. Adicione título e nome do autor com fontes profissionais
5. Exporte em PNG de alta qualidade

### Opção 2: Usar Photoshop/GIMP
1. Abra a capa gerada
2. Adicione camada de texto
3. Título: Fonte grande, bold, no topo
4. Autor: Fonte média, na base
5. Use cores contrastantes
6. Salve em PNG ou JPEG de alta qualidade

### Opção 3: Ferramenta online KDP Cover Creator
1. Acesse [KDP Cover Creator](https://kdp.amazon.com)
2. Faça upload da imagem de fundo
3. Use as ferramentas nativas para adicionar texto
4. Preview em diferentes tamanhos
5. Download final

### Checklist KDP:
- [ ] Proporção 1.6:1 ou próxima
- [ ] Mínimo 1000px no lado curto
- [ ] Máximo 10.000px no lado longo
- [ ] Título legível em thumbnail
- [ ] Cores vibrantes
- [ ] Sem bordas brancas
- [ ] Formato: JPEG ou TIFF
- [ ] Tamanho arquivo: máx 50MB

## 💡 Dicas

### 1. Configure as 3 APIs para máxima variedade

Cada API tem seu estilo único:
- **DALL-E 3:** Mais artístico e criativo
- **Gemini:** Estilo equilibrado e profissional
- **Grok:** Estilo próprio do xAI

```bash
set OPENAI_API_KEY=sk-...
set GOOGLE_API_KEY=...
set XAI_API_KEY=...
python src\cover_generator.py --batch
```

### 2. Resultado: 3 opções para escolher

Com as 3 APIs configuradas, você terá 3 capas diferentes para cada livro e poderá escolher a melhor!

### 3. Teste com um livro primeiro

Antes do batch, teste com um livro:

```bash
python src\cover_generator.py --input "translated\Chess\Nezhmetdinov_pt.txt"
```

### 4. Monitore os logs

```bash
tail -f logs\cover_generator_*.log
```

### 5. Revise as capas

As capas geradas são sugestões. Você pode:
- Escolher a melhor entre as 2-3 geradas
- Editar no Photoshop/GIMP se necessário
- Adicionar tipografia posteriormente

## 🎉 Resultado Final

Após rodar o sistema completo, você terá:

```
translated/
├── Chess/
│   ├── Nezhmetdinov_pt.txt          # Livro traduzido
│   ├── cover_abc123_dalle_3.png     # Capa DALL-E 3
│   ├── cover_abc123_gemini_imagen.png # Capa Gemini
│   └── cover_abc123_grok_xai.png    # Capa Grok

docx/
├── Chess/
│   └── Nezhmetdinov_Final.docx      # Livro formatado

GitHub
└── Backup automático via auto-git
```

## 📞 APIs e Recursos

**OpenAI (DALL-E 3):**
- Docs: https://platform.openai.com/docs/guides/images
- Preços: https://openai.com/pricing
- API Keys: https://platform.openai.com/api-keys

**Google (Gemini Imagen):**
- Docs: https://ai.google.dev/gemini-api/docs/imagen
- API Keys: https://aistudio.google.com/app/apikey
- Preços: https://ai.google.dev/pricing

**xAI (Grok):**
- Site: https://x.ai
- Console: https://console.x.ai
- Docs: https://docs.x.ai

**Ollama (análise local):**
- Site: https://ollama.com
- Modelos: https://ollama.com/library

## ✅ Checklist

- [ ] Ollama instalado e rodando
- [ ] Modelo `qwen2.5:7b` baixado (`ollama pull qwen2.5:7b`)
- [ ] **As 3 API keys configuradas:**
  - [ ] OPENAI_API_KEY (DALL-E 3)
  - [ ] GOOGLE_API_KEY (Gemini Imagen)
  - [ ] XAI_API_KEY (Grok)
- [ ] Livros traduzidos em `translated/`
- [ ] Testou com um livro individual
- [ ] Pronto para batch com 3 capas por livro!

---

**Sistema de capas integrado ao Googolplex-Books! 🎨📚✨**

Agora seus livros terão:
1. ✅ Download automático (2 fontes)
2. ✅ Tradução para português
3. ✅ DOCX formatado profissionalmente
4. ✅ **Capas geradas por IA** 🆕
5. ✅ Backup automático no GitHub

**Pipeline completo de publicação automatizado!** 🚀

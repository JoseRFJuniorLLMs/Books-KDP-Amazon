# BooksKDP - Regras de Negócio

## ⚠️ REGRA PRINCIPAL: DOMÍNIO PÚBLICO

**ANTES DE TUDO: Verificar se o livro está em DOMÍNIO PÚBLICO**

### Verificação em 3 Pontos (via LLM)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PONTO 1: ANTES DE BAIXAR                                                   │
│  • Verifica autor + título                                                  │
│  • Autor morreu há mais de 70 anos?                                         │
│  • Obra publicada há mais de 95 anos?                                       │
│  • Se NÃO → não baixa                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PONTO 2: DEPOIS DE BAIXAR                                                  │
│  • Confirma autor no conteúdo do arquivo                                    │
│  • Verifica data de morte do autor                                          │
│  • Confirma se morreu há 70+ anos                                           │
│  • Se DÚVIDA → deleta arquivo                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PONTO 3: ANTES DE PROCESSAR                                                │
│  • Última verificação                                                       │
│  • Confirma que pode ser publicado comercialmente                           │
│  • Gera certificado de domínio público                                      │
│  • Se NÃO APROVADO → não processa                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Resumo

**1 TXT → 2 LIVROS + 2 CAPAS**

| Livro | Descrição | Arquivos |
|-------|-----------|----------|
| **A) Tradução Fiel** | Tradução + notas EXPLICATIVAS (história, filosofia) | `.docx` + `_cover.png` |
| **B) Vocabulário EN** | Tradução + 100 palavras PT→EN + notas + glossário | `_vocab.docx` + `_vocab_cover.png` |

---

## Pipeline Completo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. TXT ORIGINAL                                                            │
│     books/txt/other/{Autor}/{Livro}.txt                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. VERIFICA DOMÍNIO PÚBLICO (3 pontos)                                     │
│     • API: Gemini (conhecimento sobre autores)                              │
│     • Gera certificado: _DOMINIO_PUBLICO.json                               │
│     • Se REJEITADO → move para books/rejeitados/                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. DETECTA IDIOMA + PAÍS DO AUTOR                                          │
│     • API: Gemini                                                           │
│     • Idiomas: en, es, fr, de, it, ru, pt                                   │
│     • País: Grécia, Alemanha, França, Rússia, USA, Brasil...                │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  4. TRADUZ TÍTULO PARA PORTUGUÊS                                            │
│     • API: Google Cloud Translation                                         │
│     • "The Republic" → "A República"                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5. LIMPA OCR                                                               │
│     • Remove artefatos: □, ■, �                                             │
│     • Corrige quebras: pa-\nlavra → palavra                                 │
│     • Remove espaços/linhas extras                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  6. TRADUZ TEXTO PARA PORTUGUÊS                                             │
│     • API: Google Cloud Translation (melhor qualidade)                      │
│     • Divide em chunks de 4500 chars                                        │
│     • Idioma destino: pt-BR                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  7. CORRIGE ORTOGRAFIA E ACENTUAÇÃO                                         │
│     • API: LanguageTool (especializado em PT-BR)                            │
│     • Corrige: acentos, gramática, pontuação                                │
│     • Chunks de 15000 chars                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  8. GERA RESUMO PARA CAPAS                                                  │
│     • API: Gemini                                                           │
│     • Máximo 3 frases                                                       │
│     • Tema principal + atmosfera + elementos visuais                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                  ┌──────────────────┴──────────────────┐
                  ▼                                     ▼
╔═══════════════════════════════════╗  ╔═══════════════════════════════════════╗
║  PIPELINE A: TRADUÇÃO FIEL        ║  ║  PIPELINE B: VOCABULÁRIO EN           ║
╠═══════════════════════════════════╣  ╠═══════════════════════════════════════╣
║                                   ║  ║                                       ║
║  A1. NOTAS EXPLICATIVAS           ║  ║  B1. EXTRAI 100 PALAVRAS              ║
║      • API: Gemini                ║  ║      • Palavras mais frequentes       ║
║      • História, filosofia        ║  ║      • Dicionário PT→EN               ║
║      • Cultura, referências       ║  ║      • Exclui stopwords               ║
║      • Máximo 30 notas            ║  ║                                       ║
║                                   ║  ║                                       ║
║  A2. GERA DOCX                    ║  ║  B2. GERA DOCX                        ║
║      • Texto traduzido            ║  ║      • Palavras em NEGRITO            ║
║      • Notas de rodapé            ║  ║      • Notas (palavra = translation)  ║
║      • SEM glossário              ║  ║      • Glossário no final             ║
║      • Template preservado        ║  ║      • Template preservado            ║
║                                   ║  ║                                       ║
║  A3. GERA CAPA                    ║  ║  B3. GERA CAPA                        ║
║      • API: Gemini 2.0            ║  ║      • API: Gemini 2.0                ║
║      • Estilo: ARTISTIC           ║  ║      • Estilo: MODERN                 ║
║      • Pintura a óleo             ║  ║      • Minimalista                    ║
║      • Baseado: título + resumo   ║  ║      • Baseado: título + resumo       ║
║                                   ║  ║                                       ║
╠═══════════════════════════════════╣  ╠═══════════════════════════════════════╣
║  SAÍDA:                           ║  ║  SAÍDA:                               ║
║  {Livro} - Tradução/              ║  ║  {Livro} - Vocabulário EN/            ║
║  ├── {Livro}.docx                 ║  ║  ├── {Livro}_vocab.docx               ║
║  └── {Livro}_cover.png            ║  ║  └── {Livro}_vocab_cover.png          ║
╚═══════════════════════════════════╝  ╚═══════════════════════════════════════╝
                  │                                     │
                  └──────────────────┬──────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SAÍDA FINAL                                                                │
│                                                                             │
│  books/{País}/{Autor}/                                                      │
│  ├── _DOMINIO_PUBLICO.json                                                  │
│  ├── {Livro} - Tradução/                                                    │
│  │   ├── {Livro}.docx                                                       │
│  │   └── {Livro}_cover.png                                                  │
│  └── {Livro} - Vocabulário EN/                                              │
│      ├── {Livro}_vocab.docx                                                 │
│      └── {Livro}_vocab_cover.png                                            │
│                                                                             │
│  EXEMPLO:                                                                   │
│  books/Grécia/Aristóteles/                                                  │
│  ├── _DOMINIO_PUBLICO.json                                                  │
│  ├── A Política - Tradução/                                                 │
│  │   ├── A Política.docx                                                    │
│  │   └── A Política_cover.png                                               │
│  └── A Política - Vocabulário EN/                                           │
│      ├── A Política_vocab.docx                                              │
│      └── A Política_vocab_cover.png                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## APIs Utilizadas

| Etapa | API | Motivo |
|-------|-----|--------|
| Domínio Público | **Gemini** | Conhecimento sobre autores e datas |
| País do Autor | **Gemini** | Conhecimento geral |
| Tradução Texto | **Google Cloud Translation** | Melhor qualidade de tradução |
| Correção Ortográfica | **LanguageTool** | Especializado em PT-BR |
| Notas Explicativas | **Gemini** | Análise de contexto histórico |
| Resumo (3 frases) | **Gemini** | Síntese de conteúdo |
| Capas | **Gemini 2.0** | Geração de imagens |

---

## Regras de Ouro

1. **DOMÍNIO PÚBLICO** - verificar ANTES de processar
2. **Template é SAGRADO** - nunca deletar/modificar
3. **1 TXT = 4 arquivos** - 2 DOCX + 2 PNG
4. **Organizar por país/autor** - `books/{País}/{Autor}/`
5. **Título em português** - sempre traduzir
6. **Livro A**: tradução fiel + notas EXPLICATIVAS
7. **Livro B**: 100 palavras EN + notas VOCABULÁRIO + glossário
8. **2 capas** - artistic (A) e modern (B)
9. **DOCX > 100KB** - nunca gerar arquivo vazio
10. **UTF-8** - português tem acentos

---

## Comando

```bash
python -m src.pipeline.smart_processor \
    --input books/txt/other \
    --output books \
    --words 100 \
    --limit 10
```

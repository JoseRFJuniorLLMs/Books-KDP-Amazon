# FAZ.PY - Processador de Livros para KDP

## Go vs Python - Por que Python?

### O Gargalo NÃO é o Python

```
┌─────────────────────────────────────────────────────────────────┐
│ TEMPO DE PROCESSAMENTO DE UM LIVRO (estimativa)                 │
├─────────────────────────────────────────────────────────────────┤
│ Inferência do LLM (Ollama/API)     █████████████████████  95%   │
│ Manipulação DOCX (python-docx)     █                       3%   │
│ I/O (leitura/escrita arquivos)     ░                       1%   │
│ Processamento Python (lógica)      ░                       1%   │
└─────────────────────────────────────────────────────────────────┘
```

**O tempo é dominado pela IA (95%+), não pelo código.**

### Por que NÃO usar Go para DOCX?

| Aspecto | Python (python-docx) | Go (unioffice) |
|---------|---------------------|----------------|
| Maturidade | ★★★★★ (10+ anos) | ★★☆☆☆ (limitado) |
| Notas de rodapé | ✅ Suportado | ❌ Não suportado |
| Estilos complexos | ✅ Completo | ⚠️ Parcial |
| Cabeçalhos/rodapés | ✅ Completo | ⚠️ Básico |
| Documentação | ✅ Excelente | ⚠️ Escassa |
| Licença | MIT (gratuito) | **Pago para comercial** |
| Comunidade | Enorme | Pequena |

### Quando Go SERIA melhor?

1. **Servidor de API de alta concorrência** - milhares de requests/segundo
2. **CLI distribuído** - binário único sem dependências
3. **Processamento de texto puro** - sem DOCX

### Conclusão

Para **geração de DOCX com formatação rica**, Python é a escolha correta:
- Bibliotecas maduras e completas
- O gargalo é a IA, não o Python
- Menos código, menos bugs, mais rápido de desenvolver

---

## Instalação Rápida

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar modelo local (baixa Qwen2.5)
python setup_modelo.py

# 3. Executar
python faz.py --input livro.txt
```

## Modelos Recomendados

| Modelo | VRAM | Qualidade PT-BR | Comando |
|--------|------|-----------------|---------|
| **qwen2.5:7b** | 6GB | ★★★★★ | `ollama pull qwen2.5:7b` |
| qwen2.5:14b | 10GB | ★★★★★+ | `ollama pull qwen2.5:14b` |
| llama3.1:8b | 8GB | ★★★★☆ | `ollama pull llama3.1:8b` |

## Sobre o Sabiá-2

⚠️ **O Sabiá-2 NÃO está disponível para download local.**

É acessível apenas via API paga da Maritaca AI: https://www.maritaca.ai/

O **Qwen2.5** é a melhor alternativa gratuita para português.

## Uso

```bash
# Processar um arquivo
python faz.py --input txt/Autor/livro.txt --output docx/livro_final.docx

# Processar todos os livros (batch)
python faz.py

# Usar modelo diferente
python faz.py --model qwen2.5:14b

# Usar API externa
python faz.py --backend gemini
```

## Melhorias Implementadas

1. ✅ **Modelos locais** - Ollama (Qwen2.5, Llama3.1, etc.)
2. ✅ **Notas de rodapé reais** - Numeração automática [1], [2], etc.
3. ✅ **Numeração de páginas** - Campo PAGE no rodapé
4. ✅ **Cabeçalhos/rodapés preservados** - Herda do template
5. ✅ **Cache SQLite** - Evita reprocessar chunks idênticos
6. ✅ **Processamento paralelo** - Múltiplos chunks simultâneos
7. ✅ **Contagem de tokens precisa** - tiktoken
8. ✅ **Configuração flexível** - Tudo via .env
9. ✅ **Logging completo** - Arquivo + console
10. ✅ **Retry inteligente** - Backoff exponencial com jitter

## Estrutura de Arquivos

```
BooksKDP/
├── modelo/
│   ├── faz.py              # Script principal (melhorado)
│   ├── setup_modelo.py     # Instalação do ambiente
│   ├── requirements.txt    # Dependências Python
│   ├── .env.exemplo        # Configuração exemplo
│   └── cache.db            # Cache SQLite (gerado)
├── txt/                    # Textos de entrada
│   └── Autor/
│       └── livro.txt
├── docx/                   # Documentos gerados
│   └── Autor/
│       └── livro_Final.docx
├── Estrutura.docx          # Template DOCX
└── .env                    # Sua configuração
```

 RELATÓRIO DO PROJETO BooksKDP
                                                                                                                      
  1. ESTRUTURA DO PROJETO

  D:\Books\BooksKDP\
  ├── main.py                    (apenas template PyCharm - não usado)
  ├── .venv/                     (ambiente virtual Python)
  └── modelo/
      ├── data/
      │   └── books.db           (base de dados principal)
      ├── cache.db               (cache de traduções)
      ├── database.py            (gerenciador de banco de dados)
      ├── hunter.py              (caçador de livros v1)
      ├── hunter_v2.py           (caçador de livros v2)
      ├── tradutor.py            (sistema de tradução)
      ├── correcaoKDP.py         (correção + formatação - usa Gemini)
      ├── faz.py                 (processador otimizado - usa Ollama)
      ├── setup_modelo.py        (configuração do ambiente)
      └── baixar_sabia.py        (download modelo Sabiá-7B)

  ---
  2. SCRIPTS E SUAS FUNÇÕES
  Script: database.py
  Função Principal: Gerencia banco SQLite. Importa catálogo do Project Gutenberg (CSV), cria tabelas (authors, books, 
    subjects, book_subjects), permite buscas de livros/autores em domínio público
  ────────────────────────────────────────
  Script: hunter.py
  Função Principal: Caça livros v1 - Lista interna de 100+ autores clássicos (russos, franceses, ingleses, alemães,   
    etc.). Busca em Archive.org, Gutenberg, Standard Ebooks. Baixa EPUBs/PDFs para pasta CALIBRE
  ────────────────────────────────────────
  Script: hunter_v2.py
  Função Principal: Caça livros v2 - Usa catálogo REAL do Gutenberg (89k+ livros). Mais robusto, com APIs Gutendex e  
    Open Library. Baixa por autor ou top autores
  ────────────────────────────────────────
  Script: tradutor.py
  Função Principal: Extrai texto de PDF/EPUB/HTML/TXT/DOCX, detecta idioma, traduz para PT-BR usando Ollama (Qwen2.5),

    corrige texto e gera DOCX formatado
  ────────────────────────────────────────
  Script: correcaoKDP.py
  Função Principal: Processador completo usando Google Gemini. Corrige OCR, identifica notas de rodapé, gera DOCX     
    formatado. Suporta múltiplos autores/livros. Envia e-mail de notificação
  ────────────────────────────────────────
  Script: faz.py
  Função Principal: Versão otimizada do processador. Suporta Ollama, Gemini e OpenAI. Processamento paralelo
  (asyncio),
     cache SQLite, notas de rodapé reais, numeração de páginas
  ────────────────────────────────────────
  Script: setup_modelo.py
  Função Principal: Instala dependências Python, configura Ollama, baixa modelos (Qwen2.5:7b recomendado), testa      
    conexão
  ────────────────────────────────────────
  Script: baixar_sabia.py
  Função Principal: Baixa modelo Sabiá-7B (brasileiro) do HuggingFace, cria Modelfile e importa no Ollama
  ---
  3. ESTATÍSTICAS DA BASE DE DADOS

  Base Principal (books.db)
  ┌───────────────────┬────────────┐
  │      Métrica      │ Quantidade │
  ├───────────────────┼────────────┤
  │ Total de Livros   │ 76.342     │
  ├───────────────────┼────────────┤
  │ Total de Autores  │ 37.028     │
  ├───────────────────┼────────────┤
  │ Livros Baixados   │ 0          │
  ├───────────────────┼────────────┤
  │ Total de Assuntos │ 41.525     │
  ├───────────────────┼────────────┤
  │ Idiomas Distintos │ 118        │
  └───────────────────┴────────────┘
  Distribuição por Idioma (Top 10)
  ┌────────────────┬────────┐
  │     Idioma     │ Livros │
  ├────────────────┼────────┤
  │ Inglês (en)    │ 60.376 │
  ├────────────────┼────────┤
  │ Francês (fr)   │ 4.028  │
  ├────────────────┼────────┤
  │ Finlandês (fi) │ 3.509  │
  ├────────────────┼────────┤
  │ Alemão (de)    │ 2.338  │
  ├────────────────┼────────┤
  │ Italiano (it)  │ 1.084  │
  ├────────────────┼────────┤
  │ Holandês (nl)  │ 1.078  │
  ├────────────────┼────────┤
  │ Espanhol (es)  │ 869    │
  ├────────────────┼────────┤
  │ Húngaro (hu)   │ 648    │
  ├────────────────┼────────┤
  │ Português (pt) │ 643    │
  ├────────────────┼────────┤
  │ Chinês (zh)    │ 435    │
  └────────────────┴────────┘
  Cache (cache.db)
  ┌──────────────┬───────────┐
  │    Tabela    │ Registros │
  ├──────────────┼───────────┤
  │ translations │ 0 (vazio) │
  └──────────────┴───────────┘
  ---
  4. FLUXO DE TRABALHO

  1. Importar Catálogo: python database.py --import
  2. Caçar Livros: python hunter_v2.py --russians ou --top 50
  3. Traduzir/Corrigir: python tradutor.py ou python faz.py
  4. Saída: DOCXs formatados prontos para KDP

  ---
  5. MODELOS DE IA SUPORTADOS
  ┌─────────┬────────────────────┬──────┐
  │ Backend │ Modelo Recomendado │ VRAM │
  ├─────────┼────────────────────┼──────┤
  │ Ollama  │ qwen2.5:7b         │ 6GB  │
  ├─────────┼────────────────────┼──────┤
  │ Gemini  │ gemini-1.5-pro     │ API  │
  ├─────────┼────────────────────┼──────┤
  │ OpenAI  │ gpt-4o-mini        │ API  │
  └─────────┴────────────────────┴──────┘

✻ Crunched for 1m 51s

❯ 1 organiza o porjeto 2 - correcaoKDP.py quero uma versao melhorada disso que use modelos locais. 3 quero algo         para ver a base de dados, e que seja atualizado ela quando um livro for feiot, tipo um campo chamado processado    
  , quero uma api ou um html que mostre a base de dados                                                               
                                                                                                                      
● Vou planejar e implementar essas melhorias. Primeiro, deixa eu entender melhor a estrutura atual.                       
● Bash(dir /s /b "D:\Books\BooksKDP" 2>nul | findstr /v ".venv" | findstr /v "__pycache__" | head -50)
  ⎿  dir: cannot access '/s': No such file or directory                                                                    dir: cannot access '/b': No such file or directory
     dir: cannot access '2': No such file or directory                                                                     … +2 lines (ctrl+o to expand)
                                                                                                                      ● Bash(powershell -Command "Get-ChildItem -Path 'D:\Books\BooksKDP' -Recurse -Name | Where-Object { $_ -notlike             '.venv*' -and $_ -notlike '*__pycache__*' } | Select-Ob…)
  ⎿  Running in the background (↓ to manage)                                                                          
                                                                                                                      
● Stop Task(Stop task: b4877b0)                                              
  ⎿  Task b4877b0 (local_bash) stopped                                                                                
✔ Task #1 created: Reorganizar estrutura do projeto BooksKDP
✔ Task #2 created: Criar versão melhorada do correcaoKDP com modelos locais                                           
✔ Task #3 created: Adicionar campo 'processado' na base de dados
✔ Task #4 created: Criar API/Dashboard para visualizar base de dados                                                  
✔ Task #1 updated: status → in progress                                                                               
                                                                                                                      
● Vou começar reorganizando o projeto e criando os novos arquivos.                                                                                                                      
● Bash(cd "D:\Books\BooksKDP" && mkdir -p src config templates static logs data 2>/dev/null || (mkdir src 2>nul &           mkdir config 2>nul & mkdir templates 2>nul & mkdir st…)
  ⎿  (No content)                                                                                                     
                                                                                                                      
● Write(BooksKDP\config\settings.py)                                                                                    ⎿  Wrote 1 lines to BooksKDP\config\settings.py                                                                     
     # -*- coding: utf-8 -*-                                                                                               """                                               
     SETTINGS.PY - Configurações Centralizadas do BooksKDP                                                            
     ======================================================
     Todas as configurações do projeto em um só lugar.                                                                     """
                                                                                                                           import os
     from pathlib import Path                                                                                         
     from dotenv import load_dotenv

✻ Reorganizando estrutura do projeto… (Esc to interrupt · ctrl+t to hide tasks · 3m 18s · ↓ 2.8k tokens)
  ⎿  ◼ #1 Reorganizar estrutura do projeto BooksKDP
     ◻ #2 Criar versão melhorada do correcaoKDP com modelos locais
     ◻ #3 Adicionar campo 'processado' na base de dados
     ◻ #4 Criar API/Dashboard para visualizar base de dados

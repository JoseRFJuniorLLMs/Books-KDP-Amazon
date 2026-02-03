  Para usar, ative o venv primeiro:

  # Ativar o ambiente virtual
  .venv\Scripts\Activate

  # Iniciar o Dashboard (API)
  python run_api.py

  # Ou processar livros
  python run_processor.py --input arquivo.txt --author "Nome"
  # Processar UM livro
  python run_processor.py --input txt/Autor/livro.txt --author "Dostoiévski"

  # Processar TODOS os livros em txt/
 

  # Usar modelo específico
  python run_processor.py --input livro.txt --model qwen2.5:14b

  # Usar Gemini em vez de Ollama
  python run_processor.py --input livro.txt --backend gemini

    # Ver progresso
  type logs\calibre_batch_*.log | tail -50

  # Ver DOCXs gerados
  dir docx\ /s /b | find /c ".docx"

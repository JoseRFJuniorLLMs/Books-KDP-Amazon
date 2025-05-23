# Books-KDP-Amazon
# Formatação de Livro com OpenAI e Python

Este projeto utiliza a API da OpenAI e a biblioteca Python `python-docx` para transformar um texto bruto em um livro formatado, pronto para publicação. O processo inclui correção gramatical, formatação de capítulos, parágrafos justificados e geração de um arquivo `.docx` com estrutura adequada.

## Como Funciona

1. **Entrada de Dados**: O texto bruto de um livro é fornecido em um arquivo `.txt`.
2. **Correção e Formatação**: Através da API OpenAI, o texto é corrigido e formatado de acordo com as regras estabelecidas.
3. **Template de Documento**: O projeto utiliza um template `.docx` para estruturar o livro com cabeçalhos, quebras de página e formatação de parágrafos.
4. **Geração do Documento Final**: O texto formatado é inserido no template e salvo como um novo arquivo `.docx`.

## Requisitos

Antes de executar o projeto, instale as dependências necessárias com o comando:

```bash
pip install openai python-docx python-dotenv
```

Além disso, crie um arquivo `.env` na raiz do projeto e adicione sua chave da API do OpenAI:

```env
OPENAI_API_KEY=your_api_key_here
```

## Estrutura do Projeto

- **`rascunho.txt`**: Arquivo contendo o texto bruto a ser formatado.
- **`Estrutura.docx`**: Template do livro (formato `.docx`) que será utilizado para estruturar o arquivo final.
- **`Livro_Final_Formatado.docx`**: O arquivo gerado com o texto formatado e estruturado.

## Como Usar

1. Coloque o seu texto bruto no arquivo `rascunho.txt`.
2. Coloque o template de formatação `Estrutura.docx` no diretório do projeto.
3. Execute o script `formatar_livro.py` (ou o nome que você der ao arquivo que contém o código).

O script irá:
- Ler o texto bruto do arquivo `rascunho.txt`.
- Enviar o texto para a API da OpenAI, que realizará a formatação e correção.
- Aplicar a formatação no template `.docx`.
- Gerar o arquivo final `Livro_Final_Formatado.docx`.

## Exemplo de Execução

```bash
python formatar_livro.py
```

Ao final, o livro formatado será gerado no arquivo `Livro_Final_Formatado.docx`.

## Licença

Este projeto está licenciado sob a Licença MIT – veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## Contribuições

Contribuições são bem-vindas! Se você tem sugestões ou melhorias, abra um pull request ou abra uma issue no GitHub.

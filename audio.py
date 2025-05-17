import os
import json
import openai
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da chave API
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise Exception("A chave API não foi encontrada nas variáveis de ambiente.")

openai.api_key = api_key

PROGRESSO_FILE = "progressohipnose.json"

def carregar_progresso():
    if os.path.exists(PROGRESSO_FILE):
        with open(PROGRESSO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def salvar_progresso(pasta_livro, nome_livro, parte): # pasta_livro aqui é o diretório do arquivo
    progresso = carregar_progresso()
    progresso[nome_livro] = parte
    with open(PROGRESSO_FILE, 'w', encoding='utf-8') as f:
        json.dump(progresso, f)

def texto_para_audio(texto, nome_arquivo):
    print(f"Iniciando conversão de texto para áudio: {nome_arquivo}")
    try:
        # Utilizando o novo modelo `gpt-4o-audio-preview` e a voz Juniper
        # Nota: O endpoint correto para a API de áudio é openai.audio.speech.create
        # E o modelo pode ser "tts-1" ou "tts-1-hd". "gpt-4o-audio-preview" não é um modelo de TTS.
        # Vou corrigir para um modelo TTS válido e o endpoint correto.
        response = openai.audio.speech.create( # CORREÇÃO AQUI
            model="tts-1",  # ou "tts-1-hd" para maior qualidade
            input=texto,    # CORREÇÃO AQUI (parâmetro é 'input')
            voice="coral", # Voz Juniper (verifique se "juniper" é uma opção válida ou use uma das padrão como "alloy", "echo", "fable", "onyx", "nova", "shimmer")
            response_format="mp3"
        )

        # Salvar o arquivo de áudio diretamente do stream da resposta
        # A API v1 retorna um objeto de resposta que pode ser streamado para um arquivo
        print(f"Áudio sendo gerado...")
        response.stream_to_file(nome_arquivo) # CORREÇÃO AQUI
        print(f"Áudio salvo em: {nome_arquivo}")

        # Verificar se o arquivo foi criado
        if os.path.exists(nome_arquivo):
            print(f"Arquivo {nome_arquivo} criado com sucesso.")
            print(f"Tamanho do arquivo: {os.path.getsize(nome_arquivo)} bytes")
        else:
            print(f"Erro: Arquivo {nome_arquivo} não foi criado.")
            return f"Erro: Arquivo {nome_arquivo} não foi criado após a API." # Adicionado retorno de erro

    except Exception as e:
        print(f"Ocorreu um erro ao converter texto para áudio: {e}")
        # Tentar extrair mais detalhes do erro se for um erro da API OpenAI
        if hasattr(e, 'response') and e.response:
            try:
                error_details = e.response.json()
                print(f"Detalhes do erro da API: {error_details}")
                return f"Erro API: {error_details.get('error', {}).get('message', str(e))}"
            except: # Em caso de falha ao decodificar o JSON do erro
                pass
        return f"Erro: {str(e)}"

def ler_arquivo(caminho_arquivo):
    print(f"Lendo arquivo: {caminho_arquivo}")
    if not os.path.exists(caminho_arquivo): # Adicionada verificação se o arquivo existe
        print(f"Erro: O arquivo {caminho_arquivo} não foi encontrado.")
        return None
    with open(caminho_arquivo, 'r', encoding='utf-8') as f:
        conteudo = f.read()
    print(f"Tamanho do conteúdo lido: {len(conteudo)} caracteres")
    return conteudo

def processar_arquivo(caminho_arquivo, forçar_reprocessamento=False):
    print(f"Processando arquivo: {caminho_arquivo}")
    nome_arquivo_base = os.path.basename(caminho_arquivo)
    nome_livro = os.path.splitext(nome_arquivo_base)[0] # nome_livro será "stf"

    conteudo = ler_arquivo(caminho_arquivo)
    if conteudo is None: # Se ler_arquivo retornou None (arquivo não encontrado)
        return # Interrompe o processamento deste arquivo

    # Dividir o texto em partes respeitando o limite máximo
    TAMANHO_MAXIMO = 4000 # Limite da API da OpenAI para TTS é geralmente 4096 caracteres
    partes = [conteudo[i:i + TAMANHO_MAXIMO] for i in range(0, len(conteudo), TAMANHO_MAXIMO)]
    print(f"Número de partes a serem processadas: {len(partes)}")

    # Carregar progresso
    progresso = carregar_progresso()
    parte_iniciada = progresso.get(nome_livro, 0) # Usa nome_livro (sem extensão) como chave
    print(f"Retomando processamento a partir da parte: {parte_iniciada}")

    # Obter o diretório do arquivo de entrada para salvar os áudios lá
    diretorio_arquivo = os.path.dirname(caminho_arquivo)
    if not diretorio_arquivo: # Se o arquivo estiver no mesmo diretório do script, dirname retorna ''
        diretorio_arquivo = "." # Usar o diretório atual

    # Gerar áudio para cada parte
    for index in range(len(partes)):
        # Se for forçar reprocessamento ou se a parte ainda não foi processada
        if forçar_reprocessamento or index >= parte_iniciada:
            parte_texto = partes[index]
            # Nome do arquivo de áudio será <nome_do_livro>_parte_<numero>.mp3
            nome_arquivo_audio = f"{nome_livro}_parte_{index + 1}.mp3"
            caminho_audio = os.path.join(diretorio_arquivo, nome_arquivo_audio)

            print(f"Processando parte {index + 1} com {len(parte_texto)} caracteres.")
            erro = texto_para_audio(parte_texto, caminho_audio)
            if erro:  # Se houver erro, interrompa o processamento
                print(f"Erro encontrado ao processar a parte {index + 1}: {erro}")
                # Não salvar progresso se houve erro para tentar novamente depois
                break

            # Salvar progresso após processar cada parte com sucesso
            salvar_progresso(diretorio_arquivo, nome_livro, index + 1)
        else:
            print(f"Parte {index + 1} já processada. Pulando...")

# Esta função não será mais usada diretamente no __main__ se você quer processar um único arquivo
# def processar_pasta_livros(pasta_livro, forçar_reprocessamento=False):
# print(f"Processando pasta: {pasta_livro}")
# for arquivo in os.listdir(pasta_livro):
# if arquivo.endswith(".txt"):
# caminho_arquivo = os.path.join(pasta_livro, arquivo)
# processar_arquivo(caminho_arquivo, forçar_reprocessamento)

if __name__ == "__main__":
    # Defina o caminho para o seu arquivo específico
    caminho_do_arquivo_txt = "stf.txt"  # <--- COLOQUE O NOME DO SEU ARQUIVO AQUI

    # Verifique se o arquivo existe antes de tentar processá-lo
    if not os.path.exists(caminho_do_arquivo_txt):
        print(f"ERRO: O arquivo de texto '{caminho_do_arquivo_txt}' não foi encontrado.")
        print("Certifique-se de que o arquivo está no mesmo diretório do script ou forneça o caminho completo.")
    else:
        forçar_reprocessamento = True  # Defina como True se quiser forçar a reexecução de todas as partes
        print(f"Iniciando processamento do arquivo: {caminho_do_arquivo_txt}")
        processar_arquivo(caminho_do_arquivo_txt, forçar_reprocessamento)
        print("Processamento concluído.")
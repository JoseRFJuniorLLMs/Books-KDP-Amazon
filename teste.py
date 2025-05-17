from google.cloud import texttospeech
import traceback

print("Tentando inicializar o cliente Google Cloud TTS...")
try:
    client = texttospeech.TextToSpeechClient()
    print("Cliente TTS inicializado com sucesso.")

    synthesis_input = texttospeech.SynthesisInput(text="Olá, Junior. Isto é um teste do Google Cloud TTS.")
    print("Input de síntese criado.")

    voice = texttospeech.VoiceSelectionParams(
        language_code="pt-BR",
        name="pt-BR-Wavenet-A" # Você pode tentar outras vozes como "pt-BR-Standard-A"
    )
    print(f"Parâmetros de voz definidos para: {voice.name}")

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    print("Configuração de áudio definida.")

    print("Enviando requisição de síntese de fala...")
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    print("Resposta recebida.")

    with open("test_output.mp3", "wb") as out:
        out.write(response.audio_content)
        print("Arquivo de áudio 'test_output.mp3' salvo com sucesso no diretório atual.")
    print("Teste concluído com sucesso!")

except Exception as e:
    print(f"---------------------------------------------------------")
    print(f"Ocorreu um erro no teste do Google Cloud TTS: {e}")
    print(f"---------------------------------------------------------")
    traceback.print_exc()
    print(f"---------------------------------------------------------")
    print("Verifique os passos de troubleshooting:")
    print("1. API Cloud Text-to-Speech está habilitada no Console do GCP?")
    print("2. Faturamento está habilitado para o projeto?")
    print("3. Autenticação está configurada corretamente (ADC ou GOOGLE_APPLICATION_CREDENTIALS)?")
    print("4. A conta/serviço tem as permissões IAM necessárias (ex: 'Usuário da API Cloud Text-to-Speech')?")
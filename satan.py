# -*- coding: utf-8 -*-
# Nome do Arquivo: satan.py
# Data da versão: 2025-04-26 - OpenAI TTS + PT-BR + Google Calendar Read

import os
import os.path
import subprocess
import sys
import tempfile
from dotenv import load_dotenv
import datetime # Para lidar com datas da agenda

# --- Imports do LangChain ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import BaseTool
from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate

# --- Imports para Reconhecimento de Voz ---
import speech_recognition as sr

# --- Imports para Síntese de Voz (OpenAI TTS) ---
from openai import OpenAI
import playsound

# --- Imports para Autenticação e APIs Google ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build # Para construir o service client
from googleapiclient.errors import HttpError # Para tratar erros da API Google

# === CARREGA VARIÁVEIS DE AMBIENTE ===
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") # Para o LLM Gemini
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # Para o TTS OpenAI
# Não precisamos mais da variável GOOGLE_APPLICATION_CREDENTIALS aqui, pois usaremos OAuth 2.0 com credentials.json

# === CONFIGURAÇÕES ===
# LLM
MODEL_NAME = "gemini-1.5-pro"
TEMPERATURE = 0.3
# OpenAI TTS
TTS_MODEL_OPENAI = "tts-1"
TTS_VOICE_OPENAI = "nova"
# Google OAuth & APIs
CREDENTIALS_FILENAME = 'credentials.json' # Arquivo baixado do Google Cloud Console (OAuth Desktop Client ID)
TOKEN_FILENAME = 'token.json' # Arquivo para armazenar tokens do usuário após autorização
# --- !!! DEFINA OS ESCOPOS NECESSÁRIOS E AUTORIZADOS AQUI !!! ---
# Começando apenas com leitura da agenda. Adicione outros se configurou e precisa.
SCOPES = ['https://www.googleapis.com/auth/calendar.events.readonly']
# Exemplo com mais escopos (SE VOCÊ OS AUTORIZOU NA TELA DE CONSENTIMENTO):
# SCOPES = [
#     'https://www.googleapis.com/auth/calendar.events.readonly',
#     'https://www.googleapis.com/auth/gmail.readonly',
#     'https://www.googleapis.com/auth/drive.metadata.readonly'
# ]
# ------------------------------------------------------------------

# --- Configuração do LLM LangChain ---
# (Código inalterado)
if not GOOGLE_API_KEY: sys.exit("Erro Crítico: Variável GOOGLE_API_KEY não definida.")
try:
    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=GOOGLE_API_KEY, temperature=TEMPERATURE, convert_system_message_to_human=True)
    print(f"LLM LangChain ({MODEL_NAME}) inicializado.")
except Exception as e: sys.exit(f"Erro crítico ao inicializar o LLM LangChain: {e}")

# --- Inicialização do Cliente OpenAI (para TTS) ---
# (Código inalterado)
openai_tts_ready = False
openai_client = None
try:
    if not OPENAI_API_KEY: raise EnvironmentError("Variável OPENAI_API_KEY não definida.")
    openai_client = OpenAI()
    print("Cliente OpenAI (para TTS) inicializado.")
    openai_tts_ready = True
except EnvironmentError as e_env: print(f"Erro Crítico TTS OpenAI: {e_env}")
except Exception as e: print(f"Erro crítico ao inicializar cliente OpenAI: {e}")
if not openai_tts_ready: print("AVISO: OpenAI TTS não funcionará.")


# --- Função para Autenticação Google OAuth 2.0 ---
def get_google_credentials():
    """Obtém ou atualiza credenciais OAuth 2.0 do usuário."""
    creds = None
    if os.path.exists(TOKEN_FILENAME):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILENAME, SCOPES)
            # print(f"Credenciais carregadas de '{TOKEN_FILENAME}'.") # Debug
        except Exception as e:
            print(f"Erro ao carregar '{TOKEN_FILENAME}': {e}. Tentando re-autorizar.")
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Credenciais Google expiradas, atualizando...")
                creds.refresh(Request())
                print("Credenciais Google atualizadas.")
                # Salva as credenciais atualizadas
                with open(TOKEN_FILENAME, 'w') as token_file:
                    token_file.write(creds.to_json())
                print(f"Credenciais atualizadas salvas em '{TOKEN_FILENAME}'.")
            except Exception as e:
                print(f"Erro ao atualizar credenciais Google: {e}")
                print("Será necessário re-autorizar.")
                # Tenta apagar token inválido para forçar fluxo
                if os.path.exists(TOKEN_FILENAME): os.remove(TOKEN_FILENAME)
                creds = None
        else:
            if not os.path.exists(CREDENTIALS_FILENAME):
                print(f"Erro Crítico OAuth: Arquivo '{CREDENTIALS_FILENAME}' não encontrado.")
                print("Faça o download do JSON do OAuth Client ID (Desktop App) e renomeie.")
                return None
            try:
                print(f"Arquivo '{TOKEN_FILENAME}' não encontrado ou inválido. Iniciando fluxo de autorização...")
                print("Uma janela do navegador será aberta para você autorizar o acesso.")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILENAME, SCOPES)
                creds = flow.run_local_server(port=0) # Abre navegador
                print("Autorização do Google concedida!")
                with open(TOKEN_FILENAME, 'w') as token_file:
                    token_file.write(creds.to_json())
                print(f"Credenciais salvas em '{TOKEN_FILENAME}'.")
            except Exception as e:
                 print(f"Erro crítico durante o fluxo de autorização Google: {e}")
                 return None
    return creds

# --- Executa Autenticação Google OAuth na Inicialização ---
print("\n--- Verificando Credenciais Google OAuth 2.0 ---")
google_creds = get_google_credentials()
google_auth_ready = bool(google_creds) # Flag para saber se a autenticação funcionou
if not google_auth_ready:
    print("ERRO CRÍTICO: Falha ao obter credenciais do Google OAuth.")
    print("O acesso a Agenda/Gmail/Drive não funcionará.")
    # sys.exit(1) # Pode descomentar para parar se for essencial
else:
     print("Credenciais Google OAuth verificadas/obtidas com sucesso.")
print("-" * 50)


# --- Definição das Ferramentas Customizadas ---

# Ferramenta 1: Executar Comandos Windows (Inalterada)
class WindowsCommandExecutorTool(BaseTool):
    name: str = "windows_command_executor"
    description: str = ( /* ... descrição completa ... */ ) # Cole a descrição correta
    def _run(self, command_string: str) -> str:
        # ... (código _run inalterado) ...
        print(f"\n LCHAIN TOOL: Recebido para execução: C:\\> {command_string}")
        if not isinstance(command_string, str) or not command_string.strip(): return "Erro: Input inválido."
        forbidden_commands = ["format", "shutdown"]
        command_start = ""
        if command_string:
            command_parts = command_string.strip().split()
            if command_parts: command_start = command_parts[0].lower()
        if command_start in forbidden_commands: return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro: Comando '{command_start}' bloqueado."
        try:
            result = subprocess.run(command_string, shell=True, capture_output=True, text=True, check=False, encoding='cp850', errors='ignore')
            output = f"Return Code: {result.returncode}\nSTDOUT:\n{result.stdout.strip() or '(None)'}\nSTDERR:\n{result.stderr.strip() or '(None)'}"
            print(f" LCHAIN TOOL: Execução concluída. Código: {result.returncode}")
            if result.returncode != 0: print(f" LCHAIN TOOL: STDERR: {result.stderr.strip() or '(None)'}")
            return output
        except FileNotFoundError: return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro: Comando '{command_start}' não encontrado."
        except Exception as e: return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro Inesperado: {e}"

# Ferramenta 2: Listar Eventos Google Calendar (NOVA)
class ListCalendarEventsTool(BaseTool):
    """Ferramenta para listar eventos de hoje do Google Calendar."""
    name: str = "google_calendar_list_today_events"
    description: str = (
        "Use esta ferramenta para obter uma lista dos eventos do Google Calendar do usuário para o dia de HOJE. "
        "A entrada para esta ferramenta geralmente não é necessária ou pode ser algo como 'hoje' ou 'eventos de hoje'. "
        "Retorna uma string listando os eventos de hoje (horário e título) ou uma mensagem indicando que não há eventos."
    )

    def _run(self, query: str = "hoje") -> str: # Query pode ser ignorado por enquanto
        """Lista os próximos 10 eventos de hoje do calendário principal."""
        print(f"\n LCHAIN TOOL: Executando {self.name}...")
        creds = get_google_credentials() # Pega as credenciais OAuth
        if not creds:
            return "Erro: Falha ao obter credenciais Google OAuth. Não é possível acessar a agenda."

        try:
            service = build('calendar', 'v3', credentials=creds)

            # Pega data/hora atual em UTC para consistência com a API
            now = datetime.datetime.utcnow()
            timeMin = now.isoformat() + 'Z' # 'Z' indica UTC
            # Calcula fim do dia (aproximado, sem lidar com timezone local complexo por agora)
            # Pega o início do dia UTC e adiciona 1 dia
            start_of_day = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc)
            end_of_day = start_of_day + datetime.timedelta(days=1)
            timeMax = end_of_day.isoformat()

            print(f"   (Buscando eventos entre {timeMin} e {timeMax})") # Debug

            events_result = service.events().list(
                calendarId='primary', # Calendário principal do usuário
                timeMin=timeMin,
                timeMax=timeMax,
                maxResults=15, # Busca um pouco mais para garantir os de hoje
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])

            if not events:
                print("   (Nenhum evento encontrado para hoje.)")
                return "Nenhum evento encontrado na sua agenda para hoje."

            output_lines = ["Eventos de hoje na sua agenda:"]
            event_count = 0
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                # Formata a hora (precisa tratar data/hora e só data)
                try:
                    # Tenta converter para objeto datetime e formatar hora local (simplificado)
                    dt_obj = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                    # Formatação básica HH:MM (pode precisar de ajuste de fuso horário para precisão)
                    # Para simplificar, vamos mostrar UTC ou data
                    if 'T' in start: # É datetime
                        hour_minute = dt_obj.strftime('%H:%M')
                    else: # É só data (evento dia inteiro)
                         hour_minute = "Dia Inteiro"

                except ValueError:
                     hour_minute = start # Se formato for inesperado, mostra string original

                summary = event.get('summary', '(Sem Título)')
                output_lines.append(f"- {hour_minute}: {summary}")
                event_count += 1

            print(f"   ({event_count} eventos formatados.)")
            return "\n".join(output_lines)

        except HttpError as error:
            error_msg = f"Erro ao acessar Google Calendar API: {error}"
            print(f" LCHAIN TOOL: {error_msg}")
            # Verifica se o erro é falta de escopo
            if error.resp.status == 403:
                 return f"Erro: Permissão negada para acessar a agenda. Verifique os escopos autorizados. Detalhe: {error}"
            return error_msg
        except Exception as e:
            error_msg = f"Erro inesperado ao buscar eventos da agenda: {e}"
            print(f" LCHAIN TOOL: {error_msg}")
            return error_msg

# --- Fim das Ferramentas ---


# --- Inicialização das Ferramentas para o Agente ---
# AGORA INCLUI A NOVA FERRAMENTA DE AGENDA!
tools = [
    WindowsCommandExecutorTool(),
    ListCalendarEventsTool()
]

# --- Configuração do Agente (ReAct com Prompt Customizado PT-BR) ---
# (A lógica de customização do prompt permanece a mesma)
try:
    react_prompt_original = hub.pull("hwchase17/react")
    parts = react_prompt_original.template.split("Begin!")
    if len(parts) == 2:
        template_customizado = parts[0].strip() + \
            "\n\nIMPORTANT FINAL INSTRUCTION: Your final answer (Final Answer:) MUST always be in Brazilian Portuguese (Português do Brasil)." + \
            "\n\nBegin!" + parts[1]
    else:
        template_customizado = react_prompt_original.template + \
            "\n\nIMPORTANT FINAL INSTRUCTION: Your final answer (Final Answer:) MUST always be in Brazilian Portuguese (Português do Brasil)."

    react_prompt_ptbr = PromptTemplate.from_template(template_customizado)
    react_prompt_ptbr.input_variables = react_prompt_original.input_variables

    print("--- Prompt Customizado (Verifique Instrução PT-BR e Ferramentas) ---")
    # Imprime trecho para confirmação
    # (código de impressão do prompt inalterado)
    try:
        instr_index = template_customizado.find("IMPORTANT FINAL INSTRUCTION:")
        if instr_index != -1:
             start_index = max(0, instr_index - 50)
             end_index = min(len(template_customizado), instr_index + 150)
             print(f"...{template_customizado[start_index:end_index]}...")
        else: print("(Instrução PT-BR não encontrada no ponto esperado)")
    except Exception as e_print: print(f"(Erro ao imprimir trecho do prompt: {e_print})")
    print("-------------------------------------------------------------")

    # Cria o agente com o prompt e a lista de ferramentas ATUALIZADA
    agent = create_react_agent(llm=llm, tools=tools, prompt=react_prompt_ptbr)

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools, # Passa a lista de ferramentas atualizada
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10
    )
    print("\nAgente LangChain (ReAct PT-BR com Ferramentas) e Executor configurados.")
    print("Ferramentas disponíveis:", [tool.name for tool in tools]) # Mostra ferramentas carregadas
    print("-" * 30)

except Exception as e:
    print(f"Erro crítico ao configurar o Agente LangChain customizado: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


# --- Função para Capturar e Reconhecer Voz ---
# (Função ouvir_comando inalterada)
def ouvir_comando(timeout_microfone=5, frase_limite_segundos=10):
    # ... (código ouvir_comando inalterado) ...
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("\nAjustando ruído ambiente... Aguarde.")
            try:
                r.adjust_for_ambient_noise(source, duration=1)
                print(f"Fale seu comando ou pergunta (limite: {frase_limite_segundos}s):") # Atualiza prompt
                audio = r.listen(source, timeout=timeout_microfone, phrase_time_limit=frase_limite_segundos)
            except sr.WaitTimeoutError: return None # Silêncio é normal, não imprime erro
            except Exception as e_listen: print(f"Erro durante a escuta: {e_listen}"); return None
    except OSError as e_mic: print(f"Erro Microfone: {e_mic}"); return None
    except Exception as e_mic_geral: print(f"Erro Microfone Geral: {e_mic_geral}"); return None

    print("Reconhecendo...")
    try:
        texto_comando = r.recognize_google(audio, language='pt-BR')
        print(f"Você disse: '{texto_comando}'")
        return texto_comando
    except sr.UnknownValueError: print("Não entendi o áudio."); return None
    except sr.RequestError as e: print(f"Erro Serviço Reconhecimento: {e}"); return None
    except Exception as e: print(f"Erro Reconhecimento: {e}"); return None

# --- Função para Falar (TTS com OpenAI) ---
# (Função falar inalterada)
def falar(texto):
    # ... (código falar inalterado) ...
    if not openai_tts_ready or not texto:
        if texto: print(f"\n(Saída que seria falada): {texto}")
        else: print("[TTS] Nada para falar.")
        return
    print(f"\n🔊 Falando (OpenAI TTS - {TTS_VOICE_OPENAI}): {texto}")
    temp_filename = None
    try:
        response = openai_client.audio.speech.create(model=TTS_MODEL_OPENAI, voice=TTS_VOICE_OPENAI, input=texto)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            fp.write(response.content)
            temp_filename = fp.name
        if temp_filename: playsound.playsound(temp_filename)
    except ImportError: print("Erro: 'playsound' não instalado? (pip install playsound==1.2.2)")
    except Exception as e: print(f"Erro OpenAI TTS / playsound: {e}")
    finally:
        if temp_filename and os.path.exists(temp_filename):
            try: os.remove(temp_filename)
            except Exception as e_del: print(f"Aviso: Falha ao deletar temp audio: {e_del}")


# --- Loop Principal Interativo com Voz (Com Ferramenta de Agenda) ---
print("\nLangChain Windows Voice Commander Agent (OpenAI TTS / PT-BR / Calendar)") # Título atualizado
print("======================================================================")
print("!!! AVISO DE RISCO EXTREMO !!!")
# ... (avisos) ...
print("======================================================================")
print(f"Usando LLM: {MODEL_NAME} | TTS: OpenAI ({TTS_VOICE_OPENAI})")
print("Verifique se GOOGLE_API_KEY, OPENAI_API_KEY, e credentials.json estão configurados!")
if not google_auth_ready: print("AVISO: Acesso a serviços Google (Agenda) está desabilitado.")
print("Fale 'sair' para terminar.")

while True:
    task_text = ouvir_comando()

    if task_text:
        if task_text.lower().strip() == 'sair':
            falar("Encerrando o assistente.")
            break

        # Verifica se o usuário pediu algo relacionado à agenda (exemplo simples)
        # O Agente LangChain deve fazer isso de forma mais inteligente com a descrição da ferramenta
        if not google_auth_ready and ("agenda" in task_text.lower() or "evento" in task_text.lower()):
             falar("Desculpe, não consigo acessar sua agenda pois a autenticação com o Google falhou na inicialização.")
             continue # Pula para a próxima iteração do loop

        try:
            print(f"\n>>> Enviando tarefa ( '{task_text}' ) para o agente...")
            response = agent_executor.invoke({"input": task_text})
            agent_output_text = response.get("output", "Não obtive uma resposta final do agente.")

            print("\n--- Resposta Final do Agente ---")
            print(agent_output_text)
            print("------------------------------")
            falar(agent_output_text)

        except Exception as e:
            error_message = f"Ocorreu um erro durante a execução do agente: {e}"
            print(f"\n!!! {error_message} !!!")
            # Imprime traceback para depuração mais detalhada do erro do agente
            import traceback
            traceback.print_exc()
            falar(f"Ocorreu um erro interno ao processar sua solicitação.")

    else:
        # Não imprime nada se não ouviu comando, para não poluir
        # print("Nenhum comando de voz válido recebido. Aguardando...")
        pass # Simplesmente volta ao início do loop para ouvir novamente

# --- Fim do Script ---
print("\nScript LangChain com Voz terminado.")
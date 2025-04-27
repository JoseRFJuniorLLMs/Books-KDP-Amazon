# -*- coding: utf-8 -*-
# Nome do Arquivo: satan.py
# Data da versão: 2025-04-26 - OpenAI TTS + PT-BR + Google Calendar Read + Gmail Read

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
from langchain_community.agent_toolkits import GmailToolkit # <--- Import do Gmail Toolkit

# --- Imports para Reconhecimento de Voz ---
import speech_recognition as sr

# --- Imports para Síntese de Voz (OpenAI TTS) ---
from openai import OpenAI
# Tenta importar playsound, trata erro depois se falhar
try:
    import playsound
    playsound_installed = True
except ImportError:
    playsound_installed = False
    print("AVISO: Biblioteca 'playsound' não encontrada. Instale com 'pip install playsound==1.2.2'")

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

# === CONFIGURAÇÕES ===
# LLM
MODEL_NAME = "gemini-1.5-pro"
TEMPERATURE = 0.3
# OpenAI TTS
TTS_MODEL_OPENAI = "tts-1"
TTS_VOICE_OPENAI = "nova"
# Google OAuth & APIs
CREDENTIALS_FILENAME = 'credentialsDesk.json'  # Arquivo baixado do Google Cloud Console
TOKEN_FILENAME = 'token.json' # Arquivo para armazenar tokens do usuário
# --- !!! DEFINA OS ESCOPOS NECESSÁRIOS E AUTORIZADOS AQUI !!! ---
# Adicionado escopo do Gmail para leitura
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events.readonly', # Ler Agenda
    'https://www.googleapis.com/auth/gmail.readonly'           # Ler Gmail
]
# ------------------------------------------------------------------

# --- Configuração do LLM LangChain ---
if not GOOGLE_API_KEY: sys.exit("Erro Crítico: Variável GOOGLE_API_KEY não definida.")
try:
    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=GOOGLE_API_KEY, temperature=TEMPERATURE, convert_system_message_to_human=True)
    print(f"LLM LangChain ({MODEL_NAME}) inicializado.")
except Exception as e: sys.exit(f"Erro crítico ao inicializar o LLM LangChain: {e}")

# --- Inicialização do Cliente OpenAI (para TTS) ---
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
# (Função get_google_credentials inalterada - ela usará a lista SCOPES atualizada)
def get_google_credentials():
    """Obtém ou atualiza credenciais OAuth 2.0 do usuário."""
    creds = None
    if os.path.exists(TOKEN_FILENAME):
        try:
            # Importante: Carrega o token verificando se ele contém TODOS os escopos atuais
            creds = Credentials.from_authorized_user_file(TOKEN_FILENAME, SCOPES)
            print(f"Credenciais carregadas de '{TOKEN_FILENAME}'.")
        except ValueError as e: # Ocorre se os escopos no token não baterem com SCOPES
            print(f"Erro/Incompatibilidade de escopos ao carregar '{TOKEN_FILENAME}': {e}. Re-autorização necessária.")
            creds = None
            if os.path.exists(TOKEN_FILENAME): os.remove(TOKEN_FILENAME) # Força fluxo
        except Exception as e: # Outros erros de leitura/formato
            print(f"Erro ao carregar '{TOKEN_FILENAME}': {e}. Tentando re-autorizar.")
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Credenciais Google expiradas, atualizando...")
                creds.refresh(Request())
                print("Credenciais Google atualizadas.")
                with open(TOKEN_FILENAME, 'w') as token_file: token_file.write(creds.to_json())
                print(f"Credenciais atualizadas salvas em '{TOKEN_FILENAME}'.")
            except Exception as e:
                print(f"Erro ao atualizar credenciais Google: {e}. Re-autorização necessária.")
                if os.path.exists(TOKEN_FILENAME):
                    try: os.remove(TOKEN_FILENAME)
                    except Exception: pass
                creds = None
        else:
            if not os.path.exists(CREDENTIALS_FILENAME):
                print(f"Erro Crítico OAuth: Arquivo '{CREDENTIALS_FILENAME}' não encontrado.")
                return None
            try:
                print(f"Arquivo '{TOKEN_FILENAME}' não encontrado ou inválido/incompleto. Iniciando fluxo de autorização...")
                print(f"Solicitando acesso para: {SCOPES}")
                print("Uma janela do navegador será aberta para você autorizar o acesso.")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILENAME, SCOPES)
                creds = flow.run_local_server(port=0) # Abre navegador
                print("Autorização do Google concedida!")
                with open(TOKEN_FILENAME, 'w') as token_file: token_file.write(creds.to_json())
                print(f"Credenciais salvas em '{TOKEN_FILENAME}'.")
            except Exception as e:
                 print(f"Erro crítico durante o fluxo de autorização Google: {e}")
                 return None
    return creds

# --- Executa Autenticação Google OAuth na Inicialização ---
print("\n--- Verificando Credenciais Google OAuth 2.0 ---")
google_creds = get_google_credentials()
google_auth_ready = bool(google_creds)
if not google_auth_ready:
    print("ERRO CRÍTICO: Falha ao obter credenciais do Google OAuth.")
    print("O acesso a Agenda/Gmail/Drive não funcionará.")
else:
     print("Credenciais Google OAuth verificadas/obtidas com sucesso.")
print("-" * 50)


# --- Inicializa o Gmail Toolkit (se autenticação Google funcionou) ---
gmail_tools = [] # Lista para guardar as ferramentas do Gmail
if google_auth_ready:
    try:
        print("Inicializando Gmail Toolkit...")
        # O GmailToolkit precisa do 'service' da API construído com as credenciais
        gmail_service = build('gmail', 'v1', credentials=google_creds)
        gmail_toolkit = GmailToolkit(api_resource=gmail_service)
        gmail_tools = gmail_toolkit.get_tools() # Pega as ferramentas prontas (ex: search, get_message)
        print(f"Gmail Toolkit inicializado com {len(gmail_tools)} ferramentas.")
        # print("Ferramentas Gmail:", [tool.name for tool in gmail_tools]) # Para debug
    except Exception as e_gmail_toolkit:
        print(f"AVISO: Erro ao inicializar GmailToolkit: {e_gmail_toolkit}")
        print("       Verifique se a API do Gmail está habilitada no Google Cloud.")
        gmail_tools = [] # Garante que a lista está vazia se falhar
else:
    print("AVISO: GmailToolkit não será inicializado (autenticação Google falhou).")
print("-" * 50)


# --- Definição das Ferramentas Customizadas ---

# Ferramenta 1: Executar Comandos Windows
class WindowsCommandExecutorTool(BaseTool):
    """Ferramenta para executar comandos no Prompt do Windows (cmd.exe)."""
    name: str = "windows_command_executor"
    description: str = (
        "Executa um comando FORNECIDO COMO STRING única diretamente no Prompt de Comando do Windows (cmd.exe) na máquina local. "
        "Use esta ferramenta para interagir com o sistema operacional Windows do usuário (listar arquivos, criar pastas, etc.). "
        "A entrada DEVE ser a string exata do comando a ser executado (ex: 'dir C:\\Users'). "
        "A saída será uma string formatada contendo 'Return Code:', 'STDOUT:', e 'STDERR:' da execução. "
        "SEMPRE verifique o 'Return Code' e 'STDERR' na saída para determinar se o comando foi bem-sucedido. Um Return Code diferente de 0 indica erro. "
        "Exemplos de comandos válidos: 'dir', 'mkdir nome_pasta', 'ipconfig', 'del arquivo.txt'. "
        "AVISO DE SEGURANÇA EXTREMO: Esta ferramenta executa comandos reais no sistema. Use com MÁXIMA cautela. "
        "Prefira comandos simples e diretos. Evite comandos destrutivos como 'del' ou 'rmdir' sem confirmação clara ou necessidade absoluta."
    )
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

# Ferramenta 2: Listar Eventos Google Calendar
class ListCalendarEventsTool(BaseTool):
    """Ferramenta para listar eventos de hoje do Google Calendar."""
    name: str = "google_calendar_list_today_events"
    description: str = (
        "Use esta ferramenta para obter uma lista dos eventos do Google Calendar do usuário para o dia de HOJE. "
        "A entrada para esta ferramenta geralmente não é necessária ou pode ser algo como 'hoje' ou 'eventos de hoje'. "
        "Retorna uma string listando os eventos de hoje (horário e título) ou uma mensagem indicando que não há eventos."
    )
    def _run(self, query: str = "hoje") -> str:
        # ... (código _run inalterado) ...
        print(f"\n LCHAIN TOOL: Executando {self.name}...")
        creds = get_google_credentials()
        if not creds: return "Erro: Falha ao obter credenciais Google OAuth."
        try:
            service = build('calendar', 'v3', credentials=creds)
            now = datetime.datetime.utcnow()
            timeMin_dt = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc)
            timeMin = timeMin_dt.isoformat()
            timeMax_dt = timeMin_dt + datetime.timedelta(days=1)
            timeMax = timeMax_dt.isoformat()
            print(f"   (Buscando eventos entre {timeMin} e {timeMax} UTC)")
            events_result = service.events().list(calendarId='primary', timeMin=timeMin, timeMax=timeMax, maxResults=15, singleEvents=True, orderBy='startTime').execute()
            events = events_result.get('items', [])
            if not events: print("   (Nenhum evento encontrado.)"); return "Nenhum evento hoje."
            output_lines = ["Eventos de hoje:"]
            for event in events:
                start_data = event['start']
                is_all_day = 'date' in start_data and 'dateTime' not in start_data
                start_str = start_data.get('dateTime', start_data.get('date'))
                hour_minute = "N/A"
                try:
                    if not is_all_day:
                         dt_obj_utc = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                         dt_obj_local = dt_obj_utc.astimezone()
                         hour_minute = dt_obj_local.strftime('%H:%M')
                    else: hour_minute = "Dia Inteiro"
                except ValueError:
                     if is_all_day: hour_minute = "Dia Inteiro"
                     else: hour_minute = start_str
                summary = event.get('summary', '(Sem Título)')
                output_lines.append(f"- {hour_minute}: {summary}")
            print(f"   ({len(events)} eventos encontrados.)")
            return "\n".join(output_lines)
        except HttpError as error:
            error_msg = f"Erro Google Calendar API: {error}"; print(f" LCHAIN TOOL: {error_msg}")
            if error.resp.status == 403: return f"Erro: Permissão negada - Agenda. {error}"
            return error_msg
        except Exception as e:
            error_msg = f"Erro inesperado - Agenda: {e}"; print(f" LCHAIN TOOL: {error_msg}")
            import traceback; traceback.print_exc(); return error_msg
# --- Fim das Ferramentas ---


# --- Inicialização das Ferramentas para o Agente ---
# Junta as ferramentas base com as do Gmail (se disponíveis)
base_tools = [
    WindowsCommandExecutorTool(),
    ListCalendarEventsTool()
]
# Adiciona ferramentas do Gmail SE o toolkit foi inicializado com sucesso
if 'gmail_tools' in locals() and gmail_tools:
    tools = base_tools + gmail_tools
    print(f"Total de {len(tools)} ferramentas carregadas (incluindo Gmail).")
else:
    tools = base_tools # Usa apenas as ferramentas base se Gmail falhou
    print(f"Total de {len(tools)} ferramentas carregadas (Gmail indisponível).")


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
    try:
        instr_index = template_customizado.find("IMPORTANT FINAL INSTRUCTION:")
        if instr_index != -1:
             start_index = max(0, instr_index - 50); end_index = min(len(template_customizado), instr_index + 150)
             print(f"...{template_customizado[start_index:end_index]}...")
        else: print("(Instrução PT-BR não encontrada)")
    except Exception as e_print: print(f"(Erro ao imprimir prompt: {e_print})")
    print("-------------------------------------------------------------")

    # Cria o agente com o prompt e a lista de ferramentas ATUALIZADA
    agent = create_react_agent(llm=llm, tools=tools, prompt=react_prompt_ptbr)

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools, # Passa a lista de ferramentas atualizada
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=15
    )
    print("\nAgente LangChain (ReAct PT-BR com Ferramentas) e Executor configurados.")
    print("Ferramentas disponíveis para o agente:", [tool.name for tool in tools]) # Mostra ferramentas carregadas
    print("-" * 30)

except Exception as e:
    print(f"Erro crítico ao configurar o Agente LangChain customizado: {e}")
    import traceback; traceback.print_exc(); sys.exit(1)


# --- Função para Capturar e Reconhecer Voz ---
# (Função ouvir_comando inalterada)
def ouvir_comando(timeout_microfone=5, frase_limite_segundos=10):
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("\nAjustando ruído ambiente... Aguarde.")
            try: r.adjust_for_ambient_noise(source, duration=1)
            except Exception as e_noise: print(f"Aviso: Falha ajuste ruído: {e_noise}")
            print(f"Fale seu comando ou pergunta (limite: {frase_limite_segundos}s):")
            try: audio = r.listen(source, timeout=timeout_microfone, phrase_time_limit=frase_limite_segundos)
            except sr.WaitTimeoutError: return None
            except Exception as e_listen: print(f"Erro escuta: {e_listen}"); return None
    except OSError as e_mic: print(f"Erro Microfone: {e_mic}"); return None
    except Exception as e_mic_geral: print(f"Erro Microfone Geral: {e_mic_geral}"); return None
    print("Reconhecendo...")
    try:
        texto_comando = r.recognize_google(audio, language='pt-BR')
        print(f"Você disse: '{texto_comando}'")
        return texto_comando
    except sr.UnknownValueError: print("Não entendi."); return None
    except sr.RequestError as e: print(f"Erro Serviço Reconhecimento: {e}"); return None
    except Exception as e: print(f"Erro Reconhecimento: {e}"); return None

# --- Função para Falar (TTS com OpenAI) ---
# (Função falar inalterada)
def falar(texto):
    global playsound_installed
    if not openai_tts_ready or not texto:
        if texto: print(f"\n(Saída falada): {texto}")
        else: print("[TTS] Nada para falar.")
        return
    print(f"\n🔊 Falando (OpenAI TTS - {TTS_VOICE_OPENAI}): {texto}")
    temp_filename = None
    try:
        response = openai_client.audio.speech.create(model=TTS_MODEL_OPENAI, voice=TTS_VOICE_OPENAI, input=texto)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            fp.write(response.content)
            temp_filename = fp.name
        if temp_filename:
            if playsound_installed:
                 playsound.playsound(temp_filename)
            else:
                 print("AVISO: 'playsound' não instalado. Não é possível tocar.")
                 # Tenta abrir com player padrão do Windows como fallback
                 try: os.startfile(temp_filename)
                 except Exception as e_start: print(f"Falha ao tentar abrir áudio com player padrão: {e_start}")
    except NameError: print("Erro: 'playsound' não importado? Instale com 'pip install playsound==1.2.2'")
    except Exception as e: print(f"Erro OpenAI TTS / playsound: {e}")
    finally:
        if temp_filename and os.path.exists(temp_filename):
            # Adiciona um pequeno delay antes de tentar remover, pode ajudar no Windows
            import time; time.sleep(0.5)
            try: os.remove(temp_filename)
            except Exception as e_del: print(f"Aviso: Falha deletar temp audio: {temp_filename}: {e_del}")


# --- Loop Principal Interativo ---
print("\nLangChain Windows Voice Commander Agent (OpenAI TTS / PT-BR / Calendar / Gmail Read)") # Título atualizado
print("==================================================================================")
print("!!! AVISO DE RISCO EXTREMO !!!")
print("==================================================================================")
print(f"Usando LLM: {MODEL_NAME} | TTS: OpenAI ({TTS_VOICE_OPENAI})")
print("Verifique se GOOGLE_API_KEY, OPENAI_API_KEY, e token.json estão configurados!")
if not google_auth_ready: print("AVISO: Acesso a serviços Google (Agenda, Gmail) está desabilitado.")
print("Fale 'sair' para terminar.")

while True:
    task_text = ouvir_comando()

    if task_text:
        if task_text.lower().strip() == 'sair':
            falar("Encerrando o assistente.")
            break

        # Se a autenticação Google falhou, impede o uso de ferramentas Google
        # Verifica palavras chave comuns para os serviços integrados
        google_service_keywords = ["agenda", "evento", "calendário", "gmail", "email", "e-mail", "drive", "arquivo"]
        requires_google = any(keyword in task_text.lower() for keyword in google_service_keywords)

        if requires_google and not google_auth_ready:
             falar("Desculpe, não consigo acessar seus serviços Google pois a autenticação falhou na inicialização.")
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
            import traceback; traceback.print_exc()
            falar(f"Ocorreu um erro interno. Verifique o console.")

    else:
        # Silêncio, espera próximo comando
        pass # Não imprime nada para não poluir

# --- Fim do Script ---
print("\nScript LangChain com Voz terminado.")
# -*- coding: utf-8 -*-
# Nome do Arquivo: satan.py
# Data da versão: 2025-04-27 - CONTROLE TOTAL GOOGLE + FERRAMENTAS EXEMPLO

#
# ███████╗██╗   ██╗███████╗ ██████╗ ███╗   ███╗ ██████╗ ██╗   ██╗███████╗
# ██╔════╝██║   ██║██╔════╝██╔════╝ ████╗ ████║██╔════╝ ██║   ██║██╔════╝
# ███████╗██║   ██║███████╗██║  ███╗██╔████╔██║██║  ███╗██║   ██║███████╗
# ╚════██║██║   ██║╚════██║██║   ██║██║╚██╔╝██║██║   ██║██║   ██║╚════██║
# ███████║╚██████╔╝███████║╚██████╔╝██║ ╚═╝ ██║╚██████╔╝╚██████╔╝███████║
# ╚══════╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝     ╚═╝ ╚═════╝  ╚═════╝ ╚══════╝
# =====================================================================
# ==       AVISO: RISCO EXTREMO DE SEGURANÇA E PERDA DE DADOS        ==
# ==    USE ESTE CÓDIGO POR SUA CONTA E RISCO ABSOLUTAMENTE TOTAL    ==
# =====================================================================
#
# -*- coding: utf-8 -*-
# Nome do Arquivo: satan.py
# Data da versão: 2025-04-27 - Controle Total + Ferramentas + Correção SyntaxError CreateEventTool

# =====================================================================
# ==       AVISO: RISCO EXTREMO DE SEGURANÇA E PERDA DE DADOS        ==
# ==    USE ESTE CÓDIGO POR SUA CONTA E RISCO ABSOLUTAMENTE TOTAL    ==
# =====================================================================

# -*- coding: utf-8 -*-
# Nome do Arquivo: satan.py
# Data da versão: 2025-04-27 - Controle Total + Ferramentas + Correção SyntaxError (CreateEventTool + ouvir_comando)

# =====================================================================
# ==       AVISO: RISCO EXTREMO DE SEGURANÇA E PERDA DE DADOS        ==
# ==    USE ESTE CÓDIGO POR SUA CONTA E RISCO ABSOLUTAMENTE TOTAL    ==
# =====================================================================

import os
import os.path
import subprocess
import sys
import tempfile
from dotenv import load_dotenv
import datetime
import traceback
import base64
from email.message import EmailMessage
import re

# --- Imports do LangChain ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import BaseTool
from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
# from langchain_community.agent_toolkits import GmailToolkit # Usando SendGmailTool customizada

# --- Imports para Reconhecimento de Voz ---
import speech_recognition as sr

# --- Imports para Síntese de Voz (OpenAI TTS) ---
from openai import OpenAI
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
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# === CARREGA VARIÁVEIS DE AMBIENTE ===
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# === CONFIGURAÇÕES ===
MODEL_NAME = "gemini-1.5-pro"; TEMPERATURE = 0.3
TTS_MODEL_OPENAI = "tts-1"; TTS_VOICE_OPENAI = "nova"
CREDENTIALS_FILENAME = 'credentials.json'
TOKEN_FILENAME = 'token.json'
# --- ESCOPOS DE CONTROLE TOTAL (ALTÍSSIMO RISCO!) ---
SCOPES = [
    'https://www.googleapis.com/auth/calendar',             # Controle TOTAL da Agenda
    'https://mail.google.com/',                             # Controle TOTAL do Gmail
    'https://www.googleapis.com/auth/drive',                 # Controle TOTAL do Drive
    'https://www.googleapis.com/auth/youtube',               # Controle da conta YouTube
    'https://www.googleapis.com/auth/youtube.upload',        # Upload de vídeos no YouTube
    'https://www.googleapis.com/auth/userinfo.email',        # Ver email
    'https://www.googleapis.com/auth/userinfo.profile',      # Ver perfil
    'openid'                                                 # Padrão OpenID
]
# -----------------------------------------------------

# --- Configuração do LLM LangChain ---
if not GOOGLE_API_KEY: sys.exit("Erro Crítico: GOOGLE_API_KEY não definida.")
try:
    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=GOOGLE_API_KEY, temperature=TEMPERATURE, convert_system_message_to_human=True)
    print(f"LLM LangChain ({MODEL_NAME}) inicializado.")
except Exception as e: sys.exit(f"Erro crítico LLM LangChain: {e}")

# --- Inicialização do Cliente OpenAI (para TTS) ---
openai_tts_ready = False; openai_client = None
try:
    if not OPENAI_API_KEY: raise EnvironmentError("OPENAI_API_KEY não definida.")
    openai_client = OpenAI()
    print("Cliente OpenAI (para TTS) inicializado.")
    openai_tts_ready = True
except Exception as e: print(f"Erro cliente OpenAI: {e}\nAVISO: OpenAI TTS não funcionará.")

# --- Função para Autenticação Google OAuth 2.0 (Indentação Corrigida nos excepts) ---
def get_google_credentials():
    """Obtém ou atualiza credenciais OAuth 2.0 do usuário."""
    creds = None
    if os.path.exists(TOKEN_FILENAME):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILENAME, SCOPES)
        except ValueError as e:
            print(f"Erro escopos ao carregar '{TOKEN_FILENAME}': {e}. Re-autenticando.")
            creds = None
            if os.path.exists(TOKEN_FILENAME):
                try: os.remove(TOKEN_FILENAME)
                except Exception as e_del: print(f"Aviso: Falha ao remover token: {e_del}")
        except Exception as e:
            print(f"Erro geral ao carregar '{TOKEN_FILENAME}': {e}. Re-autenticando.")
            creds = None
            if os.path.exists(TOKEN_FILENAME):
                 try: os.remove(TOKEN_FILENAME)
                 except Exception as e_del: print(f"Aviso: Falha ao remover token: {e_del}")

    valid_creds_check = bool(creds and creds.valid)
    if not valid_creds_check:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Credenciais Google expiradas, atualizando..."); creds.refresh(Request()); print("Credenciais Google atualizadas.")
                try:
                    with open(TOKEN_FILENAME, 'w') as token_file: token_file.write(creds.to_json()); print(f"Credenciais salvas em '{TOKEN_FILENAME}'.")
                except Exception as e_save: print(f"Erro ao salvar token atualizado: {e_save}")
            except Exception as e_refresh:
                print(f"Erro ao atualizar credenciais Google: {e_refresh}. Re-autorização necessária.")
                if os.path.exists(TOKEN_FILENAME):
                    try: os.remove(TOKEN_FILENAME)
                    except Exception as e_del: print(f"Aviso: Falha ao remover token pós-refresh: {e_del}")
                creds = None
        else: # Inicia fluxo do zero
            if not os.path.exists(CREDENTIALS_FILENAME): print(f"Erro Crítico OAuth: '{CREDENTIALS_FILENAME}' não encontrado!"); return None
            flow = None
            try:
                print(f"Iniciando fluxo de autorização para: {SCOPES}")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILENAME, SCOPES)
            except Exception as e: print(f"ERRO FATAL ao criar fluxo: {e}"); traceback.print_exc(); return None
            if flow:
                try:
                    print(">>> NAVEGADOR DEVE ABRIR PARA AUTORIZAÇÃO GOOGLE <<<")
                    creds = flow.run_local_server(port=0)
                    print("Autorização Google concedida!")
                    try:
                        with open(TOKEN_FILENAME, 'w') as token_file: token_file.write(creds.to_json()); print(f"Credenciais salvas em '{TOKEN_FILENAME}'.")
                    except Exception as e_save: print(f"ERRO ao salvar token novo: {e_save}")
                except Exception as e: print(f"ERRO FATAL durante 'run_local_server()': {e}"); traceback.print_exc(); creds = None
            else: print("ERRO: Objeto flow não foi criado."); creds = None
    return creds

# --- Executa Autenticação Google OAuth na Inicialização ---
print("\n--- Verificando Credenciais Google OAuth 2.0 ---")
google_creds = get_google_credentials()
google_auth_ready = bool(google_creds and google_creds.valid)
if not google_auth_ready: print("ERRO CRÍTICO PÓS-AUTH: Falha Google OAuth. Serviços Google desabilitados.")
else: print("SUCESSO PÓS-AUTH: Credenciais Google OAuth OK.")
print("-" * 50)

# --- Definição das Ferramentas Customizadas ---

# Ferramenta 1: Executar Comandos Windows
class WindowsCommandExecutorTool(BaseTool):
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
        print(f"\n LCHAIN TOOL: Executando {self.name}: C:\\> {command_string}")
        if not isinstance(command_string, str) or not command_string.strip(): return "Erro: Input inválido."
        forbidden_commands = ["format", "shutdown"]; command_start = ""
        if command_string: command_parts = command_string.strip().split();
        if command_parts: command_start = command_parts[0].lower()
        if command_start in forbidden_commands: return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro: Comando '{command_start}' bloqueado."
        try:
            result = subprocess.run(command_string, shell=True, capture_output=True, text=True, check=False, encoding='cp850', errors='ignore')
            output = f"Return Code: {result.returncode}\nSTDOUT:\n{result.stdout.strip() or '(None)'}\nSTDERR:\n{result.stderr.strip() or '(None)'}"
            print(f" LCHAIN TOOL: Concluído {self.name}. Código: {result.returncode}");
            if result.returncode != 0: print(f" LCHAIN TOOL: STDERR: {result.stderr.strip() or '(None)'}")
            return output
        except FileNotFoundError: return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro: Comando '{command_start}' não encontrado."
        except Exception as e: return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro Inesperado: {e}"

# Ferramenta 2: Listar Eventos Google Calendar
class ListCalendarEventsTool(BaseTool):
    name: str = "google_calendar_list_today_events"
    description: str = (
        "Use esta ferramenta para obter uma lista dos eventos do Google Calendar do usuário para o dia de HOJE. "
        "A entrada para esta ferramenta geralmente não é necessária ou pode ser algo como 'hoje' ou 'eventos de hoje'. "
        "Retorna uma string listando os eventos de hoje (horário e título) ou uma mensagem indicando que não há eventos."
    )
    def _run(self, query: str = "") -> str:
        print(f"\n LCHAIN TOOL: Executando {self.name}...")
        creds = get_google_credentials();
        if not creds: return "Erro: Falha credenciais Google."
        try:
            service = build('calendar', 'v3', credentials=creds)
            now = datetime.datetime.utcnow(); timeMin_dt = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc); timeMin = timeMin_dt.isoformat(); timeMax_dt = timeMin_dt + datetime.timedelta(days=1); timeMax = timeMax_dt.isoformat()
            events_result = service.events().list(calendarId='primary', timeMin=timeMin, timeMax=timeMax, maxResults=15, singleEvents=True, orderBy='startTime').execute()
            events = events_result.get('items', [])
            if not events: return "Nenhum evento hoje."
            output_lines = ["Eventos de hoje:"]
            for event in events:
                start_data = event['start']; is_all_day = 'date' in start_data and 'dateTime' not in start_data; start_str = start_data.get('dateTime', start_data.get('date')); hour_minute = "N/A"
                try:
                    if not is_all_day: dt_obj_utc = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00')); dt_obj_local = dt_obj_utc.astimezone(); hour_minute = dt_obj_local.strftime('%H:%M')
                    else: hour_minute = "Dia Inteiro"
                except ValueError: hour_minute = "Dia Inteiro" if is_all_day else start_str
                summary = event.get('summary', '(Sem Título)'); output_lines.append(f"- {hour_minute}: {summary}")
            return "\n".join(output_lines)
        except HttpError as error: print(f" LCHAIN TOOL ERROR ({self.name}): {error}"); return f"Erro Calendar API: {error}"
        except Exception as e: print(f" LCHAIN TOOL ERROR ({self.name}): {e}"); traceback.print_exc(); return f"Erro inesperado Agenda: {e}"

# Ferramenta 3: Criar Evento Google Calendar (COM INDENTAÇÃO CORRIGIDA)
class CreateCalendarEventTool(BaseTool):
    """Ferramenta para criar um novo evento no Google Calendar."""
    name: str = "google_calendar_create_event"
    description: str = (
        "Use para criar um novo evento no calendário principal do Google. "
        "A entrada DEVE ser uma string descrevendo o evento, incluindo título, data e hora de início e fim. "
        "Exemplo: 'Marcar Almoço amanhã 12:30-13:30' ou 'Criar evento: Reunião Projeto 2025-05-15 10:00 às 11:00'. "
        "Se a hora de fim não for clara, assume duração de 1 hora. Datas relativas como 'hoje', 'amanhã' são aceitas."
        "Retorna confirmação ou erro."
    )
    def _parse_datetime_range(self, query: str):
        """Tenta analisar a string para extrair datas, horas e sumário. BÁSICO."""
        print(f"[DEBUG CreateEvent] Analisando: '{query}'"); start_dt, end_dt, summary = None, None, query
        try: # Tenta usar dateutil se disponível
            import dateutil.parser; from dateutil.relativedelta import relativedelta
            print("[DEBUG CreateEvent] Usando dateutil.parser...")
            cleaned_query = query.lower().replace("criar evento:", "").replace("marcar ", "").strip()
            words = cleaned_query.replace("das ", "").replace(" às ", "-").replace(" as ", "-").split()
            dt_part = " ".join(words[-3:]) if len(words) >=3 else " ".join(words)
            parsed_info = dateutil.parser.parse(dt_part, fuzzy=False, default=datetime.datetime.now())
            start_dt = parsed_info
            summary = cleaned_query.replace(dt_part,"").strip() or f"Evento: {query[:30]}"
            match_range = re.search(r'(\d{1,2}:\d{2})-(\d{1,2}:\d{2})', dt_part)
            if match_range:
                end_dt_time_str = match_range.group(2)
                end_dt_time = datetime.datetime.strptime(end_dt_time_str, "%H:%M").time()
                end_dt = start_dt.replace(hour=end_dt_time.hour, minute=end_dt_time.minute)
                if end_dt <= start_dt: end_dt += datetime.timedelta(days=1)
                print(f"[DEBUG CreateEvent] Range encontrado: {match_range.group(1)}-{match_range.group(2)}")
            else:
                end_dt = start_dt + datetime.timedelta(hours=1)
                print("[DEBUG CreateEvent] Range não encontrado, assumindo 1h.")
            print(f"[DEBUG CreateEvent] Análise OK (dateutil): start={start_dt}, end={end_dt}, summary={summary}")
        except ImportError:
            print("AVISO: dateutil não instalado (pip install python-dateutil). Análise limitada.")
            start_dt = datetime.datetime.now() + datetime.timedelta(hours=1); end_dt = start_dt + datetime.timedelta(hours=1); summary = query
            print(f"[DEBUG CreateEvent] Usando Fallback: start={start_dt}, summary={summary}")
        except Exception as e_parse:
             print(f"[DEBUG CreateEvent] Falha análise data/hora: {e_parse}"); return None, None, None
        if not start_dt: return None, None, None
        return start_dt, end_dt, summary

    def _run(self, query: str) -> str:
        print(f"\n LCHAIN TOOL: Executando {self.name} com query: '{query}'"); creds = get_google_credentials();
        if not creds: return "Erro: Falha credenciais Google."
        required_scopes = ['https://www.googleapis.com/auth/calendar.events', 'https://www.googleapis.com/auth/calendar']
        if not any(s in creds.scopes for s in required_scopes): return f"Erro: Permissão negada (escrita Agenda)."
        start_dt, end_dt, summary = self._parse_datetime_range(query)
        if not start_dt or not end_dt or not summary: return f"Erro: Não entendi detalhes (título/data/hora) em '{query}'."
        try: # Formata para API
            local_tz_offset = datetime.datetime.now(datetime.timezone.utc).astimezone().strftime('%z'); tz_str = local_tz_offset[:3] + ":" + local_tz_offset[3:]; time_zone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname() or 'America/Sao_Paulo'; start_rfc = start_dt.isoformat() + tz_str; end_rfc = end_dt.isoformat() + tz_str
        except Exception: time_zone = 'UTC'; start_rfc = start_dt.isoformat() + 'Z'; end_rfc = end_dt.isoformat() + 'Z'; print("Aviso: Usando UTC.")
        event_body = {'summary': summary, 'start': {'dateTime': start_rfc, 'timeZone': time_zone}, 'end': {'dateTime': end_rfc, 'timeZone': time_zone}}
        try:
            print(f"   (Criando evento: {summary} @ {start_rfc})"); service = build('calendar', 'v3', credentials=creds)
            created_event = service.events().insert(calendarId='primary', body=event_body).execute()
            link = created_event.get('htmlLink', 'N/A'); print(f"   (Evento criado! ID: {created_event.get('id')})")
            return f"Evento '{created_event.get('summary')}' criado. Link: {link}"
        except HttpError as error: print(f" LCHAIN TOOL ERROR ({self.name}): {error}"); return f"Erro Calendar API: {error}"
        except Exception as e: print(f" LCHAIN TOOL ERROR ({self.name}): {e}"); traceback.print_exc(); return f"Erro inesperado Agenda: {e}"

# Ferramenta 4: Enviar Email (Gmail)
class SendGmailTool(BaseTool):
    name: str = "send_gmail_message"
    description: str = (
        "Use esta ferramenta para ENVIAR um email através da conta Gmail do usuário. "
        "A entrada DEVE ser uma string formatada contendo destinatário, assunto e corpo. "
        "Use o formato: 'Para: email@dest.com Assunto: Meu Assunto Corpo: Mensagem que quero enviar aqui.' "
        "A ferramenta extrairá essas partes. "
        "Retorna confirmação de envio ou mensagem de erro. "
        "AVISO: Esta ferramenta ENVIA emails reais como o usuário."
    )
    def _run(self, query: str) -> str:
        print(f"\n LCHAIN TOOL: Executando {self.name}..."); creds = get_google_credentials();
        if not creds: return "Erro: Falha credenciais Google."
        required_scopes = ['https://www.googleapis.com/auth/gmail.send', 'https://mail.google.com/']
        if not any(s in creds.scopes for s in required_scopes): return f"Erro: Permissão negada (envio Gmail)."
        to_addr, subject, body = None, "Sem Assunto", ""
        try: # Extração básica
            to_match = re.search(r'Para:\s*([^\s<>]+@[^\s<>]+)', query, re.IGNORECASE) or re.search(r'Para:\s*.*?<([^\s<>]+@[^\s<>]+)>', query, re.IGNORECASE)
            if to_match: to_addr = to_match.group(1)
            subject_match = re.search(r'Assunto:\s*(.*?)(?=Corpo:|$)', query, re.IGNORECASE | re.DOTALL)
            if subject_match: subject = subject_match.group(1).strip() or "Sem Assunto"
            body_match = re.search(r'Corpo:\s*(.*)', query, re.IGNORECASE | re.DOTALL)
            if body_match: body = body_match.group(1).strip()
            if not to_addr or not body: raise ValueError("Faltou 'Para:' ou 'Corpo:'.")
        except Exception as e_parse: return f"Erro analisar email: {e_parse}. Use 'Para: email Assunto: texto Corpo: texto'."
        try:
            print(f"   (Enviando email para {to_addr})"); service = build('gmail', 'v1', credentials=creds)
            message = EmailMessage(); message.set_content(body); message['To'] = to_addr; message['Subject'] = subject
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {'raw': encoded_message}
            send_message = service.users().messages().send(userId='me', body=create_message).execute()
            print(f"   (Email enviado! ID: {send_message.get('id')})"); return f"Email enviado para {to_addr}."
        except HttpError as error: print(f" LCHAIN TOOL ERROR ({self.name}): {error}"); return f"Erro Gmail API: {error}"
        except Exception as e: print(f" LCHAIN TOOL ERROR ({self.name}): {e}"); traceback.print_exc(); return f"Erro inesperado Gmail: {e}"

# Ferramenta 5: Pesquisar Vídeos no YouTube
class YouTubeSearchTool(BaseTool):
    name: str = "Youtube" # Nome corrigido (era "Youtube")
    description: str = (
        "Use esta ferramenta para pesquisar vídeos no YouTube. "
        "A entrada deve ser a string de busca (termos que você quer pesquisar). "
        "Retorna uma lista com os títulos e IDs dos 5 primeiros vídeos encontrados ou uma mensagem de erro."
    )
    def _run(self, query: str) -> str:
        print(f"\n LCHAIN TOOL: Executando {self.name} com query: '{query}'"); creds = get_google_credentials();
        if not creds: return "Erro: Falha credenciais Google."
        required_scopes = ['https://www.googleapis.com/auth/youtube.readonly', 'https://www.googleapis.com/auth/youtube']
        if not any(s in creds.scopes for s in required_scopes): return f"Erro: Permissão negada (leitura YouTube)."
        if not query: return "Erro: Forneça um termo de busca para YouTube."
        try:
            service = build('youtube', 'v3', credentials=creds); print(f"   (Buscando YouTube: '{query}')")
            search_response = service.search().list(q=query, part='snippet', maxResults=5, type='video').execute()
            videos = search_response.get('items', [])
            if not videos: print("   (Nenhum vídeo encontrado)"); return f"Nenhum vídeo encontrado para: '{query}'"
            output_lines = [f"Resultados YouTube para '{query}':"]
            for item in videos:
                title = item['snippet']['title']; video_id = item['id']['videoId']; link = f"https://youtu.be/{video_id}" # Link simplificado
                output_lines.append(f"- {title} (Link: {link})")
            print(f"   ({len(videos)} vídeos encontrados.)"); return "\n".join(output_lines)
        except HttpError as error: print(f" LCHAIN TOOL ERROR ({self.name}): {error}"); return f"Erro YouTube API: {error}"
        except Exception as e: print(f" LCHAIN TOOL ERROR ({self.name}): {e}"); traceback.print_exc(); return f"Erro inesperado YouTube: {e}"

# Ferramenta 6: Listar Arquivos Google Drive (Raiz)
class DriveListFilesTool(BaseTool):
    name: str = "google_drive_list_root_files"
    description: str = (
        "Use esta ferramenta para listar os nomes dos arquivos e pastas que estão na pasta raiz ('Meu Drive') do Google Drive do usuário. "
        "A entrada geralmente não é necessária (pode ignorar). "
        "Retorna uma lista de nomes de arquivos/pastas ou uma mensagem de erro."
    )
    def _run(self, query: str = "") -> str:
        print(f"\n LCHAIN TOOL: Executando {self.name}..."); creds = get_google_credentials();
        if not creds: return "Erro: Falha credenciais Google."
        required_scopes = ['https://www.googleapis.com/auth/drive.metadata.readonly', 'https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']
        if not any(s in creds.scopes for s in required_scopes): return f"Erro: Permissão negada (leitura Drive)."
        try:
            service = build('drive', 'v3', credentials=creds); print("   (Listando raiz do Drive...)")
            results = service.files().list(pageSize=25, fields="files(id, name, mimeType)", orderBy="folder, name", q="'root' in parents and trashed = false").execute()
            items = results.get('files', [])
            if not items: print("   (Nenhum item na raiz.)"); return "Nenhum arquivo ou pasta na raiz do Drive."
            output_lines = ["Itens na Raiz do Drive:"]
            for item in items:
                name = item.get('name', 'N/A'); mime_type = item.get('mimeType', '')
                prefix = "[Pasta]" if mime_type == 'application/vnd.google-apps.folder' else "[Arquivo]"
                output_lines.append(f"- {prefix} {name}")
            print(f"   ({len(items)} itens encontrados.)"); return "\n".join(output_lines)
        except HttpError as error: print(f" LCHAIN TOOL ERROR ({self.name}): {error}"); return f"Erro Drive API: {error}"
        except Exception as e: print(f" LCHAIN TOOL ERROR ({self.name}): {e}"); traceback.print_exc(); return f"Erro inesperado Drive: {e}"

# --- Fim das Novas Ferramentas ---

# --- Inicialização das Ferramentas para o Agente ---
tools = [
    WindowsCommandExecutorTool(),
    ListCalendarEventsTool(),
    CreateCalendarEventTool(),
    SendGmailTool(),
    YouTubeSearchTool(),
    DriveListFilesTool(),
]
print(f"\nTotal de {len(tools)} ferramentas carregadas.")
print("Ferramentas disponíveis para o agente:", [tool.name for tool in tools])
print("-" * 50)

# --- Configuração do Agente (ReAct com Prompt Customizado PT-BR) ---
try:
    react_prompt_original = hub.pull("hwchase17/react"); parts = react_prompt_original.template.split("Begin!")
    if len(parts) == 2: template_customizado = parts[0].strip() + "\n\nIMPORTANT FINAL INSTRUCTION: Your final answer (Final Answer:) MUST always be in Brazilian Portuguese (Português do Brasil)." + "\n\nBegin!" + parts[1]
    else: template_customizado = react_prompt_original.template + "\n\nIMPORTANT FINAL INSTRUCTION: Your final answer (Final Answer:) MUST always be in Brazilian Portuguese (Português do Brasil)."
    react_prompt_ptbr = PromptTemplate.from_template(template_customizado); react_prompt_ptbr.input_variables = react_prompt_original.input_variables
    agent = create_react_agent(llm=llm, tools=tools, prompt=react_prompt_ptbr)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True, max_iterations=15)
    print("\nAgente LangChain (ReAct PT-BR com Ferramentas) e Executor configurados.")
    print("Ferramentas carregadas para o agente:", [tool.name for tool in agent_executor.tools]); print("-" * 30)
except Exception as e: print(f"Erro crítico Agente LangChain: {e}"); traceback.print_exc(); sys.exit(1)

# --- Função para Capturar e Reconhecer Voz (Com Correção de SyntaxError) ---
def ouvir_comando(timeout_microfone=5, frase_limite_segundos=10):
    r = sr.Recognizer(); audio = None
    try:
        with sr.Microphone() as source:
            print("\nAjustando ruído ambiente...")
            # --- CORREÇÃO DE INDENTAÇÃO AQUI ---
            try:
                r.adjust_for_ambient_noise(source, duration=1)
            except Exception as e_noise:
                print(f"Aviso: Falha ajuste ruído amb.: {e_noise}")
            # --- Fim da Correção ---
            print(f"Fale seu comando/pergunta ({frase_limite_segundos}s max):")
            try: audio = r.listen(source, timeout=timeout_microfone, phrase_time_limit=frase_limite_segundos)
            except sr.WaitTimeoutError: return None
            except Exception as e_listen: print(f"Erro escuta: {e_listen}"); return None
    except Exception as e_mic: print(f"Erro Microfone: {e_mic}"); return None
    if not audio: return None
    print("Reconhecendo..."); texto_comando = None
    try: texto_comando = r.recognize_google(audio, language='pt-BR'); print(f"Você disse: '{texto_comando}'")
    except sr.UnknownValueError: print("Não entendi.")
    except sr.RequestError as e: print(f"Erro Serviço Reconhecimento: {e}")
    except Exception as e: print(f"Erro Reconhecimento: {e}")
    return texto_comando

# --- Função para Falar (TTS com OpenAI) ---
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
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp: fp.write(response.content); temp_filename = fp.name
        if temp_filename:
            if playsound_installed: playsound.playsound(temp_filename)
            else: print("AVISO: 'playsound' não instalado.");
            try: os.startfile(temp_filename);
            except Exception: print("Falha ao abrir áudio.")
    except NameError: print("Erro: 'playsound' não importado?")
    except Exception as e: print(f"Erro OpenAI TTS / playsound: {e}")
    finally:
        if temp_filename and os.path.exists(temp_filename): import time; time.sleep(0.5);
        try: os.remove(temp_filename);
        except Exception:pass

# --- Loop Principal Interativo ---
print(f"\nLangChain Windows Voice Commander Agent (Controle Total Ativado - RISCO ALTO)")
print("================================================================================")
print("!!! AVISO DE RISCO EXTREMO - CONTROLE TOTAL ATIVADO !!!")
print("================================================================================")
print(f"Usando LLM: {MODEL_NAME} | TTS: OpenAI ({TTS_VOICE_OPENAI})")
print("Verifique APIs, Escopos Amplos, Chaves e credentials.json!")
if not google_auth_ready: print("AVISO: Acesso a serviços Google está desabilitado.")
print("Fale 'sair' para terminar.")

while True:
    task_text = ouvir_comando()
    if task_text:
        if task_text.lower().strip() == 'sair': falar("Encerrando..."); break
        google_service_keywords = ["agenda", "evento", "calendário", "gmail", "email", "e-mail", "drive", "arquivo", "youtube", "vídeo"]
        requires_google = any(keyword in task_text.lower() for keyword in google_service_keywords)
        if requires_google and not google_auth_ready: falar("Desculpe, autenticação Google falhou."); continue
        try:
            print(f"\n>>> Enviando tarefa ( '{task_text}' ) para o agente...")
            response = agent_executor.invoke({"input": task_text})
            agent_output_text = response.get("output", "Não obtive uma resposta final.")
            print("\n--- Resposta Final do Agente ---"); print(agent_output_text); print("------------------------------")
            falar(agent_output_text)
        except Exception as e:
            error_message = f"Ocorreu um erro durante a execução do agente: {e}"
            print(f"\n!!! {error_message} !!!"); traceback.print_exc()
            falar(f"Ocorreu um erro interno.")
    else: pass

# --- Fim do Script ---
print("\nScript LangChain com Voz terminado.")
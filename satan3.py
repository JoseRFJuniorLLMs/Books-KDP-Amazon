# -*- coding: utf-8 -*-
# Nome do Arquivo: satan.py
# Data da versão: 2025-05-17 - CONTROLE TOTAL GOOGLE + TTS GOOGLE CLOUD + MODELO ATUALIZADO

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

# --- Imports para Reconhecimento de Voz ---
import speech_recognition as sr

# --- Imports para Síntese de Voz (Google Cloud TTS) ---
from google.cloud import texttospeech  # MODIFICADO: Import para Google Cloud TTS

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
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # REMOVIDO/COMENTADO: Não mais usado para TTS principal

# === CONFIGURAÇÕES ===
# MODIFICADO: Atualize para o nome do modelo de preview mais recente ou desejado. Ex: "gemini-2.5-pro-preview-0528"
# Consulte a documentação do Google AI para os nomes de modelos mais atuais.
MODEL_NAME = "models/gemini-2.5-pro-preview-03-25";
TEMPERATURE = 0.3  # Exemplo: usando 'latest' que pode existir. Verifique!
# TTS_MODEL_OPENAI = "tts-1"; TTS_VOICE_OPENAI = "nova" # REMOVIDO/COMENTADO: Configs do OpenAI TTS
TTS_VOICE_GOOGLE = "pt-BR-Wavenet-A"  # MODIFICADO: Exemplo de voz do Google Cloud TTS
CREDENTIALS_FILENAME = 'credentials.json'
TOKEN_FILENAME = 'token.json'
# --- ESCOPOS DE CONTROLE TOTAL (ALTÍSSIMO RISCO!) ---
SCOPES = [
    'https://www.googleapis.com/auth/calendar',  # Controle TOTAL da Agenda
    'https://mail.google.com/',  # Controle TOTAL do Gmail
    'https://www.googleapis.com/auth/drive',  # Controle TOTAL do Drive
    'https://www.googleapis.com/auth/youtube',  # Controle da conta YouTube
    'https://www.googleapis.com/auth/youtube.upload',  # Upload de vídeos no YouTube
    'https://www.googleapis.com/auth/userinfo.email',  # Ver email
    'https://www.googleapis.com/auth/userinfo.profile',  # Ver perfil
    'openid'  # Padrão OpenID
]
# -----------------------------------------------------

# --- Configuração do LLM LangChain ---
if not GOOGLE_API_KEY: sys.exit("Erro Crítico: GOOGLE_API_KEY não definida.")
try:
    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=GOOGLE_API_KEY, temperature=TEMPERATURE,
                                 convert_system_message_to_human=True)
    print(f"LLM LangChain ({MODEL_NAME}) inicializado.")
except Exception as e:
    sys.exit(f"Erro crítico LLM LangChain: {e}")

# --- Inicialização do Cliente Google Cloud TTS ---
google_tts_ready = False
try:
    # A biblioteca google-cloud-texttospeech geralmente usa Application Default Credentials (ADC)
    # ou você pode configurar explicitamente as credenciais.
    # Se suas outras APIs do Google estiverem funcionando, esta também poderá.
    # Verifique se a API "Cloud Text-to-Speech API" está habilitada no seu projeto GCP.
    texttospeech.TextToSpeechClient()  # Tentativa de instanciar para verificar a prontidão
    print("Cliente Google Cloud TTS parece estar pronto.")
    google_tts_ready = True
except Exception as e:
    print(f"Erro ao inicializar cliente Google Cloud TTS: {e}\nAVISO: Google Cloud TTS pode não funcionar.")
    print("Verifique se a API 'Cloud Text-to-Speech' está habilitada no GCP e se a autenticação está configurada.")


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
                try:
                    os.remove(TOKEN_FILENAME)
                except Exception as e_del:
                    print(f"Aviso: Falha ao remover token: {e_del}")
        except Exception as e:
            print(f"Erro geral ao carregar '{TOKEN_FILENAME}': {e}. Re-autenticando.")
            creds = None
            if os.path.exists(TOKEN_FILENAME):
                try:
                    os.remove(TOKEN_FILENAME)
                except Exception as e_del:
                    print(f"Aviso: Falha ao remover token: {e_del}")

    valid_creds_check = bool(creds and creds.valid)
    if not valid_creds_check:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Credenciais Google expiradas, atualizando...");
                creds.refresh(Request());
                print("Credenciais Google atualizadas.")
                try:
                    with open(TOKEN_FILENAME, 'w') as token_file:
                        token_file.write(creds.to_json()); print(f"Credenciais salvas em '{TOKEN_FILENAME}'.")
                except Exception as e_save:
                    print(f"Erro ao salvar token atualizado: {e_save}")
            except Exception as e_refresh:
                print(f"Erro ao atualizar credenciais Google: {e_refresh}. Re-autorização necessária.")
                if os.path.exists(TOKEN_FILENAME):
                    try:
                        os.remove(TOKEN_FILENAME)
                    except Exception as e_del:
                        print(f"Aviso: Falha ao remover token pós-refresh: {e_del}")
                creds = None
        else:  # Inicia fluxo do zero
            if not os.path.exists(CREDENTIALS_FILENAME): print(
                f"Erro Crítico OAuth: '{CREDENTIALS_FILENAME}' não encontrado!"); return None
            flow = None
            try:
                print(f"Iniciando fluxo de autorização para: {SCOPES}")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILENAME, SCOPES)
            except Exception as e:
                print(f"ERRO FATAL ao criar fluxo: {e}"); traceback.print_exc(); return None
            if flow:
                try:
                    print(">>> NAVEGADOR DEVE ABRIR PARA AUTORIZAÇÃO GOOGLE <<<")
                    creds = flow.run_local_server(port=0)
                    print("Autorização Google concedida!")
                    try:
                        with open(TOKEN_FILENAME, 'w') as token_file:
                            token_file.write(creds.to_json()); print(f"Credenciais salvas em '{TOKEN_FILENAME}'.")
                    except Exception as e_save:
                        print(f"ERRO ao salvar token novo: {e_save}")
                except Exception as e:
                    print(f"ERRO FATAL durante 'run_local_server()': {e}"); traceback.print_exc(); creds = None
            else:
                print("ERRO: Objeto flow não foi criado."); creds = None
    return creds


# --- Executa Autenticação Google OAuth na Inicialização ---
print("\n--- Verificando Credenciais Google OAuth 2.0 ---")
google_creds = get_google_credentials()
google_auth_ready = bool(google_creds and google_creds.valid)
if not google_auth_ready:
    print("ERRO CRÍTICO PÓS-AUTH: Falha Google OAuth. Serviços Google desabilitados.")
else:
    print("SUCESSO PÓS-AUTH: Credenciais Google OAuth OK.")
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
        forbidden_commands = ["format", "shutdown"];
        command_start = ""
        command_parts = []  # Inicializa command_parts
        if command_string: command_parts = command_string.strip().split();
        if command_parts: command_start = command_parts[0].lower()
        if command_start in forbidden_commands: return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro: Comando '{command_start}' bloqueado."
        try:
            result = subprocess.run(command_string, shell=True, capture_output=True, text=True, check=False,
                                    encoding='cp850', errors='ignore')
            output = f"Return Code: {result.returncode}\nSTDOUT:\n{result.stdout.strip() or '(None)'}\nSTDERR:\n{result.stderr.strip() or '(None)'}"
            print(f" LCHAIN TOOL: Concluído {self.name}. Código: {result.returncode}");
            if result.returncode != 0: print(f" LCHAIN TOOL: STDERR: {result.stderr.strip() or '(None)'}")
            return output
        except FileNotFoundError:
            return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro: Comando '{command_start}' não encontrado."
        except Exception as e:
            return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro Inesperado: {e}"


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
            now = datetime.datetime.utcnow();
            timeMin_dt = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc);
            timeMin = timeMin_dt.isoformat();
            timeMax_dt = timeMin_dt + datetime.timedelta(days=1);
            timeMax = timeMax_dt.isoformat()
            events_result = service.events().list(calendarId='primary', timeMin=timeMin, timeMax=timeMax, maxResults=15,
                                                  singleEvents=True, orderBy='startTime').execute()
            events = events_result.get('items', [])
            if not events: return "Nenhum evento hoje."
            output_lines = ["Eventos de hoje:"]
            for event in events:
                start_data = event['start'];
                is_all_day = 'date' in start_data and 'dateTime' not in start_data;
                start_str = start_data.get('dateTime', start_data.get('date'));
                hour_minute = "N/A"
                try:
                    if not is_all_day:
                        dt_obj_utc = datetime.datetime.fromisoformat(start_str.replace('Z',
                                                                                       '+00:00')); dt_obj_local = dt_obj_utc.astimezone(); hour_minute = dt_obj_local.strftime(
                            '%H:%M')
                    else:
                        hour_minute = "Dia Inteiro"
                except ValueError:
                    hour_minute = "Dia Inteiro" if is_all_day else start_str
                summary = event.get('summary', '(Sem Título)');
                output_lines.append(f"- {hour_minute}: {summary}")
            return "\n".join(output_lines)
        except HttpError as error:
            print(f" LCHAIN TOOL ERROR ({self.name}): {error}"); return f"Erro Calendar API: {error}"
        except Exception as e:
            print(
                f" LCHAIN TOOL ERROR ({self.name}): {e}"); traceback.print_exc(); return f"Erro inesperado Agenda: {e}"


# Ferramenta 3: Criar Evento Google Calendar
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
        print(f"[DEBUG CreateEvent] Analisando: '{query}'");
        start_dt, end_dt, summary = None, None, query
        try:  # Tenta usar dateutil se disponível
            import dateutil.parser;
            from dateutil.relativedelta import relativedelta
            print("[DEBUG CreateEvent] Usando dateutil.parser...")
            cleaned_query = query.lower().replace("criar evento:", "").replace("marcar ", "").strip()
            words = cleaned_query.replace("das ", "").replace(" às ", "-").replace(" as ", "-").split()
            dt_part = " ".join(words[-3:]) if len(words) >= 3 else " ".join(words)  # Heurística simples

            # Se dt_part contiver algo como "amanhã", "hoje", dateutil.parser pode precisar de contexto
            # ou uma lógica mais robusta para o sumário.
            # Tentativa de extrair sumário antes do dt_part se dt_part parece ser apenas data/hora.
            potential_summary = cleaned_query.removesuffix(dt_part).strip()
            if potential_summary:
                summary = potential_summary
            else:  # Fallback se o sumário não foi bem extraído
                summary = f"Evento: {query[:30]}"

            parsed_info = dateutil.parser.parse(dt_part, fuzzy=False, default=datetime.datetime.now())
            start_dt = parsed_info

            # Se o sumário não foi bem pego antes, tenta pegar o que sobrou
            if summary == f"Evento: {query[:30]}" or not potential_summary:
                summary_check = cleaned_query.replace(dt_part, "").strip()
                if summary_check: summary = summary_check

            match_range = re.search(r'(\d{1,2}:\d{2})-(\d{1,2}:\d{2})', dt_part, re.IGNORECASE) or \
                          re.search(r'(\d{1,2}h\d{0,2})-(\d{1,2}h\d{0,2})', dt_part,
                                    re.IGNORECASE)  # Adiciona suporte para "10h-11h"

            if match_range:
                start_time_str = match_range.group(1).replace('h', ':')
                end_time_str = match_range.group(2).replace('h', ':')
                if ':' not in start_time_str: start_time_str += ":00"  # ex: 10 -> 10:00
                if ':' not in end_time_str: end_time_str += ":00"  # ex: 11 -> 11:00

                start_dt_time = datetime.datetime.strptime(start_time_str, "%H:%M").time()
                end_dt_time = datetime.datetime.strptime(end_time_str, "%H:%M").time()

                start_dt = start_dt.replace(hour=start_dt_time.hour, minute=start_dt_time.minute, second=0,
                                            microsecond=0)
                end_dt = start_dt.replace(hour=end_dt_time.hour, minute=end_dt_time.minute, second=0, microsecond=0)

                if end_dt <= start_dt: end_dt += datetime.timedelta(
                    days=1)  # Assume dia seguinte se hora final for menor
                print(f"[DEBUG CreateEvent] Range encontrado: {match_range.group(1)}-{match_range.group(2)}")
            else:
                # Se não houver range explícito, mas a hora foi parseada, usa essa hora.
                # Se a hora não foi parseada (ex: "Reunião amanhã"), dateutil pode ter pego meia-noite.
                # Nesse caso, uma duração de 1h pode não ser o ideal.
                # Para este exemplo, mantemos a duração de 1h se não houver range.
                end_dt = start_dt + datetime.timedelta(hours=1)
                print(
                    "[DEBUG CreateEvent] Range não encontrado ou não parseado, assumindo 1h de duração a partir de start_dt.")

            print(f"[DEBUG CreateEvent] Análise (dateutil): start={start_dt}, end={end_dt}, summary={summary}")
        except ImportError:
            print("AVISO: dateutil não instalado (pip install python-dateutil). Análise de data/hora limitada.")
            # Fallback muito básico se dateutil não estiver disponível
            now = datetime.datetime.now()
            start_dt = now + datetime.timedelta(hours=1)  # Padrão: daqui a 1 hora
            end_dt = start_dt + datetime.timedelta(hours=1)  # Padrão: duração de 1 hora
            summary = query  # Usa a query inteira como sumário
            print(
                f"[DEBUG CreateEvent] Usando Fallback (sem dateutil): start={start_dt}, end={end_dt}, summary={summary}")
        except Exception as e_parse:
            print(f"[DEBUG CreateEvent] Falha na análise de data/hora com dateutil: {e_parse}");
            traceback.print_exc();
            return None, None, None

        if not start_dt or not end_dt or not summary.strip():
            print(
                f"[DEBUG CreateEvent] Análise resultou em valores nulos ou sumário vazio. start={start_dt}, end={end_dt}, summary='{summary}'")
            return None, None, None  # Retorna None se algo crucial faltar

        return start_dt, end_dt, summary.strip()

    def _run(self, query: str) -> str:
        print(f"\n LCHAIN TOOL: Executando {self.name} com query: '{query}'");
        creds = get_google_credentials();
        if not creds: return "Erro: Falha credenciais Google."
        required_scopes = ['https://www.googleapis.com/auth/calendar.events',
                           'https://www.googleapis.com/auth/calendar']
        if not any(s in creds.scopes for s in required_scopes): return f"Erro: Permissão negada (escrita Agenda)."

        start_dt, end_dt, summary = self._parse_datetime_range(query)
        if not start_dt or not end_dt or not summary:
            return f"Erro: Não consegui entender os detalhes do evento (título, data e/ou hora) a partir de '{query}'. Por favor, tente ser mais específico, por exemplo: 'Marcar Reunião de Projeto para amanhã das 14:00 às 15:30'."

        try:  # Formata para API
            # Tenta obter o timezone local de forma mais robusta
            try:
                local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
                if local_tz:
                    start_dt = start_dt.astimezone(local_tz) if start_dt.tzinfo is None else start_dt.astimezone(
                        local_tz)
                    end_dt = end_dt.astimezone(local_tz) if end_dt.tzinfo is None else end_dt.astimezone(local_tz)
                    time_zone_str = str(local_tz)
                    start_rfc = start_dt.isoformat()
                    end_rfc = end_dt.isoformat()
                else:  # Fallback se tzinfo for None
                    raise ValueError("Não foi possível determinar o timezone local.")
            except Exception as tz_err:
                print(
                    f"Aviso: Não foi possível determinar o timezone local exato ({tz_err}). Usando UTC como fallback.")
                # Se start_dt for naive, assume que é UTC para conversão (ou o padrão do sistema)
                if start_dt.tzinfo is None: start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
                if end_dt.tzinfo is None: end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
                time_zone_str = 'UTC'
                start_rfc = start_dt.isoformat()
                end_rfc = end_dt.isoformat()

            event_body = {
                'summary': summary,
                'start': {'dateTime': start_rfc, 'timeZone': time_zone_str},
                'end': {'dateTime': end_rfc, 'timeZone': time_zone_str},
            }
            print(f"   (Corpo do Evento para API: {event_body})")
        except Exception as e_format:
            traceback.print_exc()
            return f"Erro ao formatar data/hora para API: {e_format}"

        try:
            print(f"   (Criando evento: {summary} @ {start_rfc} [{time_zone_str}])");
            service = build('calendar', 'v3', credentials=creds)
            created_event = service.events().insert(calendarId='primary', body=event_body).execute()
            link = created_event.get('htmlLink', 'N/A');
            print(f"   (Evento criado! ID: {created_event.get('id')})")
            return f"Evento '{created_event.get('summary')}' criado. Link: {link}"
        except HttpError as error:
            print(
                f" LCHAIN TOOL ERROR ({self.name}): {error}"); return f"Erro Calendar API: {error.resp.status} - {error._get_reason()}"
        except Exception as e:
            print(
                f" LCHAIN TOOL ERROR ({self.name}): {e}"); traceback.print_exc(); return f"Erro inesperado ao criar evento na Agenda: {e}"


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
        print(f"\n LCHAIN TOOL: Executando {self.name}...");
        creds = get_google_credentials();
        if not creds: return "Erro: Falha credenciais Google."
        required_scopes = ['https://www.googleapis.com/auth/gmail.send', 'https://mail.google.com/']
        if not any(s in creds.scopes for s in required_scopes): return f"Erro: Permissão negada (envio Gmail)."
        to_addr, subject, body = None, "Sem Assunto", ""
        try:  # Extração básica
            to_match = re.search(r'Para:\s*([^\s<>]+@[^\s<>]+)', query, re.IGNORECASE) or re.search(
                r'Para:\s*.*?<([^\s<>]+@[^\s<>]+)>', query, re.IGNORECASE)
            if to_match: to_addr = to_match.group(1)
            subject_match = re.search(r'Assunto:\s*(.*?)(?=Corpo:|$)', query, re.IGNORECASE | re.DOTALL)
            if subject_match: subject = subject_match.group(1).strip() or "Sem Assunto"
            body_match = re.search(r'Corpo:\s*(.*)', query, re.IGNORECASE | re.DOTALL)
            if body_match: body = body_match.group(1).strip()
            if not to_addr or not body: raise ValueError(
                "Faltou 'Para:' ou 'Corpo:'. Verifique se a mensagem contém 'Para: email@exemplo.com Assunto: Seu Assunto Corpo: Sua mensagem.'")
        except Exception as e_parse:
            return f"Erro ao analisar os detalhes do email: {e_parse}. Certifique-se de usar o formato: 'Para: email@exemplo.com Assunto: Meu Assunto Corpo: A mensagem a ser enviada.'"
        try:
            print(f"   (Enviando email para {to_addr})");
            service = build('gmail', 'v1', credentials=creds)
            message = EmailMessage();
            message.set_content(body);
            message['To'] = to_addr;
            message['Subject'] = subject
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {'raw': encoded_message}
            send_message = service.users().messages().send(userId='me', body=create_message).execute()
            print(f"   (Email enviado! ID: {send_message.get('id')})");
            return f"Email enviado para {to_addr} com o assunto '{subject}'."
        except HttpError as error:
            print(
                f" LCHAIN TOOL ERROR ({self.name}): {error}"); return f"Erro Gmail API: {error.resp.status} - {error._get_reason()}"
        except Exception as e:
            print(
                f" LCHAIN TOOL ERROR ({self.name}): {e}"); traceback.print_exc(); return f"Erro inesperado ao enviar email pelo Gmail: {e}"


# Ferramenta 5: Pesquisar Vídeos no YouTube
class YouTubeSearchTool(BaseTool):
    name: str = "Youtube"  # Nome corrigido e mais descritivo
    description: str = (
        "Use esta ferramenta para pesquisar vídeos no YouTube. "
        "A entrada deve ser a string de busca (termos que você quer pesquisar). "
        "Retorna uma lista com os títulos e links dos 5 primeiros vídeos encontrados ou uma mensagem de erro."
    )

    def _run(self, query: str) -> str:
        print(f"\n LCHAIN TOOL: Executando {self.name} com query: '{query}'");
        creds = get_google_credentials();
        if not creds: return "Erro: Falha credenciais Google."
        required_scopes = ['https://www.googleapis.com/auth/youtube.readonly',
                           'https://www.googleapis.com/auth/youtube']
        if not any(s in creds.scopes for s in required_scopes): return f"Erro: Permissão negada (leitura YouTube)."
        if not query: return "Erro: Forneça um termo de busca para YouTube."
        try:
            service = build('youtube', 'v3', credentials=creds);
            print(f"   (Buscando YouTube: '{query}')")
            search_response = service.search().list(q=query, part='snippet', maxResults=5, type='video').execute()
            videos = search_response.get('items', [])
            if not videos: print("   (Nenhum vídeo encontrado)"); return f"Nenhum vídeo encontrado para: '{query}'"
            output_lines = [f"Resultados da pesquisa no YouTube por '{query}':"]
            for item in videos:
                title = item['snippet']['title'];
                video_id = item['id']['videoId'];
                link = f"https://www.youtube.com/watch?v={video_id}"
                output_lines.append(f"- Título: {title} (Link: {link})")
            print(f"   ({len(videos)} vídeos encontrados.)");
            return "\n".join(output_lines)
        except HttpError as error:
            print(
                f" LCHAIN TOOL ERROR ({self.name}): {error}"); return f"Erro YouTube API: {error.resp.status} - {error._get_reason()}"
        except Exception as e:
            print(
                f" LCHAIN TOOL ERROR ({self.name}): {e}"); traceback.print_exc(); return f"Erro inesperado ao pesquisar no YouTube: {e}"


# Ferramenta 6: Listar Arquivos Google Drive (Raiz)
class DriveListFilesTool(BaseTool):
    name: str = "google_drive_list_root_files"
    description: str = (
        "Use esta ferramenta para listar os nomes dos arquivos e pastas que estão na pasta raiz ('Meu Drive') do Google Drive do usuário. "
        "A entrada geralmente não é necessária (pode ignorar). "
        "Retorna uma lista de nomes de arquivos/pastas ou uma mensagem de erro."
    )

    def _run(self, query: str = "") -> str:
        print(f"\n LCHAIN TOOL: Executando {self.name}...");
        creds = get_google_credentials();
        if not creds: return "Erro: Falha credenciais Google."
        required_scopes = ['https://www.googleapis.com/auth/drive.metadata.readonly',
                           'https://www.googleapis.com/auth/drive.readonly',
                           'https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']
        if not any(s in creds.scopes for s in required_scopes): return f"Erro: Permissão negada (leitura Drive)."
        try:
            service = build('drive', 'v3', credentials=creds);
            print("   (Listando raiz do Drive...)")
            results = service.files().list(pageSize=25, fields="files(id, name, mimeType)", orderBy="folder, name",
                                           q="'root' in parents and trashed = false").execute()
            items = results.get('files', [])
            if not items: print("   (Nenhum item na raiz.)"); return "Nenhum arquivo ou pasta na raiz do Drive."
            output_lines = ["Itens na Raiz do Google Drive:"]
            for item in items:
                name = item.get('name', 'N/A');
                mime_type = item.get('mimeType', '')
                prefix = "[Pasta]" if mime_type == 'application/vnd.google-apps.folder' else "[Arquivo]"
                output_lines.append(f"- {prefix} {name}")
            print(f"   ({len(items)} itens encontrados.)");
            return "\n".join(output_lines)
        except HttpError as error:
            print(
                f" LCHAIN TOOL ERROR ({self.name}): {error}"); return f"Erro Drive API: {error.resp.status} - {error._get_reason()}"
        except Exception as e:
            print(
                f" LCHAIN TOOL ERROR ({self.name}): {e}"); traceback.print_exc(); return f"Erro inesperado ao listar arquivos do Drive: {e}"


# --- Fim das Novas Ferramentas ---

# --- Inicialização das Ferramentas para o Agente ---
tools = [
    WindowsCommandExecutorTool(),
    ListCalendarEventsTool(),
    CreateCalendarEventTool(),
    SendGmailTool(),
    YouTubeSearchTool(),  # Nome da classe atualizado para YouTubeSearchTool
    DriveListFilesTool(),
]
print(f"\nTotal de {len(tools)} ferramentas carregadas.")
print("Ferramentas disponíveis para o agente:", [tool.name for tool in tools])
print("-" * 50)

# --- Configuração do Agente (ReAct com Prompt Customizado PT-BR) ---
try:
    react_prompt_original = hub.pull("hwchase17/react");
    parts = react_prompt_original.template.split("Begin!")
    if len(parts) == 2:
        template_customizado = parts[
                                   0].strip() + "\n\nIMPORTANT FINAL INSTRUCTION: Your final answer (Final Answer:) MUST always be in Brazilian Portuguese (Português do Brasil)." + "\n\nBegin!" + \
                               parts[1]
    else:
        template_customizado = react_prompt_original.template + "\n\nIMPORTANT FINAL INSTRUCTION: Your final answer (Final Answer:) MUST always be in Brazilian Portuguese (Português do Brasil)."
    react_prompt_ptbr = PromptTemplate.from_template(template_customizado);
    react_prompt_ptbr.input_variables = react_prompt_original.input_variables
    agent = create_react_agent(llm=llm, tools=tools, prompt=react_prompt_ptbr)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True,
                                   max_iterations=15)
    print("\nAgente LangChain (ReAct PT-BR com Ferramentas) e Executor configurados.")
    print("Ferramentas carregadas para o agente:", [tool.name for tool in agent_executor.tools]);
    print("-" * 30)
except Exception as e:
    print(f"Erro crítico Agente LangChain: {e}"); traceback.print_exc(); sys.exit(1)


# --- Função para Capturar e Reconhecer Voz (Com Correção de SyntaxError) ---
def ouvir_comando(timeout_microfone=5, frase_limite_segundos=10):
    r = sr.Recognizer();
    audio = None
    try:
        with sr.Microphone() as source:
            print("\nAjustando ruído ambiente...")
            try:
                r.adjust_for_ambient_noise(source, duration=1)
            except Exception as e_noise:
                print(f"Aviso: Falha ajuste ruído amb.: {e_noise}")
            print(f"Fale seu comando/pergunta ({frase_limite_segundos}s max):")
            try:
                audio = r.listen(source, timeout=timeout_microfone, phrase_time_limit=frase_limite_segundos)
            except sr.WaitTimeoutError:
                print("Tempo de escuta esgotado."); return None  # Adicionado print
            except Exception as e_listen:
                print(f"Erro escuta: {e_listen}"); return None
    except sr.RequestError as e_mic_req:
        print(f"Erro serviço de reconhecimento (Microfone indisponível?): {e_mic_req}"); return None
    except Exception as e_mic:
        print(f"Erro Microfone: {e_mic}"); traceback.print_exc(); return None  # Adicionado traceback
    if not audio: return None
    print("Reconhecendo...");
    texto_comando = None
    try:
        texto_comando = r.recognize_google(audio, language='pt-BR'); print(f"Você disse: '{texto_comando}'")
    except sr.UnknownValueError:
        print("Não entendi o que você disse.")  # Mensagem mais clara
    except sr.RequestError as e:
        print(f"Erro Serviço Reconhecimento Google Speech: {e}")
    except Exception as e:
        print(f"Erro Desconhecido no Reconhecimento: {e}")
    return texto_comando


# --- Função para Falar (TTS com Google Cloud) --- MODIFICADO
def falar(texto):
    global playsound_installed, google_tts_ready, TTS_VOICE_GOOGLE  # Adicionado TTS_VOICE_GOOGLE
    if not google_tts_ready or not texto:
        if texto:
            print(f"\n(Simulando saída falada - Google TTS não pronto): {texto}")
        else:
            print("[TTS] Nada para falar.")
        if not google_tts_ready and texto: print(
            "AVISO: Google Cloud TTS não está pronto. Verifique a configuração e logs.")
        return

    print(f"\n🔊 Falando (Google Cloud TTS - Voz: {TTS_VOICE_GOOGLE}): {texto}")
    temp_filename = None
    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=texto)
        voice = texttospeech.VoiceSelectionParams(
            language_code="pt-BR",  # Idioma
            name=TTS_VOICE_GOOGLE  # Nome da voz (configurável no início do script)
            # Ex: "pt-BR-Wavenet-A", "pt-BR-Standard-B", etc.
            # Consulte https://cloud.google.com/text-to-speech/docs/voices para mais opções
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            fp.write(response.audio_content)
            temp_filename = fp.name

        if temp_filename:
            if playsound_installed:
                playsound.playsound(temp_filename)
            else:
                print("AVISO: 'playsound' não instalado. Tentando abrir com o player padrão.")
                try:
                    if sys.platform == "win32":
                        os.startfile(temp_filename)
                    elif sys.platform == "darwin":
                        subprocess.call(["open", temp_filename])  # macOS
                    else:
                        subprocess.call(["xdg-open", temp_filename])  # Linux
                except Exception as e_open:
                    print(f"Falha ao abrir áudio com player padrão: {e_open}")
    except Exception as e:
        print(f"Erro Google Cloud TTS / playsound: {e}")
        traceback.print_exc()
    finally:
        if temp_filename and os.path.exists(temp_filename):
            import time;
            time.sleep(0.5);  # Pequena pausa para garantir que o arquivo não está em uso
            try:
                os.remove(temp_filename)
            except PermissionError:
                print(f"Aviso: Não foi possível remover o arquivo temporário {temp_filename}. Pode estar em uso.")
            except Exception as e_del:
                print(f"Aviso: Erro ao remover arquivo temporário {temp_filename}: {e_del}")


# --- Loop Principal Interativo ---
print(f"\nLangChain Windows Voice Commander Agent (Controle Total Ativado - RISCO ALTO)")
print("================================================================================")
print("!!! AVISO DE RISCO EXTREMO - CONTROLE TOTAL ATIVADO !!!")
print("================================================================================")
# MODIFICADO: Atualizada a mensagem sobre o TTS
print(f"Usando LLM: {MODEL_NAME} | TTS: Google Cloud TTS (Voz: {TTS_VOICE_GOOGLE})")
print("Verifique APIs, Escopos Amplos, Chaves e credentials.json!")
if not google_auth_ready: print(
    "AVISO: Acesso a serviços Google pode estar desabilitado devido à falha na autenticação OAuth.")
if not google_tts_ready: print("AVISO: Google Cloud TTS não está pronto. A saída de voz pode não funcionar.")
print("Fale 'sair' para terminar.")

while True:
    task_text = ouvir_comando()
    if task_text:
        if task_text.lower().strip() == 'sair':
            falar("Encerrando as operações. Até logo!")
            break

        google_service_keywords = ["agenda", "evento", "calendário", "gmail", "email", "e-mail", "drive", "arquivo",
                                   "youtube", "vídeo"]
        requires_google_services = any(keyword in task_text.lower() for keyword in google_service_keywords)

        if requires_google_services and not google_auth_ready:
            error_msg = "Desculpe, não posso realizar essa tarefa porque a autenticação com os serviços Google falhou. Verifique as credenciais e as permissões."
            print(f"ERRO: {error_msg}")
            falar(error_msg)
            continue
        try:
            print(f"\n>>> Enviando tarefa ( '{task_text}' ) para o agente...")
            # Adicionando o nome do usuário ao input, se disponível
            user_name = "Junior"  # Você pode tornar isso dinâmico se desejar
            input_for_agent = f"Meu nome é {user_name}. Minha solicitação é: {task_text}"
            if "meu nome é" in task_text.lower():  # Evitar duplicar se já informado
                input_for_agent = task_text

            response = agent_executor.invoke({"input": input_for_agent})
            agent_output_text = response.get("output", "Não obtive uma resposta final do agente.")

            print("\n--- Resposta Final do Agente ---");
            print(agent_output_text);
            print("------------------------------")
            falar(agent_output_text)
        except Exception as e:
            error_message = f"Ocorreu um erro crítico durante a execução do agente: {e}"
            print(f"\n!!! {error_message} !!!");
            traceback.print_exc()
            falar(
                f"Desculpe {user_name if 'user_name' in locals() else ''}, ocorreu um erro interno ao processar seu pedido. Por favor, tente novamente.")
    else:
        # Opcional: emitir um som ou mensagem se nenhum comando foi ouvido após o timeout
        # falar("Não detectei nenhum comando.") # Descomente se quiser feedback sonoro para silêncio
        pass  # Mantém o loop rodando silenciosamente se nada for dito

# --- Fim do Script ---
print("\nScript LangChain com Voz terminado.")
# -*- coding: utf-8 -*-
# Nome do Arquivo: satan.py
# Data da versão: 2025-05-17 - CONTROLE TOTAL GOOGLE + TTS GOOGLE CLOUD + MODELO ATUALIZADO
# Modificações por Junior (via Gemini): 2025-05-20
#   - Adicionada funcionalidade Win Hoff MP3 e Pomodoro
#   - Adicionada funcionalidade de acesso aos Contatos Google (People API)
#   - Corrigido SyntaxError em CheckGmailTool e outros refinamentos
#   - Revertida voz TTS para original do usuário
#   - Adicionada exibição do timer Pomodoro no terminal
#   - Adicionada ferramenta de Pesquisa Web Direta (simulada)
#   - Adicionada ferramenta de Notícias e Informação (NewsAPI)
# MODIFICAÇÕES ADICIONAIS (2025-05-23 via Gemini):
#   - Lista de SCOPES expandida para permissões mais abrangentes.
#   - CheckGmailTool atualizada para verificação de escopo mais robusta (any()).
# MODIFICAÇÕES ADICIONAIS (2025-05-23 - Noite via Gemini):
#   - CheckGmailTool agora lista emails recentes (lidos ou não lidos) do INBOX.
#   - Adicionada nova ferramenta SearchEmailsTool para buscar e listar todos os emails.

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
import threading
import time
import calendar
import json  # Para processar JSON da NewsAPI

try:
    import dateutil.parser
    import dateutil.tz
    from dateutil.relativedelta import relativedelta

    dateutil_available = True
except ImportError:
    dateutil_available = False
    print(
        "AVISO: Biblioteca 'python-dateutil' não encontrada. Instale com 'pip install python-dateutil'. A análise de datas complexas para o calendário será limitada.")

try:
    import requests  # Para a ferramenta de Notícias

    requests_available = True
except ImportError:
    requests_available = False
    print(
        "AVISO: Biblioteca 'requests' não encontrada. Instale com 'pip install requests'. A ferramenta de notícias não funcionará.")

# --- Imports do LangChain ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import BaseTool
from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
# from langchain.prompts import PromptTemplate # Removido se não usado diretamente

# --- Imports para Reconhecimento de Voz ---
import speech_recognition as sr

# --- Imports para Síntese de Voz (Google Cloud TTS) ---
from google.cloud import texttospeech

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
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
USER_NAME = "Junior"

# === CONFIGURAÇÕES ===
MODEL_NAME = "gemini-1.5-pro-latest"
TEMPERATURE = 0.3
TTS_VOICE_GOOGLE = "pt-BR-Chirp3-HD-Laomedeia"
CREDENTIALS_FILENAME = 'credentials.json'
TOKEN_FILENAME = 'token.json'

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://mail.google.com/',  # Permissão total para Gmail (leitura, escrita, etc.)
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid',
    'https://www.googleapis.com/auth/contacts',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/photoslibrary',
    'https://www.googleapis.com/auth/photoslibrary.sharing',
]
WINHOFF_MP3_FILE = "winhoff.mp3"

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
    texttospeech.TextToSpeechClient()
    print("Cliente Google Cloud TTS parece estar pronto (bibliotecas carregadas).")
    google_tts_ready = True
except Exception as e:
    print(f"Erro ao verificar cliente Google Cloud TTS: {e}\nAVISO: Google Cloud TTS pode não funcionar.")
    print("Verifique se a API 'Cloud Text-to-Speech' está habilitada no GCP e se a autenticação está configurada.")


# --- Função para Autenticação Google OAuth 2.0 ---
def get_google_credentials():
    creds = None
    if os.path.exists(TOKEN_FILENAME):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILENAME, SCOPES)
            if creds:
                token_scopes_set = set(creds.scopes if creds.scopes is not None else [])
                required_scopes_set = set(SCOPES)
                if not required_scopes_set.issubset(token_scopes_set):
                    print(
                        f"AVISO: Escopos no token ({token_scopes_set}) não cobrem todos os escopos requeridos ({required_scopes_set}). Forçando re-autenticação.")
                    creds = None
                    if os.path.exists(TOKEN_FILENAME):
                        try:
                            os.remove(TOKEN_FILENAME)
                            print(
                                f"Arquivo '{TOKEN_FILENAME}' removido para re-autenticação devido à mudança de escopos.")
                        except Exception as e_rem:
                            print(f"AVISO: Falha ao remover token.json para re-auth: {e_rem}")
        except ValueError as e:
            print(
                f"Erro de valor ao carregar '{TOKEN_FILENAME}' (possivelmente escopos mudaram ou token corrompido): {e}. Tentando re-autenticar.")
            creds = None
            if os.path.exists(TOKEN_FILENAME):
                try:
                    os.remove(TOKEN_FILENAME)
                except Exception as e_rem:
                    print(f"AVISO: Falha ao remover token.json para re-auth: {e_rem}")
        except Exception as e:
            print(f"Erro geral ao carregar '{TOKEN_FILENAME}': {e}. Tentando re-autenticar.")
            creds = None
            if os.path.exists(TOKEN_FILENAME):
                try:
                    os.remove(TOKEN_FILENAME)
                except Exception as e_rem:
                    print(f"AVISO: Falha ao remover token.json para re-auth: {e_rem}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("Credenciais Google atualizadas.")
                with open(TOKEN_FILENAME, 'w') as token_file:
                    token_file.write(creds.to_json())
            except Exception as e_refresh:
                print(f"Erro ao atualizar credenciais Google: {e_refresh}. Re-autorização necessária.")
                if os.path.exists(TOKEN_FILENAME):
                    try:
                        os.remove(TOKEN_FILENAME)
                    except Exception as e_rem:
                        print(f"AVISO: Falha ao remover token.json para re-auth: {e_rem}")
                creds = None

        if not creds:
            if not os.path.exists(CREDENTIALS_FILENAME):
                print(f"Erro Crítico: Arquivo de credenciais '{CREDENTIALS_FILENAME}' não encontrado!")
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILENAME, SCOPES)
                print(">>> ATENÇÃO: SEU NAVEGADOR DEVE ABRIR PARA AUTORIZAÇÃO GOOGLE <<<")
                print("Por favor, conceda as permissões solicitadas.")
                creds = flow.run_local_server(port=0)
                print("Autorização Google concedida com sucesso!")
                with open(TOKEN_FILENAME, 'w') as token_file:
                    token_file.write(creds.to_json())
                    print(f"Novas credenciais salvas em '{TOKEN_FILENAME}'.")
            except Exception as e_flow:
                print(f"ERRO FATAL durante o fluxo de autorização do Google: {e_flow}");
                traceback.print_exc();
                creds = None
    return creds


# --- Executa Autenticação Google OAuth na Inicialização ---
print("\n--- Verificando Credenciais Google OAuth 2.0 ---")
google_creds = get_google_credentials()
google_auth_ready = bool(google_creds and google_creds.valid)
if not google_auth_ready:
    print("ERRO CRÍTICO PÓS-AUTH: Falha na autenticação Google OAuth. Serviços Google podem não funcionar.")
else:
    print("SUCESSO PÓS-AUTH: Credenciais Google OAuth OK.")
print("-" * 50)


# --- Definição das Ferramentas Customizadas ---
class WindowsCommandExecutorTool(BaseTool):
    name: str = "windows_command_executor"
    description: str = (
        "Executa um comando FORNECIDO COMO STRING única diretamente no Prompt de Comando do Windows. Use com cautela.")

    def _run(self, command_string: str) -> str:  # Implementação original mantida
        print(f"\n LCHAIN TOOL: Executando {self.name}: C:\\> {command_string}")
        if not isinstance(command_string,
                          str) or not command_string.strip(): return "Erro: Input inválido para comando."
        forbidden_commands = ["format", "shutdown", "del ", "rd ", "/s", "/q"]
        command_lower = command_string.lower()
        if any(fc in command_lower for fc in forbidden_commands):
            return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro: Comando contendo termo bloqueado ('{command_lower[:20]}...') foi bloqueado por segurança."
        try:
            result = subprocess.run(command_string, shell=True, capture_output=True, text=True, check=False,
                                    encoding='cp850', errors='replace')
            stdout = result.stdout.strip() or '(None)'
            stderr = result.stderr.strip() or '(None)'
            return f"Return Code: {result.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        except FileNotFoundError:
            return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro: Comando ou programa '{command_string.split()[0]}' não encontrado."
        except Exception as e:
            return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro Inesperado ao executar comando: {e}"


class GetCalendarEventsTool(BaseTool):
    name: str = "google_calendar_get_events_for_period"
    description: str = (
        "Busca e lista eventos do Google Calendar para um período (ex: 'hoje', 'amanhã', 'esta semana', 'próximo mês', 'junho 2025', '25/05/2025'). Padrão: hoje. Max 50 eventos.")

    # Implementação original mantida
    def _make_aware(self, dt_obj: datetime.datetime, target_tz) -> datetime.datetime:
        return dt_obj.replace(tzinfo=target_tz) if dt_obj.tzinfo is None else dt_obj.astimezone(target_tz)

    def _get_start_of_day(self, dt_obj: datetime.datetime) -> datetime.datetime:
        return dt_obj.replace(hour=0, minute=0, second=0, microsecond=0)

    def _get_end_of_day(self, dt_obj: datetime.datetime) -> datetime.datetime:
        return dt_obj.replace(hour=23, minute=59, second=59, microsecond=999999)

    def _parse_query_to_daterange(self, query_str: str) -> tuple[str | None, str | None, str]:
        if not dateutil_available: now_utc = datetime.datetime.utcnow(); return (
            self._get_start_of_day(now_utc).isoformat() + 'Z', self._get_end_of_day(now_utc).isoformat() + 'Z',
            "hoje (dateutil indisponível)")
        try:
            local_tz = dateutil.tz.tzlocal()
        except:
            local_tz = datetime.timezone.utc; print(
                "Aviso: Não foi possível determinar o fuso horário local preciso, usando UTC.")
        now_local = datetime.datetime.now(local_tz);
        query_lower = query_str.lower().strip()
        time_min_local, time_max_local = None, None;
        period_desc = query_str or "hoje"
        pt_month_map = {"janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
                        "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
        if not query_lower or "hoje" in query_lower or (
                "eventos" in query_lower and not any(kw in query_lower for kw in ["amanhã", "semana", "mês", "ano"])):
            period_desc = "hoje";
            time_min_local, time_max_local = self._get_start_of_day(now_local), self._get_end_of_day(now_local)
        elif "amanhã" in query_lower:
            tomorrow_local = now_local + datetime.timedelta(days=1);
            period_desc = "amanhã";
            time_min_local, time_max_local = self._get_start_of_day(tomorrow_local), self._get_end_of_day(
                tomorrow_local)
        elif "esta semana" in query_lower or "semana atual" in query_lower:
            period_desc = "esta semana";
            start_of_week = now_local - datetime.timedelta(days=now_local.weekday());
            end_of_week = start_of_week + datetime.timedelta(days=6);
            time_min_local, time_max_local = self._get_start_of_day(start_of_week), self._get_end_of_day(end_of_week)
        elif "próxima semana" in query_lower:
            period_desc = "próxima semana";
            start_of_current_week = now_local - datetime.timedelta(days=now_local.weekday());
            start_of_next_week = start_of_current_week + datetime.timedelta(weeks=1);
            end_of_next_week = start_of_next_week + datetime.timedelta(days=6);
            time_min_local, time_max_local = self._get_start_of_day(start_of_next_week), self._get_end_of_day(
                end_of_next_week)
        elif "este mês" in query_lower or "mês atual" in query_lower:
            period_desc = "este mês";
            start_of_month = now_local.replace(day=1);
            _, num_days = calendar.monthrange(now_local.year, now_local.month);
            end_of_month = now_local.replace(day=num_days);
            time_min_local, time_max_local = self._get_start_of_day(start_of_month), self._get_end_of_day(end_of_month)
        elif "próximo mês" in query_lower:
            period_desc = "próximo mês";
            first_day_current_month = now_local.replace(day=1);
            first_day_next_month = first_day_current_month + relativedelta(months=1);
            _, num_days_next_month = calendar.monthrange(first_day_next_month.year, first_day_next_month.month);
            end_of_next_month = first_day_next_month.replace(day=num_days_next_month);
            time_min_local, time_max_local = self._get_start_of_day(first_day_next_month), self._get_end_of_day(
                end_of_next_month)
        elif "este ano" in query_lower:
            period_desc = f"o ano de {now_local.year}";
            time_min_local, time_max_local = self._get_start_of_day(
                now_local.replace(month=1, day=1)), self._get_end_of_day(now_local.replace(month=12, day=31))
        else:
            year_match = re.search(r'\b(\d{4})\b', query_lower);
            parsed_as_specific_period = False
            for month_name, month_num in pt_month_map.items():
                if month_name in query_lower:
                    year_to_use = now_local.year;
                    if year_match: year_to_use = int(year_match.group(1))
                    start_of_target_month = datetime.datetime(year_to_use, month_num, 1, tzinfo=local_tz);
                    _, num_days_in_month = calendar.monthrange(year_to_use, month_num);
                    end_of_target_month = start_of_target_month.replace(day=num_days_in_month);
                    time_min_local, time_max_local = self._get_start_of_day(
                        start_of_target_month), self._get_end_of_day(end_of_target_month);
                    period_desc = f"{month_name.capitalize()} de {year_to_use}";
                    parsed_as_specific_period = True;
                    break
            if not parsed_as_specific_period and year_match and len(
                    query_lower.split()) == 1 and query_lower == year_match.group(1):
                year_val = int(year_match.group(1));
                period_desc = f"o ano de {year_val}";
                time_min_local, time_max_local = self._get_start_of_day(
                    datetime.datetime(year_val, 1, 1, tzinfo=local_tz)), self._get_end_of_day(
                    datetime.datetime(year_val, 12, 31, tzinfo=local_tz));
                parsed_as_specific_period = True
            if not parsed_as_specific_period:
                try:
                    default_date_for_parser = now_local.replace(hour=0, minute=0, second=0, microsecond=0);
                    parsed_dt = dateutil.parser.parse(query_str, default=default_date_for_parser, dayfirst=True);
                    parsed_dt_local = self._make_aware(parsed_dt, local_tz);
                    time_min_local, time_max_local = self._get_start_of_day(parsed_dt_local), self._get_end_of_day(
                        parsed_dt_local);
                    period_desc = f"o dia {time_min_local.strftime('%d/%m/%Y')}"
                except (dateutil.parser.ParserError, ValueError) as e:
                    print(f"Não foi possível interpretar '{query_str}' como período/data. Usando 'hoje'. Erro: {e}");
                    period_desc = "hoje (falha no parse)";
                    time_min_local, time_max_local = self._get_start_of_day(now_local), self._get_end_of_day(now_local)
        if time_min_local and time_max_local: return time_min_local.isoformat(), time_max_local.isoformat(), period_desc
        print(f"Falha crítica ao determinar período para '{query_str}'. Usando 'hoje'.");
        time_min_local, time_max_local = self._get_start_of_day(now_local), self._get_end_of_day(now_local);
        return time_min_local.isoformat(), time_max_local.isoformat(), "hoje (padrão crítico)"

    def _run(self, query: str = "") -> str:
        creds = get_google_credentials();
        if not creds: return "Erro: Falha nas credenciais Google para Calendário."
        time_min_str, time_max_str, period_description = self._parse_query_to_daterange(query)
        if not time_min_str or not time_max_str: return f"Não foi possível determinar o período para a consulta: '{query}'."
        print(f"   Buscando eventos para o período: {period_description} (De: {time_min_str} Até: {time_max_str})")
        try:
            service = build('calendar', 'v3', credentials=creds)
            events_result = service.events().list(calendarId='primary', timeMin=time_min_str, timeMax=time_max_str,
                                                  maxResults=50, singleEvents=True, orderBy='startTime').execute();
            events = events_result.get('items', [])
            if not events: return f"Nenhum evento encontrado para {period_description}."
            output_lines = [f"Eventos para {period_description}:"]
            for event in events:
                start_data = event['start'];
                is_all_day = 'date' in start_data and 'dateTime' not in start_data
                start_str = start_data.get('dateTime', start_data.get('date'));
                summary = event.get('summary', '(Sem Título)')
                try:
                    if not is_all_day and dateutil_available:
                        dt_obj_aware = dateutil.parser.isoparse(start_str);
                        local_tz_for_display = dateutil.tz.tzlocal();
                        dt_obj_local = dt_obj_aware.astimezone(local_tz_for_display);
                        is_multi_day_period = (dateutil.parser.isoparse(time_max_str) - dateutil.parser.isoparse(
                            time_min_str)).days > 0
                        hour_minute = dt_obj_local.strftime(
                            '%d/%m %H:%M') if is_multi_day_period else dt_obj_local.strftime('%H:%M')
                    elif is_all_day and dateutil_available:
                        dt_obj_date = datetime.datetime.strptime(start_str, '%Y-%m-%d').date();
                        hour_minute = f"{dt_obj_date.strftime('%d/%m')} (Dia Inteiro)"
                    else:
                        hour_minute = start_str
                except Exception as e_date:
                    print(
                        f"Erro ao formatar data do evento '{summary}': {e_date}"); hour_minute = "Horário Indisponível" if not is_all_day else "Dia Inteiro"
                output_lines.append(f"- {hour_minute}: {summary}")
            if len(events) >= 50 and events_result.get('nextPageToken'): output_lines.append(
                "\nAviso: Muitos eventos encontrados, a lista pode estar truncada em 50 resultados.")
            return "\n".join(output_lines)
        except HttpError as error:
            return f"Erro ao acessar o Google Calendar (HttpError {error.resp.status}): {error._get_reason()}"
        except Exception as e:
            traceback.print_exc(); return f"Erro inesperado ao buscar eventos do calendário: {e}"


class CreateCalendarEventTool(BaseTool):
    name: str = "google_calendar_create_event";
    description: str = (
        "Use para criar um novo evento no calendário. Ex: 'marcar reunião às 14h amanhã sobre projeto X'")

    # Implementação original mantida
    def _parse_datetime_range(self, query: str):
        if not dateutil_available: return None, None, query
        try:
            now_local_default = datetime.datetime.now(dateutil.tz.tzlocal())
            parsed_info = dateutil.parser.parse(query, fuzzy_with_tokens=True, default=now_local_default, dayfirst=True)
            start_dt = parsed_info[0]
            summary_tokens = [t for t in parsed_info[1] if
                              t.strip() and t.lower() not in ["às", "as", "de", "do", "da"]]
            summary = " ".join(summary_tokens).strip() or f"Evento: {query[:30]}"
            end_dt = start_dt + datetime.timedelta(hours=1)
            range_match = re.search(r'(das|de)\s*(\d{1,2}(:\d{2})?)\s*(às|as|a)\s*(\d{1,2}(:\d{2})?)', query,
                                    re.IGNORECASE)
            if range_match:
                start_time_str = range_match.group(2).replace('h', ':');
                end_time_str = range_match.group(5).replace('h', ':')
                if ':' not in start_time_str: start_time_str += ":00"
                if ':' not in end_time_str: end_time_str += ":00"
                start_time_obj = datetime.datetime.strptime(start_time_str, "%H:%M").time();
                end_time_obj = datetime.datetime.strptime(end_time_str, "%H:%M").time()
                start_dt = start_dt.replace(hour=start_time_obj.hour, minute=start_time_obj.minute, second=0,
                                            microsecond=0)
                end_dt = start_dt.replace(hour=end_time_obj.hour, minute=end_time_obj.minute, second=0, microsecond=0)
                if end_dt <= start_dt: end_dt += datetime.timedelta(days=1)
            return start_dt, end_dt, summary
        except Exception as e_parse:
            print(
                f"DEBUG CreateCalendarEventTool _parse_datetime_range Error: {e_parse} para query '{query}'"); return None, None, query

    def _make_aware(self, dt_obj: datetime.datetime, target_tz):
        return dt_obj.replace(tzinfo=target_tz) if dt_obj.tzinfo is None else dt_obj.astimezone(target_tz)

    def _run(self, query: str) -> str:
        creds = get_google_credentials();
        if not creds: return "Erro: Falha nas credenciais Google para Calendário."
        start_dt, end_dt, summary = self._parse_datetime_range(query)
        if not start_dt or not end_dt or not summary: return f"Erro: Não foi possível entender os detalhes do evento a partir de '{query}'. Por favor, seja mais específico com data, hora e descrição."
        try:
            local_tz = dateutil.tz.tzlocal() if dateutil_available else datetime.timezone.utc
            start_dt_aware = self._make_aware(start_dt, local_tz);
            end_dt_aware = self._make_aware(end_dt, local_tz)
            time_zone_str = str(local_tz)
            event_body = {'summary': summary,
                          'start': {'dateTime': start_dt_aware.isoformat(), 'timeZone': time_zone_str},
                          'end': {'dateTime': end_dt_aware.isoformat(), 'timeZone': time_zone_str}}
            service = build('calendar', 'v3', credentials=creds);
            created_event = service.events().insert(calendarId='primary', body=event_body).execute()
            return f"Evento '{created_event.get('summary')}' criado com sucesso. Link: {created_event.get('htmlLink', 'Link não disponível')}"
        except HttpError as error:
            return f"Erro ao criar evento no Google Calendar (HttpError {error.resp.status}): {error._get_reason()}"
        except Exception as e:
            traceback.print_exc(); return f"Erro inesperado ao criar evento: {e}"


class SendGmailTool(BaseTool):
    name: str = "send_gmail_message";
    description: str = (
        "Use para ENVIAR um email. Input: 'Para: email@dest.com Assunto: Meu Assunto Corpo: Conteúdo do email'")

    def _run(self, query: str) -> str:  # Implementação original mantida
        creds = get_google_credentials();
        if not creds: return "Erro: Falha nas credenciais Google para Gmail."
        to_addr, subject, body = None, "Sem Assunto", ""
        try:
            to_match = re.search(r'para:\s*([\w\.-]+@[\w\.-]+)', query, re.IGNORECASE);
            if to_match: to_addr = to_match.group(1).strip()
            subject_match = re.search(r'assunto:\s*(.*?)(?=corpo:|$)', query, re.IGNORECASE | re.DOTALL);
            if subject_match: subject = subject_match.group(1).strip() or "Sem Assunto"
            body_match = re.search(r'corpo:\s*(.*)', query, re.IGNORECASE | re.DOTALL);
            if body_match: body = body_match.group(1).strip()
            if not to_addr: return "Erro: Endereço 'Para:' não especificado ou inválido. Use o formato 'Para: email@exemplo.com'."
            if not body: return "Erro: 'Corpo:' do email não especificado."
        except Exception as e_parse:
            return f"Erro ao analisar detalhes do email: {e_parse}."
        try:
            service = build('gmail', 'v1', credentials=creds);
            message = EmailMessage();
            message.set_content(body);
            message['To'] = to_addr;
            message['Subject'] = subject;
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            service.users().messages().send(userId='me', body={'raw': encoded_message}).execute()
            return f"Email enviado para {to_addr} com assunto '{subject}'."
        except HttpError as error:
            return f"Erro ao enviar email via Gmail API (HttpError {error.resp.status}): {error._get_reason()}"
        except Exception as e:
            traceback.print_exc(); return f"Erro inesperado ao enviar email: {e}"


class YouTubeSearchTool(BaseTool):
    name: str = "Youtube";
    description: str = ("Use para pesquisar vídeos no YouTube. Forneça o termo de busca.")

    def _run(self, query: str) -> str:  # Implementação original mantida
        creds = get_google_credentials();
        if not query: return "Erro: Forneça um termo de busca para o YouTube."
        try:
            youtube_service_args = {'developerKey': GOOGLE_API_KEY} if not creds else {'credentials': creds}
            service = build('youtube', 'v3', **youtube_service_args)
            search_response = service.search().list(q=query, part='id,snippet', maxResults=3, type='video').execute();
            videos = search_response.get('items', [])
            if not videos: return f"Nenhum vídeo encontrado no YouTube para: '{query}'"
            return "Resultados do YouTube:\n" + "\n".join(
                [f"- {item['snippet']['title']} (https://www.youtube.com/watch?v={item['id']['videoId']})" for item in
                 videos])
        except HttpError as error:
            return f"Erro na API do YouTube (HttpError {error.resp.status}): {error._get_reason()}"
        except Exception as e:
            traceback.print_exc(); return f"Erro inesperado na busca do YouTube: {e}"


class DriveListFilesTool(BaseTool):
    name: str = "google_drive_list_root_files";
    description: str = ("Use para listar os primeiros 15 arquivos/pastas na raiz ('Meu Drive') do Google Drive.")

    def _run(self, query: str = "") -> str:  # Implementação original mantida
        creds = get_google_credentials();
        if not creds: return "Erro: Falha nas credenciais Google para Drive."
        try:
            service = build('drive', 'v3', credentials=creds)
            results = service.files().list(pageSize=15, fields="files(id, name, mimeType)", orderBy="folder, name",
                                           q="'root' in parents and trashed=false").execute();
            items = results.get('files', [])
            if not items: return "Nenhum item encontrado na raiz do Google Drive."
            output_list = ["Itens na Raiz do Google Drive:"]
            for item in items:
                prefix = "[Pasta]" if item.get('mimeType') == 'application/vnd.google-apps.folder' else "[Arquivo]"
                output_list.append(f"- {prefix} {item.get('name', 'Nome não disponível')}")
            return "\n".join(output_list)
        except HttpError as error:
            return f"Erro na API do Google Drive (HttpError {error.resp.status}): {error._get_reason()}"
        except Exception as e:
            traceback.print_exc(); return f"Erro inesperado ao listar arquivos do Drive: {e}"


# --- FERRAMENTA CheckGmailTool MODIFICADA ---
class CheckGmailTool(BaseTool):
    name: str = "google_gmail_check_emails"  # Nome ligeiramente alterado para refletir o novo comportamento
    description: str = (  # Descrição atualizada
        "Verifica e lista os e-mails mais recentes (até 5, assunto, remetente, data e ID) "
        "na caixa de entrada principal do Gmail, independentemente de estarem lidos ou não. "
        "Usado para notificações periódicas do e-mail mais recente ou para uma rápida olhada nos e-mails atuais."
    )
    last_notified_email_id: str | None = None

    def _run(self, query: str = "") -> str | dict:
        print(f"\n LCHAIN TOOL (BACKGROUND/AGENT): Executando {self.name}...")
        creds = get_google_credentials()
        if not creds:
            error_msg_creds = "Erro: Falha nas credenciais Google para verificar e-mails."
            print(f"   {self.name} - {error_msg_creds}")
            return error_msg_creds

        required_scopes_check = ['https://www.googleapis.com/auth/gmail.readonly', 'https://mail.google.com/']
        current_granted_scopes = creds.scopes if creds and hasattr(creds, 'scopes') and creds.scopes is not None else []
        if not any(s in current_granted_scopes for s in required_scopes_check):
            error_msg_scopes = (f"Erro: Permissões insuficientes para ler e-mails. "
                                f"Pelo menos um dos seguintes escopos é necessário mas não foi concedido: "
                                f"{', '.join(required_scopes_check)}. Escopos concedidos: {current_granted_scopes}")
            print(f"   {self.name} - {error_msg_scopes}")
            return error_msg_scopes

        try:
            service = build('gmail', 'v1', credentials=creds)
            # Modificado para não buscar apenas 'UNREAD', mas os mais recentes do INBOX
            results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=5).execute()
            messages_summary_list = results.get('messages', [])

            if not messages_summary_list:
                return "Nenhum e-mail encontrado na caixa de entrada."

            output_lines_details = []
            # Para a notificação falada, pegaremos informações do primeiro (mais recente) e-mail
            first_email_summary_for_speech = {}

            for i, msg_summary in enumerate(messages_summary_list):
                msg_id = msg_summary['id']
                msg = service.users().messages().get(userId='me', id=msg_id, format='metadata',
                                                     metadataHeaders=['From', 'Subject', 'Date']).execute()
                payload = msg.get('payload', {})
                headers = payload.get('headers', [])
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '(Sem Assunto)')
                sender_raw = next((h['value'] for h in headers if h['name'].lower() == 'from'),
                                  '(Remetente Desconhecido)')
                date_str = next((h['value'] for h in headers if h['name'].lower() == 'date'), None)

                clean_sender_match = re.search(r'([^<]+)<', sender_raw)
                clean_sender = clean_sender_match.group(1).strip() if clean_sender_match else sender_raw.split('@')[
                    0].strip()

                friendly_date = "(Data desc.)"
                if dateutil_available and date_str:
                    try:
                        dt_obj = dateutil.parser.parse(date_str)
                        if dt_obj:
                            if dt_obj.tzinfo: dt_obj = dt_obj.astimezone(dateutil.tz.tzlocal())
                            friendly_date = dt_obj.strftime('%d/%m %H:%M')
                    except Exception as e_date_parse:
                        print(
                            f"Aviso: Não foi possível parsear a data '{date_str}' do e-mail ID {msg_id}. Erro: {e_date_parse}")
                        friendly_date = date_str.split(' (')[0] if date_str else "(Data desc.)"
                elif date_str:
                    friendly_date = date_str.split(' (')[0]

                output_lines_details.append(
                    f"- De: {clean_sender}, Assunto: {subject} (Recebido: {friendly_date}, ID: {msg_id})")

                if i == 0:  # Captura detalhes do primeiro e-mail para possível notificação
                    first_email_summary_for_speech = {"sender": clean_sender, "subject": subject, "id": msg_id}

            details_string = "E-mails mais recentes na caixa de entrada:\n" + "\n".join(output_lines_details)

            # Lógica de notificação: só fala se o e-mail mais recente for diferente do último notificado
            spoken_output = None
            if first_email_summary_for_speech and self.last_notified_email_id != first_email_summary_for_speech.get(
                    "id"):
                self.last_notified_email_id = first_email_summary_for_speech.get("id")
                spoken_output = (
                    f"Novo e-mail na sua caixa de entrada de {first_email_summary_for_speech.get('sender', 'Desconhecido')} "
                    f"sobre {first_email_summary_for_speech.get('subject', 'sem assunto')}.")
            elif not first_email_summary_for_speech:  # Caso algo dê errado ao pegar o primeiro email
                spoken_output = "Verifiquei seus e-mails recentes."

            if spoken_output:  # Se houver algo para falar (novo e-mail)
                return {"spoken": spoken_output, "details": details_string}
            else:  # Se não há e-mail novo para notificar, ou se a ferramenta é chamada diretamente
                # Retorna os detalhes para o agente, que pode decidir o que fazer/falar.
                # Para chamada direta, o agente pode usar os "details".
                # Para background, se não há "spoken", nada é falado.
                return {"spoken": None, "details": details_string} if self.last_notified_email_id else details_string


        except HttpError as error:
            error_reason = f"Erro ao acessar Gmail (HttpError {error.resp.status}): {error._get_reason()}"
            print(f"   {self.name} - {error_reason}")
            return error_reason
        except Exception as e:
            error_reason = f"Erro inesperado ao verificar e-mails: {e}"
            print(f"   {self.name} - {error_reason}")
            traceback.print_exc()
            return error_reason


# --- NOVA FERRAMENTA: SearchEmailsTool ---
class SearchEmailsTool(BaseTool):
    name: str = "search_gmail_emails"
    description: str = (
        "Busca e-mails no Gmail com base em uma consulta fornecida pelo usuário "
        "(ex: 'de:exemplo@email.com', 'assunto:importante', 'relatório de ontem', 'is:starred'). "
        "Se nenhuma consulta específica for fornecida (ou se a consulta for genérica como 'meus emails' ou 'caixa de entrada'), "
        "lista os 10 e-mails mais recentes da caixa de entrada. "
        "Retorna remetente, assunto, data e um trecho (snippet) dos e-mails encontrados."
    )

    def _run(self, query: str = "") -> str:
        print(f"\n LCHAIN TOOL: Executando {self.name} com query: '{query}'")
        creds = get_google_credentials()
        if not creds:
            return "Erro: Falha nas credenciais Google para buscar e-mails."

        # Validação de escopos (opcional aqui, pois get_google_credentials já deveria ter validado,
        # mas uma checagem específica não faria mal se esta ferramenta tivesse requisitos únicos)
        # Para esta ferramenta, 'https://mail.google.com/' é suficiente.

        try:
            service = build('gmail', 'v1', credentials=creds)

            search_query_internal = query.strip()
            # Se a query for muito genérica, foca na caixa de entrada por padrão
            if not search_query_internal or search_query_internal.lower() in ["meus emails", "emails",
                                                                              "caixa de entrada", "listar emails"]:
                search_query_internal = "in:inbox"

            print(f"   Executando busca no Gmail com q='{search_query_internal}'")

            # Lista mensagens com base na query
            # Pedimos ID e ThreadID. O snippet pode ser obtido depois com messages.get
            list_request = service.users().messages().list(userId='me', q=search_query_internal, maxResults=10,
                                                           fields="messages(id,threadId),nextPageToken")
            response = list_request.execute()
            messages_summary = response.get('messages', [])

            if not messages_summary:
                return f"Nenhum e-mail encontrado para a busca: '{query}' (interpretado como q='{search_query_internal}')."

            output_lines = [f"Resultados da busca por '{query}' (q='{search_query_internal}'):"]
            count = 0
            for msg_summary in messages_summary:
                if count >= 10: break  # Garante o limite caso a API retorne mais por algum motivo inesperado
                msg_id = msg_summary['id']
                # Pega detalhes da mensagem: snippet e cabeçalhos relevantes
                # Usar fields para otimizar a resposta da API
                msg = service.users().messages().get(userId='me', id=msg_id, format='MINIMAL',
                                                     fields="id,snippet,internalDate,payload/headers").execute()

                snippet = msg.get('snippet', '(Sem trecho)')
                payload = msg.get('payload', {})
                headers = payload.get('headers', [])

                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '(Sem Assunto)')
                sender_raw = next((h['value'] for h in headers if h['name'].lower() == 'from'),
                                  '(Remetente Desconhecido)')
                date_str = next((h['value'] for h in headers if h['name'].lower() == 'date'), None)

                clean_sender_match = re.search(r'([^<]+)<', sender_raw)
                clean_sender = clean_sender_match.group(1).strip() if clean_sender_match else sender_raw.split('@')[
                    0].strip()

                friendly_date = "(Data desc.)"
                if dateutil_available:
                    if date_str:  # Tenta parsear o cabeçalho Date
                        try:
                            dt_obj = dateutil.parser.parse(date_str)
                            if dt_obj.tzinfo: dt_obj = dt_obj.astimezone(dateutil.tz.tzlocal())
                            friendly_date = dt_obj.strftime('%d/%m/%Y %H:%M')
                        except Exception:  # Fallback para internalDate se o header Date falhar
                            try:
                                internal_date_ms = int(msg.get('internalDate', 0))
                                if internal_date_ms > 0:
                                    dt_obj = datetime.datetime.fromtimestamp(internal_date_ms / 1000,
                                                                             tz=datetime.timezone.utc)
                                    friendly_date = dt_obj.astimezone(dateutil.tz.tzlocal()).strftime('%d/%m/%Y %H:%M')
                            except Exception as e_int_date:
                                print(f"Aviso: Falha ao parsear internalDate para msg ID {msg_id}: {e_int_date}")
                    elif msg.get('internalDate'):  # Se não houver cabeçalho Date, usa internalDate
                        try:
                            internal_date_ms = int(msg.get('internalDate', 0))
                            if internal_date_ms > 0:
                                dt_obj = datetime.datetime.fromtimestamp(internal_date_ms / 1000,
                                                                         tz=datetime.timezone.utc)
                                friendly_date = dt_obj.astimezone(dateutil.tz.tzlocal()).strftime('%d/%m/%Y %H:%M')
                        except Exception as e_int_date:
                            print(f"Aviso: Falha ao parsear internalDate para msg ID {msg_id}: {e_int_date}")
                elif date_str:  # Se dateutil não estiver disponível, usa a string bruta do cabeçalho Date
                    friendly_date = date_str.split(' (')[0]

                output_lines.append(
                    f"\n- De: {clean_sender}\n  Assunto: {subject}\n  Data: {friendly_date}\n  Trecho: {snippet}\n  (ID: {msg_id})")
                count += 1

            if response.get('nextPageToken'):
                output_lines.append(
                    "\n(Existem mais resultados. Refine sua busca ou peça para ver a próxima página - funcionalidade de paginação não implementada nesta ferramenta).")

            return "\n".join(output_lines)

        except HttpError as error:
            return f"Erro ao buscar e-mails no Gmail (HttpError {error.resp.status}): {error._get_reason()}"
        except Exception as e:
            traceback.print_exc()
            return f"Erro inesperado ao buscar e-mails: {e}"


class ReadFullEmailContentTool(BaseTool):
    name: str = "google_gmail_read_full_email_content";
    description: str = (
        "Lê o conteúdo completo (corpo em texto puro) de um e-mail específico do Gmail, dado o seu ID de mensagem.")

    # Implementação original mantida
    def _get_plain_text_body(self, payload: dict) -> str:
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
                    return base64.urlsafe_b64decode(part['body']['data'].encode('ASCII')).decode('utf-8',
                                                                                                 errors='replace')
                if part.get('mimeType', '').startswith('multipart/') and 'parts' in part:
                    nested_body = self._get_plain_text_body(part)
                    if nested_body and nested_body != "[Conteúdo em texto puro não encontrado ou formato não suportado para extração direta.]": return nested_body
        elif payload.get('mimeType') == 'text/plain' and payload.get('body', {}).get('data'):
            return base64.urlsafe_b64decode(payload['body']['data'].encode('ASCII')).decode('utf-8', errors='replace')
        return "[Conteúdo em texto puro não encontrado ou formato não suportado para extração direta.]"

    def _run(self, message_id: str) -> str:
        if not message_id or not isinstance(message_id, str): return "Erro: ID da mensagem inválido ou não fornecido."
        creds = get_google_credentials();
        if not creds: return "Erro: Falha nas credenciais Google para Gmail."
        try:
            service = build('gmail', 'v1', credentials=creds);
            msg = service.users().messages().get(userId='me', id=message_id, format='full').execute()
            payload = msg.get('payload', {});
            headers = payload.get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "(Sem assunto)")
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "(Remetente desconhecido)")
            body_text = self._get_plain_text_body(payload)
            return f"E-mail de: {sender}\nAssunto: {subject}\n\nConteúdo:\n{body_text}"
        except HttpError as error:
            return f"Erro ao ler e-mail (ID: {message_id}) (HttpError {error.resp.status}): {error._get_reason()}"
        except Exception as e:
            traceback.print_exc(); return f"Erro inesperado ao ler e-mail (ID: {message_id}): {e}"


class ListGoogleContactsTool(BaseTool):
    name: str = "google_contacts_list"
    description: str = (
        "Use para listar contatos da conta Google do usuário. Opcionalmente, pode receber um argumento numérico para definir o número máximo de contatos a serem retornados (padrão é 20, máximo é 50). Retorna nome, endereços de e-mail e números de telefone dos contatos.")

    def _run(self, query: str = "20") -> str:  # Implementação original mantida
        print(f"\n LCHAIN TOOL: Executando {self.name} com query: '{query}'")
        creds = get_google_credentials();
        if not creds: return "Erro: Falha nas credenciais Google. Não é possível acessar os contatos."
        try:
            max_contacts = 20
            if query.strip().isdigit(): max_contacts = min(int(query.strip()), 50)
            print(f"   Buscando até {max_contacts} contatos...")
            service = build('people', 'v1', credentials=creds)
            results = service.people().connections().list(resourceName='people/me', pageSize=max_contacts,
                                                          personFields='names,emailAddresses,phoneNumbers',
                                                          sortOrder='FIRST_NAME_ASCENDING').execute()
            connections = results.get('connections', [])
            if not connections: return "Nenhum contato encontrado na sua conta Google."
            output_lines = [f"Contatos encontrados (até {max_contacts}):"]
            for person in connections:
                display_name = "Nome não disponível"
                if person.get('names'): display_name = person['names'][0].get('displayName', display_name)
                contact_info_parts = [f"- {display_name}:"]
                email_list = [e.get('value') for e in person.get('emailAddresses', []) if e.get('value')]
                if email_list: contact_info_parts.append(f"    Emails: {', '.join(email_list)}")
                phone_list = [p.get('value') for p in person.get('phoneNumbers', []) if p.get('value')]
                if phone_list: contact_info_parts.append(f"    Telefones: {', '.join(phone_list)}")
                if not email_list and not phone_list: contact_info_parts.append("    (sem e-mail ou telefone listado)")
                output_lines.append("\n".join(contact_info_parts))
            if len(connections) == max_contacts and results.get('nextPageToken'): output_lines.append(
                f"\nAviso: Mais contatos existem além dos {max_contacts} listados.")
            return "\n".join(output_lines)
        except HttpError as error:
            error_details = error._get_reason();
            status_code = error.resp.status
            if status_code == 403 and (
                    "People API has not been used in project" in error_details or "enable the API" in error_details):
                return (
                    f"Erro ao acessar Google Contacts (HttpError {status_code}): {error_details}. A Google People API pode não estar habilitada no seu projeto Google Cloud, ou as permissões não foram concedidas. Verifique o Google Cloud Console e certifique-se de que a 'People API' está ativa e que você concedeu permissão de 'contacts' e re-autorize o script (excluindo token.json se necessário).")
            return f"Erro ao acessar o Google Contacts (HttpError {status_code}): {error_details}"
        except Exception as e:
            traceback.print_exc(); return f"Erro inesperado ao buscar contatos: {e}"


class DirectWebSearchTool(BaseTool):
    name: str = "direct_web_search"
    description: str = (
        "Realiza uma pesquisa na web para uma determinada consulta e retorna o título, URL e um resumo (snippet) do primeiro resultado. Útil para obter informações gerais ou respostas rápidas da web.")

    def _run(self, query: str) -> str:  # Implementação original mantida
        print(f"\n LCHAIN TOOL: Executando {self.name} com query: '{query}'")
        if not query: return "Erro: Nenhuma consulta fornecida para a pesquisa na web."
        try:
            print(
                f"Simulando busca web para: {query} (Esta ferramenta é um placeholder para a capacidade de busca do Gemini)")
            if "história de portugal" in query.lower():
                title = "História de Portugal – Wikipédia, a enciclopédia livre";
                url = "https://pt.wikipedia.org/wiki/Hist%C3%B3ria_de_Portugal";
                snippet = "A história de Portugal como nação europeia remonta à Baixa Idade Média, quando o Condado Portucalense se tornou autónomo do Reino de Leão..."
                return f"Resultado da Pesquisa Web (Simulado):\nTítulo: {title}\nURL: {url}\nResumo: {snippet}"
            else:
                return f"Pesquisa solicitada para '{query}'. O assistente principal (Gemini) deve realizar a busca."
        except Exception as e:
            traceback.print_exc(); return f"Erro inesperado ao tentar simular a pesquisa na web para '{query}': {e}"


class GetNewsTool(BaseTool):
    name: str = "get_latest_news"
    description: str = (
        "Busca as últimas notícias sobre um tópico específico usando a NewsAPI. A entrada deve ser o tópico de interesse (ex: 'inteligência artificial', 'desporto Portugal'). Retorna os títulos e um breve resumo dos principais artigos.")

    def _run(self, topic: str) -> str:  # Implementação original mantida
        print(f"\n LCHAIN TOOL: Executando {self.name} com tópico: '{topic}'")
        global NEWS_API_KEY, requests_available
        if not requests_available: return "Erro: A biblioteca 'requests' não está instalada. Não é possível buscar notícias."
        if not NEWS_API_KEY: return "Erro: A chave da API para NewsAPI não está configurada. Verifique a variável de ambiente NEWS_API_KEY."
        if not topic: return "Erro: Nenhum tópico fornecido para a busca de notícias."
        params = {'q': topic, 'apiKey': NEWS_API_KEY, 'language': 'pt', 'pageSize': 5, 'sortBy': 'publishedAt'}
        try:
            response = requests.get('https://newsapi.org/v2/top-headlines', params=params);
            response.raise_for_status()
            news_data = response.json()
            if news_data.get(
                "status") != "ok": return f"Erro ao buscar notícias da NewsAPI: {news_data.get('message', 'Erro desconhecido da API')}"
            articles = news_data.get("articles", [])
            if not articles: return f"Nenhuma notícia encontrada para o tópico '{topic}'."
            output_lines = [f"Últimas notícias sobre '{topic}':"]
            for article in articles:
                title = article.get('title', 'Sem título');
                source_name = article.get('source', {}).get('name', 'Fonte desconhecida')
                description = article.get('description', 'Sem descrição');
                url = article.get('url', '#')
                output_lines.append(f"\n- Título: {title}");
                output_lines.append(f"  Fonte: {source_name}")
                if description: output_lines.append(f"  Resumo: {description}")
                output_lines.append(f"  Link: {url}")
            return "\n".join(output_lines)
        except requests.exceptions.RequestException as e:
            print(f"Erro de rede ao contatar NewsAPI: {e}"); return f"Erro de rede ao buscar notícias: {e}"
        except json.JSONDecodeError:
            return "Erro: A resposta da NewsAPI não foi um JSON válido."
        except Exception as e:
            traceback.print_exc(); return f"Erro inesperado ao buscar notícias: {e}"


# --- Variáveis e Instâncias para Threads de Background ---
check_gmail_tool_instance = CheckGmailTool()  # Instância da ferramenta modificada
last_checked_time = 0
stop_background_threads = threading.Event()

# --- Inicialização das Ferramentas para o Agente ---
tools = [
    WindowsCommandExecutorTool(), GetCalendarEventsTool(), CreateCalendarEventTool(),
    SendGmailTool(), YouTubeSearchTool(), DriveListFilesTool(),
    check_gmail_tool_instance,  # CheckGmailTool modificada
    SearchEmailsTool(),  # Nova ferramenta SearchEmailsTool
    ReadFullEmailContentTool(), ListGoogleContactsTool(),
    DirectWebSearchTool(), GetNewsTool()
]
print(f"\nTotal de {len(tools)} ferramentas carregadas.");
print("Ferramentas disponíveis para o agente:", [tool.name for tool in tools]);
print("-" * 50)

# --- Configuração do Agente ---
try:
    react_prompt_template = hub.pull("hwchase17/react")
    agent = create_react_agent(llm=llm, tools=tools, prompt=react_prompt_template)
    agent_executor = AgentExecutor(
        agent=agent, tools=tools, verbose=True,
        handle_parsing_errors="Sua resposta anterior não estava no formato ReAct correto. Por favor, certifique-se de que sua resposta comece com 'Thought:' e, se usar uma ferramenta, siga com 'Action:' e 'Action Input:', OU comece com 'Final Answer:' se tiver a resposta final. Não adicione texto antes de 'Thought:' ou 'Final Answer:'.",
        max_iterations=15, max_execution_time=300
    )
    print("\nAgente LangChain (ReAct) e Executor configurados.");
    print("-" * 30)
except Exception as e:
    print(f"Erro crítico na configuração do Agente LangChain: {e}");
    traceback.print_exc();
    sys.exit(1)


# --- Função para Capturar e Reconhecer Voz ---
def ouvir_comando(timeout_microfone=5, frase_limite_segundos=10):  # Implementação original mantida
    r = sr.Recognizer();
    audio = None
    try:
        with sr.Microphone() as source:
            print("\nAjustando ruído ambiente (0.5s)...");
            try:
                r.adjust_for_ambient_noise(source, duration=0.5)
            except Exception as e_noise:
                print(f"Aviso: Falha no ajuste de ruído ambiente: {e_noise}")
            print(f"Fale seu comando ou pergunta ({frase_limite_segundos}s max):")
            try:
                audio = r.listen(source, timeout=timeout_microfone, phrase_time_limit=frase_limite_segundos)
            except sr.WaitTimeoutError:
                print("Tempo de escuta do microfone esgotado."); return None
            except Exception as e_listen:
                print(f"Erro durante a escuta do microfone: {e_listen}"); return None
    except sr.RequestError as e_mic_req:
        print(
            f"Erro no serviço de reconhecimento (API Speech não alcançável ou problema de rede?): {e_mic_req}"); return None
    except OSError as e_os_mic:
        if e_os_mic.errno == -9999 or "No Default Input Device Available" in str(
                e_os_mic) or "Dispositivo de entrada padrão não disponível" in str(e_os_mic):
            print(
                f"ERRO DE MICROFONE: Nenhum dispositivo de entrada de áudio padrão encontrado. Verifique seu microfone. Detalhes: {e_os_mic}")
        else:
            print(f"Erro de OS com o Microfone: {e_os_mic}"); traceback.print_exc()
        return None
    except Exception as e_mic:
        print(f"Erro geral com o Microfone: {e_mic}"); traceback.print_exc(); return None
    if not audio: return None
    print("Reconhecendo fala...");
    texto_comando = None
    try:
        texto_comando = r.recognize_google(audio, language='pt-BR');
        print(f"Você disse: '{texto_comando}'")
    except sr.UnknownValueError:
        print("Não entendi o que você disse.")
    except sr.RequestError as e_rec_req:
        print(f"Erro no Serviço de Reconhecimento Google Speech: {e_rec_req}")
    except Exception as e_rec:
        print(f"Erro Desconhecido no Reconhecimento de Fala: {e_rec}")
    return texto_comando


# --- Função para Falar (TTS com Google Cloud) ---
def falar(texto):  # Implementação original mantida, com pequena melhoria na remoção do tempfile
    global playsound_installed, google_tts_ready, TTS_VOICE_GOOGLE
    if not texto: print("[TTS] Nada para falar."); return
    if not google_tts_ready: print(f"\n(Simulando saída falada - Google TTS não pronto): {texto}"); return
    print(f"\n🔊 Falando (Google Cloud TTS - Voz: {TTS_VOICE_GOOGLE}): {texto}")
    temp_filename = None
    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=texto)
        voice_params = texttospeech.VoiceSelectionParams(language_code="pt-BR", name=TTS_VOICE_GOOGLE)
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        response = client.synthesize_speech(
            request={'input': synthesis_input, 'voice': voice_params, 'audio_config': audio_config})
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            fp.write(response.audio_content);
            temp_filename = fp.name
        if temp_filename:
            if playsound_installed:
                playsound.playsound(temp_filename)
            else:
                print("AVISO: playsound não instalado. Tentando abrir MP3 com o sistema.")
                if sys.platform == "win32":
                    os.startfile(temp_filename)
                elif sys.platform == "darwin":
                    subprocess.call(["open", temp_filename])
                else:
                    subprocess.call(["xdg-open", temp_filename])
                time.sleep(2)  # Dar um tempo para o player externo iniciar antes de tentar excluir
    except Exception as e:
        print(f"Erro durante Google Cloud TTS ou reprodução do áudio: {e}"); traceback.print_exc()
    finally:
        if temp_filename and os.path.exists(temp_filename):
            time.sleep(1)
            try:
                os.remove(temp_filename)
            except PermissionError:
                print(
                    f"AVISO: Não foi possível remover o arquivo de áudio temporário {temp_filename} pois está em uso.")
            except Exception as e_del:
                print(f"Aviso: Erro ao remover arquivo de áudio temporário {temp_filename}: {e_del}")


# --- Funções para Win Hoff MP3 e Pomodoro ---
# Implementações originais mantidas, com pequenos ajustes de feedback por voz
def play_winhoff_sound():
    global playsound_installed, WINHOFF_MP3_FILE
    if not os.path.exists(WINHOFF_MP3_FILE):
        msg = f"AVISO: Arquivo de áudio '{WINHOFF_MP3_FILE}' não encontrado."
        print(msg);
        falar(msg.replace("AVISO: ", "Atenção, "))
        return
    if not playsound_installed:
        msg = f"AVISO: Biblioteca 'playsound' não instalada. Não é possível tocar {WINHOFF_MP3_FILE}."
        print(msg);
        falar(msg.replace("AVISO: ", "Atenção, "))
        return
    try:
        print(f"▶️ Tocando {WINHOFF_MP3_FILE}..."); playsound.playsound(WINHOFF_MP3_FILE)
    except Exception as e:
        print(f"Erro ao tentar tocar {WINHOFF_MP3_FILE} com playsound: {e}"); falar(
            "Ocorreu um erro ao tentar tocar o som do exercício.")


def winhoff_periodic_task(interval_seconds, stop_event):
    print(
        f"[Thread Win Hoff Periódico] Iniciada. Tocando {WINHOFF_MP3_FILE} a cada {interval_seconds / 3600:.1f} horas.")
    while not stop_event.wait(timeout=interval_seconds):
        if stop_event.is_set(): break
        print(
            f"[Thread Win Hoff Periódico] Intervalo de {interval_seconds / 3600:.1f}h concluído. Tocando {WINHOFF_MP3_FILE}.")
        play_winhoff_sound()
    print("[Thread Win Hoff Periódico] Encerrada.")


def pomodoro_task(pomodoro_duration_seconds, stop_event):
    print(
        f"[Thread Pomodoro] Iniciada. Duração: {pomodoro_duration_seconds / 60:.0f} min, seguido por {WINHOFF_MP3_FILE}.")
    while not stop_event.is_set():
        print(f"\n[Thread Pomodoro] Novo ciclo de {pomodoro_duration_seconds / 60:.0f} minutos.")
        falar(f"Iniciando Pomodoro de {pomodoro_duration_seconds / 60:.0f} minutos.")
        tempo_restante = pomodoro_duration_seconds
        while tempo_restante > 0 and not stop_event.is_set():
            minutos = tempo_restante // 60;
            segundos = tempo_restante % 60
            sys.stdout.write(f"\rTempo Pomodoro: {minutos:02d}:{segundos:02d}   ");
            sys.stdout.flush()
            if stop_event.wait(1): break
            tempo_restante -= 1
        if stop_event.is_set():
            sys.stdout.write("\r[Thread Pomodoro] Interrompido.                 \n");
            sys.stdout.flush()
            falar("Pomodoro interrompido.");
            break
        if tempo_restante == 0:
            sys.stdout.write("\r[Thread Pomodoro] Ciclo Concluído!              \n");
            sys.stdout.flush()
            print(f"[Thread Pomodoro] Tocando {WINHOFF_MP3_FILE}.")
            falar("Pomodoro concluído. Hora do exercício.");
            play_winhoff_sound();
            falar("Exercício finalizado.")
        if stop_event.wait(2): break
    sys.stdout.write("\r[Thread Pomodoro] Encerrada.                   \n");
    sys.stdout.flush()
    print("[Thread Pomodoro] Encerrada.")


# --- Função de Verificação Periódica de E-mails MODIFICADA ---
def periodic_email_check(interval_seconds, stop_event):
    global last_checked_time, google_auth_ready, USER_NAME, check_gmail_tool_instance
    print(f"[Thread E-mail] Iniciada. Verificando e-mails a cada {interval_seconds} segundos.")
    while not stop_event.is_set():
        if not google_auth_ready:
            if stop_event.wait(60): break
            continue

        current_time = time.time()
        if (current_time - last_checked_time) >= interval_seconds or last_checked_time == 0:
            print(f"\n[Thread E-mail] Verificando e-mails...")
            try:
                # A CheckGmailTool agora retorna um dict com "spoken" e "details"
                # "spoken" será None se não houver um novo e-mail específico para anunciar desde a última vez.
                check_result = check_gmail_tool_instance._run()
                last_checked_time = time.time()

                if isinstance(check_result, dict) and check_result.get("spoken"):
                    spoken_message = check_result["spoken"]
                    # Personaliza a mensagem para o usuário, se houver nome e mensagem
                    full_spoken_message = f"{USER_NAME}, {spoken_message[0].lower() + spoken_message[1:]}" if USER_NAME and spoken_message else spoken_message
                    if full_spoken_message:  # Só fala se houver algo construído
                        falar(full_spoken_message)
                elif isinstance(check_result, str) and "Erro:" in check_result:
                    print(f"[Thread E-mail] Erro retornado pela ferramenta de verificação: {check_result}")
                # Se check_result["spoken"] for None (nenhum novo e-mail para notificar), não fala nada.

            except Exception as e:
                print(f"[Thread E-mail] Erro crítico na verificação periódica: {e}");
                traceback.print_exc()
                last_checked_time = time.time()

        time_to_next_check = max(0, interval_seconds - (time.time() - last_checked_time))
        wait_duration = min(time_to_next_check, 60)
        if stop_event.wait(wait_duration): break

    print("[Thread E-mail] Encerrada.")


# --- Iniciar Threads de Background ---
all_threads = []  # Implementação original mantida
print("\n--- Iniciando Threads de Background ---")
email_check_interval = 300
if google_auth_ready:
    print(f"Thread de verificação de e-mails será iniciada (intervalo: {email_check_interval}s).")
    email_thread = threading.Thread(target=periodic_email_check, args=(email_check_interval, stop_background_threads),
                                    daemon=True, name="EmailCheckThread")
    all_threads.append(email_thread);
    email_thread.start()
else:
    print("AVISO: Thread de verificação de e-mails NÃO iniciada devido à falha na autenticação Google.")
can_start_audio_threads = playsound_installed and os.path.exists(WINHOFF_MP3_FILE)
if not playsound_installed: print(
    f"AVISO: 'playsound' não instalado. As threads de áudio ({WINHOFF_MP3_FILE}) não serão iniciadas.")
if not os.path.exists(WINHOFF_MP3_FILE) and playsound_installed: print(
    f"AVISO: Arquivo '{WINHOFF_MP3_FILE}' não encontrado. As threads de áudio não serão iniciadas.")
if can_start_audio_threads:
    winhoff_interval_2_hours = 2 * 60 * 60
    print(f"Thread Win Hoff Periódico ({WINHOFF_MP3_FILE} a cada 2 horas) será iniciada.")
    winhoff_periodic_thread = threading.Thread(target=winhoff_periodic_task,
                                               args=(winhoff_interval_2_hours, stop_background_threads), daemon=True,
                                               name="WinHoffPeriodicThread")
    all_threads.append(winhoff_periodic_thread);
    winhoff_periodic_thread.start()
    pomodoro_duration = 30 * 60
    print(
        f"Thread Pomodoro ({WINHOFF_MP3_FILE} a cada {pomodoro_duration / 60} minutos, com timer visível) será iniciada.")
    pomodoro_thread = threading.Thread(target=pomodoro_task, args=(pomodoro_duration, stop_background_threads),
                                       daemon=True, name="PomodoroThread")
    all_threads.append(pomodoro_thread);
    pomodoro_thread.start()
else:
    print(
        f"AVISO: Threads de áudio para '{WINHOFF_MP3_FILE}' não foram iniciadas devido a problemas com 'playsound' ou o arquivo MP3.")
print("-" * 50)

# --- Loop Principal Interativo ---
# Implementação original mantida, com pequenas melhorias no feedback
print(f"\nLangChain Windows Voice Commander Agent (Controle Total Ativado - RISCO ALTO)")
print("================================================================================");
print("!!! AVISO DE RISCO EXTREMO - CONTROLE TOTAL ATIVADO !!!");
print("================================================================================")
print(f"Usando LLM: {MODEL_NAME} | TTS: Google Cloud TTS (Voz: {TTS_VOICE_GOOGLE}) | Usuário: {USER_NAME}")
if not google_auth_ready: print("AVISO: Acesso a serviços Google PODE ESTAR DESABILITADO devido à falha OAuth.")
if not google_tts_ready: print("AVISO: Google Cloud TTS não está pronto. Saída de voz PODE NÃO FUNCIONAR.")
if not can_start_audio_threads: print(f"AVISO: Funcionalidades de áudio com '{WINHOFF_MP3_FILE}' estão desabilitadas.")
if not requests_available: print(
    f"AVISO: Funcionalidade de Notícias está DESABILITADA (biblioteca 'requests' não encontrada).")
if not NEWS_API_KEY and requests_available: print(
    f"AVISO: Funcionalidade de Notícias está DESABILITADA (NEWS_API_KEY não configurada no .env).")

falar(f"Olá {USER_NAME}! Sistema de controle por voz pronto e atualizado. Fale 'sair' para terminar.")
try:
    while True:
        task_text = ouvir_comando()
        if task_text:
            if task_text.lower().strip() == 'sair':
                falar(f"Encerrando as operações, {USER_NAME}. Até logo!");
                stop_background_threads.set();
                break
            google_service_keywords = ["agenda", "evento", "calendário", "gmail", "email", "e-mail", "drive", "arquivo",
                                       "youtube", "vídeo", "contato", "contatos", "planilha", "documento", "tarefa",
                                       "fotos"]
            requires_google_services = any(keyword in task_text.lower() for keyword in google_service_keywords)
            if requires_google_services and not google_auth_ready:
                error_msg = f"Desculpe {USER_NAME}, não posso realizar essa tarefa porque a autenticação com os serviços Google falhou. Verifique o console para erros de autenticação."
                print(f"ERRO: {error_msg}");
                falar(error_msg);
                continue
            try:
                input_for_agent = f"O nome do usuário é {USER_NAME}. A solicitação do usuário é: {task_text}"
                print(f"\n>>> Enviando tarefa ( '{input_for_agent}' ) para o agente...")
                response = agent_executor.invoke({"input": input_for_agent})
                agent_output_text = response.get("output", "Não obtive uma resposta final do agente.")
                print("\n--- Resposta Final do Agente ---");
                print(agent_output_text);
                print("------------------------------")
                falar(agent_output_text)
            except Exception as e_agent:
                error_message = f"Ocorreu um erro crítico durante a execução do agente: {e_agent}"
                print(f"\n!!! {error_message} !!!");
                traceback.print_exc()
                falar(
                    f"Desculpe {USER_NAME}, ocorreu um erro interno severo ao processar seu pedido. Por favor, tente novamente ou verifique os logs para detalhes técnicos.")
        else:
            pass
except KeyboardInterrupt:
    print("\nInterrupção pelo teclado recebida. Encerrando...");
    falar(f"Encerrando devido à interrupção, {USER_NAME}.");
    stop_background_threads.set()
finally:
    print("\nLimpando e aguardando threads de background finalizarem...")
    if not stop_background_threads.is_set(): stop_background_threads.set()
    for t in all_threads:
        if t.is_alive():
            print(f"Aguardando thread {t.name} finalizar...");
            t.join(timeout=5)
            if t.is_alive(): print(f"AVISO: Thread {t.name} não finalizou a tempo.")
    print("\nScript LangChain com Voz terminado.")
# -*- coding: utf-8 -*-
# --- Using Google's Gemini API (gemini-1.5-pro) ---

# Standard Python Libraries
import sys
from dotenv import load_dotenv
import os
import re
import logging
from tqdm import tqdm
import time
import shutil
import traceback # Para log de erros detalhado
import glob # Para encontrar arquivos .txt
import smtplib # For email
import ssl # For email security
from email.message import EmailMessage # For constructing email
import subprocess
import copy # << NOVO: Para copiar objetos docx >>

# Third-party Libraries
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Inches
from docx.shared import RGBColor
import google.generativeai as genai

# === SETUP LOGGING ===
log_dir = "logs"
if not os.path.exists(log_dir): os.makedirs(log_dir)
log_filepath = os.path.join(log_dir, "book_processor_multi_author_mem.log")
PROCESSED_LOG_FILE = os.path.join(log_dir, "processed_books.log")
TRANSLATED_LOG_FILE = os.path.join(log_dir, "translated_books.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(funcName)s - %(message)s',
    handlers=[ logging.FileHandler(log_filepath, encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# === CARREGA VARIÁVEIS DE AMBIENTE ===
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
EMAIL_SENDER_ADDRESS = os.getenv("EMAIL_SENDER_ADDRESS")
EMAIL_SENDER_APP_PASSWORD = os.getenv("EMAIL_SENDER_APP_PASSWORD")
EMAIL_RECIPIENT_ADDRESS = os.getenv("EMAIL_RECIPIENT_ADDRESS", "web2ajax@gmail.com")
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", 587))

# === CONFIGURAÇÕES ===
BASE_INPUT_TXT_DIR = "txt"
BASE_OUTPUT_DOCX_DIR = "docx"
BASE_OUTPUT_TXT_DIR = "txt" # Mantido para possível uso futuro, mas as notas TXT serão removidas
TEMPLATE_DOCX = "Estrutura.docx"
FINAL_DOCX_BASENAME = "Livro_Final_Formatado_Sem_Notas.docx" # Para tradutor
FINAL_DOCX_WITH_NOTES_BASENAME = "Livro_Final_Com_Notas_No_Fim.docx" # << NOVO NOME BASE >>
# FINAL_NUMBERED_TXT_BASENAME = "Livro_Final_Com_Notas_Numeros.txt" # Removido
# NOTES_TXT_FILE_BASENAME = "notas_rodape.txt" # Removido
TRANSLATED_DOCX_SUFFIX = "-A0.docx"
MODEL_NAME = "gemini-1.5-pro"
MAX_CHUNK_TOKENS = 1500
MAX_OUTPUT_TOKENS = 8192
TEMPERATURE = 0.5
PATH_TO_TRANSLATOR_SCRIPT = "script_tradutor_hibrido.py"
NUM_WORDS_TO_TRANSLATE = 100
NORMAL_STYLE_NAME = "Normal"
CHAPTER_PATTERNS = [r'^\s*Capítulo \w+', r'^\s*CAPÍTULO \w+', r'^\s*Capítulo \d+', r'^\s*CHAPTER \w+', r'^\s*Chapter \d+', r'^\s*LIVRO \w+', r'^\s*PARTE \w+']
PAGE_BREAK_MARKER = "===QUEBRA_DE_PAGINA==="
AI_FAILURE_MARKER = "*** FALHA NA IA - TEXTO ORIGINAL ABAIXO ***"
FORMATTING_ERROR_MARKER = "*** ERRO DE FORMATAÇÃO - TEXTO ORIGINAL ABAIXO ***"
# Regex para encontrar marcadores de nota gerados pela IA no Passo 2
# Captura o marcador inteiro (grupo 0), o tipo (grupo 1), a referência (grupo 2), e o conteúdo (grupo 3)
# NOTA: Ajustado para ser não-guloso (.*?) e lidar melhor com múltiplos marcadores
FOOTNOTE_MARKER_PATTERN = re.compile(
    r'\[NOTA_(IDIOMA|CITACAO|NOME|TERMO):([^\]]+?)\]\s*\[CONTEUDO_NOTA:([^\]]*?)\]',
    re.IGNORECASE
)

# --- Validações e Setup (API Key, Email Config, Gemini Client) ---
if not GOOGLE_API_KEY: logger.error("FATAL: GOOGLE_API_KEY não encontrada."); exit(1)
email_configured = bool(EMAIL_SENDER_ADDRESS and EMAIL_SENDER_APP_PASSWORD and EMAIL_RECIPIENT_ADDRESS)
if not email_configured: logger.warning("AVISO: Configurações de e-mail incompletas. Notificação desativada.")
else: logger.info(f"Config e-mail OK: De '{EMAIL_SENDER_ADDRESS}' Para '{EMAIL_RECIPIENT_ADDRESS}'.")
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    safety_settings_lenient = {'HATE': 'BLOCK_NONE', 'HARASSMENT': 'BLOCK_NONE', 'SEXUAL': 'BLOCK_NONE', 'DANGEROUS': 'BLOCK_NONE'}
    generation_config = genai.GenerationConfig(temperature=TEMPERATURE, max_output_tokens=MAX_OUTPUT_TOKENS)
    gemini_model = genai.GenerativeModel(MODEL_NAME, safety_settings=safety_settings_lenient, generation_config=generation_config)
    logger.info(f"Modelo Gemini '{MODEL_NAME}' inicializado.")
except Exception as e: logger.error(f"FATAL: Falha ao inicializar Gemini: {e}"); logger.error(traceback.format_exc()); exit(1)

# --- Funções Auxiliares ---
def count_tokens_approx(text):
    if not text: return 0; return len(text) // 3

def create_chunks(text, max_tokens, author_name="N/A", book_name="N/A"):
    # (Função create_chunks permanece inalterada - como na última versão completa)
    log_prefix = f"[{author_name}/{book_name}]"
    chunks = []; current_chunk = ""; current_chunk_tokens = 0
    paragraphs = text.split("\n\n")
    for i, paragraph_text in enumerate(paragraphs):
        if not paragraph_text.strip():
            if chunks and chunks[-1].strip() and not chunks[-1].endswith("\n\n"): chunks[-1] += "\n\n"
            continue
        paragraph_tokens = count_tokens_approx(paragraph_text)
        tokens_with_separator = paragraph_tokens + (count_tokens_approx("\n\n") if current_chunk else 0)
        if current_chunk_tokens + tokens_with_separator <= max_tokens:
            separator = "\n\n" if current_chunk else ""
            current_chunk += separator + paragraph_text; current_chunk_tokens = count_tokens_approx(current_chunk)
        else:
            if current_chunk: chunks.append(current_chunk)
            current_chunk = paragraph_text; current_chunk_tokens = paragraph_tokens
            if paragraph_tokens > max_tokens: # Subdivisão
                logger.warning(f"{log_prefix} Parágrafo {i+1} ({paragraph_tokens} tk) > limite {max_tokens}. SUBDIVIDINDO.")
                current_chunk = ""; current_chunk_tokens = 0; sub_chunks_added_count = 0
                sentences = re.split(r'(?<=[.!?])\s+', paragraph_text)
                if len(sentences) <= 1: sentences = paragraph_text.split('\n')
                current_sub_chunk = ""; current_sub_chunk_tokens = 0
                for sentence_num, sentence in enumerate(sentences):
                    sentence_clean = sentence.strip();
                    if not sentence_clean: continue
                    sentence_tokens = count_tokens_approx(sentence)
                    tokens_with_sub_separator = sentence_tokens + (count_tokens_approx("\n") if current_sub_chunk else 0)
                    if current_sub_chunk_tokens + tokens_with_sub_separator <= max_tokens:
                        sub_separator = "\n" if current_sub_chunk else ""
                        current_sub_chunk += sub_separator + sentence; current_sub_chunk_tokens = count_tokens_approx(current_sub_chunk)
                    else:
                        if current_sub_chunk: chunks.append(current_sub_chunk); sub_chunks_added_count += 1
                        if sentence_tokens > max_tokens:
                            chunks.append(sentence); sub_chunks_added_count += 1
                            logger.warning(f"{log_prefix} -> Sentença/Linha {sentence_num+1} ({sentence_tokens} tk) > limite. Adicionada separadamente.")
                            current_sub_chunk = ""; current_sub_chunk_tokens = 0
                        else:
                            current_sub_chunk = sentence; current_sub_chunk_tokens = sentence_tokens
                if current_sub_chunk: chunks.append(current_sub_chunk); sub_chunks_added_count += 1
                if sub_chunks_added_count == 0: logger.warning(f"{log_prefix} Parágrafo {i+1} não subdividido."); chunks.append(paragraph_text)
                current_chunk = ""; current_chunk_tokens = 0
    if current_chunk: chunks.append(current_chunk)
    merged_chunks = []; temp_chunk = ""; temp_chunk_tokens = 0
    for i, chunk in enumerate(chunks):
        chunk_tokens = count_tokens_approx(chunk)
        tokens_with_separator = chunk_tokens + (count_tokens_approx("\n\n") if temp_chunk else 0)
        if temp_chunk_tokens + tokens_with_separator <= max_tokens:
            separator = "\n\n" if temp_chunk else ""
            temp_chunk += separator + chunk; temp_chunk_tokens = count_tokens_approx(temp_chunk)
        else:
            if temp_chunk: merged_chunks.append(temp_chunk)
            temp_chunk = chunk; temp_chunk_tokens = chunk_tokens
    if temp_chunk: merged_chunks.append(temp_chunk)
    final_chunk_count = len(merged_chunks)
    if final_chunk_count < len(chunks): logger.info(f"{log_prefix} Merge: {len(chunks)} -> {final_chunk_count} chunks.")
    return merged_chunks

def _call_gemini_api(model, prompt_text, chunk_for_log, author_name="N/A", book_name="N/A"):
    """Chama API Gemini com retries e retorna (texto|None, latencia, p_tokens, o_tokens, t_tokens)."""
    # (Função _call_gemini_api permanece inalterada - como na última versão completa)
    log_prefix = f"[{author_name}/{book_name}]"
    max_retries = 5; base_wait_time = 5
    log_chunk_preview = chunk_for_log[:100].replace('\n', '\\n') + '...'
    default_return = (None, 0, 0, 0, 0)
    for attempt in range(max_retries):
        start_time = time.time(); response = None; latency = 0; prompt_tokens = 0; output_tokens = 0; total_tokens = 0; result_text = None
        try:
            response = model.generate_content(prompt_text); latency = time.time() - start_time
            try: # Get usage metadata
                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    prompt_tokens = usage.prompt_token_count if hasattr(usage, 'prompt_token_count') else 0
                    output_tokens = usage.candidates_token_count if hasattr(usage, 'candidates_token_count') else 0
                    total_tokens = usage.total_token_count if hasattr(usage, 'total_token_count') else (prompt_tokens + output_tokens)
                    logger.debug(f"{log_prefix} API OK ({latency:.2f}s). Tokens: P{prompt_tokens}+O{output_tokens}=T{total_tokens}")
                else: logger.debug(f"{log_prefix} API OK ({latency:.2f}s). Usage metadata not found.")
            except Exception as e_usage: logger.warning(f"{log_prefix} Erro ao acessar usage_metadata: {e_usage}")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
                logger.error(f"{log_prefix} API BLOQUEOU PROMPT (Tentativa {attempt+1}): {response.prompt_feedback.block_reason.name}. Lat:{latency:.2f}s."); return default_return
            if not response.candidates: logger.error(f"{log_prefix} API SEM CANDIDATOS (Tentativa {attempt+1}). Lat:{latency:.2f}s.")
            else:
                 try:
                    candidate = response.candidates[0]
                    finish_reason = candidate.finish_reason.name if hasattr(candidate, 'finish_reason') and candidate.finish_reason else "UNKNOWN"
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        text_parts = [part.text for part in candidate.content.parts if hasattr(part, 'text')]
                        if text_parts: result_text = "".join(text_parts).strip()
                    elif hasattr(response, 'text') and response.text: result_text = response.text.strip()
                    if finish_reason == "STOP" and result_text is not None: return (result_text, latency, prompt_tokens, output_tokens, total_tokens)
                    else: logger.warning(f"{log_prefix} API terminou não OK ou texto vazio (Tentativa {attempt+1}). Finish:{finish_reason}. Lat:{latency:.2f}s.")
                 except Exception as e_details: logger.error(f"{log_prefix} Erro extrair resposta API (Tentativa {attempt+1}): {e_details}. Lat:{latency:.2f}s."); logger.error(traceback.format_exc())
            if attempt < max_retries - 1: # Wait before retry
                wait_time = base_wait_time * (2**attempt) + (os.urandom(1)[0]/255.0*base_wait_time); logger.info(f"{log_prefix} Tentando API de novo em {wait_time:.2f}s..."); time.sleep(wait_time)
            else: logger.error(f"{log_prefix} Falha final API após {max_retries} tentativas: '{log_chunk_preview}'"); return default_return
        except Exception as e: # Error during API call itself
            latency = time.time() - start_time; logger.warning(f"{log_prefix} Erro chamada API ({model.model_name}) (Tentativa {attempt+1}): {e}. Lat:{latency:.2f}s"); logger.debug(traceback.format_exc())
            if attempt < max_retries - 1:
                wait_time = base_wait_time * (2**attempt) + (os.urandom(1)[0]/255.0*base_wait_time)
                if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e): base_wait_time=max(15, base_wait_time); wait_time=base_wait_time*(2**attempt)+(os.urandom(1)[0]/255.0*base_wait_time); logger.warning(f"{log_prefix} Erro cota. Aumentando espera base.")
                logger.info(f"{log_prefix} Tentando API de novo em {wait_time:.2f}s..."); time.sleep(wait_time)
            else: logger.error(f"{log_prefix} Falha final API (erro chamada): '{log_chunk_preview}'"); return default_return
    logger.error(f"{log_prefix} Loop API concluído sem sucesso: '{log_chunk_preview}'"); return default_return

def format_with_ai_correction_only(model, chunk, author_name, book_name, is_first_chunk=False):
    """Chama API Gemini para CORREÇÃO. Retorna tupla com stats."""
    # (Prompt interno inalterado)
    context_start = "Você está formatando o início..."
    ocr_errors_examples = "* **Troca de letras..."
    chunk_prompt = f"""{context_start} ... {author_name} ... {ocr_errors_examples} ... {chunk} ... """ # Prompt completo aqui
    return _call_gemini_api(model, chunk_prompt, chunk, author_name, book_name)

def format_with_ai_footnote_only(model, chunk, author_name, book_name):
    """Chama API Gemini para ID DE NOTAS. Retorna tupla com stats."""
    # (Prompt interno inalterado)
    chunk_prompt = f"""Você é um assistente de edição ... {author_name} ... {chunk} ... """ # Prompt completo aqui
    return _call_gemini_api(model, chunk_prompt, chunk, author_name, book_name)

# --- FUNÇÕES DE PROCESSAMENTO DOS PASSOS ---

# <<< MODIFICADO: apply_formatting_pass1 agora é apply_formatting_to_doc >>>
# <<< Recebe texto completo, adiciona ao doc (respeitando template) e lida com marcadores [N] >>>
def apply_formatting_to_doc(doc, text_content, normal_style_name, chapter_patterns, author_name, book_name, handle_note_markers=False, notes_mapping=None):
    """
    Adiciona o text_content formatado ao objeto doc existente.
    Se handle_note_markers=True, busca por placeholders como __NOTE_X__
    e os substitui por marcadores [X] em negrito.
    """
    log_prefix = f"[{author_name}/{book_name}]"
    if not text_content: return doc # Retorna doc inalterado se não há texto

    if notes_mapping is None: notes_mapping = {}

    #logger.debug(f"{log_prefix} Aplicando formatação ao DOCX...")
    normal_style = None
    try: # Busca estilo Normal
        if normal_style_name in doc.styles: normal_style = doc.styles[normal_style_name]
    except Exception as e_style: logger.error(f"{log_prefix} Erro acessar estilo '{normal_style_name}': {e_style}.")

    chapter_regex = re.compile('|'.join(chapter_patterns), re.IGNORECASE)
    # Processa partes separadas por quebra de página MANUAL
    parts = text_content.split(PAGE_BREAK_MARKER)

    for part_index, part in enumerate(parts):
        part_clean = part.strip()
        # Adiciona quebra de página ANTES da nova parte (exceto a primeira)
        if part_index > 0:
             # Evita quebras duplicadas
             last_para_is_page_break = False
             if doc.paragraphs:
                 last_p = doc.paragraphs[-1]
                 if not last_p.text.strip() and any(run.text and '\f' in run.text for run in last_p.runs): last_para_is_page_break = True
             if not last_para_is_page_break: doc.add_page_break()

        if not part_clean: continue

        # Processa parágrafos dentro da parte
        paragraphs_in_part = part_clean.split("\n\n")
        for paragraph_text in paragraphs_in_part:
            paragraph_text_clean = paragraph_text.strip()
            if not paragraph_text_clean: # Parágrafo vazio para espaçamento
                if doc.paragraphs and doc.paragraphs[-1].text.strip():
                     p = doc.add_paragraph();
                     if normal_style: p.style = normal_style
                continue

            is_ai_failure_marker = paragraph_text_clean.startswith(AI_FAILURE_MARKER)
            is_formatting_error_marker = paragraph_text_clean.startswith(FORMATTING_ERROR_MARKER)
            is_chapter = not is_ai_failure_marker and not is_formatting_error_marker and chapter_regex.match(paragraph_text_clean) is not None

            p = doc.add_paragraph() # Adiciona novo parágrafo

            # --- Lógica para lidar com marcadores de nota [N] ---
            # Usamos um placeholder simples (__NOTE_X__) internamente e substituímos aqui
            # Isso é mais robusto do que tentar achar o marcador complexo no DOCX
            if handle_note_markers and re.search(r'__NOTE_(\d+)__', paragraph_text_clean):
                # Divide o texto pelos placeholders
                sub_parts = re.split(r'(__NOTE_(\d+)__)', paragraph_text_clean)
                for sub_part in sub_parts:
                    if not sub_part: continue
                    match = re.match(r'__NOTE_(\d+)__', sub_part)
                    if match:
                        note_number = int(match.group(1))
                        # Adiciona o marcador [N] em negrito
                        run_marker = p.add_run(f"[{note_number}]")
                        run_marker.bold = True
                    else:
                        # Adiciona o texto normal
                        run_text = p.add_run(sub_part)
                        # Aplica formatação baseada no tipo de parágrafo (capítulo, erro, normal)
                        if is_chapter: run_text.bold=False # Sobrescreve negrito se for capítulo
                        elif is_ai_failure_marker or is_formatting_error_marker: run_text.italic=True; run_text.font.color.rgb=RGBColor(0xFF, 0, 0)
                        # Estilo Normal é aplicado ao parágrafo, não ao run
            else:
                # Se não há marcadores de nota, adiciona o texto todo de uma vez
                run = p.add_run(paragraph_text_clean)
                if is_ai_failure_marker or is_formatting_error_marker: run.italic=True; run.font.color.rgb=RGBColor(0xFF, 0, 0)
                # Formatação de capítulo/estilo será aplicada ao parágrafo abaixo

            # Aplica estilo e formatação ao PARÁGRAFO
            try:
                if is_chapter:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    # Aplica fonte ao primeiro run (pode precisar ajustar se houver runs pré-existentes)
                    if p.runs: p.runs[0].font.name = 'French Script MT'; p.runs[0].font.size = Pt(48); p.runs[0].bold=False
                elif is_ai_failure_marker or is_formatting_error_marker:
                    if normal_style: p.style = normal_style
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT # Garante alinhamento
                elif normal_style:
                    p.style = normal_style
            except Exception as e_apply_style: logger.error(f"{log_prefix} Erro ao aplicar estilo/formatação ao parágrafo: {e_apply_style}")

    return doc

# <<< MODIFICADO run_correction_pass >>>
def run_correction_pass(model, input_txt_path, template_docx_path, author_name, book_name):
    """
    Executa o Passo 1: Corrige texto via API.
    NÃO salva DOCX aqui, apenas retorna o objeto doc e o texto corrigido.
    NÃO limpa mais o template.
    Retorna: (success_bool, doc_object|None, corrected_text_str|None, total_latency, total_prompt_tokens, total_output_tokens, total_tokens)
    """
    log_prefix = f"[{author_name}/{book_name}]"
    logger.info(f"{log_prefix} --- Iniciando Passo 1: Correção (sem salvar DOCX) ---")
    default_return = (False, None, None, 0, 0, 0, 0)
    try:
        with open(input_txt_path, "r", encoding="utf-8") as f: texto_original = f.read()
    except Exception as e: logger.error(f"{log_prefix} FATAL ao ler entrada: {e}"); return default_return

    logger.info(f"{log_prefix} Dividindo texto original em chunks...")
    text_chunks = create_chunks(texto_original, MAX_CHUNK_TOKENS, author_name, book_name)
    if not text_chunks: logger.error(f"{log_prefix} Nenhum chunk gerado."); return default_return

    # --- Carrega Template SEM LIMPAR ---
    doc = None
    try:
        if not os.path.exists(template_docx_path):
            logger.error(f"{log_prefix} FATAL: Template '{template_docx_path}' não encontrado."); return default_return
        doc = Document(template_docx_path) # Carrega template com conteúdo existente
        logger.info(f"{log_prefix} Template '{os.path.basename(template_docx_path)}' carregado (conteúdo preservado).")
        # Verifica estilo normal
        if NORMAL_STYLE_NAME not in doc.styles:
            logger.warning(f"{log_prefix} AVISO: Estilo '{NORMAL_STYLE_NAME}' NÃO encontrado no template.")
    except Exception as e_load_template:
        logger.error(f"{log_prefix} FATAL: Falha ao carregar template: {e_load_template}."); return default_return

    logger.info(f"{log_prefix} Iniciando chamadas à API para CORREÇÃO de {len(text_chunks)} chunks...")
    corrected_text_list_pass1 = []
    processed_chunks_count = 0; failed_chunks_count = 0
    total_latency_pass1 = 0; total_prompt_tokens_pass1 = 0; total_output_tokens_pass1 = 0; total_tokens_pass1 = 0

    progress_bar = tqdm(enumerate(text_chunks), total=len(text_chunks), desc=f"{log_prefix} P1: Corrigindo", unit="chunk", leave=False)
    for i, chunk in progress_bar:
        corrected_chunk, latency, p_tokens, o_tokens, t_tokens = format_with_ai_correction_only(
            model, chunk, author_name, book_name, is_first_chunk=(i == 0)
        )
        total_latency_pass1 += latency; total_prompt_tokens_pass1 += p_tokens; total_output_tokens_pass1 += o_tokens; total_tokens_pass1 += t_tokens

        # Acumula texto corrigido ou original (fallback) na lista
        if corrected_chunk is not None:
            corrected_text_list_pass1.append(corrected_chunk)
            processed_chunks_count += 1
        else:
            logger.warning(f"{log_prefix} Chunk {i+1} falhou na CORREÇÃO (API). Usando original no texto.")
            corrected_text_list_pass1.append(f"{AI_FAILURE_MARKER}\n\n{chunk}") # Adiciona marcador
            failed_chunks_count += 1

    # --- Adiciona o conteúdo corrigido ao objeto DOC carregado (APÓS o conteúdo do template) ---
    full_corrected_text = "\n\n".join(corrected_text_list_pass1)
    logger.info(f"{log_prefix} Adicionando texto corrigido ao DOCX carregado do template...")
    try:
        # Usamos a função auxiliar para adicionar o texto formatado
        doc = apply_formatting_to_doc(doc, full_corrected_text, NORMAL_STYLE_NAME, CHAPTER_PATTERNS, author_name, book_name, handle_note_markers=False)
    except Exception as e_apply:
        logger.error(f"{log_prefix} Erro CRÍTICO ao aplicar texto corrigido ao DOCX: {e_apply}")
        logger.error(traceback.format_exc())
        # Retorna falha, mas com o texto e stats que conseguiu coletar
        return (False, None, full_corrected_text, total_latency_pass1, total_prompt_tokens_pass1, total_output_tokens_pass1, total_tokens_pass1)

    # Não salva o DOCX aqui!
    logger.info(f"{log_prefix} --- Passo 1 concluído (Correção). Chunks OK: {processed_chunks_count}, Falhas: {failed_chunks_count} ---")
    logger.info(f"{log_prefix} Stats API P1: Lat:{total_latency_pass1:.2f}s, Toks:{total_tokens_pass1}(P:{total_prompt_tokens_pass1},O:{total_output_tokens_pass1})")

    # Retorna sucesso, o objeto doc modificado, o texto corrigido completo e as estatísticas
    success = failed_chunks_count == 0
    return (success, doc, full_corrected_text, total_latency_pass1, total_prompt_tokens_pass1, total_output_tokens_pass1, total_tokens_pass1)


# <<< MODIFICADO run_footnote_id_pass para retornar SÓ o texto marcado >>>
def run_footnote_id_pass(model, corrected_text_content, author_name, book_name):
    """
    Executa o Passo 2: Identifica notas no texto já corrigido.
    Retorna: (success_bool, marked_text_str|None, total_latency, total_prompt_tokens, total_output_tokens, total_tokens)
    """
    # (Função continua a mesma da última versão completa, apenas confirma o retorno)
    log_prefix = f"[{author_name}/{book_name}]"
    logger.info(f"{log_prefix} --- Iniciando Passo 2: Identificação de Notas ---")
    default_return = (False, None, 0, 0, 0, 0)
    if corrected_text_content is None: logger.error(f"{log_prefix} Input None. Abortando P2."); return default_return
    text_chunks = create_chunks(corrected_text_content, MAX_CHUNK_TOKENS, author_name, book_name)
    if not text_chunks: logger.error(f"{log_prefix} Nenhum chunk gerado. Abortando P2."); return default_return
    logger.info(f"{log_prefix} Iniciando API ID Notas em {len(text_chunks)} chunks...")
    marked_text_list_pass2 = []
    processed_chunks_count = 0; failed_chunks_count = 0
    total_latency_pass2 = 0; total_prompt_tokens_pass2 = 0; total_output_tokens_pass2 = 0; total_tokens_pass2 = 0
    progress_bar = tqdm(enumerate(text_chunks), total=len(text_chunks), desc=f"{log_prefix} P2: Notas", unit="chunk", leave=False)
    for i, chunk in progress_bar:
        marked_chunk, latency, p_tokens, o_tokens, t_tokens = format_with_ai_footnote_only( model, chunk, author_name, book_name )
        total_latency_pass2 += latency; total_prompt_tokens_pass2 += p_tokens; total_output_tokens_pass2 += o_tokens; total_tokens_pass2 += t_tokens
        if marked_chunk is not None: marked_text_list_pass2.append(marked_chunk); processed_chunks_count += 1
        else: logger.warning(f"{log_prefix} Chunk {i+1} falhou ID Notas (API). Usando original."); marked_text_list_pass2.append(chunk); failed_chunks_count += 1
    full_marked_text = "\n\n".join(marked_text_list_pass2)
    logger.info(f"{log_prefix} --- Passo 2 concluído. Chunks OK: {processed_chunks_count}, Falhas: {failed_chunks_count} ---")
    logger.info(f"{log_prefix} Stats API P2: Lat:{total_latency_pass2:.2f}s, Toks:{total_tokens_pass2}(P:{total_prompt_tokens_pass2},O:{total_output_tokens_pass2})")
    success_overall = failed_chunks_count == 0
    # Retorna sucesso (True se rodou, mesmo com falhas), texto marcado completo e estatísticas
    return (True, full_marked_text, total_latency_pass2, total_prompt_tokens_pass2, total_output_tokens_pass2, total_tokens_pass2)


# <<< REMOVIDA a função run_final_txt_generation >>>

# <<< NOVA Função para Integrar Notas e Salvar os DOCX >>>
def run_integrate_notes_and_save(doc_base_object, marked_text_string,
                                 output_path_clean, output_path_with_notes,
                                 template_path, # Precisa do template para estilos
                                 author_name, book_name):
    """
    Recebe o DOCX base (template + texto corrigido) e o texto com marcadores da IA.
    1. Salva o DOCX base como arquivo 'limpo' (sem notas).
    2. Extrai as notas do texto marcado.
    3. Substitui os marcadores da IA por [N] em negrito no DOCX base.
    4. Adiciona a seção de notas no final do DOCX base.
    5. Salva o DOCX modificado como arquivo 'com notas'.
    Retorna: bool indicando sucesso.
    """
    log_prefix = f"[{author_name}/{book_name}]"
    logger.info(f"{log_prefix} --- Iniciando Passo 3: Integração de Notas e Salvamento DOCX ---")

    # 1. Salvar Cópia Limpa (para tradutor)
    try:
        logger.info(f"{log_prefix} Salvando DOCX limpo (sem notas) em: {os.path.basename(output_path_clean)}")
        # Precisamos do objeto docx original do Passo 1 para salvar
        if doc_base_object is None:
             logger.error(f"{log_prefix} Objeto DOCX base do Passo 1 é None. Não é possível salvar cópia limpa."); return False
        doc_base_object.save(output_path_clean)
    except Exception as e_save_clean:
        logger.error(f"{log_prefix} ERRO ao salvar DOCX limpo '{os.path.basename(output_path_clean)}': {e_save_clean}")
        logger.error(traceback.format_exc())
        return False # Falha crítica se não puder salvar o input do tradutor

    # --- Processamento para o DOCX com notas ---
    doc_with_notes = doc_base_object # Trabalha no mesmo objeto após salvar a cópia limpa

    # 2. Extrair Notas do texto marcado
    notes_content_list = []
    note_markers_found = []
    try:
        # Encontra todos os marcadores e seus conteúdos
        for match in FOOTNOTE_MARKER_PATTERN.finditer(marked_text_string):
            full_marker = match.group(0) # Ex: [NOTA_NOME:Kropotkin][CONTEUDO_NOTA:Piotr...]
            note_type = match.group(1)
            note_ref = match.group(2)
            note_content = match.group(3).strip()
            if not note_content:
                logger.warning(f"{log_prefix} Nota com conteúdo vazio encontrada para ref '{note_ref}'. Ignorando.")
                continue
            notes_content_list.append(note_content)
            note_markers_found.append(full_marker) # Guarda o marcador original para substituição

        logger.info(f"{log_prefix} Extraídas {len(notes_content_list)} notas do texto marcado.")

        # Se não encontrou notas, apenas salva o doc final igual ao limpo e termina
        if not notes_content_list:
            logger.info(f"{log_prefix} Nenhuma nota encontrada para integrar. O arquivo final será igual ao 'sem notas'.")
            try:
                # Pode copiar o arquivo limpo ou salvar o objeto doc novamente
                shutil.copy2(output_path_clean, output_path_with_notes)
                logger.info(f"{log_prefix} Cópia final (sem notas) salva como: {os.path.basename(output_path_with_notes)}")
                return True
            except Exception as e_copy:
                 logger.error(f"{log_prefix} ERRO ao copiar arquivo final sem notas: {e_copy}"); return False

    except Exception as e_extract:
        logger.error(f"{log_prefix} ERRO ao extrair notas do texto marcado: {e_extract}")
        logger.error(traceback.format_exc())
        return False

    # 3. Substituir Marcadores no DOCX por [N] em negrito
    logger.info(f"{log_prefix} Substituindo {len(note_markers_found)} marcadores de nota no DOCX por [N]...")
    note_number = 1
    # Itera pelos marcadores encontrados NA ORDEM em que apareceram no texto
    for marker_to_replace in note_markers_found:
        replacement_tag = f"[{note_number}]"
        try:
            # Usa uma função auxiliar para encontrar e substituir texto que pode estar dividido entre runs
            # Esta função é complexa e crucial
            replaced_count = find_and_replace_in_docx(doc_with_notes, marker_to_replace, replacement_tag, bold_replacement=True)
            if replaced_count == 0:
                logger.warning(f"{log_prefix} Marcador de nota {note_number} ('{marker_to_replace[:30]}...') não encontrado no DOCX para substituição.")
            elif replaced_count > 1:
                 logger.warning(f"{log_prefix} Marcador de nota {note_number} ('{marker_to_replace[:30]}...') substituído {replaced_count} vezes.")
            note_number += 1
        except Exception as e_replace:
             logger.error(f"{log_prefix} Erro ao tentar substituir marcador {note_number} ('{marker_to_replace[:30]}...'): {e_replace}")
             # Decide se continua ou aborta? Vamos continuar por enquanto.

    # 4. Adicionar Seção de Notas no Final
    try:
        logger.info(f"{log_prefix} Adicionando seção com {len(notes_content_list)} notas ao final do DOCX...")
        # Adiciona um parágrafo em branco para separar, se necessário
        if doc_with_notes.paragraphs and doc_with_notes.paragraphs[-1].text.strip():
            doc_with_notes.add_paragraph()
        # Adiciona Título (pode usar um estilo de Título do template se existir)
        doc_with_notes.add_heading("Notas", level=1) # Ou level=2, 3...
        # Adiciona cada nota numerada
        for i, note_text in enumerate(notes_content_list):
            p = doc_with_notes.add_paragraph()
            # Adiciona número em negrito
            run_num = p.add_run(f"{i+1}. ")
            run_num.bold = True
            # Adiciona conteúdo da nota
            p.add_run(note_text)
            # Aplica estilo 'Normal' se disponível (para consistência)
            try:
                if NORMAL_STYLE_NAME in doc_with_notes.styles: p.style = doc_with_notes.styles[NORMAL_STYLE_NAME]
            except Exception: pass # Ignora erro de estilo aqui
    except Exception as e_append:
        logger.error(f"{log_prefix} ERRO ao adicionar seção de notas ao DOCX: {e_append}")
        logger.error(traceback.format_exc())
        return False # Falha se não conseguir adicionar notas

    # 5. Salvar DOCX Modificado com Notas
    try:
        logger.info(f"{log_prefix} Salvando DOCX final com notas em: {os.path.basename(output_path_with_notes)}")
        doc_with_notes.save(output_path_with_notes)
    except Exception as e_save_notes:
        logger.error(f"{log_prefix} ERRO ao salvar DOCX final com notas '{os.path.basename(output_path_with_notes)}': {e_save_notes}")
        logger.error(traceback.format_exc())
        return False

    logger.info(f"{log_prefix} --- Passo 3 concluído (Integração de Notas e Salvamento DOCX). ---")
    return True

# <<< NOVA Função Auxiliar para Substituir Texto em DOCX (Complexa!) >>>
# Baseado em abordagens comuns, pode precisar de ajustes
def find_and_replace_in_docx(doc_obj, text_to_find, text_to_replace, bold_replacement=False):
    """Encontra e substitui texto em um objeto Document, tentando lidar com runs divididos."""
    replace_count = 0
    # Expressão regular para encontrar o texto ignorando case
    # Usamos re.escape para tratar caracteres especiais no text_to_find
    pattern = re.compile(re.escape(text_to_find), re.IGNORECASE)

    for para in doc_obj.paragraphs:
        # Verifica se o padrão existe no parágrafo para otimizar
        if not pattern.search(para.text):
            continue

        # Combina runs adjacentes com a mesma formatação para simplificar a busca
        # (Esta parte pode ser complexa e opcional, mas ajuda com runs divididos)
        # Para simplificar por agora, vamos trabalhar com a busca no texto completo do parágrafo

        # Itera enquanto encontrar o padrão no texto atual do parágrafo
        while True:
            match = pattern.search(para.text)
            if not match:
                break # Sai do while se não encontrar mais

            # Achou! Agora a parte difícil: substituir mantendo o máximo de formatação
            # Esta é uma implementação SIMPLIFICADA. Uma versão robusta é muito mais complexa.
            # Ela basicamente reinsere o parágrafo com a substituição feita.
            # PODE PERDER formatação complexa dentro do parágrafo.

            start, end = match.span()
            para_text_original = para.text
            # Substitui a primeira ocorrência encontrada
            new_para_text = para_text_original[:start] + text_to_replace + para_text_original[end:]

            # Limpa runs antigos
            inline = para.runs
            for i in range(len(inline)):
                p = inline[0]._element
                p.getparent().remove(p)

            # Adiciona o novo texto (sem negrito por padrão)
            # A aplicação do negrito no replacement precisa ser mais inteligente,
            # talvez dividindo o text_to_replace se ele contiver formatação.
            # Por hora, aplicamos ao run inteiro do replacement se bold_replacement=True
            new_run = para.add_run(new_para_text)
            if bold_replacement:
                 # Esta abordagem simples aplica negrito a todo o texto substituído
                 # Não funciona bem se o texto substituído precisar ter partes não-negrito
                 # Mas para o caso de "**[N]**", onde N é um número, funciona.
                 # Precisamos garantir que text_to_replace seja tratado corretamente
                 # Se text_to_replace é `**[N]**`, adicionamos `[N]` com negrito.
                 match_num = re.match(r'\*\*\[(\d+)\]\*\*', text_to_replace)
                 if match_num:
                     para.clear() # Limpa o run que adicionamos
                     run_num = para.add_run(f"[{match_num.group(1)}]")
                     run_num.bold = True
                 else: # Caso geral (não deve acontecer aqui)
                     new_run.bold = True

            replace_count += 1
            #logger.debug(f"Substituído '{text_to_find}' por '{text_to_replace}' no parágrafo.")

            # IMPORTANTE: Como recriamos o parágrafo, precisamos re-verificar
            # o para.text atualizado, pois o match.span() original não vale mais.
            # O `while True` e `break` cuidam disso.

    # A busca/substituição em tabelas, cabeçalhos, rodapés não está implementada aqui.
    return replace_count


# --- Funções para Gerenciar Logs de Processados (Corrigidas e Inalteradas)---

def load_processed_files(filepath):
    processed = set()
    try: # << CORRIGIDO >>
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                cleaned = line.strip();
                if cleaned: processed.add(cleaned)
        logger.info(f"Carregados {len(processed)} registros de CORREÇÕES de '{filepath}'.")
    except FileNotFoundError: logger.info(f"Log de correções '{filepath}' não encontrado.")
    except Exception as e: logger.error(f"Erro ao carregar log de correções '{filepath}': {e}")
    return processed

def log_processed_file(filepath, file_identifier):
    try:
        with open(filepath, 'a', encoding='utf-8') as f: f.write(f"{file_identifier}\n")
    except Exception as e: logger.error(f"Erro ao registrar '{file_identifier}' no log de correções '{filepath}': {e}")

def load_translated_files(filepath):
    processed = set()
    try: # << CORRIGIDO >>
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                cleaned = line.strip();
                if cleaned: processed.add(cleaned)
        logger.info(f"Carregados {len(processed)} registros de TRADUÇÕES de '{filepath}'.")
    except FileNotFoundError: logger.info(f"Log de traduções '{filepath}' não encontrado.")
    except Exception as e: logger.error(f"Erro ao carregar log de traduções '{filepath}': {e}")
    return processed

def log_translated_file(filepath, file_identifier):
    try:
        with open(filepath, 'a', encoding='utf-8') as f: f.write(f"{file_identifier}\n")
        logger.debug(f"Registrado '{file_identifier}' como TRADUZIDO em '{filepath}'.")
    except Exception as e: logger.error(f"Erro ao registrar '{file_identifier}' no log de traduções '{filepath}': {e}")


# --- FUNÇÃO DE ENVIO DE E-MAIL (Inalterada da última versão) ---
def send_completion_email(sender_email, sender_password, recipient_email, smtp_server, smtp_port,
                          processed_correction, skipped_correction, failed_correction,
                          processed_translation, skipped_translation, failed_translation,
                          total_duration_seconds,
                          main_log_path, processed_log_path, translated_log_path,
                          total_correction_latency_secs, total_correction_tokens,
                          total_footnote_latency_secs, total_footnote_tokens,
                          avg_correction_time_secs, total_correction_time_secs,
                          avg_translation_time_secs, total_translation_time_secs,
                          processed_correction_books, skipped_correction_books, failed_correction_books,
                          processed_translation_books, skipped_translation_books, failed_translation_books
                          ):
    """Envia um e-mail de notificação de conclusão com resumo detalhado e estatísticas."""
    # (Função send_completion_email permanece inalterada - como na última versão completa)
    global email_configured
    if not email_configured: logger.warning("Envio e-mail desativado."); return
    logger.info(f"Preparando e-mail para {recipient_email}...")
    subject = "Script Processador Livros (Correção+Tradução) - Concluído"
    body = f"""Olá,\n\nO script concluiu a execução.\n\nResumo Geral:\n{'-'*50}\n"""
    body += f"- Tempo Total: {total_duration_seconds:.2f}s ({total_duration_seconds/60:.2f}m)\n"
    body += f"\nResumo Correção:\n{'-'*50}\n"
    body += f"- Corrigidos OK: {processed_correction}\n- Pulados: {skipped_correction}\n- Falhas: {failed_correction}\n"
    if processed_correction > 0:
        body += f"- Tempo Total Correção (OK): {total_correction_time_secs:.2f}s ({total_correction_time_secs/60:.2f}m)\n"
        body += f"- Tempo Médio Correção: {avg_correction_time_secs:.2f}s\n"
        body += f"- API P1 (Correção): Lat {total_correction_latency_secs:.2f}s / Tokens {total_correction_tokens}\n"
        body += f"- API P2 (Notas):    Lat {total_footnote_latency_secs:.2f}s / Tokens {total_footnote_tokens}\n"
    body += f"\nResumo Tradução:\n{'-'*50}\n"
    body += f"- Traduzidos OK: {processed_translation}\n- Pulados: {skipped_translation}\n- Falhas: {failed_translation}\n"
    if processed_translation > 0:
        body += f"- Tempo Total Tradução (OK): {total_translation_time_secs:.2f}s ({total_translation_time_secs/60:.2f}m)\n"
        body += f"- Tempo Médio Tradução: {avg_translation_time_secs:.2f}s\n"
    body += f"\nDetalhes por Livro:\n{'-'*50}\n"
    if processed_correction_books: body += f"\nCorrigidos OK ({len(processed_correction_books)}):\n - " + "\n - ".join(processed_correction_books) + "\n"
    if skipped_correction_books: body += f"\nPulados Correção ({len(skipped_correction_books)}):\n - " + "\n - ".join(skipped_correction_books) + "\n"
    if failed_correction_books: body += f"\nFalha Correção ({len(failed_correction_books)}):\n - " + "\n - ".join(failed_correction_books) + "\n"
    if processed_translation_books: body += f"\nTraduzidos OK ({len(processed_translation_books)}):\n - " + "\n - ".join(processed_translation_books) + "\n"
    if skipped_translation_books: body += f"\nPulados Tradução ({len(skipped_translation_books)}):\n - " + "\n - ".join(skipped_translation_books) + "\n"
    if failed_translation_books: body += f"\nFalha Tradução ({len(failed_translation_books)}):\n - " + "\n - ".join(failed_translation_books) + "\n"
    total_listed = len(processed_correction_books)+len(skipped_correction_books)+len(failed_correction_books)+len(processed_translation_books)+len(skipped_translation_books)+len(failed_translation_books)
    if total_listed > 50: body += "\n(Nota: Listas de livros podem estar longas. Consulte logs.)\n"
    body += f"\n{'-'*50}\nLogs:\n- Detalhado: {os.path.abspath(main_log_path)}\n- Correções OK: {os.path.abspath(processed_log_path)}\n- Traduções OK: {os.path.abspath(translated_log_path)}\n\nAtenciosamente,\nScript Processador"
    message = EmailMessage(); message['Subject'] = subject; message['From'] = sender_email; message['To'] = recipient_email; message.set_content(body)
    context = ssl.create_default_context()
    try:
        server = None; logger.info(f"Conectando SMTP: {smtp_server}:{smtp_port}...")
        if smtp_port == 465: server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=30); server.login(sender_email, sender_password)
        else: server = smtplib.SMTP(smtp_server, smtp_port, timeout=30); server.ehlo(); server.starttls(context=context); server.ehlo(); server.login(sender_email, sender_password)
        logger.info("Enviando e-mail resumo..."); server.send_message(message); logger.info(f"✅ E-mail enviado para {recipient_email}.")
    except Exception as e: logger.error(f"ERRO ao enviar e-mail: {e}"); logger.debug(traceback.format_exc())
    finally:
        if server:
            try: server.quit()
            except Exception: pass


# --- FUNÇÃO PRINCIPAL (main - Refatorada para novo fluxo) ---
def main():
    start_time_main = time.time()
    logger.info("========================================================")
    logger.info(f"Iniciando Processador (v Refatorado) - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    # ... (logs iniciais de config) ...
    logger.info("========================================================")

    processed_files_set = load_processed_files(PROCESSED_LOG_FILE)
    translated_files_set = load_translated_files(TRANSLATED_LOG_FILE)

    if not os.path.isdir(BASE_INPUT_TXT_DIR): logger.error(f"FATAL: Diretório '{BASE_INPUT_TXT_DIR}' não encontrado!"); return
    try: author_folders = sorted([f for f in os.listdir(BASE_INPUT_TXT_DIR) if os.path.isdir(os.path.join(BASE_INPUT_TXT_DIR, f))])
    except Exception as e: logger.error(f"FATAL: Erro listar autores: {e}"); return
    if not author_folders: logger.warning(f"Nenhuma pasta de autor encontrada."); return
    logger.info(f"Autores encontrados ({len(author_folders)}): {', '.join(author_folders)}")

    # --- Inicializa Contadores e Acumuladores ---
    # (Contadores e Acumuladores como na versão anterior)
    total_books_processed_correction = 0; total_books_skipped_correction = 0; total_books_failed_correction = 0
    total_translation_processed = 0; total_translation_skipped = 0; total_translation_failed = 0
    grand_total_correction_latency = 0; grand_total_correction_prompt_tokens = 0; grand_total_correction_output_tokens = 0; grand_total_correction_total_tokens = 0
    grand_total_footnote_latency = 0; grand_total_footnote_prompt_tokens = 0; grand_total_footnote_output_tokens = 0; grand_total_footnote_total_tokens = 0
    correction_times = []; translation_times = []
    processed_correction_list = []; skipped_correction_list = []; failed_correction_list = []
    processed_translation_list = []; skipped_translation_list = []; failed_translation_list = []

    # === LOOP PRINCIPAL: AUTOR ===
    for author_name in author_folders:
        author_input_dir = os.path.join(BASE_INPUT_TXT_DIR, author_name)
        logger.info(f"--- Verificando Autor: {author_name} ---")
        try: # Busca recursiva
            search_pattern = os.path.join(author_input_dir, '**', '*.txt')
            input_txt_files_found = sorted(glob.glob(search_pattern, recursive=True))
            input_txt_files = [f for f in input_txt_files_found if not (os.path.basename(f).endswith(FINAL_NUMBERED_TXT_BASENAME) or os.path.basename(f).endswith(NOTES_TXT_FILE_BASENAME) or os.path.basename(f).startswith("backup_"))] # FINAL_NUMBERED_TXT_BASENAME e NOTES_TXT_FILE_BASENAME não são mais usados, mas mantemos o filtro por segurança
            #logger.info(f"[{author_name}] Encontrados {len(input_txt_files_found)} .txt (antes de filtrar), {len(input_txt_files)} válidos.")
        except Exception as e: logger.error(f"[{author_name}] Erro buscar .txt: {e}"); continue
        if not input_txt_files: logger.warning(f"[{author_name}] Nenhum .txt válido encontrado."); continue
        logger.info(f"[{author_name}] Processando {len(input_txt_files)} arquivos .txt válidos.")

        # === LOOP INTERNO: LIVRO ===
        for input_txt_path in input_txt_files:
            try: # Try geral para processamento do livro
                # --- Definição de Paths e Identificadores ---
                relative_path = os.path.relpath(input_txt_path, BASE_INPUT_TXT_DIR)
                file_identifier = relative_path.replace('\\', '/')
                log_prefix_book = f"[{file_identifier}]"
                logger.info(f"--------------------------------------------------------")
                logger.info(f"{log_prefix_book} Processando Livro...")

                path_parts = file_identifier.split('/')
                author_name_from_path = path_parts[0]
                book_subpath_parts = path_parts[1:-1]
                book_filename = path_parts[-1]
                base_book_name = os.path.splitext(book_filename)[0]
                book_subdir_rel = os.path.join(*book_subpath_parts)
                author_output_docx_book_dir = os.path.join(BASE_OUTPUT_DOCX_DIR, author_name_from_path, book_subdir_rel)
                # Removido: author_output_txt_book_dir não é mais necessário
                os.makedirs(author_output_docx_book_dir, exist_ok=True) # Garante que o diretório de saída DOCX existe

                output_path_clean_docx = os.path.join(author_output_docx_book_dir, f"{base_book_name}_{FINAL_DOCX_BASENAME}")
                output_path_notes_docx = os.path.join(author_output_docx_book_dir, f"{base_book_name}_{FINAL_DOCX_WITH_NOTES_BASENAME}") # NOVO NOME
                translated_docx_path = os.path.join(author_output_docx_book_dir, f"{base_book_name}_{FINAL_DOCX_BASENAME.replace('.docx', TRANSLATED_DOCX_SUFFIX)}")
            except Exception as e_path:
                logger.error(f"Erro fatal processando caminhos para '{input_txt_path}': {e}"); logger.error(traceback.format_exc());
                failed_correction_list.append(f"{file_identifier} (Erro de Path)") # Adiciona à falha de correção, pois não pode nem começar
                total_books_failed_correction += 1
                continue # Pula para o próximo livro

            correction_step_success = False # Flag para sucesso da *etapa* de correção completa

            # --- Verifica Status da CORREÇÃO ---
            if file_identifier in processed_files_set:
                logger.info(f"{log_prefix_book} CORREÇÃO já feita. Pulando etapa de correção.")
                total_books_skipped_correction += 1
                skipped_correction_list.append(file_identifier)
                correction_step_success = True # Permite tentar a tradução
                # Precisamos garantir que output_path_clean_docx aponta para o arquivo que deve existir
                output_docx_path_for_translator = output_path_clean_docx # Caminho que o tradutor espera
            else:
                # --- Executa a CORREÇÃO (Passos 1 e 2) ---
                logger.info(f"{log_prefix_book} Iniciando processamento (Correção e ID Notas)...")
                book_start_time = time.time()
                book_correction_success = False # Sucesso específico dos passos de correção deste livro

                # Acumuladores de stats para ESTE livro
                book_corr_latency = 0; book_corr_p_tokens = 0; book_corr_o_tokens = 0; book_corr_t_tokens = 0
                book_note_latency = 0; book_note_p_tokens = 0; book_note_o_tokens = 0; book_note_t_tokens = 0

                try:
                    # PASSO 1: Correção (retorna obj doc, texto string, stats)
                    # Template NÃO é mais limpo aqui dentro
                    pass1_ok, doc_base_obj, corrected_text, lat1, p1, o1, t1 = run_correction_pass(
                        gemini_model, input_txt_path, TEMPLATE_DOCX, author_name_from_path, base_book_name
                    )
                    book_corr_latency+=lat1; book_corr_p_tokens+=p1; book_corr_o_tokens+=o1; book_corr_t_tokens+=t1

                    if not pass1_ok or doc_base_obj is None or corrected_text is None:
                        logger.error(f"{log_prefix_book} Passo 1 (Correção) FALHOU ou retornou None.")
                        all_steps_successful_for_book = False # Erro geral para o livro
                    else:
                        # PASSO 2: Identificação de Notas (usa texto corrigido string)
                        pass2_ok, marked_text, lat2, p2, o2, t2 = run_footnote_id_pass(
                            gemini_model, corrected_text, author_name_from_path, base_book_name
                        )
                        book_note_latency+=lat2; book_note_p_tokens+=p2; book_note_o_tokens+=o2; book_note_t_tokens+=t2

                        if not pass2_ok or marked_text is None:
                            logger.error(f"{log_prefix_book} Passo 2 (ID Notas) FALHOU ou retornou None.")
                            all_steps_successful_for_book = False
                        else:
                            # << NOVO PASSO 3: Integração e Salvamento >>
                            pass3_ok = run_integrate_notes_and_save(
                                doc_base_obj, marked_text, # Objeto doc e texto marcado
                                output_path_clean_docx, # Onde salvar o doc limpo
                                output_path_notes_docx, # Onde salvar o doc com notas
                                TEMPLATE_DOCX, # Passa o template de novo (para estilos)
                                author_name_from_path, base_book_name
                            )
                            if not pass3_ok:
                                logger.error(f"{log_prefix_book} Passo 3 (Integração/Salvar DOCX) FALHOU.")
                                all_steps_successful_for_book = False
                            else:
                                book_correction_success = True # Todos os passos da correção OK

                except Exception as e_corr_steps:
                     logger.error(f"{log_prefix_book} Erro inesperado CORREÇÃO: {e_corr_steps}"); logger.error(traceback.format_exc()); book_correction_success = False

                book_end_time = time.time()
                book_total_time = book_end_time - book_start_time

                if book_correction_success:
                    logger.info(f"✅ {log_prefix_book} Etapa de CORREÇÃO SUCESSO em {book_total_time:.2f} seg.")
                    log_processed_file(PROCESSED_LOG_FILE, file_identifier); processed_files_set.add(file_identifier)
                    total_books_processed_correction += 1; correction_step_success = True
                    processed_correction_list.append(file_identifier)
                    correction_times.append(book_total_time)
                    # Acumula stats GERAIS
                    grand_total_correction_latency += book_corr_latency; grand_total_correction_prompt_tokens += book_corr_p_tokens; grand_total_correction_output_tokens += book_corr_o_tokens; grand_total_correction_total_tokens += book_corr_t_tokens
                    grand_total_footnote_latency += book_note_latency; grand_total_footnote_prompt_tokens += book_note_p_tokens; grand_total_footnote_output_tokens += book_note_o_tokens; grand_total_footnote_total_tokens += book_note_t_tokens
                    output_docx_path_for_translator = output_path_clean_docx # Confirma o path para o tradutor
                else:
                    logger.warning(f"⚠️ {log_prefix_book} Etapa de CORREÇÃO FALHAS em {book_total_time:.2f} seg.")
                    total_books_failed_correction += 1; correction_step_success = False
                    failed_correction_list.append(file_identifier)
                    output_docx_path_for_translator = None # Não há arquivo para traduzir

            # --- ETAPA DE TRADUÇÃO ---
            if correction_step_success:
                #logger.info(f"{log_prefix_book} Verificando status (Tradução)...")
                # Usa output_docx_path_for_translator definido acima
                if output_docx_path_for_translator is None or not os.path.exists(output_docx_path_for_translator):
                     logger.warning(f"{log_prefix_book} Input DOCX '{os.path.basename(output_path_clean_docx)}' tradução não encontrado. Pulando.");
                     total_translation_failed += 1
                     failed_translation_list.append(f"{file_identifier} (Input DOCX ausente)")
                elif file_identifier in translated_files_set:
                    logger.info(f"{log_prefix_book} TRADUÇÃO já feita. Pulando.");
                    total_translation_skipped += 1
                    skipped_translation_list.append(file_identifier)
                else:
                    logger.info(f"{log_prefix_book} >>> Iniciando TRADUÇÃO HÍBRIDA...")
                    translation_start_time = time.time()
                    # translated_docx_path já definido
                    if not os.path.exists(PATH_TO_TRANSLATOR_SCRIPT):
                         logger.error(f"{log_prefix_book} ERRO CRÍTICO: Script tradutor '{PATH_TO_TRANSLATOR_SCRIPT}' não encontrado.");
                         total_translation_failed += 1
                         failed_translation_list.append(f"{file_identifier} (Script tradutor não encontrado)")
                    else:
                        try:
                            command = [ sys.executable, PATH_TO_TRANSLATOR_SCRIPT, '--input', output_docx_path_for_translator, '--output', translated_docx_path, '--words', str(NUM_WORDS_TO_TRANSLATE) ]
                            logger.info(f"{log_prefix_book} Executando: {' '.join(command)}")
                            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', check=False)
                            translation_end_time = time.time()
                            translation_total_time = translation_end_time - translation_start_time
                            if result.returncode == 0:
                                logger.info(f"✅ {log_prefix_book} TRADUÇÃO HÍBRIDA SUCESSO em {translation_total_time:.2f} seg.")
                                log_translated_file(TRANSLATED_LOG_FILE, file_identifier); translated_files_set.add(file_identifier)
                                total_translation_processed += 1
                                processed_translation_list.append(file_identifier)
                                translation_times.append(translation_total_time)
                                if result.stdout: logger.debug(f"{log_prefix_book} Saída tradutor:\n{result.stdout}")
                            else:
                                logger.error(f"❌ {log_prefix_book} TRADUÇÃO HÍBRIDA FALHOU (código: {result.returncode}) em {translation_total_time:.2f} seg.")
                                if result.stderr: logger.error(f"{log_prefix_book} Erro tradutor:\n{result.stderr}")
                                else: logger.error(f"{log_prefix_book} Tradutor não reportou erro específico.")
                                total_translation_failed += 1
                                failed_translation_list.append(f"{file_identifier} (Erro script: {result.returncode})")
                        except Exception as e_translate_sub:
                             logger.error(f"{log_prefix_book} Erro CRÍTICO subprocesso tradução: {e_translate_sub}"); logger.error(traceback.format_exc());
                             total_translation_failed += 1
                             failed_translation_list.append(f"{file_identifier} (Exceção subprocesso)")
            # --- Fim Tradução ---
            logger.info(f"{log_prefix_book} --- Fim processamento livro ---")
        # Fim loop livros
        logger.info(f"--- Concluída verificação Autor: {author_name} ---")
    # --- Fim loop autores ---

    end_time_main = time.time()
    total_time_main = end_time_main - start_time_main

    # --- Cálculos Finais de Tempo e Stats ---
    total_corr_time_ok = sum(correction_times)
    avg_corr_time_ok = total_corr_time_ok / len(correction_times) if correction_times else 0
    total_trans_time_ok = sum(translation_times)
    avg_trans_time_ok = total_trans_time_ok / len(translation_times) if translation_times else 0

    # --- Resumo Final Logging ---
    logger.info("===================== RESUMO FINAL =====================")
    logger.info(f"Tempo total geral: {total_time_main:.2f} seg ({total_time_main/60:.2f} min).")
    # Correção
    logger.info("--- Resumo Etapa de Correção ---")
    logger.info(f"Livros Corrigidos OK: {total_books_processed_correction}")
    logger.info(f"Livros Pulados (já corrigidos): {total_books_skipped_correction}")
    logger.info(f"Livros com Falha na Correção: {total_books_failed_correction}")
    if correction_times:
        logger.info(f"Tempo Total Correção (livros OK): {total_corr_time_ok:.2f} seg ({total_corr_time_ok/60:.2f} min)")
        logger.info(f"Tempo Médio por Correção: {avg_corr_time_ok:.2f} seg")
    # Stats API Correção (Passo 1 + Passo 2)
    logger.info(f"API Correção (Passo 1) - Latência Total: {grand_total_correction_latency:.2f}s / Tokens Totais: {grand_total_correction_total_tokens} (P: {grand_total_correction_prompt_tokens}, O: {grand_total_correction_output_tokens})")
    logger.info(f"API Notas (Passo 2)    - Latência Total: {grand_total_footnote_latency:.2f}s / Tokens Totais: {grand_total_footnote_total_tokens} (P: {grand_total_footnote_prompt_tokens}, O: {grand_total_footnote_output_tokens})")
    # Tradução
    logger.info("--- Resumo Etapa de Tradução ---")
    logger.info(f"Livros Traduzidos OK: {total_translation_processed}")
    logger.info(f"Livros Pulados (já traduzidos): {total_translation_skipped}")
    logger.info(f"Livros com Falha na Tradução: {total_translation_failed}")
    if translation_times:
        logger.info(f"Tempo Total Tradução (livros OK): {total_trans_time_ok:.2f} seg ({total_trans_time_ok/60:.2f} min)")
        logger.info(f"Tempo Médio por Tradução: {avg_trans_time_ok:.2f} seg")
    # Logs e Arquivos
    logger.info("--- Logs ---")
    logger.info(f"Log detalhado: {os.path.abspath(log_filepath)}")
    logger.info(f"Log de correções concluídas: {os.path.abspath(PROCESSED_LOG_FILE)}")
    logger.info(f"Log de traduções concluídas: {os.path.abspath(TRANSLATED_LOG_FILE)}")
    logger.info("--- Arquivos Gerados (Estrutura Exemplo) ---")
    logger.info(f"  - DOCX Limpo (p/ Tradutor): {BASE_OUTPUT_DOCX_DIR}/<Autor>/<SubpastaLivro>/<Livro>_{FINAL_DOCX_BASENAME}")
    logger.info(f"  - DOCX Com Notas no Fim:    {BASE_OUTPUT_DOCX_DIR}/<Autor>/<SubpastaLivro>/<Livro>_{FINAL_DOCX_WITH_NOTES_BASENAME}") # Atualizado
    # logger.info(f"  - TXT Numerado:   {BASE_OUTPUT_TXT_DIR}/<Autor>/<SubpastaLivro>/<Livro>_{FINAL_NUMBERED_TXT_BASENAME}") # Removido
    # logger.info(f"  - TXT Notas:      {BASE_OUTPUT_TXT_DIR}/<Autor>/<SubpastaLivro>/<Livro>_{NOTES_TXT_FILE_BASENAME}") # Removido
    logger.info(f"  - DOCX Traduzido: {BASE_OUTPUT_DOCX_DIR}/<Autor>/<SubpastaLivro>/<Livro>_{FINAL_DOCX_BASENAME.replace('.docx', TRANSLATED_DOCX_SUFFIX)}")
    logger.info("========================================================")

    # === Envio de E-mail FINAL (com mais stats e listas de livros) ===
    if email_configured:
        send_completion_email(
            sender_email=EMAIL_SENDER_ADDRESS, sender_password=EMAIL_SENDER_APP_PASSWORD,
            recipient_email=EMAIL_RECIPIENT_ADDRESS, smtp_server=EMAIL_SMTP_SERVER, smtp_port=EMAIL_SMTP_PORT,
            # Contadores
            processed_correction=total_books_processed_correction, skipped_correction=total_books_skipped_correction, failed_correction=total_books_failed_correction,
            processed_translation=total_translation_processed, skipped_translation=total_translation_skipped, failed_translation=total_translation_failed,
            # Tempos Gerais e Logs
            total_duration_seconds=total_time_main,
            main_log_path=log_filepath, processed_log_path=PROCESSED_LOG_FILE, translated_log_path=TRANSLATED_LOG_FILE,
            # Tempos Específicos
            avg_correction_time_secs=avg_corr_time_ok, total_correction_time_secs=total_corr_time_ok,
            avg_translation_time_secs=avg_trans_time_ok, total_translation_time_secs=total_trans_time_ok,
            # Stats API
            total_correction_latency_secs=grand_total_correction_latency, total_correction_tokens=grand_total_correction_total_tokens,
            total_footnote_latency_secs=grand_total_footnote_latency, total_footnote_tokens=grand_total_footnote_total_tokens,
            # << Listas de Livros >>
            processed_correction_books=processed_correction_list, skipped_correction_books=skipped_correction_list, failed_correction_books=failed_correction_list,
            processed_translation_books=processed_translation_list, skipped_translation_books=skipped_translation_list, failed_translation_books=failed_translation_list
        )
    else:
        logger.info("Envio de e-mail de resumo final pulado (configuração ausente ou incompleta no .env).")

# --- Ponto de Entrada ---
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\nProcesso interrompido manualmente (Ctrl+C).")
    except Exception as e_main:
        logger.critical(f"FATAL: Erro inesperado na execução de main(): {e_main}")
        logger.critical(traceback.format_exc())
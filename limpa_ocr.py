import re
import os
import logging
import argparse # Para facilitar a passagem de nomes de arquivo pela linha de comando

# python limpa_ocr.py rascunho.txt rascunho-limpo.txt
# === SETUP LOGGING ===
log_dir = "logs_preprocess" # Diretório de log separado
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_filepath = os.path.join(log_dir, "ocr_preprocessor.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filepath, encoding='utf-8'),
        logging.StreamHandler() # Mostra logs no console também
    ]
)
logger = logging.getLogger(__name__)

# === FUNÇÃO DE PRÉ-PROCESSAMENTO REGEX ===

def preprocess_ocr_text_standalone(text):
    """
    Realiza um pré-processamento simples no texto OCRizado em português
    para corrigir erros comuns e repetitivos usando Regex.
    Foco em manter a integridade do português e ser seguro.

    Args:
        text (str): O texto original OCRizado.

    Returns:
        str: O texto pré-processado.
    """
    if not text:
        return ""

    logger.info("Aplicando regras de pré-processamento Regex standalone...")
    processed_text = text
    rules_applied_count = 0

    # Dicionário de substituições diretas e seguras
    # (chave: padrão regex, valor: substituição)
    replacements = {
        # --- Correção de Acentos Comuns Desanexados (prefixo) ---
        # Agudos
        r"´a": "á", r"´e": "é", r"´i": "í", r"´o": "ó", r"´u": "ú",
        r"´A": "Á", r"´E": "É", r"´I": "Í", r"´O": "Ó", r"´U": "Ú",
        # Grave
        r"`a": "à", r"`A": "À",
        # Til
        r"~a": "ã", r"~o": "õ",
        r"~A": "Ã", r"~O": "Õ",
        # Circunflexo (escapar ^)
        r"\^a": "â", r"\^e": "ê", r"\^o": "ô",
        r"\^A": "Â", r"\^E": "Ê", r"\^O": "Ô",

        # --- Correção de Cedilha Comum ---
        r"c,": "ç", r"C,": "Ç",
        r"c;": "ç", r"C;": "Ç",
        # Considerar c. -> ç APENAS se for MUITO frequente e seguro no seu OCR
        # r"c\.": "ç", r"C\.": "Ç", # CUIDADO: pode afetar abreviações

        # --- Correção de problemas comuns de espaçamento ---
        r"\s{2,}": " ",             # Espaços múltiplos -> espaço único
        r"\s+([,.;:])": r"\1",      # Remove espaços antes de , . ; :
        r"([\({\[])\s+": r"\1",     # Remove espaços depois de ( { [
        r"\s+([\)\]}])": r"\1",     # Remove espaços antes de ) } ]

         # --- Correção de Hífens de Quebra de Linha (tentativa simples) ---
         # Junta palavras quebradas por hífen no final da linha seguido por
         # quebra de linha e letras minúsculas no início da próxima.
         # Ex: "palav-\nra" -> "palavra"
         # CUIDADO: Pode juntar palavras hifenizadas legítimas se a quebra coincidir. Teste!
         r"(\w+)-\n\s*([a-záéíóúâêôàãõüç]+)": r"\1\2",

        # --- OUTRAS SUBSTITUIÇÕES (ADICIONE COM CUIDADO) ---
        # Ex: r"ü": "u", r"Ü": "U", # Se ü for sempre erro
        # Ex: r"ﬁ": "fi", r"ﬂ": "fl", # Ligaturas comuns

        # --- REMOÇÃO DE CARACTERES INVÁLIDOS (USE COM MUITA CAUTELA) ---
        # Adicione aqui APENAS caracteres que você tem CERTEZA que são lixo.
        # Ex: r"[■□◆◇▲△▼▽]": "", # Remover alguns símbolos geométricos comuns de OCR ruim
    }

    # Aplicar cada substituição
    for pattern, replacement in replacements.items():
        try:
            # re.sub retorna uma nova string com as substituições feitas
            new_text = re.sub(pattern, replacement, processed_text)
            if new_text != processed_text:
                rules_applied_count += 1
                # logger.debug(f"Regra aplicada: '{pattern}' -> '{replacement}'")
            processed_text = new_text
        except re.error as e:
            logger.warning(f"Erro na expressão regular '{pattern}': {e}. Pulando esta regra.")

    # Limpeza final de espaços nas extremidades de cada linha (opcional)
    # lines = processed_text.splitlines()
    # processed_text = "\n".join(line.strip() for line in lines)

    logger.info(f"Pré-processamento Regex concluído. {rules_applied_count} tipos de regras tiveram efeito.")
    # Remove espaços em branco extras no início/fim do texto completo
    return processed_text.strip()

# === FUNÇÃO PRINCIPAL DO SCRIPT ===

def main(input_file, output_file):
    """
    Função principal que lê o arquivo de entrada, pré-processa e salva no arquivo de saída.
    """
    logger.info(f"--- Iniciando Script de Pré-processamento OCR ---")
    logger.info(f"Arquivo de Entrada: {input_file}")
    logger.info(f"Arquivo de Saída:   {output_file}")

    # --- Ler Arquivo de Entrada ---
    try:
        logger.info(f"Lendo arquivo de entrada: {input_file}")
        with open(input_file, "r", encoding="utf-8") as f:
            original_content = f.read()
        logger.info(f"Arquivo lido com sucesso ({len(original_content)} caracteres).")
    except FileNotFoundError:
        logger.error(f"Erro Fatal: Arquivo de entrada '{input_file}' não encontrado.")
        return # Sai da função main
    except Exception as e:
        logger.error(f"Erro Fatal ao ler o arquivo '{input_file}': {e}")
        return # Sai da função main

    # --- Pré-processar o Conteúdo ---
    processed_content = preprocess_ocr_text_standalone(original_content)
    logger.info(f"Texto pré-processado ({len(processed_content)} caracteres).")

    # --- Salvar Arquivo de Saída ---
    try:
        logger.info(f"Salvando texto pré-processado em: {output_file}")
        # Garante que o diretório de saída exista, se necessário
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
             os.makedirs(output_dir)
             logger.info(f"Diretório de saída criado: {output_dir}")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(processed_content)
        logger.info(f"Arquivo de saída salvo com sucesso: {output_file}")
    except Exception as e:
        logger.error(f"Erro Fatal ao salvar o arquivo '{output_file}': {e}")

    logger.info(f"--- Script de Pré-processamento OCR Concluído ---")


# === EXECUÇÃO DO SCRIPT ===
if __name__ == "__main__":
    # Configuração para aceitar nomes de arquivo via linha de comando
    parser = argparse.ArgumentParser(description="Pré-processador Regex para textos OCRizados em Português.")
    parser.add_argument("input_file", help="Caminho para o arquivo de texto de entrada (.txt).")
    parser.add_argument("output_file", help="Caminho para o arquivo de texto de saída (.txt) onde o resultado será salvo.")

    args = parser.parse_args()

    # Chama a função principal com os nomes de arquivo fornecidos
    main(args.input_file, args.output_file)
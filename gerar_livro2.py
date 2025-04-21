from openai import OpenAI
from docx import Document
from dotenv import load_dotenv
import os

# === CARREGA VARIÁVEIS DE AMBIENTE DO .env ===
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

# === CONFIGURAÇÕES ===
INPUT_TXT = "rascunho.txt"
TEMPLATE_DOCX = "Estrutura.docx"
OUTPUT_DOCX = "Livro_Final_Formatado.docx"

# === SETUP OPENAI ===
client = OpenAI(api_key=API_KEY)

# === PASSO 1 – Lê o texto bruto ===
with open(INPUT_TXT, "r", encoding="utf-8") as f:
    texto_original = f.read()

# === PASSO 2 – Prompt para formatar como livro ===
prompt = f"""
Você é um editor literário. Corrija e formate o texto a seguir como um livro pronto para publicação.

Regras:
- Corrija erros gramaticais, ortográficos e de concordância
- Utilize títulos centralizados para capítulos
- Use parágrafos justificados com espaçamento apropriado
- Separe capítulos com quebras de página (escreva como: ===QUEBRA_DE_PAGINA===)
- Mantenha estilo literário fluido e bem escrito

Texto:
\"\"\"{texto_original}\"\"\"
"""

print("🔁 Enviando para ChatGPT...")
response = client.chat.completions.create(
    model="gpt-4-turbo",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7,
    max_tokens=4096
)

texto_formatado = response.choices[0].message.content
print("✅ Texto formatado recebido.")

# === PASSO 3 – Carrega o template ===
doc = Document(TEMPLATE_DOCX)

# === PASSO 4 – Limpa corpo do documento (opcional) ===
doc._body.clear_content()

# === PASSO 5 – Insere texto formatado no corpo ===
for par in texto_formatado.split("\n\n"):
    par = par.strip()
    if not par:
        continue

    if "===QUEBRA_DE_PAGINA===" in par:
        doc.add_page_break()
    else:
        doc.add_paragraph(par)

# === PASSO 6 – Salva o novo documento ===
doc.save(OUTPUT_DOCX)
print(f"📘 Livro gerado com sucesso: {OUTPUT_DOCX}")
# -*- coding: utf-8 -*-
"""
PROCESSADOR LOCAL - USA VERTEX AI COM CREDENCIAIS GCLOUD
Processa livros TXT -> DOCX com OCR, tradução e notas de rodapé
"""

import os
import json
import asyncio
import aiohttp
import re
import zipfile
from pathlib import Path
from io import BytesIO
from lxml import etree
import subprocess
import sys

# Configuração
PROJECT = "aurorav2-484411"
REGION = "us-central1"
VERTEX_URL = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}/publishers/google/models/gemini-3-pro-preview:generateContent"

# Pastas
BASE_DIR = Path("D:/dev/BooksKDP")
TXT_DIR = BASE_DIR / "txt"
OUTPUT_DIR = BASE_DIR / "livros_prontos"
TEMPLATE_PATH = BASE_DIR / "Estrutura.docx"

# Namespaces DOCX
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

LANG_WORDS = {
    'pt': ['que', 'não', 'para', 'uma', 'com', 'por', 'mais', 'como', 'mas', 'foi'],
    'es': ['que', 'los', 'las', 'una', 'para', 'con', 'más', 'como', 'pero', 'fue'],
    'en': ['the', 'and', 'that', 'have', 'for', 'with', 'this', 'from', 'was', 'were'],
    'fr': ['les', 'des', 'une', 'que', 'pour', 'dans', 'qui', 'est', 'pas', 'plus'],
    'de': ['der', 'die', 'und', 'den', 'das', 'von', 'ist', 'nicht', 'mit', 'sich'],
    'ru': ['что', 'как', 'это', 'его', 'она', 'они', 'все', 'был', 'быть', 'так'],
}

_token = None
_token_expiry = 0

def get_access_token():
    """Obtém token via gcloud."""
    global _token
    r = subprocess.run(
        ['C:/Program Files (x86)/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd',
         'auth', 'print-access-token'],
        capture_output=True, text=True, shell=True, timeout=30
    )
    _token = r.stdout.strip()
    return _token

def detectar_idioma(texto):
    texto = texto[:5000].lower()
    scores = {lang: sum(1 for w in words if f' {w} ' in texto)
              for lang, words in LANG_WORDS.items()}
    return max(scores, key=scores.get)

def chunks(texto, tam=2500):
    """Divide texto em chunks."""
    result = []
    paragrafos = texto.split("\n\n")
    cur = ""

    for p in paragrafos:
        if len(p) > tam:
            if cur:
                result.append(cur)
                cur = ""
            # Divide por linhas ou caracteres
            for i in range(0, len(p), tam):
                result.append(p[i:i+tam])
        elif len(cur) + len(p) < tam:
            cur += "\n\n" + p if cur else p
        else:
            if cur:
                result.append(cur)
            cur = p

    if cur:
        result.append(cur)

    if not result:
        for i in range(0, len(texto), tam):
            result.append(texto[i:i+tam])

    return result

async def chamar_vertex(session, prompt, chunk_original, sem):
    """Chama Vertex AI."""
    global _token

    async with sem:
        headers = {"Authorization": f"Bearer {_token}", "Content-Type": "application/json"}
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192}
        }

        for attempt in range(3):
            try:
                async with session.post(VERTEX_URL, json=payload, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=120)) as r:
                    if r.status == 200:
                        d = await r.json()
                        result = d.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if result and len(result) >= len(chunk_original) * 0.4:
                            return result
                        return chunk_original
                    elif r.status == 429:
                        print("    Rate limit, aguardando...", flush=True)
                        await asyncio.sleep(5 * (attempt + 1))
                    elif r.status == 401:
                        get_access_token()
                        headers["Authorization"] = f"Bearer {_token}"
                    else:
                        await asyncio.sleep(2)
            except Exception as e:
                await asyncio.sleep(2)

        return chunk_original

async def processar_texto(texto, titulo):
    """Processa: OCR + Tradução + Notas."""
    idioma = detectar_idioma(texto)
    print(f"  Idioma: {idioma}", flush=True)

    sem = asyncio.Semaphore(3)
    connector = aiohttp.TCPConnector(limit=5)

    async with aiohttp.ClientSession(connector=connector) as s:
        # OCR
        print("  [1/3] Correção OCR...", flush=True)
        chunks_texto = chunks(texto)
        print(f"        {len(chunks_texto)} chunks", flush=True)

        tasks = []
        for c in chunks_texto:
            prompt = f"Corrija erros de OCR. Mantenha TODO conteúdo. Retorne APENAS texto corrigido:\n\n{c}"
            tasks.append(chamar_vertex(s, prompt, c, sem))

        resultados = await asyncio.gather(*tasks)
        texto = "\n\n".join(resultados)

        # Tradução
        if idioma != 'pt':
            print(f"  [2/3] Traduzindo {idioma}->PT...", flush=True)
            lang = {'en': 'inglês', 'es': 'espanhol', 'fr': 'francês', 'de': 'alemão', 'ru': 'russo'}.get(idioma, idioma)

            chunks_texto = chunks(texto)
            tasks = []
            for c in chunks_texto:
                prompt = f"Traduza de {lang} para português brasileiro. Mantenha estilo literário. Retorne APENAS tradução:\n\n{c}"
                tasks.append(chamar_vertex(s, prompt, c, sem))

            resultados = await asyncio.gather(*tasks)
            texto = "\n\n".join(resultados)
        else:
            print("  [2/3] Já em PT, pulando tradução", flush=True)

        # Notas
        print("  [3/3] Gerando notas...", flush=True)
        notas = []
        prompt = f"""Identifique até 15 termos que precisam notas explicativas.
Formato: termo|explicação (max 20 palavras)
Texto: {texto[:6000]}"""

        try:
            async with sem:
                headers = {"Authorization": f"Bearer {_token}", "Content-Type": "application/json"}
                payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                          "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048}}
                async with s.post(VERTEX_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as r:
                    if r.status == 200:
                        d = await r.json()
                        result = d.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        for l in result.split("\n"):
                            if "|" in l:
                                p = l.split("|", 1)
                                if len(p) == 2:
                                    termo = p[0].strip().strip('- *"\'')
                                    explicacao = p[1].strip()
                                    if termo and explicacao and 2 < len(termo) < 50:
                                        notas.append((termo, explicacao))
        except:
            pass

        print(f"        {len(notas)} notas", flush=True)
        return texto, notas[:15], idioma

def criar_docx(template_bytes, texto, titulo, autor, notas):
    """Cria DOCX com template e notas de rodapé."""
    template_zip = zipfile.ZipFile(BytesIO(template_bytes))
    output = BytesIO()

    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as docx:
        for item in template_zip.namelist():
            if item in ['word/document.xml', 'word/footnotes.xml']:
                continue
            docx.writestr(item, template_zip.read(item))

        doc_xml = template_zip.read('word/document.xml')
        doc_tree = etree.fromstring(doc_xml)
        body = doc_tree.find('.//w:body', NAMESPACES)
        sectPr = body.find('w:sectPr', NAMESPACES)

        for child in list(body):
            if child.tag != '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr':
                body.remove(child)

        # Título
        p = etree.SubElement(body, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
        pPr = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr')
        jc = etree.SubElement(pPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}jc')
        jc.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 'center')
        run = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
        rPr = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
        etree.SubElement(rPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}b')
        sz = etree.SubElement(rPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz')
        sz.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '48')
        t = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
        t.text = titulo

        # Autor
        p = etree.SubElement(body, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
        pPr = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr')
        jc = etree.SubElement(pPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}jc')
        jc.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 'center')
        run = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
        t = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
        t.text = autor

        # Page break
        p = etree.SubElement(body, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
        run = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
        br = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br')
        br.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type', 'page')

        # Conteúdo com notas
        nota_id = 1
        notas_usadas = []

        for para in texto.split("\n\n"):
            para = para.strip()
            if not para:
                continue

            p = etree.SubElement(body, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
            pPr = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr')
            jc = etree.SubElement(pPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}jc')
            jc.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 'both')

            para_lower = para.lower()
            para_proc = para

            for termo, explicacao in notas:
                if termo.lower() in para_lower and (termo, explicacao) not in [(n[0], n[1]) for n in notas_usadas]:
                    pattern = re.compile(re.escape(termo), re.IGNORECASE)
                    match = pattern.search(para_proc)
                    if match:
                        para_proc = para_proc[:match.end()] + f"[[NOTA:{nota_id}]]" + para_proc[match.end():]
                        notas_usadas.append((termo, explicacao, nota_id))
                        nota_id += 1
                        break

            parts = re.split(r'\[\[NOTA:(\d+)\]\]', para_proc)
            for i, part in enumerate(parts):
                if i % 2 == 0 and part:
                    run = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
                    t = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
                    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                    t.text = part
                elif i % 2 == 1:
                    run = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
                    rPr = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
                    va = etree.SubElement(rPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}vertAlign')
                    va.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 'superscript')
                    fnRef = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}footnoteReference')
                    fnRef.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', part)

        if sectPr is not None:
            body.remove(sectPr)
            body.append(sectPr)

        docx.writestr('word/document.xml', etree.tostring(doc_tree, xml_declaration=True, encoding='UTF-8'))

        # Footnotes
        nsmap = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        footnotes = etree.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}footnotes', nsmap=nsmap)

        for sid in ['-1', '0']:
            fn = etree.SubElement(footnotes, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}footnote')
            fn.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type', 'separator' if sid == '-1' else 'continuationSeparator')
            fn.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', sid)
            p = etree.SubElement(fn, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
            r = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
            etree.SubElement(r, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}' + ('separator' if sid == '-1' else 'continuationSeparator'))

        for termo, explicacao, nid in notas_usadas:
            fn = etree.SubElement(footnotes, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}footnote')
            fn.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', str(nid))
            p = etree.SubElement(fn, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
            r1 = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
            rPr = etree.SubElement(r1, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
            va = etree.SubElement(rPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}vertAlign')
            va.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 'superscript')
            etree.SubElement(r1, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}footnoteRef')
            r2 = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
            t = etree.SubElement(r2, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            t.text = f" {termo}: {explicacao}"

        docx.writestr('word/footnotes.xml', etree.tostring(footnotes, xml_declaration=True, encoding='UTF-8'))

        try:
            ct = template_zip.read('[Content_Types].xml').decode('utf-8')
            if 'footnotes.xml' not in ct:
                ct = ct.replace('</Types>', '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/></Types>')
                docx.writestr('[Content_Types].xml', ct.encode('utf-8'))
        except:
            pass

    template_zip.close()
    output.seek(0)
    return output.getvalue()

def main():
    print("=" * 60)
    print("PROCESSADOR LOCAL - VERTEX AI")
    print("=" * 60)

    # Cria pasta de saída
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Token
    print("\nObtendo token...")
    get_access_token()
    print(f"Token: {_token[:20]}...")

    # Template
    print(f"\nCarregando template: {TEMPLATE_PATH}")
    template_bytes = TEMPLATE_PATH.read_bytes()
    print(f"Template: {len(template_bytes)} bytes")

    # Lista livros
    livros = []
    for pasta in TXT_DIR.iterdir():
        if pasta.is_dir():
            for txt in pasta.glob("*.txt"):
                livros.append((pasta.name, txt))
                break  # Só 1 txt por pasta

    # Limite para teste
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    livros = livros[:limite]

    print(f"\nProcessando {len(livros)} livros...")

    for i, (titulo, txt_path) in enumerate(livros):
        print(f"\n[{i+1}/{len(livros)}] {titulo[:50]}")

        # Verifica se já existe
        output_path = OUTPUT_DIR / f"{titulo}.docx"
        if output_path.exists():
            print("  Já existe, pulando...")
            continue

        try:
            texto = txt_path.read_text(encoding='utf-8')
            print(f"  Original: {len(texto)} chars")

            if len(texto) < 1000:
                print("  Muito curto, pulando...")
                continue

            # Processa
            texto_proc, notas, idioma = asyncio.run(processar_texto(texto, titulo))
            print(f"  Processado: {len(texto_proc)} chars")

            # Autor
            autor = titulo.split("_")[0] if "_" in titulo else titulo

            # DOCX
            docx_bytes = criar_docx(template_bytes, texto_proc, titulo, autor, notas)
            output_path.write_bytes(docx_bytes)
            print(f"  ✓ Salvo: {output_path.name} ({len(docx_bytes)//1024}KB)")

        except Exception as e:
            print(f"  ERRO: {e}")

    print("\n" + "=" * 60)
    print("COMPLETO!")
    print(f"Livros salvos em: {OUTPUT_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()

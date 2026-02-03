# -*- coding: utf-8 -*-
"""
PROCESSADOR GCP - VERSÃO ROBUSTA COM VERTEX AI
- Usa Vertex AI (OAuth2 via Service Account)
- Mantém texto original se API falhar
- Valida tamanho do output
"""

import os
import json
import asyncio
import aiohttp
import re
import zipfile
from io import BytesIO
from google.cloud import storage
from google.auth import default
from google.auth.transport.requests import Request
from lxml import etree

BUCKET = "aurorav2-484411-kdp"
PROJECT = "aurorav2-484411"
REGION = "us-central1"

# Vertex AI endpoint
VERTEX_URL = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}/publishers/google/models/gemini-2.0-flash:generateContent"

# Namespaces do DOCX
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

# Token global
_token = None

def get_access_token():
    """Obtém token OAuth2 via Application Default Credentials."""
    global _token
    credentials, project = default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    credentials.refresh(Request())
    _token = credentials.token
    return _token

def log(msg):
    print(f"[LOG] {msg}", flush=True)

def detectar_idioma(texto):
    texto = texto[:5000].lower()
    scores = {lang: sum(1 for w in words if f' {w} ' in texto)
              for lang, words in LANG_WORDS.items()}
    best = max(scores, key=scores.get)
    log(f"Idioma detectado: {best} (scores: {scores})")
    return best

async def chamar_vertex(session, prompt, chunk_original, sem, max_retries=5):
    """Chama Vertex AI. Se falhar, retorna chunk original."""
    global _token

    async with sem:
        headers = {
            "Authorization": f"Bearer {_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 8192
            }
        }

        for attempt in range(max_retries):
            try:
                async with session.post(VERTEX_URL, json=payload, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=120)) as r:
                    if r.status == 200:
                        d = await r.json()
                        result = d.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

                        # Valida resultado - deve ter pelo menos 50% do tamanho original
                        if result and len(result) >= len(chunk_original) * 0.5:
                            return result
                        else:
                            log(f"  Resultado muito curto ({len(result)} vs {len(chunk_original)}), usando original")
                            return chunk_original

                    elif r.status == 429:
                        wait = (2 ** attempt) + 1
                        log(f"  Rate limit, aguardando {wait}s...")
                        await asyncio.sleep(wait)
                    elif r.status == 401:
                        # Token expirado, renova
                        log("  Token expirado, renovando...")
                        get_access_token()
                        headers["Authorization"] = f"Bearer {_token}"
                    else:
                        error = await r.text()
                        log(f"  Erro HTTP {r.status}: {error[:300]}")
                        await asyncio.sleep(2)

            except asyncio.TimeoutError:
                log(f"  Timeout tentativa {attempt+1}")
                await asyncio.sleep(2)
            except Exception as e:
                log(f"  Erro tentativa {attempt+1}: {e}")
                await asyncio.sleep(1)

        # Falhou todas tentativas - retorna original
        log(f"  FALHA: Usando chunk original ({len(chunk_original)} chars)")
        return chunk_original

def chunks(texto, tam=3000):
    """Divide texto em chunks menores para API."""
    result = []

    # Primeiro, tenta dividir por parágrafo
    paragrafos = texto.split("\n\n")
    cur = ""

    for p in paragrafos:
        # Se parágrafo é maior que o tamanho máximo, divide por linhas
        if len(p) > tam:
            if cur:
                result.append(cur)
                cur = ""
            # Divide parágrafo grande por linhas
            linhas = p.split("\n")
            for linha in linhas:
                if len(linha) > tam:
                    # Linha muito grande, divide por caracteres
                    for i in range(0, len(linha), tam):
                        result.append(linha[i:i+tam])
                elif len(cur) + len(linha) < tam:
                    cur += "\n" + linha if cur else linha
                else:
                    if cur:
                        result.append(cur)
                    cur = linha
        elif len(cur) + len(p) < tam:
            cur += "\n\n" + p if cur else p
        else:
            if cur:
                result.append(cur)
            cur = p

    if cur:
        result.append(cur)

    # Se ainda não tem chunks, força divisão por caracteres
    if not result:
        for i in range(0, len(texto), tam):
            result.append(texto[i:i+tam])

    return result

async def processar_texto(titulo, texto):
    """Processa texto: OCR, tradução, notas. NUNCA perde conteúdo."""
    idioma = detectar_idioma(texto)
    tamanho_original = len(texto)
    log(f"Tamanho original: {tamanho_original} chars")

    # Semáforo conservador - 3 requisições simultâneas
    sem = asyncio.Semaphore(3)

    connector = aiohttp.TCPConnector(limit=5, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as s:

        # === ETAPA 1: OCR ===
        log("Etapa 1: Correção OCR...")
        chunks_texto = chunks(texto)
        log(f"  {len(chunks_texto)} chunks")

        tasks = []
        for c in chunks_texto:
            prompt = f"""Corrija erros de OCR/digitalização neste texto.
Mantenha TODO o conteúdo, apenas corrija:
- Letras trocadas (rn→m, cl→d, etc)
- Espaços errados
- Pontuação incorreta

Retorne APENAS o texto corrigido, sem comentários:

{c}"""
            tasks.append(chamar_vertex(s, prompt, c, sem))

        resultados = await asyncio.gather(*tasks)
        texto = "\n\n".join(resultados)
        log(f"  Após OCR: {len(texto)} chars ({len(texto)*100//tamanho_original}%)")

        # === ETAPA 2: TRADUÇÃO (se necessário) ===
        if idioma != 'pt':
            log(f"Etapa 2: Tradução de {idioma} para PT...")
            lang_nome = {'en': 'inglês', 'es': 'espanhol', 'fr': 'francês', 'de': 'alemão', 'ru': 'russo'}.get(idioma, idioma)

            chunks_texto = chunks(texto)
            tasks = []
            for c in chunks_texto:
                prompt = f"""Traduza este texto de {lang_nome} para português brasileiro.
Mantenha o estilo literário e TODO o conteúdo.
Retorne APENAS a tradução, sem comentários:

{c}"""
                tasks.append(chamar_vertex(s, prompt, c, sem))

            resultados = await asyncio.gather(*tasks)
            texto = "\n\n".join(resultados)
            log(f"  Após tradução: {len(texto)} chars")
        else:
            log("Etapa 2: Já em português, pulando tradução")

        # === ETAPA 3: NOTAS DE RODAPÉ ===
        log("Etapa 3: Gerando notas de rodapé...")
        notas = []

        prompt = f"""Analise este texto e identifique até 15 termos que precisam de notas explicativas.
Inclua: termos técnicos, conceitos filosóficos, referências históricas, palavras em outros idiomas.

Formato EXATO (um por linha):
termo|explicação breve (máximo 20 palavras)

Texto:
{texto[:8000]}"""

        try:
            async with sem:
                headers = {"Authorization": f"Bearer {_token}", "Content-Type": "application/json"}
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048}
                }
                async with s.post(VERTEX_URL, json=payload, headers=headers,
                                 timeout=aiohttp.ClientTimeout(total=60)) as r:
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
        except Exception as e:
            log(f"  Erro nas notas: {e}")

        log(f"  {len(notas)} notas geradas")

        return texto, notas[:15], idioma

def criar_docx_com_template(template_bytes, texto, titulo, autor, notas):
    """Cria DOCX usando template com notas de rodapé reais."""

    template_zip = zipfile.ZipFile(BytesIO(template_bytes))
    output = BytesIO()

    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as docx:
        # Copia arquivos do template (exceto os que vamos modificar)
        for item in template_zip.namelist():
            if item in ['word/document.xml', 'word/footnotes.xml']:
                continue
            docx.writestr(item, template_zip.read(item))

        # Lê e modifica document.xml
        doc_xml = template_zip.read('word/document.xml')
        doc_tree = etree.fromstring(doc_xml)
        body = doc_tree.find('.//w:body', NAMESPACES)

        # Guarda sectPr (configurações de página)
        sectPr = body.find('w:sectPr', NAMESPACES)

        # Limpa body
        for child in list(body):
            if child.tag != '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr':
                body.remove(child)

        # Adiciona título
        p_titulo = etree.SubElement(body, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
        pPr = etree.SubElement(p_titulo, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr')
        jc = etree.SubElement(pPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}jc')
        jc.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 'center')
        run = etree.SubElement(p_titulo, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
        rPr = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
        etree.SubElement(rPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}b')
        sz = etree.SubElement(rPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz')
        sz.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '48')
        t = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
        t.text = titulo

        # Adiciona autor
        p_autor = etree.SubElement(body, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
        pPr = etree.SubElement(p_autor, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr')
        jc = etree.SubElement(pPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}jc')
        jc.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 'center')
        run = etree.SubElement(p_autor, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
        t = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
        t.text = autor

        # Page break
        p_break = etree.SubElement(body, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
        run = etree.SubElement(p_break, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
        br = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br')
        br.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type', 'page')

        # Processa texto com notas
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

            # Verifica notas neste parágrafo
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

            # Adiciona texto com notas
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
                    vertAlign = etree.SubElement(rPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}vertAlign')
                    vertAlign.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 'superscript')
                    fnRef = etree.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}footnoteReference')
                    fnRef.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', part)

        # Move sectPr para o final
        if sectPr is not None:
            body.remove(sectPr)
            body.append(sectPr)

        # Salva document.xml
        docx.writestr('word/document.xml', etree.tostring(doc_tree, xml_declaration=True, encoding='UTF-8'))

        # Cria footnotes.xml
        footnotes_xml = criar_footnotes_xml(notas_usadas)
        docx.writestr('word/footnotes.xml', footnotes_xml)

        # Atualiza Content_Types
        try:
            ct = template_zip.read('[Content_Types].xml').decode('utf-8')
            if 'footnotes.xml' not in ct:
                ct = ct.replace('</Types>',
                    '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/></Types>')
                docx.writestr('[Content_Types].xml', ct.encode('utf-8'))
        except:
            pass

    template_zip.close()
    output.seek(0)
    return output.getvalue()

def criar_footnotes_xml(notas_usadas):
    """Cria footnotes.xml."""
    nsmap = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    }

    footnotes = etree.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}footnotes', nsmap=nsmap)

    # Separadores especiais
    for sid in ['-1', '0']:
        fn = etree.SubElement(footnotes, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}footnote')
        fn.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type',
               'separator' if sid == '-1' else 'continuationSeparator')
        fn.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', sid)
        p = etree.SubElement(fn, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
        r = etree.SubElement(p, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
        etree.SubElement(r, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}' +
                        ('separator' if sid == '-1' else 'continuationSeparator'))

    # Notas reais
    for termo, explicacao, nota_id in notas_usadas:
        fn = etree.SubElement(footnotes, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}footnote')
        fn.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', str(nota_id))

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

    return etree.tostring(footnotes, xml_declaration=True, encoding='UTF-8')

def main():
    """Processa livros - MODO TESTE: apenas 1 livro."""
    log("=" * 60)
    log("PROCESSADOR KDP v3 - VERTEX AI (1 LIVRO TESTE)")
    log("=" * 60)

    # Obtém token OAuth2
    log("Obtendo token OAuth2...")
    try:
        token = get_access_token()
        log(f"Token obtido: {token[:20]}...")
    except Exception as e:
        log(f"ERRO ao obter token: {e}")
        return

    client = storage.Client()
    bucket = client.bucket(BUCKET)

    # Baixa template
    log("Baixando template...")
    try:
        template_bytes = bucket.blob("template/Estrutura.docx").download_as_bytes()
        log(f"Template: {len(template_bytes)} bytes")
    except Exception as e:
        log(f"ERRO: Template não encontrado! {e}")
        return

    # Lista livros - PEGA APENAS 1 PARA TESTE
    blobs = []
    for b in bucket.list_blobs(prefix="txt/"):
        if b.name.endswith(".txt"):
            blobs.append(b)
            if len(blobs) >= 1:  # LIMITE DE TESTE
                break

    log(f"Processando {len(blobs)} livro(s) para teste")

    for blob in blobs:
        titulo = blob.name.split("/")[1] if "/" in blob.name else blob.name
        titulo = titulo.replace(".txt", "")
        log(f"\n{'='*60}")
        log(f"LIVRO: {titulo}")
        log(f"{'='*60}")

        try:
            # Lê texto
            texto = blob.download_as_text(encoding='utf-8')
            log(f"Texto original: {len(texto)} chars")

            if len(texto) < 1000:
                log("Skip: muito curto")
                continue

            # Processa
            texto_proc, notas, idioma = asyncio.run(processar_texto(titulo, texto))
            log(f"Texto processado: {len(texto_proc)} chars")
            log(f"Notas: {len(notas)}")

            # Extrai autor
            autor = "Autor"
            if "_" in titulo:
                autor = titulo.split("_")[0]
            elif " - " in titulo:
                parts = titulo.split(" - ")
                autor = parts[-1] if len(parts) > 1 else parts[0]

            # Cria DOCX
            docx_bytes = criar_docx_com_template(template_bytes, texto_proc, titulo, autor, notas)
            log(f"DOCX gerado: {len(docx_bytes)} bytes")

            # Upload
            docx_blob = bucket.blob(f"docx/{titulo}.docx")
            docx_blob.upload_from_string(docx_bytes,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            log(f"✓ Upload OK: docx/{titulo}.docx")

            # Salva info do teste
            info = {
                "titulo": titulo,
                "texto_original": len(texto),
                "texto_processado": len(texto_proc),
                "ratio": f"{len(texto_proc)*100//len(texto)}%",
                "docx_bytes": len(docx_bytes),
                "notas": len(notas),
                "idioma": idioma,
                "traduzido": idioma != 'pt'
            }
            bucket.blob("TESTE_RESULTADO.json").upload_from_string(
                json.dumps(info, ensure_ascii=False, indent=2))

        except Exception as e:
            log(f"ERRO: {e}")
            import traceback
            traceback.print_exc()

    log("\n" + "=" * 60)
    log("TESTE COMPLETO!")
    log("=" * 60)
    bucket.blob("TESTE_COMPLETO.txt").upload_from_string("OK")

if __name__ == "__main__":
    main()

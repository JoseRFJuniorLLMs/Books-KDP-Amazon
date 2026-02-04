# -*- coding: utf-8 -*-
"""
Baixa DOCXs prontos do GCS e apaga após download.
Roda em loop contínuo até o job terminar.
"""

import subprocess
import time
import os
import shutil
import sys
from pathlib import Path

# Adiciona raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.settings import BUCKET_NAME, BASE_DIR

def find_gcloud():
    """Encontra gcloud automaticamente."""
    # Tenta shutil.which primeiro
    gcloud = shutil.which("gcloud")
    if gcloud:
        return gcloud
    # Fallback para paths comuns
    common_paths = [
        "C:/Program Files (x86)/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd",
        "C:/Program Files/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd",
        "/usr/bin/gcloud",
        "/usr/local/bin/gcloud",
        os.path.expanduser("~/google-cloud-sdk/bin/gcloud"),
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("gcloud não encontrado. Instale o Google Cloud SDK.")

BUCKET = f"gs://{BUCKET_NAME}" if BUCKET_NAME else "gs://aurorav2-484411-kdp"
GCLOUD = find_gcloud()
LOCAL_DIR = BASE_DIR / "livros_prontos"
LOCAL_DIR.mkdir(exist_ok=True)

def run_gcloud(args):
    """Executa comando gcloud."""
    cmd = [GCLOUD] + args
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=60)
    return r.stdout, r.stderr, r.returncode

def listar_docx_gcs():
    """Lista DOCXs no GCS."""
    out, err, code = run_gcloud(["storage", "ls", f"{BUCKET}/docx/"])
    if code == 0:
        return [l.strip() for l in out.split('\n') if l.strip() and '.docx' in l]
    return []

def baixar_e_apagar(gcs_path):
    """Baixa arquivo e apaga do GCS."""
    filename = gcs_path.split('/')[-1]
    local_path = LOCAL_DIR / filename

    # Baixa
    out, err, code = run_gcloud(["storage", "cp", gcs_path, str(local_path)])
    if code == 0 and local_path.exists():
        # Apaga do GCS
        run_gcloud(["storage", "rm", gcs_path])
        return True
    return False

def verificar_completo():
    """Verifica se o job terminou."""
    out, err, code = run_gcloud(["storage", "cat", f"{BUCKET}/COMPLETO.txt"])
    return "OK" in out

def main():
    print("=" * 60)
    print("BAIXANDO DOCXs PRONTOS")
    print("=" * 60)
    print(f"Destino: {LOCAL_DIR}")
    print("Ctrl+C para parar\n")

    total_baixados = 0

    while True:
        try:
            # Lista arquivos
            docx_files = listar_docx_gcs()

            if docx_files:
                print(f"\n[{time.strftime('%H:%M:%S')}] Encontrados: {len(docx_files)} DOCXs")

                for gcs_path in docx_files:
                    filename = gcs_path.split('/')[-1]
                    print(f"  ↓ {filename}...", end=" ")

                    if baixar_e_apagar(gcs_path):
                        total_baixados += 1
                        print("✓")
                    else:
                        print("✗")

                print(f"  Total baixados: {total_baixados}")

            # Verifica se terminou
            if verificar_completo():
                # Baixa últimos arquivos
                docx_files = listar_docx_gcs()
                for gcs_path in docx_files:
                    baixar_e_apagar(gcs_path)
                    total_baixados += 1

                print(f"\n{'=' * 60}")
                print(f"COMPLETO! {total_baixados} DOCXs baixados")
                print(f"Pasta: {LOCAL_DIR}")
                print("=" * 60)
                break

            # Aguarda antes de verificar novamente
            time.sleep(30)

        except KeyboardInterrupt:
            print(f"\n\nParado. {total_baixados} DOCXs baixados até agora.")
            break
        except Exception as e:
            print(f"Erro: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()

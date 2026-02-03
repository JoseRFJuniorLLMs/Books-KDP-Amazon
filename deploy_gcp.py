#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DEPLOY GCP - BooksKDP
=====================
Configura e faz deploy do projeto no Google Cloud Platform.

Uso:
    python deploy_gcp.py --setup     # Configura projeto (uma vez)
    python deploy_gcp.py --deploy    # Faz deploy do container
    python deploy_gcp.py --run       # Executa o job
    python deploy_gcp.py --status    # Verifica status
    python deploy_gcp.py --download  # Baixa resultados
    python deploy_gcp.py --all       # Setup + Deploy + Run
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

# =============================================================================
# CONFIGURACOES
# =============================================================================

PROJECT_ID = "aurorav2-484411"
REGION = "us-central1"
BUCKET_NAME = f"bookskdp-{PROJECT_ID}"
JOB_NAME = "bookskdp-pipeline"
IMAGE_NAME = f"gcr.io/{PROJECT_ID}/booksKDP"

BASE_DIR = Path(__file__).parent
BOOKS_DIR = BASE_DIR / "books"


def run_cmd(cmd, capture=False, check=True):
    """Executa comando e retorna resultado."""
    print(f"  $ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=isinstance(cmd, str))
        if check and result.returncode != 0:
            print(f"    ERRO: {result.stderr}")
        return result
    else:
        return subprocess.run(cmd, shell=isinstance(cmd, str))


def setup_gcp():
    """Configura projeto GCP (executar uma vez)."""
    print("=" * 60)
    print("SETUP GCP")
    print("=" * 60)

    # 1. Configura projeto
    print("\n1. Configurando projeto...")
    run_cmd(["gcloud", "config", "set", "project", PROJECT_ID])

    # 2. Habilita APIs necessarias
    print("\n2. Habilitando APIs...")
    apis = [
        "cloudbuild.googleapis.com",
        "run.googleapis.com",
        "storage.googleapis.com",
        "secretmanager.googleapis.com",
        "containerregistry.googleapis.com",
    ]
    for api in apis:
        print(f"   - {api}")
        run_cmd(["gcloud", "services", "enable", api], check=False)

    # 3. Cria bucket para livros
    print(f"\n3. Criando bucket: {BUCKET_NAME}")
    run_cmd(["gsutil", "mb", "-l", REGION, f"gs://{BUCKET_NAME}"], check=False)

    # 4. Configura secret para API key
    print("\n4. Configurando Secret Manager...")
    print("   IMPORTANTE: Configure sua GEMINI_API_KEY:")
    print(f"   gcloud secrets create gemini-api-key --replication-policy=automatic")
    print(f"   echo -n 'SUA_API_KEY' | gcloud secrets versions add gemini-api-key --data-file=-")

    # Tenta criar o secret (pode ja existir)
    run_cmd(["gcloud", "secrets", "create", "gemini-api-key",
             "--replication-policy=automatic"], check=False)

    # 5. Permissoes para Cloud Run
    print("\n5. Configurando permissoes...")

    # Obtem service account do Cloud Run
    result = run_cmd(["gcloud", "iam", "service-accounts", "list",
                      "--format=value(email)", f"--filter=displayName~compute"], capture=True)

    service_account = result.stdout.strip().split('\n')[0] if result.stdout else None
    if service_account:
        print(f"   Service Account: {service_account}")

        # Permissao para acessar secrets
        run_cmd(["gcloud", "secrets", "add-iam-policy-binding", "gemini-api-key",
                 f"--member=serviceAccount:{service_account}",
                 "--role=roles/secretmanager.secretAccessor"], check=False)

        # Permissao para acessar storage
        run_cmd(["gsutil", "iam", "ch",
                 f"serviceAccount:{service_account}:objectAdmin",
                 f"gs://{BUCKET_NAME}"], check=False)

    print("\n" + "=" * 60)
    print("SETUP COMPLETO!")
    print("=" * 60)
    print(f"""
Projeto: {PROJECT_ID}
Bucket:  gs://{BUCKET_NAME}
Region:  {REGION}

Proximo passo:
  1. Configure a API key (se ainda nao fez):
     echo -n 'SUA_GEMINI_API_KEY' | gcloud secrets versions add gemini-api-key --data-file=-

  2. Faca deploy:
     python deploy_gcp.py --deploy
    """)


def deploy():
    """Faz build e deploy do container."""
    print("=" * 60)
    print("DEPLOY")
    print("=" * 60)

    # 1. Build local da imagem
    print("\n1. Building Docker image...")
    run_cmd(["docker", "build", "-t", f"{IMAGE_NAME}:latest", "."])

    # 2. Push para GCR
    print("\n2. Pushing to Container Registry...")
    run_cmd(["docker", "push", f"{IMAGE_NAME}:latest"])

    # 3. Deploy Cloud Run Job
    print("\n3. Deploying Cloud Run Job...")
    run_cmd([
        "gcloud", "run", "jobs", "deploy", JOB_NAME,
        f"--image={IMAGE_NAME}:latest",
        f"--region={REGION}",
        "--memory=4Gi",
        "--cpu=2",
        "--task-timeout=3600s",
        "--max-retries=1",
        f"--set-env-vars=BUCKET_NAME={BUCKET_NAME}",
        "--set-secrets=GEMINI_API_KEY=gemini-api-key:latest"
    ])

    print("\n" + "=" * 60)
    print("DEPLOY COMPLETO!")
    print("=" * 60)
    print(f"""
Job: {JOB_NAME}
Image: {IMAGE_NAME}:latest

Para executar:
  python deploy_gcp.py --run
    """)


def deploy_cloud_build():
    """Faz deploy usando Cloud Build (alternativa)."""
    print("=" * 60)
    print("DEPLOY VIA CLOUD BUILD")
    print("=" * 60)

    run_cmd(["gcloud", "builds", "submit",
             f"--config=cloudbuild.yaml",
             f"--project={PROJECT_ID}"])


def run_job():
    """Executa o Cloud Run Job."""
    print("=" * 60)
    print("EXECUTANDO JOB")
    print("=" * 60)

    run_cmd([
        "gcloud", "run", "jobs", "execute", JOB_NAME,
        f"--region={REGION}",
        "--wait"
    ])

    print("\nJob iniciado! Acompanhe em:")
    print(f"https://console.cloud.google.com/run/jobs/details/{REGION}/{JOB_NAME}?project={PROJECT_ID}")


def check_status():
    """Verifica status do job e resultados."""
    print("=" * 60)
    print("STATUS")
    print("=" * 60)

    # Status do job
    print("\n1. Status do Job:")
    run_cmd([
        "gcloud", "run", "jobs", "executions", "list",
        f"--job={JOB_NAME}",
        f"--region={REGION}",
        "--limit=5"
    ])

    # Arquivos no bucket
    print(f"\n2. Arquivos no bucket ({BUCKET_NAME}):")
    result = run_cmd(["gsutil", "ls", "-l", f"gs://{BUCKET_NAME}/"], capture=True)
    if result.stdout:
        print(result.stdout)

    # DOCXs prontos
    print("\n3. DOCXs prontos:")
    result = run_cmd(["gsutil", "ls", f"gs://{BUCKET_NAME}/books/docx/"], capture=True)
    if result.stdout:
        lines = [l for l in result.stdout.split('\n') if l.endswith('.docx')]
        print(f"   Total: {len(lines)} arquivos")


def upload_books():
    """Sobe livros locais para o bucket."""
    print("=" * 60)
    print("UPLOAD DE LIVROS")
    print("=" * 60)

    txt_dir = BOOKS_DIR / "txt"
    if not txt_dir.exists():
        print(f"Diretorio nao encontrado: {txt_dir}")
        return

    # Conta arquivos
    txt_files = list(txt_dir.rglob("*.txt"))
    print(f"Encontrados: {len(txt_files)} arquivos TXT")

    # Upload
    print(f"\nFazendo upload para gs://{BUCKET_NAME}/books/txt/")
    run_cmd([
        "gsutil", "-m", "cp", "-r",
        str(txt_dir / "*"),
        f"gs://{BUCKET_NAME}/books/txt/"
    ])

    print("Upload completo!")


def download_results():
    """Baixa resultados do bucket."""
    print("=" * 60)
    print("DOWNLOAD DE RESULTADOS")
    print("=" * 60)

    docx_dir = BOOKS_DIR / "docx" / "gcp"
    docx_dir.mkdir(parents=True, exist_ok=True)

    print(f"Baixando de gs://{BUCKET_NAME}/books/docx/ para {docx_dir}")

    run_cmd([
        "gsutil", "-m", "cp", "-r",
        f"gs://{BUCKET_NAME}/books/docx/*",
        str(docx_dir)
    ])

    # Conta arquivos baixados
    docx_files = list(docx_dir.rglob("*.docx"))
    print(f"\nBaixados: {len(docx_files)} arquivos DOCX")


def main():
    parser = argparse.ArgumentParser(description="Deploy BooksKDP no GCP")
    parser.add_argument("--setup", action="store_true", help="Configura projeto GCP")
    parser.add_argument("--deploy", action="store_true", help="Faz deploy do container")
    parser.add_argument("--cloud-build", action="store_true", help="Deploy via Cloud Build")
    parser.add_argument("--run", action="store_true", help="Executa o job")
    parser.add_argument("--status", action="store_true", help="Verifica status")
    parser.add_argument("--upload", action="store_true", help="Sobe livros para bucket")
    parser.add_argument("--download", action="store_true", help="Baixa resultados")
    parser.add_argument("--all", action="store_true", help="Setup + Deploy + Run")

    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        print("\n" + "=" * 60)
        print("FLUXO RECOMENDADO:")
        print("=" * 60)
        print("""
1. python deploy_gcp.py --setup     # Configura GCP (uma vez)
2. python deploy_gcp.py --upload    # Sobe livros para processar
3. python deploy_gcp.py --deploy    # Faz deploy do container
4. python deploy_gcp.py --run       # Executa processamento
5. python deploy_gcp.py --status    # Acompanha
6. python deploy_gcp.py --download  # Baixa DOCXs prontos
        """)
        return

    if args.all:
        setup_gcp()
        deploy()
        run_job()
    else:
        if args.setup:
            setup_gcp()
        if args.upload:
            upload_books()
        if args.deploy:
            deploy()
        if args.cloud_build:
            deploy_cloud_build()
        if args.run:
            run_job()
        if args.status:
            check_status()
        if args.download:
            download_results()


if __name__ == "__main__":
    main()

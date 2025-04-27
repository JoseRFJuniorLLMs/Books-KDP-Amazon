# Arquivo: test_oauth.py
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import sys
import traceback

CREDENTIALS_FILENAME = 'credentials.json'
TOKEN_FILENAME = 'token_test.json' # Usa nome diferente para teste
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events.readonly',
    'https://www.googleapis.com/auth/gmail.readonly'
]

print("-" * 30)
print("INICIANDO TESTE DE AUTENTICAÇÃO GOOGLE OAUTH")
print(f"Credenciais esperadas: '{CREDENTIALS_FILENAME}'")
print(f"Escopos solicitados: {SCOPES}")
print(f"Arquivo de token de teste: '{TOKEN_FILENAME}'")
print("-" * 30)

# Apaga token de teste antigo, se existir
if os.path.exists(TOKEN_FILENAME):
    print(f"Removendo '{TOKEN_FILENAME}' antigo...")
    try: os.remove(TOKEN_FILENAME)
    except Exception as e_del: print(f"Aviso: não foi possível remover token antigo: {e_del}")

if not os.path.exists(CREDENTIALS_FILENAME):
    print(f"\nERRO FATAL: '{CREDENTIALS_FILENAME}' não encontrado! Verifique nome/local.")
    sys.exit(1)

flow = None
creds = None

try:
    print(f"\n1. Tentando criar fluxo a partir de '{CREDENTIALS_FILENAME}'...")
    # Esta linha lê o token.json e verifica os escopos
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILENAME, SCOPES)
    print("   SUCESSO: Fluxo 'InstalledAppFlow' criado.")
except Exception as e:
    print(f"\n   ERRO FATAL ao criar fluxo: {e}")
    traceback.print_exc() # Imprime erro detalhado
    sys.exit(1)

try:
    print("\n2. Tentando iniciar servidor local (run_local_server)...")
    print("   >>> SE TUDO ESTIVER OK, O NAVEGADOR DEVE ABRIR AGORA <<<")
    # Esta é a linha que abre o navegador
    creds = flow.run_local_server(port=0)
    print("\n   SUCESSO: Autorização concedida pelo usuário no navegador!")
except Exception as e:
    print(f"\n   ERRO FATAL durante 'flow.run_local_server()': {e}")
    print("   Causas comuns: navegador não abriu, erro na página de permissão, porta bloqueada?")
    traceback.print_exc() # Imprime erro detalhado
    sys.exit(1)

if creds:
    try:
        print(f"\n3. Tentando salvar credenciais obtidas em '{TOKEN_FILENAME}'...")
        with open(TOKEN_FILENAME, 'w') as token_file:
            token_file.write(creds.to_json())
        print(f"   SUCESSO: Credenciais salvas em '{TOKEN_FILENAME}'.")
    except Exception as e:
        print(f"\n   ERRO FATAL ao tentar salvar o token em '{TOKEN_FILENAME}': {e}")
        traceback.print_exc()
else:
    print("\nERRO PÓS-FLUXO: Não foi possível obter as credenciais após o fluxo (talvez o usuário negou?).")

print("\n--- Teste de Autenticação Concluído ---")
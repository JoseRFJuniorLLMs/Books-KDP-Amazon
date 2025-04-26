import os
import subprocess
import sys
from dotenv import load_dotenv

# --- Imports do LangChain ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import BaseTool
from langchain import hub # Para puxar prompts padrão de agentes
from langchain.agents import AgentExecutor, create_react_agent

# === CARREGA VARIÁVEIS DE AMBIENTE ===
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# === CONFIGURAÇÕES DO MODELO ===
MODEL_NAME = "gemini-1.5-pro"
TEMPERATURE = 0.3 # Temperatura um pouco mais baixa para ser mais direto

# --- Configuração do LLM LangChain ---
if not GOOGLE_API_KEY:
    print("Erro Crítico: Variável de ambiente GOOGLE_API_KEY não definida.")
    sys.exit(1)
try:
    # Usamos ChatGoogleGenerativeAI para modelos Gemini mais recentes
    # convert_system_message_to_human=True pode ser necessário para alguns agentes
    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        google_api_key=GOOGLE_API_KEY,
        temperature=TEMPERATURE,
        convert_system_message_to_human=True
    )
    print(f"LLM LangChain ({MODEL_NAME}) inicializado.")
except Exception as e:
    print(f"Erro crítico ao inicializar o LLM LangChain: {e}")
    sys.exit(1)

# --- Definição da Ferramenta Customizada (Custom Tool) ---
class WindowsCommandExecutorTool(BaseTool):
    """Ferramenta para executar comandos no Prompt do Windows (cmd.exe)."""
    name: str = "windows_command_executor"
    description: str = (
        # Descrição MUITO importante para o Agente entender o que a ferramenta faz
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
        """Executa o comando no shell e retorna uma string formatada com os resultados."""
        print(f"\n LCHAIN TOOL: Recebido para execução: C:\\> {command_string}")
        if not isinstance(command_string, str) or not command_string.strip():
             return "Erro Interno da Ferramenta: Input inválido. O comando deve ser uma string não vazia."

        # Validação básica (opcional, mas recomendada) - pode ser expandida
        forbidden_commands = ["format", "shutdown"] # Adicione comandos perigosos que você quer bloquear
        command_start = command_string.strip().split()[0].lower()
        if command_start in forbidden_commands:
             print(f" LCHAIN TOOL: Bloqueado comando perigoso '{command_start}'.")
             return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\nErro: Comando '{command_start}' bloqueado por segurança."

        try:
            # A execução do subprocess é a mesma da versão anterior
            result = subprocess.run(
                command_string,
                shell=True,          # O GRANDE RISCO DE SEGURANÇA ESTÁ AQUI
                capture_output=True,
                text=True,
                check=False,
                encoding='cp850',    # Codepage comum PT-BR Console (ou 'utf-8')
                errors='ignore'      # Ignora erros de decodificação
            )
            # Formata a saída de forma clara para o Agente/LLM processar
            output = f"Return Code: {result.returncode}\n"
            output += f"STDOUT:\n{result.stdout.strip() if result.stdout else '(None)'}\n"
            output += f"STDERR:\n{result.stderr.strip() if result.stderr else '(None)'}"

            print(f" LCHAIN TOOL: Execução concluída. Código de Retorno: {result.returncode}")
            if result.returncode != 0:
                 print(f" LCHAIN TOOL: STDERR: {result.stderr.strip() if result.stderr else '(None)'}")
            return output

        except FileNotFoundError:
             # Se o próprio comando não for encontrado (ex: digitou 'dix' em vez de 'dir')
             error_msg = f"Erro de Execução: Comando ou programa inicial '{command_string.split()[0]}' não encontrado. Verifique se o comando existe e está no PATH do sistema."
             print(f" LCHAIN TOOL: {error_msg}")
             # Retorna um formato consistente com erro
             return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\n{error_msg}"
        except Exception as e:
             # Outros erros inesperados durante a execução
             error_msg = f"Erro Inesperado na Ferramenta ao executar comando: {e}"
             print(f" LCHAIN TOOL: {error_msg}")
             return f"Return Code: -1\nSTDOUT:\n(None)\nSTDERR:\n{error_msg}"

    # async def _arun(self, command_string: str) -> str:
    #     # Implementação assíncrona se for usar agentes/loops assíncronos
    #     raise NotImplementedError("Execução assíncrona não implementada")


# --- Inicialização das Ferramentas para o Agente ---
tools = [WindowsCommandExecutorTool()] # Lista de ferramentas disponíveis

# --- Configuração do Agente (ReAct) ---
try:
    # Puxa um prompt padrão do tipo ReAct (Reason+Act) do LangChain Hub
    # Este prompt guia o LLM sobre como usar as ferramentas e raciocinar
    react_prompt = hub.pull("hwchase17/react")

    # Cria o agente ReAct
    # O agente usará o LLM para decidir qual ferramenta usar (se alguma) baseado no prompt e na entrada
    agent = create_react_agent(llm=llm, tools=tools, prompt=react_prompt)

    # Cria o Executor do Agente, que roda o ciclo de Raciocínio -> Ação -> Observação
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True, # MUITO útil para depurar: mostra os pensamentos e ações do agente
        handle_parsing_errors=True, # Tenta lidar com erros se o LLM não formatar a resposta perfeitamente
        max_iterations=10 # Define um limite de iterações para evitar loops infinitos
    )
    print("Agente LangChain (ReAct) e Executor configurados.")
    print("-" * 30)

except Exception as e:
    print(f"Erro crítico ao configurar o Agente LangChain: {e}")
    sys.exit(1)


# --- Loop Principal Interativo ---
print("\nLangChain Windows Commander Agent")
print("==================================")
print("!!! AVISO DE RISCO EXTREMO - AGENT VERSION !!!")
print("Este agente pode executar comandos GERADOS POR IA diretamente no seu Windows.")
print("Ele pode decidir executar múltiplos comandos para completar uma tarefa.")
print("USE POR SUA CONTA E RISCO TOTAL. Monitore o output 'verbose' de perto.")
print("==================================")
print("Digite 'sair' para terminar.")


while True:
    try:
        task = input("\n>>> Descreva a tarefa para o agente Windows (ou 'sair'): ")
        if task.lower().strip() == 'sair':
            break
        if not task.strip():
            continue

        # Invoca o agente com a tarefa do usuário
        # O agente irá raciocinar, escolher a ferramenta (ou não), executá-la,
        # e potencialmente repetir ou analisar o resultado.
        # A entrada é um dicionário.
        response = agent_executor.invoke({"input": task})

        # Exibe a resposta final que o agente determinou
        print("\n--- Resposta Final do Agente ---")
        print(response.get("output", "Nenhuma resposta final do agente foi fornecida."))
        print("------------------------------")

    except KeyboardInterrupt:
        print("\nSainindo por solicitação do usuário...")
        break
    except Exception as e:
        print(f"\n!!! Ocorreu um erro inesperado no loop principal LangChain: {e} !!!")
        # Você pode querer adicionar um log mais detalhado aqui
        # break # Descomente se quiser que o script pare em caso de erro

print("\nScript LangChain terminado.")
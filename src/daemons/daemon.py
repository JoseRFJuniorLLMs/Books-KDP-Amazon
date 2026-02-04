#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RUN_DAEMON.PY - Daemon Autônomo 24/7
====================================
Roda CONTINUAMENTE o dia todo sem supervisão:
1. Baixa livros (Hunter)
2. Traduz livros (Translator)
3. Repete indefinidamente

Recursos:
- Loop infinito automático
- Retry em caso de erro
- Logging detalhado
- Estatísticas em tempo real
- Para com Ctrl+C

Uso:
    python run_daemon.py --languages en es --batch-size 50
    python run_daemon.py --languages en es ru --batch-size 100 --model qwen2.5:7b
"""

import os
import sys
import time
import json
import signal
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

# Fix Windows encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configurações
sys.path.insert(0, str(Path(__file__).parent))
from config.settings import BASE_DIR, OLLAMA_BASE_URL

# ============================================================================
# LOGGING
# ============================================================================

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"daemon_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8'),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# ESTATÍSTICAS
# ============================================================================

class DaemonStats:
    """Estatísticas do daemon."""

    def __init__(self):
        self.stats_file = BASE_DIR / "data" / "daemon_stats.json"
        self.stats_file.parent.mkdir(exist_ok=True)
        self.load()

    def load(self):
        """Carrega estatísticas do arquivo."""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                self.total_books_downloaded = data.get('total_books_downloaded', 0)
                self.total_books_translated = data.get('total_books_translated', 0)
                self.total_cycles = data.get('total_cycles', 0)
                self.total_errors = data.get('total_errors', 0)
                self.start_time = data.get('start_time', datetime.now().isoformat())
                self.last_cycle = data.get('last_cycle', None)
            except Exception:
                self._reset()
        else:
            self._reset()

    def _reset(self):
        """Reseta estatísticas."""
        self.total_books_downloaded = 0
        self.total_books_translated = 0
        self.total_cycles = 0
        self.total_errors = 0
        self.start_time = datetime.now().isoformat()
        self.last_cycle = None

    def save(self):
        """Salva estatísticas em arquivo."""
        data = {
            'total_books_downloaded': self.total_books_downloaded,
            'total_books_translated': self.total_books_translated,
            'total_cycles': self.total_cycles,
            'total_errors': self.total_errors,
            'start_time': self.start_time,
            'last_cycle': self.last_cycle
        }
        with open(self.stats_file, 'w') as f:
            json.dump(data, f, indent=2)

    def add_cycle(self, downloaded: int, translated: int, errors: int = 0):
        """Adiciona estatísticas de um ciclo."""
        self.total_books_downloaded += downloaded
        self.total_books_translated += translated
        self.total_cycles += 1
        self.total_errors += errors
        self.last_cycle = datetime.now().isoformat()
        self.save()

    def print_stats(self):
        """Imprime estatísticas."""
        start = datetime.fromisoformat(self.start_time)
        uptime = datetime.now() - start

        logger.info("="*70)
        logger.info("📊 ESTATÍSTICAS DO DAEMON")
        logger.info("="*70)
        logger.info(f"⏱️  Tempo ativo: {uptime}")
        logger.info(f"🔄 Ciclos completados: {self.total_cycles}")
        logger.info(f"📥 Livros baixados: {self.total_books_downloaded}")
        logger.info(f"🌍 Livros traduzidos: {self.total_books_translated}")
        logger.info(f"❌ Erros totais: {self.total_errors}")

        if self.total_cycles > 0:
            avg_download = self.total_books_downloaded / self.total_cycles
            avg_translate = self.total_books_translated / self.total_cycles
            logger.info(f"📊 Média por ciclo: {avg_download:.1f} downloads, {avg_translate:.1f} traduções")

        logger.info("="*70)

# ============================================================================
# VERIFICAÇÕES
# ============================================================================

def check_ollama_running():
    """Verifica se Ollama está rodando."""
    import requests
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def start_ollama():
    """Inicia Ollama se não estiver rodando."""
    if check_ollama_running():
        logger.info("✅ Ollama já está rodando")
        return True

    logger.info("🚀 Iniciando Ollama...")

    try:
        if sys.platform == 'win32':
            subprocess.Popen(
                ['ollama', 'serve'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        else:
            subprocess.Popen(
                ['ollama', 'serve'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        # Aguarda iniciar
        for i in range(15):
            time.sleep(1)
            if check_ollama_running():
                logger.info("✅ Ollama iniciado com sucesso")
                return True

        logger.error("❌ Ollama não iniciou")
        return False

    except Exception as e:
        logger.error(f"❌ Erro ao iniciar Ollama: {e}")
        return False

def check_model_exists(model_name: str) -> bool:
    """Verifica se modelo existe."""
    import requests
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return any(m['name'] == model_name for m in models)
    except Exception:
        pass
    return False

def ensure_model(model_name: str):
    """Garante que modelo está disponível."""
    if check_model_exists(model_name):
        logger.info(f"✅ Modelo {model_name} já existe")
        return True

    logger.info(f"📥 Baixando modelo {model_name}...")

    try:
        result = subprocess.run(
            ['ollama', 'pull', model_name],
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutos
        )

        if result.returncode == 0:
            logger.info(f"✅ Modelo {model_name} baixado")
            return True
        else:
            logger.error(f"❌ Erro ao baixar modelo: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"❌ Erro ao baixar modelo: {e}")
        return False

# ============================================================================
# EXECUTOR
# ============================================================================

class CycleExecutor:
    """Executa um ciclo de download + tradução."""

    def __init__(self, languages: List[str], batch_size: int, model: str):
        self.languages = languages
        self.batch_size = batch_size
        self.model = model
        self.base_dir = BASE_DIR

    def run_command(self, name: str, command: List[str], timeout: int = 3600) -> Dict:
        """Executa comando e retorna resultado."""
        logger.info(f"🔹 Iniciando: {name}")
        start = time.time()

        try:
            result = subprocess.run(
                command,
                cwd=str(self.base_dir),
                capture_output=True,
                text=True,
                timeout=timeout
            )

            elapsed = time.time() - start
            success = result.returncode == 0

            if success:
                logger.info(f"✅ {name} completado em {elapsed:.1f}s")
            else:
                logger.error(f"❌ {name} falhou: {result.stderr[:200]}")

            return {
                'success': success,
                'elapsed': elapsed,
                'stdout': result.stdout,
                'stderr': result.stderr
            }

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            logger.error(f"❌ {name} timeout após {elapsed:.1f}s")
            return {'success': False, 'elapsed': elapsed, 'error': 'timeout'}

        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"❌ {name} erro: {e}")
            return {'success': False, 'elapsed': elapsed, 'error': str(e)}

    def count_files(self, directory: Path, pattern: str) -> int:
        """Conta arquivos que combinam com padrão."""
        if not directory.exists():
            return 0
        return len(list(directory.rglob(pattern)))

    def execute_cycle(self) -> Dict:
        """Executa um ciclo completo."""
        logger.info("\n" + "="*70)
        logger.info(f"🔄 INICIANDO NOVO CICLO - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*70)

        cycle_start = time.time()
        results = {
            'downloaded': 0,
            'translated': 0,
            'errors': 0,
            'elapsed': 0
        }

        # Conta livros antes
        txt_dir = self.base_dir / "txt"
        translated_dir = self.base_dir / "translated"

        books_before = self.count_files(txt_dir, "*.txt")
        translated_before = self.count_files(translated_dir, "*_pt.txt")

        # 1. DUAL HUNTER - Baixar livros (Gutenberg + Archive.org)
        hunter_cmd = [
            sys.executable,
            'run_dual_hunter.py',
            '--languages'] + self.languages + [
            '--limit', str(self.batch_size)
        ]

        logger.info(f"📥 Fase 1/2: Baixando livros ({self.batch_size} por idioma de 2 fontes)")
        hunter_result = self.run_command(
            "Dual Hunter (Gutenberg + Archive.org)",
            hunter_cmd,
            timeout=7200  # 2 horas (mais tempo para 2 fontes)
        )

        if not hunter_result['success']:
            results['errors'] += 1
            logger.warning("⚠️ Hunter falhou, continuando para tradução...")

        # Conta novos livros
        books_after = self.count_files(txt_dir, "*.txt")
        results['downloaded'] = max(0, books_after - books_before)
        logger.info(f"📚 Novos livros baixados: {results['downloaded']}")

        # 2. TRANSLATOR - Traduzir livros
        translator_cmd = [
            sys.executable,
            'run_translator.py',
            '--languages'] + self.languages + [
            '--model', self.model
        ]

        logger.info(f"🌍 Fase 2/2: Traduzindo livros (modelo: {self.model})")
        translator_result = self.run_command(
            "Translator",
            translator_cmd,
            timeout=7200  # 2 horas
        )

        if not translator_result['success']:
            results['errors'] += 1
            logger.warning("⚠️ Translator falhou")

        # Conta novas traduções
        translated_after = self.count_files(translated_dir, "*_pt.txt")
        results['translated'] = max(0, translated_after - translated_before)
        logger.info(f"🌍 Novos livros traduzidos: {results['translated']}")

        # 3. PROCESSOR - Gerar DOCX (se houver novos livros traduzidos)
        docx_dir = self.base_dir / "docx"
        results['docx_generated'] = 0

        if results['translated'] > 0:
            logger.info(f"📝 Fase 3/4: Gerando DOCX dos livros traduzidos")

            processor_cmd = [
                sys.executable,
                'src/processor.py',
                '--batch'
            ]

            processor_result = self.run_command(
                "DOCX Processor",
                processor_cmd,
                timeout=7200  # 2 horas
            )

            if processor_result['success']:
                # Conta DOCXs gerados
                docx_after = self.count_files(docx_dir, "*.docx")
                results['docx_generated'] = max(0, docx_after - self.count_files(docx_dir, "*.docx"))
                logger.info(f"📝 DOCX gerados: {results['docx_generated']}")
            else:
                results['errors'] += 1
                logger.warning("⚠️ DOCX Processor falhou")
        else:
            logger.info(f"📝 Fase 3/4: Sem novos livros para processar DOCX")

        # 4. COVER GENERATOR - Gerar capas (se houver novos livros)
        results['covers_generated'] = 0

        if results['translated'] > 0:
            logger.info(f"🎨 Fase 4/4: Gerando capas de livros")

            cover_cmd = [
                sys.executable,
                'src/cover_generator.py',
                '--batch'
            ]

            cover_result = self.run_command(
                "Cover Generator",
                cover_cmd,
                timeout=3600  # 1 hora
            )

            if cover_result['success']:
                results['covers_generated'] = results['translated']  # Assume 1 capa por livro
                logger.info(f"🎨 Capas geradas para {results['covers_generated']} livros")
            else:
                results['errors'] += 1
                logger.warning("⚠️ Cover Generator falhou")
        else:
            logger.info(f"🎨 Fase 4/4: Sem novos livros para gerar capas")

        # Tempo total
        results['elapsed'] = time.time() - cycle_start

        logger.info("="*70)
        logger.info(f"✅ CICLO COMPLETADO EM {results['elapsed']/60:.1f} minutos")
        logger.info(f"   Downloads: {results['downloaded']}")
        logger.info(f"   Traduções: {results['translated']}")
        logger.info(f"   DOCX gerados: {results.get('docx_generated', 0)}")
        logger.info(f"   Capas geradas: {results.get('covers_generated', 0)}")
        logger.info(f"   Erros: {results['errors']}")
        logger.info("="*70)

        return results

# ============================================================================
# DAEMON
# ============================================================================

class Daemon:
    """Daemon principal que roda continuamente."""

    def __init__(self, languages: List[str], batch_size: int, model: str,
                 cycle_delay: int, max_cycles: int):
        self.languages = languages
        self.batch_size = batch_size
        self.model = model
        self.cycle_delay = cycle_delay
        self.max_cycles = max_cycles
        self.running = True
        self.stats = DaemonStats()
        self.executor = CycleExecutor(languages, batch_size, model)

        # Handler para Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handler para sinais de interrupção."""
        logger.info("\n\n⚠️ Sinal de parada recebido, finalizando...")
        self.running = False

    def run(self):
        """Roda daemon continuamente."""
        logger.info("="*70)
        logger.info("🤖 DAEMON AUTÔNOMO 24/7 - INICIADO")
        logger.info("="*70)
        logger.info(f"Idiomas: {', '.join(self.languages)}")
        logger.info(f"Tamanho do lote: {self.batch_size} livros por idioma")
        logger.info(f"Modelo: {self.model}")
        logger.info(f"Delay entre ciclos: {self.cycle_delay}s")
        logger.info(f"Máximo de ciclos: {'∞' if self.max_cycles == 0 else self.max_cycles}")
        logger.info("="*70)
        logger.info("💡 Pressione Ctrl+C para parar com segurança")
        logger.info("="*70)

        # Preparação inicial
        if not start_ollama():
            logger.error("❌ Não foi possível iniciar Ollama")
            return 1

        if not ensure_model(self.model):
            logger.error(f"❌ Modelo {self.model} não disponível")
            return 1

        # Loop principal
        cycle_count = 0

        while self.running:
            try:
                if self.max_cycles > 0 and cycle_count >= self.max_cycles:
                    logger.info(f"\n✅ Limite de {self.max_cycles} ciclos atingido")
                    break

                cycle_count += 1

                # Executa ciclo
                results = self.executor.execute_cycle()

                # Atualiza estatísticas
                self.stats.add_cycle(
                    results['downloaded'],
                    results['translated'],
                    results['errors']
                )

                # Mostra estatísticas
                self.stats.print_stats()

                # Aguarda antes do próximo ciclo
                if self.running and (self.max_cycles == 0 or cycle_count < self.max_cycles):
                    logger.info(f"\n⏳ Aguardando {self.cycle_delay}s antes do próximo ciclo...")
                    logger.info(f"💡 Pressione Ctrl+C para parar\n")

                    for i in range(self.cycle_delay):
                        if not self.running:
                            break
                        time.sleep(1)

            except Exception as e:
                logger.error(f"\n❌ Erro no ciclo: {e}")
                self.stats.total_errors += 1
                self.stats.save()

                # Aguarda antes de retry
                logger.info("⏳ Aguardando 60s antes de tentar novamente...")
                time.sleep(60)

        # Finalização
        logger.info("\n" + "="*70)
        logger.info("🛑 DAEMON FINALIZADO")
        logger.info("="*70)
        self.stats.print_stats()

        return 0

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Daemon Autônomo 24/7 - Roda continuamente",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Roda indefinidamente
  python run_daemon.py --languages en es --batch-size 50

  # Roda 10 ciclos
  python run_daemon.py --languages en es ru --batch-size 100 --max-cycles 10

  # Ciclo rápido (5 min entre ciclos)
  python run_daemon.py --languages en --batch-size 20 --cycle-delay 300
"""
    )

    parser.add_argument('--languages', '-l', nargs='+', default=['en', 'es'],
                       help='Idiomas para processar (en, es, ru, fr, de)')
    parser.add_argument('--batch-size', '-b', type=int, default=50,
                       help='Livros por idioma em cada ciclo (padrão: 50)')
    parser.add_argument('--model', '-m', default='qwen2.5:7b',
                       help='Modelo Ollama (padrão: qwen2.5:7b)')
    parser.add_argument('--cycle-delay', '-d', type=int, default=600,
                       help='Segundos entre ciclos (padrão: 600 = 10min)')
    parser.add_argument('--max-cycles', '-c', type=int, default=0,
                       help='Máximo de ciclos (0 = infinito)')

    args = parser.parse_args()

    # Cria daemon e executa
    daemon = Daemon(
        languages=args.languages,
        batch_size=args.batch_size,
        model=args.model,
        cycle_delay=args.cycle_delay,
        max_cycles=args.max_cycles
    )

    return daemon.run()

if __name__ == "__main__":
    sys.exit(main())

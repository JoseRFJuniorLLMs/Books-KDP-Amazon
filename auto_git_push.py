#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AUTO_GIT_PUSH.PY - Git Auto-Commit/Push
========================================
Monitora novos livros traduzidos e faz commit/push automaticamente.

Recursos:
- Detecta novos livros na pasta translated/
- Commit automático para cada livro novo
- Push automático para o repositório
- Roda em loop contínuo
- Logging detalhado

Uso:
    python auto_git_push.py
    python auto_git_push.py --check-interval 60
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
from datetime import datetime
from typing import Set, List

# Fix Windows encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configurações
sys.path.insert(0, str(Path(__file__).parent))
from config.settings import BASE_DIR

# ============================================================================
# LOGGING
# ============================================================================

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"auto_git_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8'),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# STATS
# ============================================================================

class GitStats:
    """Estatísticas do auto-git."""

    def __init__(self):
        self.stats_file = BASE_DIR / "data" / "auto_git_stats.json"
        self.stats_file.parent.mkdir(exist_ok=True)
        self.load()

    def load(self):
        """Carrega estatísticas."""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.total_commits = data.get('total_commits', 0)
                self.total_pushes = data.get('total_pushes', 0)
                self.total_files = data.get('total_files', 0)
                self.start_time = data.get('start_time', datetime.now().isoformat())
                self.last_commit = data.get('last_commit', None)
            except:
                self._reset()
        else:
            self._reset()

    def _reset(self):
        """Reseta estatísticas."""
        self.total_commits = 0
        self.total_pushes = 0
        self.total_files = 0
        self.start_time = datetime.now().isoformat()
        self.last_commit = None

    def save(self):
        """Salva estatísticas."""
        data = {
            'total_commits': self.total_commits,
            'total_pushes': self.total_pushes,
            'total_files': self.total_files,
            'start_time': self.start_time,
            'last_commit': self.last_commit
        }
        with open(self.stats_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_commit(self, files_count: int):
        """Registra um commit."""
        self.total_commits += 1
        self.total_files += files_count
        self.last_commit = datetime.now().isoformat()
        self.save()

    def add_push(self):
        """Registra um push."""
        self.total_pushes += 1
        self.save()

# ============================================================================
# GIT AUTO-PUSH
# ============================================================================

class GitAutoPush:
    """Monitor de arquivos com auto-commit/push."""

    def __init__(self, check_interval: int = 30, batch_commits: bool = False):
        self.check_interval = check_interval
        self.batch_commits = batch_commits
        self.running = True
        self.stats = GitStats()
        self.known_files: Set[str] = set()
        self.base_dir = BASE_DIR

        # Handler para Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Inicializa lista de arquivos conhecidos
        self._scan_existing_files()

    def _signal_handler(self, signum, frame):
        """Handler para sinais de interrupção."""
        logger.info("\n\n⚠️ Sinal de parada recebido, finalizando auto-git...")
        self.running = False

    def _scan_existing_files(self):
        """Escaneia arquivos existentes."""
        translated_dir = self.base_dir / "translated"
        if translated_dir.exists():
            for file in translated_dir.rglob("*_pt.txt"):
                self.known_files.add(str(file.relative_to(self.base_dir)))
        logger.info(f"📂 Arquivos conhecidos: {len(self.known_files)}")

    def _get_translated_files(self) -> Set[str]:
        """Retorna conjunto de arquivos traduzidos."""
        translated_dir = self.base_dir / "translated"
        files = set()
        if translated_dir.exists():
            for file in translated_dir.rglob("*_pt.txt"):
                files.add(str(file.relative_to(self.base_dir)))
        return files

    def _run_git_command(self, command: List[str], description: str) -> bool:
        """Executa comando git."""
        try:
            result = subprocess.run(
                command,
                cwd=str(self.base_dir),
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                logger.info(f"✅ {description}")
                return True
            else:
                logger.error(f"❌ {description} falhou: {result.stderr[:200]}")
                return False

        except Exception as e:
            logger.error(f"❌ Erro em {description}: {e}")
            return False

    def _commit_and_push(self, new_files: List[str]) -> bool:
        """Faz commit e push dos novos arquivos."""
        if not new_files:
            return False

        logger.info("="*70)
        logger.info(f"📝 Novos arquivos detectados: {len(new_files)}")
        logger.info("="*70)

        # Lista os arquivos
        for file in new_files[:5]:  # Mostra no máximo 5
            logger.info(f"  • {file}")
        if len(new_files) > 5:
            logger.info(f"  ... e mais {len(new_files) - 5} arquivo(s)")

        # Git add
        if not self._run_git_command(['git', 'add', '.'], 'git add'):
            return False

        # Verifica se há algo para commitar
        result = subprocess.run(
            ['git', 'diff', '--cached', '--quiet'],
            cwd=str(self.base_dir),
            capture_output=True
        )

        if result.returncode == 0:
            logger.info("ℹ️ Nada para commitar")
            return False

        # Commit message
        if len(new_files) == 1:
            # Extrai nome do livro do caminho
            file_path = Path(new_files[0])
            book_name = file_path.parent.name if file_path.parent.name != 'translated' else file_path.stem.replace('_pt', '')
            commit_msg = f"Adicionar tradução: {book_name}"
        else:
            commit_msg = f"Adicionar {len(new_files)} novas traduções"

        commit_msg += "\n\nCo-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

        # Git commit
        commit_cmd = ['git', 'commit', '-m', commit_msg]
        if not self._run_git_command(commit_cmd, 'git commit'):
            return False

        self.stats.add_commit(len(new_files))

        # Git push
        if not self._run_git_command(['git', 'push'], 'git push'):
            logger.warning("⚠️ Push falhou, mas commit foi feito")
            return False

        self.stats.add_push()

        logger.info("="*70)
        logger.info(f"✅ COMMIT E PUSH CONCLUÍDOS")
        logger.info(f"   Arquivos: {len(new_files)}")
        logger.info(f"   Total de commits: {self.stats.total_commits}")
        logger.info(f"   Total de pushes: {self.stats.total_pushes}")
        logger.info("="*70)

        return True

    def run(self):
        """Roda monitor em loop."""
        logger.info("="*70)
        logger.info("🔄 AUTO GIT COMMIT/PUSH - INICIADO")
        logger.info("="*70)
        logger.info(f"Intervalo de verificação: {self.check_interval}s")
        logger.info(f"Diretório monitorado: translated/")
        logger.info(f"Padrão de arquivos: *_pt.txt")
        logger.info("="*70)
        logger.info("💡 Pressione Ctrl+C para parar")
        logger.info("="*70)

        check_count = 0

        while self.running:
            try:
                time.sleep(self.check_interval)

                if not self.running:
                    break

                check_count += 1

                # Verifica novos arquivos
                current_files = self._get_translated_files()
                new_files = current_files - self.known_files

                if new_files:
                    new_files_list = sorted(list(new_files))

                    # Faz commit e push
                    if self._commit_and_push(new_files_list):
                        # Atualiza arquivos conhecidos
                        self.known_files.update(new_files)
                else:
                    # Log de status a cada 10 verificações
                    if check_count % 10 == 0:
                        uptime_start = datetime.fromisoformat(self.stats.start_time)
                        uptime = datetime.now() - uptime_start
                        logger.info(f"✅ Auto-git ativo | Uptime: {uptime} | Commits: {self.stats.total_commits} | Pushes: {self.stats.total_pushes}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Erro no loop: {e}")
                time.sleep(30)

        # Finalização
        logger.info("\n" + "="*70)
        logger.info("🛑 AUTO GIT FINALIZADO")
        logger.info("="*70)
        logger.info(f"Total de commits: {self.stats.total_commits}")
        logger.info(f"Total de pushes: {self.stats.total_pushes}")
        logger.info(f"Total de arquivos: {self.stats.total_files}")
        logger.info("="*70)

        return 0

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Auto Git Commit/Push para novos livros",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Padrão (verifica a cada 30s)
  python auto_git_push.py

  # Verifica a cada 60s
  python auto_git_push.py --check-interval 60

  # Verifica a cada 2 minutos
  python auto_git_push.py --check-interval 120
"""
    )

    parser.add_argument('--check-interval', '-i', type=int, default=30,
                       help='Intervalo de verificação em segundos (padrão: 30)')

    args = parser.parse_args()

    # Verifica se está em um repositório git
    if not (BASE_DIR / ".git").exists():
        logger.error("❌ Não é um repositório git!")
        return 1

    # Cria monitor e executa
    monitor = GitAutoPush(
        check_interval=args.check_interval
    )

    return monitor.run()

if __name__ == "__main__":
    sys.exit(main())

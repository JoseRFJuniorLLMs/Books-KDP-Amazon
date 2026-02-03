#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WATCHDOG_DAEMON.PY - Monitor de Auto-Restart
==============================================
Monitora o daemon e reinicia automaticamente se cair.

Recursos:
- Verifica se daemon está rodando a cada 30s
- Reinicia automaticamente se cair
- Logging detalhado de reinicializações
- Pode rodar como serviço

Uso:
    python watchdog_daemon.py
    python watchdog_daemon.py --languages en es --batch-size 50
"""

import os
import sys
import time
import json
import signal
import logging
import argparse
import subprocess
import psutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List

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
        logging.FileHandler(LOG_DIR / f"watchdog_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8'),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# WATCHDOG STATS
# ============================================================================

class WatchdogStats:
    """Estatísticas do watchdog."""

    def __init__(self):
        self.stats_file = BASE_DIR / "data" / "watchdog_stats.json"
        self.stats_file.parent.mkdir(exist_ok=True)
        self.load()

    def load(self):
        """Carrega estatísticas."""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                self.total_restarts = data.get('total_restarts', 0)
                self.start_time = data.get('start_time', datetime.now().isoformat())
                self.last_restart = data.get('last_restart', None)
                self.daemon_crashes = data.get('daemon_crashes', 0)
            except:
                self._reset()
        else:
            self._reset()

    def _reset(self):
        """Reseta estatísticas."""
        self.total_restarts = 0
        self.start_time = datetime.now().isoformat()
        self.last_restart = None
        self.daemon_crashes = 0

    def save(self):
        """Salva estatísticas."""
        data = {
            'total_restarts': self.total_restarts,
            'start_time': self.start_time,
            'last_restart': self.last_restart,
            'daemon_crashes': self.daemon_crashes
        }
        with open(self.stats_file, 'w') as f:
            json.dump(data, f, indent=2)

    def add_restart(self, was_crash: bool = False):
        """Registra uma reinicialização."""
        self.total_restarts += 1
        if was_crash:
            self.daemon_crashes += 1
        self.last_restart = datetime.now().isoformat()
        self.save()

# ============================================================================
# DAEMON MONITOR
# ============================================================================

class DaemonMonitor:
    """Monitor do daemon com auto-restart."""

    def __init__(self, languages: List[str], batch_size: int, model: str,
                 cycle_delay: int, max_cycles: int, check_interval: int = 30):
        self.languages = languages
        self.batch_size = batch_size
        self.model = model
        self.cycle_delay = cycle_delay
        self.max_cycles = max_cycles
        self.check_interval = check_interval
        self.running = True
        self.daemon_process: Optional[subprocess.Popen] = None
        self.stats = WatchdogStats()

        # Handler para Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handler para sinais de interrupção."""
        logger.info("\n\n⚠️ Sinal de parada recebido, finalizando watchdog...")
        self.running = False
        if self.daemon_process:
            logger.info("🛑 Parando daemon...")
            self.stop_daemon()

    def is_daemon_running(self) -> bool:
        """Verifica se o daemon está rodando."""
        # Verifica se há processo run_daemon.py rodando
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'run_daemon.py' in ' '.join(cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def start_daemon(self) -> bool:
        """Inicia o daemon."""
        logger.info("="*70)
        logger.info("🚀 Iniciando daemon...")
        logger.info("="*70)

        try:
            cmd = [
                sys.executable,
                str(BASE_DIR / "run_daemon.py"),
                '--languages'] + self.languages + [
                '--batch-size', str(self.batch_size),
                '--model', self.model,
                '--cycle-delay', str(self.cycle_delay),
                '--max-cycles', str(self.max_cycles)
            ]

            logger.info(f"Comando: {' '.join(cmd)}")

            # Inicia daemon em processo separado
            if sys.platform == 'win32':
                self.daemon_process = subprocess.Popen(
                    cmd,
                    cwd=str(BASE_DIR),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                self.daemon_process = subprocess.Popen(
                    cmd,
                    cwd=str(BASE_DIR),
                    preexec_fn=os.setsid
                )

            # Aguarda um pouco para verificar se iniciou
            time.sleep(5)

            if self.is_daemon_running():
                logger.info("✅ Daemon iniciado com sucesso (PID: {})".format(self.daemon_process.pid))
                self.stats.add_restart(was_crash=False)
                return True
            else:
                logger.error("❌ Daemon não iniciou corretamente")
                return False

        except Exception as e:
            logger.error(f"❌ Erro ao iniciar daemon: {e}")
            return False

    def stop_daemon(self):
        """Para o daemon."""
        if self.daemon_process:
            try:
                if sys.platform == 'win32':
                    # Windows - envia Ctrl+C
                    self.daemon_process.send_signal(signal.CTRL_C_EVENT)
                else:
                    # Unix - envia SIGTERM
                    os.killpg(os.getpgid(self.daemon_process.pid), signal.SIGTERM)

                # Aguarda processo terminar (máximo 30s)
                try:
                    self.daemon_process.wait(timeout=30)
                    logger.info("✅ Daemon parado com sucesso")
                except subprocess.TimeoutExpired:
                    logger.warning("⚠️ Daemon não parou, forçando...")
                    self.daemon_process.kill()

            except Exception as e:
                logger.error(f"❌ Erro ao parar daemon: {e}")

            self.daemon_process = None

    def run(self):
        """Roda watchdog continuamente."""
        logger.info("="*70)
        logger.info("👁️ WATCHDOG DAEMON - AUTO-RESTART HABILITADO")
        logger.info("="*70)
        logger.info(f"Configuração do daemon:")
        logger.info(f"  • Idiomas: {', '.join(self.languages)}")
        logger.info(f"  • Batch size: {self.batch_size}")
        logger.info(f"  • Modelo: {self.model}")
        logger.info(f"  • Cycle delay: {self.cycle_delay}s")
        logger.info(f"  • Max cycles: {'∞' if self.max_cycles == 0 else self.max_cycles}")
        logger.info(f"\nWatchdog verificará a cada {self.check_interval}s")
        logger.info("="*70)
        logger.info("💡 Pressione Ctrl+C para parar watchdog e daemon")
        logger.info("="*70)

        # Inicia daemon pela primeira vez
        if not self.start_daemon():
            logger.error("❌ Falha ao iniciar daemon")
            return 1

        # Loop de monitoramento
        check_count = 0
        consecutive_failures = 0

        while self.running:
            try:
                time.sleep(self.check_interval)
                check_count += 1

                if not self.running:
                    break

                # Verifica se daemon está rodando
                if not self.is_daemon_running():
                    consecutive_failures += 1
                    logger.warning("="*70)
                    logger.warning(f"⚠️ DAEMON CAIU! (falha #{consecutive_failures})")
                    logger.warning("="*70)

                    self.stats.add_restart(was_crash=True)

                    # Aguarda um pouco antes de reiniciar
                    logger.info("⏳ Aguardando 10s antes de reiniciar...")
                    time.sleep(10)

                    # Reinicia daemon
                    if self.start_daemon():
                        logger.info(f"✅ Daemon reiniciado automaticamente")
                        consecutive_failures = 0
                    else:
                        logger.error(f"❌ Falha ao reiniciar daemon (tentativa {consecutive_failures})")

                        # Se falhar 3 vezes consecutivas, aguarda mais tempo
                        if consecutive_failures >= 3:
                            wait_time = 60
                            logger.warning(f"⚠️ {consecutive_failures} falhas consecutivas, aguardando {wait_time}s...")
                            time.sleep(wait_time)

                else:
                    # Daemon rodando normalmente
                    consecutive_failures = 0

                    # Log de status a cada 10 verificações (5 minutos se check_interval=30s)
                    if check_count % 10 == 0:
                        uptime_start = datetime.fromisoformat(self.stats.start_time)
                        uptime = datetime.now() - uptime_start
                        logger.info(f"✅ Watchdog ativo | Uptime: {uptime} | Restarts: {self.stats.total_restarts} | Crashes: {self.stats.daemon_crashes}")

            except KeyboardInterrupt:
                # Ctrl+C já é tratado pelo signal handler
                break
            except Exception as e:
                logger.error(f"❌ Erro no watchdog: {e}")
                time.sleep(30)

        # Finalização
        logger.info("\n" + "="*70)
        logger.info("🛑 WATCHDOG FINALIZADO")
        logger.info("="*70)
        logger.info(f"Total de restarts: {self.stats.total_restarts}")
        logger.info(f"Total de crashes: {self.stats.daemon_crashes}")
        logger.info("="*70)

        return 0

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Watchdog para daemon - Auto-restart habilitado",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Watchdog com configuração padrão
  python watchdog_daemon.py

  # Watchdog com configuração personalizada
  python watchdog_daemon.py --languages en es ru --batch-size 100

  # Watchdog com verificação mais frequente
  python watchdog_daemon.py --check-interval 15
"""
    )

    parser.add_argument('--languages', '-l', nargs='+', default=['en', 'es'],
                       help='Idiomas para o daemon (en, es, ru, fr, de)')
    parser.add_argument('--batch-size', '-b', type=int, default=50,
                       help='Livros por idioma (padrão: 50)')
    parser.add_argument('--model', '-m', default='bigllama/mistralv01-7b:latest',
                       help='Modelo Ollama (padrão: bigllama/mistralv01-7b:latest)')
    parser.add_argument('--cycle-delay', '-d', type=int, default=600,
                       help='Delay entre ciclos (padrão: 600s)')
    parser.add_argument('--max-cycles', '-c', type=int, default=0,
                       help='Máximo de ciclos do daemon (0 = infinito)')
    parser.add_argument('--check-interval', '-i', type=int, default=30,
                       help='Intervalo de verificação em segundos (padrão: 30)')

    args = parser.parse_args()

    # Cria monitor e executa
    monitor = DaemonMonitor(
        languages=args.languages,
        batch_size=args.batch_size,
        model=args.model,
        cycle_delay=args.cycle_delay,
        max_cycles=args.max_cycles,
        check_interval=args.check_interval
    )

    return monitor.run()

if __name__ == "__main__":
    sys.exit(main())

# coding: utf-8
"""
识别子进程工作包 (Worker Package)

包含模型加载、任务处理和 Worker 门面类。
"""

from multiprocessing import Queue
from multiprocessing.managers import ListProxy
import faulthandler
from pathlib import Path
from config_server import BASE_DIR
from .. import logger
from .worker import RecognizerWorker

def start_worker(queue_in: Queue, queue_out: Queue, sockets_id: ListProxy, stdin_fn: int):
    """识别子进程启动入口"""
    native_log_path = Path(BASE_DIR) / 'logs' / 'worker_native_crash_latest.log'
    native_log_path.parent.mkdir(parents=True, exist_ok=True)
    with native_log_path.open('w', encoding='utf-8') as native_log:
        native_log.write('VoxCaps native Worker crash trace\n')
        native_log.flush()
        faulthandler.enable(file=native_log, all_threads=True)
        try:
            worker = RecognizerWorker(queue_in, queue_out, sockets_id, stdin_fn)
            worker.run()
        finally:
            faulthandler.disable()

__all__ = ['RecognizerWorker', 'start_worker']

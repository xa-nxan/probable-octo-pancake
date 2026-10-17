import threading
import queue
import concurrent.futures
import MetaTrader5 as mt5
import asyncio
import time

class MT5Worker:
    def __init__(self):
        self.cmd_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._run, daemon=True)
        self.connected = False
        self.symbols_info = {}

    def start(self):
        self.worker_thread.start()

    def _run(self):
        # Initial connection
        self.connected = mt5.initialize()
        if self.connected:
            print("MT5Worker: Initialized MT5 successfully.")
        else:
            print("MT5Worker: Failed to initialize MT5.")

        last_health_check = time.time()

        while True:
            try:
                # 5-second health check
                if time.time() - last_health_check > 5:
                    last_health_check = time.time()
                    if self.connected:
                        info = mt5.terminal_info()
                        if info is None:
                            self.connected = False
                            print("MT5Worker: Lost connection to MT5.")
                    else:
                        print("MT5Worker: Attempting to reconnect...")
                        self.connected = mt5.initialize()
                        if self.connected:
                            print("MT5Worker: Reconnected to MT5.")

                # Wait for a command with a short timeout to allow health checks
                cmd, args, kwargs, future = self.cmd_queue.get(timeout=1.0)
                
                if cmd in ("STOP", "shutdown"):
                    mt5.shutdown()
                    self.connected = False
                    future.set_result(True)
                    self.cmd_queue.task_done()
                    break
                
                if not self.connected:
                    future.set_exception(Exception("MT5 not connected"))
                    self.cmd_queue.task_done()
                    continue

                # Execute the MT5 command
                # Note: MetaTrader 5 C extension rejects calls with empty kwargs dict (**{})
                # with "Unnamed arguments not allowed". Only pass kwargs if non-empty!
                try:
                    func = getattr(mt5, cmd)
                    if kwargs:
                        result = func(*args, **kwargs)
                    else:
                        result = func(*args)
                    self.last_worker_error = mt5.last_error()
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                finally:
                    self.cmd_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"MT5Worker Error: {e}")

    def get_last_error(self):
        return getattr(self, 'last_worker_error', (0, 'No error'))

    def execute(self, cmd, *args, **kwargs):
        """Synchronously enqueue and wait for result. Do not call this from the asyncio event loop!"""
        future = concurrent.futures.Future()
        self.cmd_queue.put((cmd, args, kwargs, future))
        return future.result()

    async def execute_async(self, cmd, *args, **kwargs):
        """Asynchronously enqueue and await result."""
        future = concurrent.futures.Future()
        self.cmd_queue.put((cmd, args, kwargs, future))
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, future.result)

# Global singleton
mt5_worker = MT5Worker()

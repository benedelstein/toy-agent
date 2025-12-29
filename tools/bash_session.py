import subprocess
import queue
import threading
import os
import time

class BashSession:
    def __init__(self):
        self._create_process()
        self.output_queue = queue.Queue()
        self.error_queue = queue.Queue()
        self._start_readers()
        
    def _create_process(self):
        self.process = subprocess.Popen(
            ['/bin/bash'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )
    
    def _start_readers(self):
        # These threads READ from process pipes and WRITE to queues
        def pipe_to_queue(pipe, q):
            for line in iter(pipe.readline, ''):
                q.put(line)
            pipe.close()

        self.output_thread = threading.Thread(
            target=pipe_to_queue,
            args=(self.process.stdout, self.output_queue),
            daemon=True
        )
        self.error_thread = threading.Thread(
            target=pipe_to_queue,
            args=(self.process.stderr, self.error_queue),
            daemon=True
        )
        self.output_thread.start()
        self.error_thread.start()

    def _read_output(self, timeout: float = 0.1) -> str:
        """Read from output queue (populated by background thread)"""
        lines = []
        while True:
            try:
                line = self.output_queue.get(timeout=timeout)
                lines.append(line)
            except queue.Empty:
                break
        return ''.join(lines)

    def _read_error(self, timeout: float = 0.1) -> str:
        """Read from error queue (populated by background thread)"""
        lines = []
        while True:
            try:
                line = self.error_queue.get(timeout=timeout)
                lines.append(line)
            except queue.Empty:
                break
        return ''.join(lines)
    
    def restart(self):
        self.terminate()
        self.__init__()
        
    def terminate(self):
        self.process.terminate()
    
    def execute_command(self, command: str, timeout: float = 10) -> dict:
        if self.process.stdin is None:
            raise ValueError("Process stdin is not available")

        # Use marker to know when command is done
        marker = f"__END__{os.getpid()}__"
        full_command = f"{command}; echo {marker}\n"

        self.process.stdin.write(full_command)
        self.process.stdin.flush()

        # Read until we see the marker
        output_lines = []
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            try:
                line = self.output_queue.get(timeout=0.1)
                if marker in line:
                    break
                output_lines.append(line)
            except queue.Empty:
                pass

        stdout = ''.join(output_lines)
        stderr = self._read_error()

        return {"stdout": stdout, "stderr": stderr}
    
    
if __name__ == "__main__":
    session = BashSession()
    while True:
        command = input("% ")
        if command == "exit":
            break
        result = session.execute_command(command)
        print(result["stdout"])
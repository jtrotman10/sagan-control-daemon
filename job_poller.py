import sys

import time
from codecs import decode

import os
from requests import get, patch, put
from threading import Thread
from subprocess import Popen, PIPE, TimeoutExpired
from requests.exceptions import ConnectionError
import websocket
from queue import Queue, Empty

from websocket._exceptions import WebSocketConnectionClosedException

_current_poller = None


def websocket_recv(ws: websocket.WebSocket, in_queue: Queue):
    while ws.connected:
        try:
            message = ws.recv()
            in_queue.put(message)
        except WebSocketConnectionClosedException:
            break


def process_read(out_stream, out_queue: Queue):
    while True:
        data = os.read(out_stream.fileno(), 512)
        if data == b'':
            break
        out_queue.put(decode(data))


def main():
    global _current_poller
    _current_poller = Poller(int(sys.argv[1]), sys.argv[2])
    _current_poller.go()


class Poller:
    def __init__(self, device_id, host):
        self.device_id = device_id
        self.host = host
        self.run_job = None
        self.experiment_process = None  # type: Popen
        self.results_stream = None
        self.error_stream = None
        self.stdout_text = b''
        self.stderr_text = b''
        self.state = 'polling'
        self.state_machine = {
            'polling': self.check_for_jobs,
            'running': self.run_experiment,
            'termination_requested': self.kill_subproc
        }

    def go(self):
        print('Device id: {}'.format(self.device_id))
        print('Awaiting work.')

        while self.state is not 'exit':
            try:
                self.heartbeat()
                self.state_machine[self.state]()
            except ConnectionError as error:
                print(error)
                exit(1)

    def heartbeat(self):
        url = '{0}/dispatch/devices/{1}/heartbeat'.format(self.host, self.device_id)
        response = put(url, {'state': 0 if self.state is 'polling' else 1})
        if response.status_code not in (200, 204):
            exit(1)

    def check_for_jobs(self):
        url = '{0}/dispatch/devices/{1}/queue'.format(self.host, self.device_id)
        jobs = get(url).json()
        if len(jobs) > 0:
            next_job = jobs[0]
            print('Found job id {}, fetching experiment.'.format(next_job['id']))
            self.run_job = next_job['id']
            experiment = self.get_experiment(next_job['experiment'])
            self.start_experiment(experiment)
            self.notify_start()
            self.state = 'running'
        else:
            time.sleep(0.5)
        return

    def get_experiment(self, experiment_id):
        url = '{0}/dispatch/experiments/{1}'.format(self.host, experiment_id)
        return get(url).json()

    def get_state(self):
        url = '{0}/dispatch/jobs/{1}'.format(self.host, self.run_job)
        return get(url).json()['state']

    def notify_start(self):
        return put('{0}/dispatch/jobs/{1}/start'.format(self.host, self.run_job), {})

    def post_results(self):
        return put(
            '{0}/dispatch/jobs/{1}/finish'.format(self.host, self.run_job),
            {
                'out': self.stdout_text,
                'error': self.stderr_text
            }
        )

    def start_experiment(self, experiment):
        print('Starting experiment "{}".'.format(experiment['title']))
        with open('file.py', 'w') as f:
            f.write(experiment['code_string'])

        self.experiment_process = Popen(
            [sys.executable, '-u', 'file.py'],
            stdin=PIPE,
            stdout=PIPE,
            # stderr=PIPE,
            bufsize=0

        )
        self.results_stream = self.experiment_process.stdout
        self.error_stream = self.experiment_process.stderr
        self.out_queue = Queue()
        self.experiment_read_thread = Thread(target=process_read, args=(self.experiment_process.stdout, self.out_queue))
        self.experiment_read_thread.start()
        self.open_websocket('ws://echo.websocket.org/')

    def read_output(self):
        output = ''
        while True:
            try:
                output += self.out_queue.get_nowait()
            except Empty:
                break
        return output

    def is_experiment_running(self):
        return self.experiment_process.poll() is None

    def end_experiment(self):
        print('Job finished, awaiting work.')
        self.results_stream = None
        self.error_stream = None
        self.experiment_process = None
        self.stderr_text = b''
        self.stdout_text = b''

    def open_websocket(self, url):
        self.websocket = websocket.WebSocket()
        self.websocket.connect(url)
        self.in_queue = Queue()
        self.websocket_recv_thread = Thread(target=websocket_recv, args=(self.websocket, self.in_queue))
        self.websocket_recv_thread.start()

    def close_websocket(self):
        self.websocket.close()
        self.websocket_recv_thread.join()

    def read_input(self):
        input = ''
        while True:
            try:
                input += self.in_queue.get_nowait()
            except Empty:
                break
        return input

    def run_experiment(self):
        input = self.read_input()
        try:
            self.experiment_process.stdin.write(input.encode())
        except BrokenPipeError:
            pass
        output = self.read_output()
        if output != '':
            self.websocket.send(output)
            sys.stdout.write(output)
        if not self.is_experiment_running():
            self.experiment_read_thread.join()
            output = self.read_output()
            self.websocket.send(output)
            self.websocket.close()
            self.websocket_recv_thread.join()
            self.post_results()
            self.end_experiment()
            self.state = 'polling'

    def kill_subproc(self):
        print('Terminating job.')
        self.experiment_process.terminate()
        try:
            self.communicate(timeout=10)
        except TimeoutExpired:
            print('Process taking to long to terminate, killing.')
            self.experiment_process.kill()
            try:
                self.communicate(timeout=10)
            except TimeoutExpired:
                print('WARNING: Experiment failed to stop.')
        self.post_results()
        self.end_experiment()
        self.state = 'polling'


if __name__ == '__main__':
    main()

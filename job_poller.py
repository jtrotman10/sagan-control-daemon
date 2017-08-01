#!/env/bin/python3

from subprocess import Popen, PIPE, TimeoutExpired, check_call, STDOUT

import select

import shutil
from websocket import WebSocketConnectionClosedException
from requests.exceptions import ConnectionError
from threading import Thread, Event, RLock
from requests import get, put, post
from codecs import decode
from time import sleep
from glob import glob
import websocket
import time
import json
import sys
import os
import re

_current_poller = None
_TELEMETRY_PIPE_PATH = "/opt/sagan-control-daemon/telemetry"


# --------------- end web socket event handlers -------------------------


def process_read(out_stream, socket, log_stream):
    while True:
        try:
            data = os.read(out_stream.fileno(), 512)
        except OSError:
            break
        if data == b'':
            break
        try:
            socket.emit("stdout", data.decode("utf8"))
            log_stream.write(data)
        except (BrokenPipeError, WebSocketConnectionClosedException):
            break


def process_error(out_stream, socket, log_stream):
    while True:
        try:
            data = os.read(out_stream.fileno(), 512)
        except OSError:
            break
        if data == b'':
            break
        try:
            socket.emit('stder', decode(data))
            log_stream.write(data)
        except (BrokenPipeError, WebSocketConnectionClosedException):
            break


def heart_beat(url):
    response = put(url, {})
    return response.status_code in {200, 204}


def heart_beat_loop(url, heart_beat_time, stop_trigger: Event, leds, leds_lock):
    retry_count = 0
    while not stop_trigger.is_set():
        try:
            if not heart_beat(url):
                exit(2)
            if leds_lock.acquire(blocking=False):
                leds.write('g\n')
                leds.flush()
                leds_lock.release()
        except ConnectionError:
            if retry_count > 3:
                exit(1)
            else:
                if leds_lock.acquire(blocking=False):
                    leds.write('r\n')
                    leds.flush()
                    leds_lock.release()
                sleep(10)
                retry_count += 1
        else:
            retry_count = 0
        sleep(heart_beat_time)

READ_LEN = 512
DELIMITER = b'\n'


def handle_telemetry_pipe(socket, _FIFO_PATH, process: Popen):
    pipe = None
    try:
        pipe = os.open(_FIFO_PATH, os.O_NONBLOCK | os.O_RDONLY)
    except FileNotFoundError:
        socket.emit('error', "sagan telemetry configuration error")

    buf = b''
    while process.poll() is None:
        r, w, x = select.select([pipe], [], [], 1)
        if pipe in r:
            try:
                new_data = os.read(pipe, READ_LEN)
            except OSError as os_error:
                if os_error.errno == 35:
                    # errno 32 is "File temporarily unavailable"
                    continue
                else:
                    print('error reading pipe')
                    print(os_error, file=sys.stderr)
                    break
            delim_pos = new_data.find(DELIMITER)
            if delim_pos:
                buf += new_data[:delim_pos + 1]
                socket.emit('telem', buf.strip().decode())
                buf = new_data[delim_pos + 1:]
            else:
                buf += new_data


class Socket:
    def __init__(self, **kwargs):
        self.url = kwargs.get("url")
        self.stdin = kwargs.get("stdin")
        self.running = True
        self.socket = websocket.WebSocketApp(
            self.url,
            on_message=self.on_message,
        )
        self.socket.keep_running = True
        self._stop = Event()
        self.wst = Thread(target=self._run)
        self.wst.daemon = True
        self.wst.start()
        self.buffer = []
        self.buffer_max_size = 200

    def _run(self):
        while not self._stop.is_set():
            self.socket.run_forever()

    def on_message(self, _, message):
        payload = json.loads(message)['a']
        payload = [payload["0"], payload["1"]]
        if str(payload[0]) == "stdin":
            self.stdin.write(payload[1].encode())
        else:
            pass

    def close(self):
        self._stop.set()
        try:
            self.socket.close()
        except WebSocketConnectionClosedException:
            pass

    def emit(self, channel, message):
        payload = json.dumps({
            'a': {
                '0': channel,
                '1': message
            }
        })
        try:
            self.socket.send(payload)
        except (BrokenPipeError, WebSocketConnectionClosedException):
            return False
        return True


class Poller:
    def __init__(self, device_id, host, leds=None):
        self.device_id = device_id
        self.host = host

        self.out_thread = None
        self.run_job = None

        self.out_log = None
        self.experiment_process = None  # type: Popen

        self.socket = None

        self.FIFO = None
        self.fifo_thread = None

        self.results_stream = None
        self.error_stream = None

        self.socket_url = None
        self.telemetry_pipe = None

        self.stdout_text = b''
        self.stderr_text = b''

        self.socket_close_socket = None  # type: Event
        self.state = 'polling'
        self.state_machine = {
            'polling': self.check_for_jobs,
            'running': self.run_experiment,
            'termination_requested': self.kill_subproc
        }
        self.leds_file = leds
        self.leds_lock = RLock()
        if not leds:
            self.leds_file = open('/dev/null', 'w')

    def set_leds(self, cmd):
        with self.leds_lock:
            self.leds_file.write(cmd + '\n')
            self.leds_file.flush()

    def go(self):
        self.set_leds('~')
        print('Device id: {}'.format(self.device_id))
        print('Awaiting work.')
        url = '{0}/dispatch/devices/{1}/heartbeat'.format(self.host, self.device_id)
        stop_event = Event()
        heart_beat_thread = Thread(target=heart_beat_loop, args=(url, 5, stop_event, self.leds_file, self.leds_lock))
        heart_beat_thread.start()
        retry_count = 0
        try:
            while self.state is not 'exit':
                try:
                    self.state_machine[self.state]()
                except ConnectionError as error:
                    print(error)
                    if retry_count > 3:
                        exit(1)
                    else:
                        sleep(10)
                        retry_count += 1
                        continue
                else:
                    retry_count = 0
        except KeyboardInterrupt:
            self.state = 'exit'

        if self.experiment_process:
            self.kill_subproc()
        stop_event.set()
        heart_beat_thread.join()
        self.set_leds('n')

    def check_for_jobs(self):
        url = '{0}/dispatch/devices/{1}/queue'.format(self.host, self.device_id)
        result = get(url)
        if result.status_code != 200:
            exit(2)
        jobs = [job for job in result.json() if job['state'] == 0]
        if len(jobs) > 0:
            next_job = jobs[0]
            print('Found job id {}, fetching experiment.'.format(next_job['id']))
            self.run_job = next_job['id']
            self.socket_url = next_job['socket']
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
        print('Packing results.')
        self.set_leds('~')
        self.out_log.flush()
        check_call(['/usr/bin/zip', 'results.zip'] + glob('*'))
        print('Uploading results.')
        result = post(
            '{0}/api/files/'.format(self.host),
            files={
                'file': ('results.zip', open('results.zip', 'rb')),
                'description': ('', 'Experiment results for job {}'.format(self.run_job))
            }
        )
        if result.status_code != 201:
            print("Failed to upload results")
            return

        result = put(
            '{0}/dispatch/jobs/{1}/finish'.format(self.host, self.run_job),
            {
                'out': '',
                'error': '',
                'results': result.json()['id']
            }
        )
        if result.status_code != 200:
            print("Failed to notify server that job finished")

        print('Results uploaded.')

    def clean_sandbox(self):
        os.chdir('..')
        shutil.rmtree('sandbox')
        os.mkdir('sandbox')


    def start_experiment_proc(self, experiment):
        with open('experiment.py', 'w') as f:
            f.write(experiment['code_string'])

        env = os.environ.copy()
        env['PATH'] += ':/home/pi/Documents/cuberider/'
        env['TELEMETRY'] = _TELEMETRY_PIPE_PATH
        self.experiment_process = Popen(
            [sys.executable, '-u', 'experiment.py'],
            stdin=PIPE,
            stdout=PIPE,
            stderr=STDOUT,
            bufsize=0,
            env=env
        )

    def start_experiment(self, experiment):
        print('Starting experiment "{}".'.format(experiment['title']))
        self.leds_lock.acquire()
        self.set_leds('n')

        self.clean_sandbox()

        self.start_experiment_proc(experiment)

        # instantiate the socket
        self.socket = Socket(url=self.socket_url, stdin=self.experiment_process.stdin)

        # create experiment log file
        self.out_log = open('experiment_log.txt', 'wb')

        self.fifo_thread = Thread(
            target=handle_telemetry_pipe,
            args=(
                self.socket,
                _TELEMETRY_PIPE_PATH,
                self.experiment_process
            )
        )
        self.fifo_thread.start()

        self.out_thread = Thread(
            target=process_read,
            args=(
                self.experiment_process.stdout,
                self.socket,
                self.out_log
            )
        )
        self.out_thread.start()

    def end_experiment(self):
        self.out_thread.join()
        self.fifo_thread.join()
        self.post_results()
        self.experiment_process = None
        self.clean_sandbox()
        self.socket.close()
        self.set_leds('g')
        self.leds_lock.release()
        print('Job finished.')

    def run_experiment(self):
        try:
            self.experiment_process.wait(1)
        except TimeoutExpired:
            state = self.get_state()
            if state == 2:
                self.kill_subproc()
        else:
            self.end_experiment()
            self.state = 'polling'

    def kill_subproc(self):
        print('Terminating job.')
        self.experiment_process.terminate()
        try:
            self.experiment_process.wait(timeout=10)
        except TimeoutExpired:
            print('Process taking to long to terminate, killing.')
            self.experiment_process.kill()
            try:
                self.experiment_process.wait(timeout=10)
            except TimeoutExpired:
                print('WARNING: Experiment failed to stop.')
        self.end_experiment()
        self.state = 'polling'


def main():
    global _current_poller
    leds = None
    if len(sys.argv) > 4:
        leds = open(sys.argv[4], 'w')
    os.chdir(sys.argv[3])
    _current_poller = Poller(int(sys.argv[1]), sys.argv[2], leds)
    _current_poller.go()


if __name__ == '__main__':
    main()

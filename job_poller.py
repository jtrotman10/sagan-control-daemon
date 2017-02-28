#!/env/bin/python3

from subprocess import Popen, PIPE, TimeoutExpired, check_call, STDOUT
from websocket import WebSocketConnectionClosedException
from requests.exceptions import ConnectionError
from threading import Thread, Event
from requests import get, put, post
from codecs import decode
from time import sleep
from glob import glob
import websocket
import time
import json
import sys
import os

_current_poller = None

# --------------- web socket event handlers -------------------------


def emit(ws, channel, message):
    ws.send('{"a": {"0":"{}","1":"{}"}}'.format(channel, message))


def on_error(ws, error):
    print("### web socket error  ### {}".format(error))


def on_close(ws):
    print("### web socket closed ###")


def on_open(ws):
    print("### web socket opened ###")

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
            print("socket emit <{}>".format(data.decode("utf8")))
            emit(socket, 'stdout', data.decode("utf8"))
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
            emit(socket, 'stder', decode(data))
            log_stream.write(data)
        except (BrokenPipeError, WebSocketConnectionClosedException):
            break


def heart_beat(url, heart_beat_time, stop_trigger: Event):
    retry_count = 0
    while not stop_trigger.is_set():
        try:
            response = put(url, {})
            if response.status_code not in (200, 204):
                exit(1)
        except ConnectionError:
            if retry_count > 3:
                exit(1)
            else:
                sleep(10)
                retry_count += 1
        else:
            retry_count = 0
        sleep(heart_beat_time)


class Poller:
    def __init__(self, device_id, host, leds=None):
        self.device_id = device_id
        self.host = host
        self.out_thread = None
        self.run_job = None
        self.out_log = None
        self.experiment_process = None  # type: Popen
        self.ip = None
        self.port = None
        self.socket = None
        self.results_stream = None
        self.error_stream = None
        self.socket_url = None
        self.stdout_text = b''
        self.stderr_text = b''
        self.state = 'polling'
        self.state_machine = {
            'polling': self.check_for_jobs,
            'running': self.run_experiment,
            'termination_requested': self.kill_subproc
        }
        self.leds_file = leds
        if not leds:
            self.leds_file = open('/dev/null', 'w')

    def set_leds(self, cmd):
        self.leds_file.write(cmd + '\n')
        self.leds_file.flush()

    def go(self):
        print('Device id: {}'.format(self.device_id))
        print('Awaiting work.')
        url = '{0}/dispatch/devices/{1}/heartbeat'.format(self.host, self.device_id)
        self.set_leds('g')
        stop_event = Event()
        heart_beat_thread = Thread(target=heart_beat, args=(url, 5, stop_event))
        heart_beat_thread.start()
        retry_count = 0
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
            except KeyboardInterrupt:
                self.state = 'exit'
            else:
                retry_count = 0

        if self.experiment_process:
            self.kill_subproc()
        stop_event.set()
        heart_beat_thread.join()
        self.set_leds('n')

    def check_for_jobs(self):
        url = '{0}/dispatch/devices/{1}/queue'.format(self.host, self.device_id)
        jobs = [job for job in get(url).json() if job['state'] == 0]
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
        print('Uploading results.')
        self.set_leds('~')
        self.out_log.flush()
        check_call(['/usr/bin/zip', 'results.zip'] + glob('*'))
        result = post(
            '{0}/api/files/'.format(self.host),
            files={
                'file': ('results.zip', open('results.zip', 'rb')),
                'description': ('', 'Experiment results for job {}'.format(self.run_job))
            }
        )
        if result.status_code != 201:
            print("Failed to upload results")
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

    def clean_sandbox(self):
        files = os.listdir(path='.')
        if files:
            check_call(['/bin/bash', '-c', 'rm -r {}'.format(' '.join(files))])

    def start_experiment_proc(self, experiment):
        with open('experiment.py', 'w') as f:
            f.write(experiment['code_string'])

        env = os.environ.copy()
        env['PATH'] += ':/home/pi/Documents/cuberider/'
        self.experiment_process = Popen(
            [sys.executable, '-u', 'experiment.py'],
            stdin=PIPE,
            stdout=PIPE,
            stderr=STDOUT,
            bufsize=0,
            env=env
        )

    def handle_stdin(self, message):
        print("stdin message recieved <{}>".format(message))
        self.experiment_process.stdin.write(message)
        self.out_log.write(message)

    def on_message(self, _, message):
        payload = json.loads(message)['a']
        payload = [payload["0"], payload["1"]]
        if str(payload[0]) == "stdin":
            self.handle_stdin(payload[1])
        else:
            pass

    def start_experiment(self, experiment):
        print('Starting experiment "{}".'.format(experiment['title']))
        self.set_leds('n')
        self.clean_sandbox()

        # connect the socket
        self.ip = (self.socket_url.split(":")[1])[2:]
        self.port = self.socket_url.split(":")[1]

        # connect to the websocket
        self.socket = websocket.WebSocketApp(
            self.socket_url,
            on_message=self.on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        self.socket.run_forever()
        print("socket initialised")
        self.start_experiment_proc(experiment)

        # create experiment log file
        self.out_log = open('experiment_log.txt', 'wb')

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
        self.socket.close()
        self.post_results()
        self.experiment_process = None
        self.clean_sandbox()
        self.set_leds('g')
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
        self.post_results()
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

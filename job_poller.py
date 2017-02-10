import sys

import time
from requests import get, patch, put
from datetime import datetime

from subprocess import Popen, PIPE, TimeoutExpired

from requests.exceptions import ConnectionError

_current_poller = None


def main():
    global _current_poller
    _current_poller = Poller(int(sys.argv[1]), sys.argv[2])
    _current_poller.go()


class Poller:
    def __init__(self, device_id, host):
        self.device_id = device_id
        self.host = host
        self.run_job = None
        self.experiment_process = None
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
                print(repr(error))
                time.sleep(5)

    def heartbeat(self):
        url = '{0}/dispatch/devices/{1}/heartbeat'.format(self.host, self.device_id)
        patch(url, {'state': 0 if self.state is 'polling' else 1})

    def check_for_jobs(self):
        url = '{0}/dispatch/devices/{1}/queue'.format(self.host, self.device_id)
        jobs = get(url).json()
        if len(jobs) > 0:
            next_job = sorted(jobs, key=lambda x: x['time_scheduled'])[0]
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

    def run_experiment(self):
        try:
            self.communicate(timeout=1)
        except TimeoutExpired:
            pass

        if self.get_state() == 2:
            self.state = 'termination_requested'

        if not self.is_experiment_running():
            # Experiment has stopped
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

    def communicate(self, **kwargs):
        out, err = self.experiment_process.communicate(**kwargs)
        self.stdout_text += out
        self.stderr_text += err

    def is_experiment_running(self):
        return self.experiment_process.poll() is None

    def start_experiment(self, experiment):
        print('Starting experiment "{}".'.format(experiment['name']))
        self.experiment_process = Popen(
            [sys.executable, '-c', experiment['text']],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            bufsize=1
        )
        self.results_stream = self.experiment_process.stdout
        self.error_stream = self.experiment_process.stderr

    def end_experiment(self):
        print('Job finished, awaiting work.')
        self.results_stream = None
        self.error_stream = None
        self.experiment_process = None
        self.stderr_text = b''
        self.stdout_text = b''

if __name__ == '__main__':
    main()

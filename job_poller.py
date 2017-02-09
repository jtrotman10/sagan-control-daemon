import io

import sys

import time
from requests import get, patch
from datetime import datetime

from subprocess import Popen, PIPE


def main():
    poller = Poller(int(sys.argv[1]), sys.argv[2])
    poller.go()


class Poller:
    def __init__(self, device_id, host):
        self.device_id = device_id
        self.host = host
        self.run_job = None
        self.experiment_process = None
        self.results_stream = None
        self.error_stream = None
        self.results = ''

    def go(self):
        while True:
            # Super simple work loop, only two state, polling for work, or doing it
            if self.experiment_process is None:
                print('Polling for job')
                jobs = self.check_for_jobs()
                if len(jobs) > 0:
                    print('Found job, starting')
                    next_job = sorted(jobs, key=lambda x: x['time_scheduled'])[0]
                    self.run_job = next_job['id']
                    text = self.get_experiment(next_job['experiment'])
                    self.start_experiment(text)
                    self.notify_start()
                else:
                    time.sleep(5)
            else:
                print("Waiting for job to finish")
                for line in self.results_stream:
                    self.results += line
                    self.update_status(line)

                if not self.is_experiment_running():
                    print('Job finished')
                    # Experiment has stopped
                    self.post_results(self.results + 'Error :\n' + self.error_stream.read())
                    self.end_experiment()

    def check_for_jobs(self):
        url = '{0}/dispatch/device/{1}/jobs'.format(self.host, self.device_id)
        return get(url).json()

    def get_experiment(self, experiment_id):
        url = '{0}/dispatch/experiment/{1}'.format(self.host, experiment_id)
        return get(url).json()['text']

    def update_job(self, **kwargs):
        url = '{0}/dispatch/job/{1}'.format(self.host, self.run_job)
        update = {
            'id': self.run_job
        }
        update.update(kwargs)
        return patch(url, data=update)

    def notify_start(self):
        return self.update_job(time_started=datetime.utcnow())

    def update_status(self, text):
        return self.update_job(live_status=text)

    def post_results(self, results):
        return self.update_job(time_finished=datetime.utcnow(), result=results)

    def is_experiment_running(self):
        return self.experiment_process.poll() is None

    def start_experiment(self, experiment_text):
        self.results = ''
        self.experiment_process = Popen(
            [sys.executable, '-c', experiment_text],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            universal_newlines=True,
            bufsize=1
        )
        self.results_stream = self.experiment_process.stdout
        self.error_stream = self.experiment_process.stderr

    def end_experiment(self):
        self.results_stream = None
        self.error_stream = None
        self.experiment_process = None


if __name__ == '__main__':
    main()

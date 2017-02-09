from random import choice
import json

import sys

from os.path import isfile
from subprocess import check_call, Popen, CalledProcessError, PIPE


class StateMachine:
    states = ()
    events = ()
    transitions = {}

    def __init__(self):
        self._state = 'halted'
        self._next_state = None
        self._event = None

        # pre-start sanity check
        for state in self.states:
            assert hasattr(self, state), "Missing state method for {}".format(state)
            for event, next_state in self.transitions[state].items():
                assert next_state in self.states, "Unknown state {}".format(next_state)
                assert event in self.events, "Unknown state {}".format(event)
                assert hasattr(self, '{}_{}'.format(state, event)), "Missing event method for {} in state {}".format(
                    event,
                    state)

        # BFS to check all states are connected
        visited = {state: False for state in self.states}
        queue = [self.states[0]]
        while queue:
            v = queue.pop(0)
            visited[v] = True
            for event, u in self.transitions[v].items():
                if not visited[u]:
                    queue.append(u)

        assert all(visited.values()), "Unconnected states: {}".format(
            ' '.join([k for k, v in visited.items() if not v]))

    def dispatch_event(self, state, event):
        print('event {}'.format(event))
        return self.__getattribute__(
            '{}_{}'.format(state, event))()

    def dispatch_state(self, state):
        return self.__getattribute__(
            state
        )()

    def trigger(self, event):
        assert event in self.transitions[self._state]
        self.dispatch_event(self._state, event)
        assert self._next_state is None
        self._next_state = self.transitions[self._state][event]

    def run(self):
        while True:
            print('state {}'.format(self._state))
            self.dispatch_state(self._state)
            if self._next_state is not None:
                self._state = self._next_state
                self._next_state = None

            if self._state is 'halted':
                return


class SaganController(StateMachine):
    def __init__(self, config_file_path):
        super().__init__()
        self.config_file_path = config_file_path
        self.config = self.initial_config.copy()

    states = [
        'started',
        'starting_ap',
        'serving_config_page',
        'attempting_wifi_connection',
        'pairing',
        'checking_in',
        'polling_for_work',
        'halted'
    ]

    events = [
        'start',
        'halt',
        'config_invalid',
        'config_valid',
        'ap_started',
        'known_network_found',
        'received_new_config',
        'wifi_connection_success',
        'wifi_connection_failure',
        'pairing_failure',
        'pairing_success',
        'network_failure',
        'check_in_success',
        'check_in_failure',
        'token_expired'
    ]

    transitions = {
        'halted': {
            'start': 'started'
        },
        'started': {
            'config_invalid': 'starting_ap',
            'config_valid': 'checking_in',
            'halt': 'halted'
        },
        'starting_ap': {
            'ap_started': 'serving_config_page',
            'halt': 'halted'
        },
        'serving_config_page': {
            'received_new_config': 'attempting_wifi_connection',
            'halt': 'halted'
        },
        'attempting_wifi_connection': {
            'wifi_connection_success': 'pairing',
            'wifi_connection_failure': 'starting_ap',
            'halt': 'halted'
        },
        'pairing': {
            'pairing_failure': 'starting_ap',
            'pairing_success': 'checking_in',
            'halt': 'halted'
        },
        'checking_in': {
            'check_in_failure': 'starting_ap',
            'check_in_success': 'polling_for_work',
            'halt': 'halted'
        },
        'polling_for_work': {
            'network_failure': 'starting_ap',
            'token_expired': 'checking_in',
            'halt': 'halted'
        }
    }

    initial_config = {
        'pairing_code': '',
        'ssid': '',
        'psk': ''
    }

    def save_config(self):
        with open(self.config_file_path, 'w') as f:
            json.dump(self.config, f)

    def load_config(self):
        if not isfile(self.config_file_path):
            self.save_config()
        else:
            with open(self.config_file_path, 'r') as f:
                self.config.update(json.load(f))

    def check_config(self):
        required_fields = ['pairing_code']
        return all(self.config.get(field, None) for field in required_fields)

    def halted(self):
        self.trigger('start')

    def halted_start(self):
        pass

    def started(self):
        self.load_config()
        if self.check_config():
            self.trigger('config_valid')
        else:
            self.trigger('config_invalid')

    def started_halt(self):
        pass

    def started_config_valid(self):
        pass

    def started_config_invalid(self):
        pass

    def starting_ap(self):
        try:
            check_call(['bash', './start-ap.sh'])
            self.trigger('ap_started')
        except CalledProcessError:
            self.trigger('halt')

    def starting_ap_known_network_found(self):
        pass

    def starting_ap_ap_started(self):
        pass

    def starting_ap_halt(self):
        check_call(['bash', 'stop-ap.sh'])

    def serving_config_page(self):
        server = Popen(['bash', 'serve-config-page.sh'], stdout=PIPE, stderr=None)
        try:
            out, error = server.communicate()
            lines = out.decode().split('\n')
            print('New config {}'.format(self.config))
            self.config['pairing_code'] = lines[0]
            check_call(['bash', 'add-wifi-network.sh', self.config['ssid'], self.config['psk']])
            self.trigger('received_new_config')
        except CalledProcessError:
            self.trigger('halt')

    def serving_config_page_received_new_config(self):
        check_call(['bash', 'stop-ap.sh'])

    def serving_config_page_halt(self):
        check_call(['bash', 'stop-ap.sh'])

    def attempting_wifi_connection(self):
        timeout = 2
        try:
            check_call(['bash', 'check-connection.sh', str(timeout)])
            self.trigger('wifi_connection_success')
        except CalledProcessError:
            self.trigger('wifi_connection_failure')

    def attempting_wifi_connection_wifi_connection_success(self):
        pass

    def attempting_wifi_connection_wifi_connection_failure(self):
        pass

    def attempting_wifi_connection_halt(self):
        pass

    def pairing(self):
        self.trigger(choice(list(self.transitions['pairing'].keys())))

    def pairing_halt(self):
        pass

    def pairing_pairing_failure(self):
        pass

    def pairing_pairing_success(self):
        pass

    def checking_in(self):
        self.trigger(choice(list(self.transitions['checking_in'].keys())))

    def checking_in_check_in_success(self):
        pass

    def checking_in_check_in_failure(self):
        pass

    def checking_in_halt(self):
        pass

    def polling_for_work(self):
        try:
            check_call(['bash', 'run-job-poller.sh'])
        except CalledProcessError as error:
            if error.returncode == 1:
                self.trigger('network_error')
            elif error.returncode == 2:
                self.trigger('token_expired')
            else:
                self.trigger('halt')

    def polling_for_work_network_failure(self):
        pass

    def polling_for_work_token_expired(self):
        pass

    def polling_for_work_halt(self):
        pass


def main():
    sagan_controller = SaganController(sys.argv[1])
    sagan_controller.run()


if __name__ == '__main__':
    main()

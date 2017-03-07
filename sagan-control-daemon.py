from signal import signal, SIGINT, SIGTERM
from codecs import decode
import json

import sys
import os

from os.path import isfile
from subprocess import check_call, check_output, Popen, CalledProcessError, PIPE, TimeoutExpired
from re import compile

from requests.api import post


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

    def _term(self, signum, frame):
        print('TERM received.')
        self.trigger('halt')

    def run(self):
        signal(SIGINT, self._term)
        signal(SIGTERM, self._term)
        while True:
            try:
                print('state {}'.format(self._state))
                self.dispatch_state(self._state)
                if self._next_state is not None:
                    self._state = self._next_state
                    self._next_state = None

                if self._state is 'halted':
                    return
            except KeyboardInterrupt:
                self._term()


ap_list_re = compile(r'SSID: ([^\n]*)')


def ap_scan(interface):
    retry_count = 0
    while retry_count < 3:
        try:
            output = check_output(['/sbin/iw', interface, 'scan', 'ap-force'], timeout=20)
            break
        except (CalledProcessError, TimeoutExpired):
            retry_count += 1
    else:
        return []

    output = decode(output)
    results = set()
    for result in ap_list_re.finditer(output):
        ssid = result.group(1).strip()
        if len(ssid) > 0:
            results.add(ssid)

    return list(results)


class SaganController(StateMachine):
    def __init__(self, config_file_path):
        super().__init__()
        self.config_file_path = config_file_path
        self.config = self.initial_config.copy()
        self.leds_file = open('leds', 'w')

    states = [
        'started',
        'starting_ap',
        'serving_config_page',
        'attempting_wifi_connection',
        'pairing',
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
    ]

    transitions = {
        'halted': {
            'start': 'started'
        },
        'started': {
            'config_invalid': 'starting_ap',
            'config_valid': 'polling_for_work',
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
            'pairing_success': 'polling_for_work',
            'halt': 'halted'
        },
        'polling_for_work': {
            'network_failure': 'starting_ap',
            'halt': 'halted'
        }
    }

    initial_config = {
        'pairing_code': '',
        'device_name': '',
        'device_id': '',
        'ssid': '',
        'psk': '',
        'host': 'http://launchpad.cuberider.com',
        'interface': 'wlan0',
        'user': 'pi',
        'error': ''
    }

    def save_config(self):
        with open(self.config_file_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def load_config(self):
        if not isfile(self.config_file_path):
            # This writes a default config file containing initial_config
            self.save_config()
        else:
            with open(self.config_file_path, 'r') as f:
                self.config.update(json.load(f))

    def check_config(self):
        required_fields = ['device_id']
        return all(self.config.get(field, None) for field in required_fields)

    def set_leds(self, cmd):
        self.leds_file.write(cmd + '\n')
        self.leds_file.flush()

    def halted(self):
        self.trigger('start')

    def halted_start(self):
        self.set_leds('~')
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
            check_call(['/bin/bash', './start-ap.sh', self.config['interface']])
            self.trigger('ap_started')
        except CalledProcessError:
            self.trigger('halt')

    def starting_ap_known_network_found(self):
        pass

    def starting_ap_ap_started(self):
        pass

    def starting_ap_halt(self):
        check_call(['/bin/bash', 'stop-ap.sh', self.config['interface']])

    def serving_config_page(self):
        try:
            ap_list = ap_scan(self.config['interface'])
        except CalledProcessError:
            self.trigger('halt')
            return
        print('Visible APs: {}'.format(ap_list))
        process_args = [
            sys.executable,
            'server.py',
            '0.0.0.0',
            '80',
            'networks',
            ','.join(ap_list)
        ]

        if self.config['error'] != '':
            process_args += [
                'error',
                self.config['error']
            ]

        if self.config['device_id']:
            process_args += ['paired', '1']
        self.server = Popen(process_args, stdout=PIPE)
        self.set_leds('y')
        lines = [decode(self.server.stdout.readline()) for _ in range(5)]
        if lines[4] != '\n':
            self.trigger('halt')
            return
        self.config['pairing_code'] = lines[0].strip()
        self.config['ssid'] = lines[1].strip()
        self.config['psk'] = lines[2].strip()
        self.config['device_name'] = lines[3].strip()
        print('New config {}'.format(self.config))
        self.server.terminate()
        try:
            self.server.wait(10)
            self.set_leds('~')
            check_call(['/bin/bash', 'stop-ap.sh', self.config['interface']])
            self.trigger('received_new_config')
        except (TimeoutExpired, CalledProcessError):
            self.trigger('halt')
        self.set_leds('~')

    def serving_config_page_received_new_config(self):
        pass

    def serving_config_page_halt(self):
        check_call(['/bin/bash', 'stop-ap.sh', self.config['interface']])

    def attempting_wifi_connection(self):
        timeout = 20
        try:
            check_call([
                '/bin/bash',
                'add-wifi-network.sh',
                self.config['ssid'],
                self.config['psk'],
                self.config['interface']
            ])
            check_call(['/bin/bash', 'check-connection.sh', str(timeout)])
            self.trigger('wifi_connection_success')
        except CalledProcessError:
            self.trigger('wifi_connection_failure')

    def attempting_wifi_connection_wifi_connection_success(self):
        self.config['error'] = ''
        self.save_config()

    def attempting_wifi_connection_wifi_connection_failure(self):
        self.config['error'] = 'Could not connect to the wifi network.'
        self.save_config()

    def attempting_wifi_connection_halt(self):
        pass

    def pairing(self):
        if self.config['device_id'] == '':
            try:
                result = post(
                    '{}/dispatch/devices/'.format(self.config['host']),
                    {
                        'code': self.config['pairing_code'],
                        'name': self.config['device_name']
                    }
                )
                if result.status_code != 201:
                    self.trigger('pairing_failure')
                else:
                    device = result.json()
                    self.config['device_id'] = device['id']
                    self.config['device_name'] = device['name']
                    self.save_config()
                    self.trigger('pairing_success')
            except (KeyError):
                self.trigger('pairing_failure')
        else:
            self.trigger('pairing_success')

    def pairing_halt(self):
        pass

    def pairing_pairing_failure(self):
        self.config['error'] = 'Could not pair with the give code.'
        self.save_config()

    def pairing_pairing_success(self):
        self.config['error'] = ''
        self.save_config()

    def polling_for_work(self):
        try:
            check_call([
                '/usr/bin/sudo',
                '-u',
                self.config['user'],
                sys.executable,
                'job_poller.py',
                str(self.config['device_id']),
                self.config['host'],
                os.path.join(os.curdir, 'sandbox'),
                os.path.join(os.curdir, 'leds')
            ])
        except CalledProcessError as error:
            if error.returncode == 1:
                self.config['error'] = 'Could not connect to the internet over the Wifi network selected.'
                self.trigger('network_failure')
            elif error.returncode == 2:
                self.config['error'] = 'Device not paired with Launchpad.'
                self.config['device_id'] = ''
                self.config['device_name'] = ''
                self.trigger('network_failure')
            elif error.returncode == 143:
                # term'd
                pass
            else:
                self.trigger('halt')
            self.save_config()

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

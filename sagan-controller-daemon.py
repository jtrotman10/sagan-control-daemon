from random import choice


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

    def transition_to(self, state):
        print()
        self._state = state

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
            'config_valid': 'checking_in'
        },
        'starting_ap': {
            'ap_started': 'serving_config_page'
        },
        'serving_config_page': {
            'received_new_config': 'attempting_wifi_connection'
        },
        'attempting_wifi_connection': {
            'wifi_connection_success': 'pairing',
            'wifi_connection_failure': 'starting_ap'
        },
        'pairing': {
            'pairing_failure': 'starting_ap',
            'pairing_success': 'checking_in'
        },
        'checking_in': {
            'check_in_failure': 'starting_ap',
            'check_in_success': 'polling_for_work'
        },
        'polling_for_work': {
            'network_failure': 'starting_ap',
            'token_expired': 'checking_in'
        }
    }

    def halted(self):
        self.trigger('start')

    def halted_start(self):
        pass

    def started(self):
        self.trigger(choice(list(self.transitions['started'].keys())))

    def started_config_valid(self):
        pass

    def started_config_invalid(self):
        pass

    def starting_ap(self):
        self.trigger(choice(list(self.transitions['starting_ap'].keys())))

    def starting_ap_known_network_found(self):
        pass

    def starting_ap_ap_started(self):
        pass

    def serving_config_page(self):
        self.trigger(choice(list(self.transitions['serving_config_page'].keys())))

    def serving_config_page_received_new_config(self):
        pass

    def attempting_wifi_connection(self):
        self.trigger(choice(list(self.transitions['attempting_wifi_connection'].keys())))

    def attempting_wifi_connection_wifi_connection_success(self):
        pass

    def attempting_wifi_connection_wifi_connection_failure(self):
        pass

    def pairing(self):
        self.trigger(choice(list(self.transitions['pairing'].keys())))

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

    def polling_for_work(self):
        self.trigger(choice(list(self.transitions['polling_for_work'].keys())))

    def polling_for_work_network_failure(self):
        pass

    def polling_for_work_token_expired(self):
        pass


def main():
    sagan_controller = SaganController()
    sagan_controller.run()


if __name__ == '__main__':
    main()

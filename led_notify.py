import time
import RPi.GPIO as GPIO
from math import cos, pi
from threading import Thread
from queue import Queue, Empty


class Notifier:
    def __init__(self):
        self.r = None
        self.g = None
        self.b = None
        self.queue = Queue()
        self.pattern_params = {
            'w': ((0, 0),    (0, 0),    (0, 0)),
            'r': ((1, 0),    (0, 0),    (0, 0)),
            'g': ((0, 0),    (1, 0),    (0, 0)),
            'b': ((0, 0),    (0, 0),    (1, 0)),
            'c': ((0, 0.25), (1, 0),    (1, 0)),
            'y': ((1, 0),    (1, 0),    (0, 0.25)),
            'm': ((1, 0),    (0, 0.25), (1, 0)),
            '~': ((1, 0),    (3, 0.33), (3, .66))
        }

    def init(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(23, GPIO.OUT)
        GPIO.setup(24, GPIO.OUT)
        GPIO.setup(25, GPIO.OUT)

        self.r = GPIO.PWM(25, 1000)  # channel=24 frequency=50Hz
        self.g = GPIO.PWM(23, 1000)  # channel=24 frequency=50Hz
        self.b = GPIO.PWM(24, 1000)  # channel=24 frequency=50Hz
        self.r.start(100)
        self.g.start(100)
        self.b.start(100)

    def teardown(self):
        self.r.stop()
        self.g.stop()
        self.b.stop()
        GPIO.cleanup()

    def read_commands(self):
        try:
            while True:
                cmd = input()
                self.queue.put(cmd)
                if cmd == 'x':
                    break
        except KeyboardInterrupt:
            self.queue.put('x')

    def update_leds(self):
        period = 1000
        i = 0
        pattern = None
        while 1:
            try:
                cmd = self.queue.get_nowait()
            except Empty:
                cmd = None
            if cmd:
                if cmd == 'x':
                    if pattern:
                        self.teardown()
                    break
                if cmd == 'n':
                    if pattern:
                        self.teardown()
                        pattern = None
                else:
                    if not pattern:
                        self.init()
                    pattern = cmd

            if pattern:
                params = self.pattern_params[pattern]
                self.r.ChangeDutyCycle(int(cos((params[0][0] * i + params[0][1] * period) * pi / period) * 50) + 50)
                self.g.ChangeDutyCycle(int(cos((params[1][0] * i + params[1][1] * period) * pi / period) * 50) + 50)
                self.b.ChangeDutyCycle(int(cos((params[2][0] * i + params[2][1] * period) * pi / period) * 50) + 50)
            i += 1

    def run(self):
        update_thread = Thread(target=self.update_leds)
        update_thread.start()
        self.read_commands()
        update_thread.join()


def main():
    notifier = Notifier()
    notifier.run()


if __name__ == '__main__':
    main()
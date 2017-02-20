import time
from time import sleep

import RPi.GPIO as GPIO
from math import cos, pi
from threading import Thread
from queue import Queue, Empty

import sys


class Notifier:
    def __init__(self, cmd_file=None):
        self.r = None
        self.g = None
        self.b = None
        self.queue = Queue()
        self.pattern_params = {
            'w': ((0, 0), (0, 0), (0, 0)),
            'r': ((1, 0), (0, 0), (0, 0)),
            'g': ((0, 0), (1, 0), (0, 0)),
            'b': ((0, 0), (0, 0), (1, 0)),
            'c': ((0, 0), (1, 0), (1, 0)),
            'y': ((1, 0), (1, 0), (0, 0)),
            'm': ((1, 0), (0, 0), (1, 0)),
            '~': ((1, 0), (1, 0.33), (1, .66))
        }
        self.cmds = {
            'w',
            'r',
            'g',
            'b',
            'c',
            'y',
            'm',
            '~',
            'n',
            'x'
        }
        self.cmd_file = cmd_file or sys.stdin

    def init(self):
        led1_pin = 27
        led2_pin = 22
        red_pin = 25
        green_pin = 23
        blue_pin = 24

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(red_pin, GPIO.OUT)
        GPIO.setup(green_pin, GPIO.OUT)
        GPIO.setup(blue_pin, GPIO.OUT)
        GPIO.setup(led1_pin, GPIO.OUT)
        GPIO.setup(led2_pin, GPIO.OUT)
        GPIO.output(led1_pin, True)
        GPIO.output(led2_pin, True)

        self.r = GPIO.PWM(red_pin, 1000)  # channel=24 frequency=50Hz
        self.g = GPIO.PWM(green_pin, 1000)  # channel=24 frequency=50Hz
        self.b = GPIO.PWM(blue_pin, 1000)  # channel=24 frequency=50Hz
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
                cmd = self.cmd_file.readline().strip()
                if cmd not in self.cmds:
                    continue
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
                self.r.ChangeDutyCycle(int(cos((params[0][0] * i + params[0][1] * period) * 2 * pi / period) * 50) + 50)
                self.g.ChangeDutyCycle(int(cos((params[1][0] * i + params[1][1] * period) * 2 * pi / period) * 50) + 50)
                self.b.ChangeDutyCycle(int(cos((params[2][0] * i + params[2][1] * period) * 2 * pi / period) * 50) + 50)
            i += 1

            sleep(0.1)

    def run(self):
        update_thread = Thread(target=self.update_leds)
        update_thread.start()
        self.read_commands()
        update_thread.join()


def main():
    file = None
    if len(sys.argv) > 1:
        file = open(sys.argv[1])
    notifier = Notifier(file)
    notifier.run()


if __name__ == '__main__':
    main()

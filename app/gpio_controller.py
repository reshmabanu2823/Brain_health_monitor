import platform
import sys

# ── Auto detect if running on Raspberry Pi or PC ──────────────────
def is_raspberry_pi():
    try:
        with open('/proc/cpuinfo', 'r') as f:
            return 'Raspberry Pi' in f.read()
    except:
        return False

IS_RPI = is_raspberry_pi()

# ── GPIO Setup (only on RPi) ──────────────────────────────────────
if IS_RPI:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GREEN_LED = 17
    RED_LED   = 27
    BUZZER    = 22
    GPIO.setup(GREEN_LED, GPIO.OUT)
    GPIO.setup(RED_LED,   GPIO.OUT)
    GPIO.setup(BUZZER,    GPIO.OUT)
    GPIO.output(GREEN_LED, GPIO.LOW)
    GPIO.output(RED_LED,   GPIO.LOW)
    GPIO.output(BUZZER,    GPIO.LOW)

import time

def alert_no_tumor():
    if IS_RPI:
        GPIO.output(GREEN_LED, GPIO.HIGH)
        GPIO.output(RED_LED,   GPIO.LOW)
        GPIO.output(BUZZER,    GPIO.HIGH)
        time.sleep(0.3)
        GPIO.output(BUZZER,    GPIO.LOW)
    else:
        print("[PC MODE] GREEN LED ON — No Tumor")

def alert_tumor_detected():
    if IS_RPI:
        GPIO.output(RED_LED,   GPIO.HIGH)
        GPIO.output(GREEN_LED, GPIO.LOW)
        for _ in range(3):
            GPIO.output(BUZZER, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(BUZZER, GPIO.LOW)
            time.sleep(0.15)
    else:
        print("[PC MODE] RED LED ON — Tumor Detected")

def reset_gpio():
    if IS_RPI:
        GPIO.output(GREEN_LED, GPIO.LOW)
        GPIO.output(RED_LED,   GPIO.LOW)
        GPIO.output(BUZZER,    GPIO.LOW)

def cleanup():
    if IS_RPI:
        GPIO.cleanup()

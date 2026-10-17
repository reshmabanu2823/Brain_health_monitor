# Maker UNO single-channel setup

This implementation targets the **user's Maker UNO**, not the R4 board currently listed on the [official Basic kit page](https://docs.upsidedownlabs.tech/kits/diy-neuroscience/basic/index.html). Confirm the board marking before upload. [Cytron's Maker UNO documentation](https://www.cytron.io/p-maker-uno-simplifying-arduino-for-education) describes its Arduino compatibility, CH340 USB interface and Micro USB connector. The [manufacturer starter manual](https://cdn.cytron.io/makeruno/Maker_UNO_Starter_Kit_Module.pdf) identifies ATmega328P and A0–A5. Do not use R4 ADC settings or firmware for this board.

## Wiring

Power off before wiring. Following the [BioAmp EXG Pill connection documentation](https://docs.upsidedownlabs.tech/hardware/bioamp/bioamp-exg-pill/index.html):

| BioAmp EXG Pill | Maker UNO |
|---|---|
| VCC | 5V |
| GND | GND |
| OUT | A0 |

Connect supplied electrode cable to amplifier's matching connector. Use vendor's EEG electrode-placement/skin-preparation guide for the actual band/accessory supplied. Differential inputs and reference electrode form **one channel**, not three. Never connect electrode leads directly to MCU pins. Confirm polarity; reversed power can damage amplifier.

Follow vendor acquisition precautions: laptop on battery, charger disconnected, away from mains-powered appliances. This kit is not established as medically isolated or clinical grade. First verify wiring and firmware without attaching electrodes to a person. No human acquisition test was performed here.

## Upload

1. Install Arduino IDE from official Arduino site.
2. Connect Maker UNO to laptop via data-capable USB cable. Install CH340 driver only if OS does not enumerate device.
3. Select **Arduino AVR Boards → Arduino Uno** for Maker UNO (ATmega328P). Select actual serial port.
4. Open `firmware/maker_uno_eeg/maker_uno_eeg.ino`. Default `SAMPLE_RATE=250`, `INPUT_PIN=A0`, `Serial.begin(115200)`.
5. Upload. This is custom **raw serial firmware**, not vendor Chords firmware; Chords binary stream is unsupported by this parser.
6. Without body electrodes attached, open Serial Monitor at **115200**. Header begins `#BHM,1,raw_adc_counts,10bit`. Subsequent rows are `sequence,micros,adc`, e.g. `0,4012,512` (format illustration, not measured hardware data).
7. Close Serial Monitor before backend connection.

No Arduino toolchain/physical board was available for target compilation/upload verification in this session. Upload errors must be checked on the actual board.

## Connect and verify

```bash
.venv/bin/python -m serial.tools.list_ports
.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Open `/eeg`, refresh ports, select **Maker UNO · USB serial**, choose listed port, connect. Wait at least six seconds. Check measured rate against configured rate, sample counters, malformed lines, discontinuities and quality reasons. ADC signal is 0–1023 counts, centered by circuit bias; it is **not microvolts**. Gain/reference/offset and bandwidth have not been calibrated. Clipping or a flat line can indicate bad wiring or saturation; a passing heuristic cannot prove signal is cortical EEG.

Start recording, stop, export CSV. Confirm `source=serial`, increasing device times and expected sample count/duration. USB receipt UTC and device-relative seconds are distinct columns. Disconnect USB: live analysis must clear, recording must become interrupted, bounded retries must be visible. Reconnect explicitly after retry limit; begin a new recording. This is the remaining physical validation checklist, not a claim that these tests have run.

## Timing and limitations

`micros()` stamps before `analogRead`; ADC conversion and loop/serial timing introduce error. Firmware skips missed deadlines and advances sequence; host detects gaps and rejects affected windows. Both uint32 sequence and micros rollover are handled. Device time cannot establish absolute UTC clock synchronization. Host measured rate is an estimate over retained consecutive samples; timing tolerance defaults to 2% rate error / 15% per-interval jitter.

Rate can be changed at compile time from 100–250 Hz; set matching `BHM_EEG_SAMPLE_RATE` and a notch strictly below Nyquist. At 100 Hz disable 50 Hz notch (`BHM_EEG_NOTCH_HZ=off`). Baud rate stays 115200. Rates above 250 Hz are refused because worst-case ASCII frames can exceed serial throughput. Fractional periods are rounded down in firmware, so requested rate need not equal achieved rate. Default 250 Hz has an exact 4000 µs target period.

Raw 10-bit converter resolution, supply/reference noise, analog bandwidth and USB-coupled noise constrain recordings. No added ADC, channel, isolation board or sensor is assumed. No calibrated amplitude/contact impedance or clinical acquisition claim is made.

## Troubleshooting

- Port absent: inspect cable, permissions and CH340 enumeration; unplug/replug and compare port list.
- Permission denied on Linux: use distribution's normal serial-device permissions/group policy, then sign in again; do not run whole application as root.
- Port busy: stop Serial Monitor, Chords or other process using it.
- Repeated malformed lines: verify uploaded BHM sketch and 115200 baud, not binary Chords firmware.
- Repeated discontinuities/wrong rate: inspect USB traffic/firmware load and match host rate; do not hide gaps with interpolation.
- No analysis: need complete window plus guards, finite samples, nonflat/unclipped signal and acceptable timing.

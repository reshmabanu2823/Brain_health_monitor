# EEG hardware acceptance

**Physical integration is unverified. No board was attached during development.** Parser/service/API tests are software tests, not hardware validation.

## Target wiring and firmware

Arduino UNO R4 Minima + BioAmp EXG Pill + electrodes, one selected analog input. Follow manufacturer wiring, electrode, power and human-subject safety instructions; verify reference and ground arrangement with the hardware supplier.

Official [Chords UNO-R4 firmware](https://github.com/upsidedownlabs/Chords-Arduino-Firmware/blob/main/UNO-R4/UNO-R4.ino) defaults to six-channel 500 Hz, 230400 baud and 14-bit ADC resolution. A 250 Hz build requires explicitly changing the firmware sampling constant and flashing that build. CORTIA does not flash firmware. Select the actual rate in acquisition settings; raw rate is retained without downsampling.

Protocol as inspected 2026-11-01:

```
C7 7C [counter] [A0 high low] ... [A5 high low] 01
```

Exactly 16 bytes per frame; unsigned big-endian channel values 0–16383. Counter wraps modulo 256. CORTIA validates all six decoded channel values but records only the selected channel. Command handshake sends `WHORU\n`, expects `UNO-R4`, then sends `START\n`. Disconnect sends `STOP\n` when possible.

Close Arduino Serial Monitor and Chords-Web before connecting. One application must own serial port. On Linux, inspect the device’s group and permissions; configure appropriate serial-device access according to your distribution. CORTIA never changes system groups or permissions automatically.

## Required physical checks

- [ ] Record exact board, firmware version/hash, BioAmp configuration, analog channel, reference and electrode montage.
- [ ] Verify serial handshake and stable live values without attaching a person initially, following hardware supplier guidance.
- [ ] Verify 500 Hz default or deliberately flashed 250 Hz firmware. Capture wall-clock duration and sample count over multiple minutes.
- [ ] Confirm ADC voltage range/gain and actual analog bandwidth before calibrating to physical amplitude units. Until then, use ADC counts only.
- [ ] Inspect raw waveform, reference placement, contact quality and motion/blink contamination; verify quality flags against observed events.
- [ ] Disconnect cable during recording. Confirm live-unavailable state, interrupted session and retained raw data.
- [ ] Reconnect quickly and verify new stream appears immediately; old points must clear.
- [ ] Test other-user attempts: cannot start, stop, or see owner’s stream. Sign back into owner account to release an owned connection if needed.
- [ ] Check missing/corrupted packets, throughput mismatch and stalled source behavior. No filled-in EEG should appear.
- [ ] Confirm long recordings remain stable and storage growth is acceptable; inspect raw and processed results against independent tools.

Thresholds are provisional. Physical testing may require firmware/protocol adjustments; document them and update decoder/config versions before accepting new data. Never reinterpret a failed hardware test as completed integration.

# Hardware Bring-Up Checklist: Maker UNO + BioAmp EXG Pill

This checklist provides step-by-step instructions for bringing up the single-channel EEG pipeline using the **Maker UNO** (ATmega328P + CH340) and **Upside Down Labs BioAmp EXG Pill**.

---

## 1. Safety & Wiring

> [!CAUTION]
> Always power off the board before wiring. Run your computer on **battery power only** (unplug the laptop charger) to eliminate mains grounding hazard and avoid 50/60 Hz power-line interference.

| BioAmp EXG Pill Pin | Maker UNO Pin | Description |
|---|---|---|
| **VCC** | **5V** | 5V Power Supply |
| **GND** | **GND** | Ground Reference |
| **OUT** | **A0** | Analog Output (0–1023 counts) |

- Connect the BioAmp electrode cable to the 3-pin connector on the BioAmp EXG Pill.
- Electrodes (Single-Channel Differential):
  - **IN+**: Active site (e.g., Fp1 or forehead)
  - **IN-**: Reference site (e.g., behind ear / mastoid or Fp2)
  - **REF**: Ground site (e.g., earlobe or bony landmark)
- Ensure clean skin contact (alcohol wipe + conductive gel or hydrogel electrodes).

---

## 2. Flashing the Firmware

1. Install the Arduino IDE and CH340 driver (if not already installed).
2. Connect Maker UNO to your computer using a data-capable USB cable.
3. Open `firmware/maker_uno_eeg/maker_uno_eeg.ino`.
4. In Arduino IDE:
   - **Tools → Board → Arduino AVR Boards → Arduino Uno**
   - **Tools → Port →** Select your board's serial port (e.g., `COM3` on Windows, `/dev/ttyUSB0` on Linux)
5. Click **Upload**.
6. *(Optional)* Quick check in Arduino Serial Monitor at **115200 baud**:
   - Header should read: `#BHM,1,raw_adc_counts,10bit`
   - Streaming lines: `<sequence>,<micros>,<adc_counts>`
7. **IMPORTANT**: **Close the Arduino Serial Monitor** before starting the server. If the Serial Monitor is open, the serial port will be locked and busy.

---

## 3. Environment Configuration & Starting Server

Optional settings in `.env` (defaults shown):
```bash
BHM_EEG_SAMPLE_RATE=250
BHM_EEG_WINDOW_SECONDS=4
BHM_EEG_GUARD_SECONDS=1
BHM_EEG_LOW_HZ=1
BHM_EEG_HIGH_HZ=40
BHM_EEG_NOTCH_HZ=50
BHM_EEG_DB=logs/eeg.db
```

Start the application server:
```powershell
# Windows (PowerShell)
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```
```bash
# Linux / macOS
.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

---

## 4. Connecting and Verifying in the UI

1. Open `http://127.0.0.1:8000/eeg` in your web browser.
2. Under **Device Source**, select **Maker UNO · USB serial**.
3. Select your serial port from the dropdown (e.g. `COM3` or `/dev/ttyUSB0`).
4. Click **Connect**.
5. **Wait at least 6 seconds**:
   - The filtering pipeline requires 6 seconds of contiguous data (4-second analysis window + 2×1-second filter guards = 1500 samples at 250 Hz) before the first PSD analysis appears.
6. Verify the **Measured Sample Rate**:
   - Must stabilize around **250 Hz** (within ±2% tolerance: 245 Hz – 255 Hz).
   - Check status shows `Checks passed` and zero discontinuities.

---

## 5. Physiological Sanity Checks

| Test | Action | Expected Signal Response |
|---|---|---|
| **Blink Artifact** | Blink eyes firmly 2–3 times | Large, sharp, prominent bipolar deflection spikes (>100–300 ADC counts). |
| **Jaw Clench** | Clench jaw tightly for 1 second | Dense, high-amplitude, high-frequency electromyographic (EMG) burst. |
| **Eyes-Closed Alpha** | Relax comfortably and close eyes for 10–20 seconds | Noticeable increase in Alpha band relative power (8–13 Hz) compared to eyes-open. |

---

## 6. Troubleshooting

| Issue | Probable Cause | Corrective Action |
|---|---|---|
| **Port absent from list** | Missing CH340 driver or charge-only USB cable | Install CH340 driver. Verify cable supports data transfer. Check Windows Device Manager (`devmgmt.msc`) under Ports (COM & LPT). |
| **Port busy (Access Denied)** | Arduino IDE Serial Monitor, Cura, PuTTY, or another app has opened the port | Close Arduino IDE Serial Monitor or any other terminal software using the port, then click Connect again. |
| **Permission Denied (Linux)** | User account not in serial group | Run `sudo usermod -a -G dialout $USER` (or `uucp` on Arch), then log out and log back in. |
| **Flatline (constant value or 0 counts)** | Loose OUT wire, disconnected electrode, or power failure | Check 5V, GND, and A0 jumper connections. Ensure electrode lead is securely clicked into the BioAmp EXG Pill. |
| **Severe 50 Hz / 60 Hz hum** | Laptop running on AC mains or proximity to mains wiring | Disconnect laptop AC charger and run on battery. Move away from high-power appliances. Verify `BHM_EEG_NOTCH_HZ=50` (or `60` in 60 Hz regions). |
| **Sample Rate Mismatch / Jitter Error** | Firmware `SAMPLE_RATE` does not match `BHM_EEG_SAMPLE_RATE`, or baud rate is wrong | Verify baud rate is 115200 in both firmware and server. Confirm firmware was compiled with `SAMPLE_RATE 250UL`. |
| **Device unplugged during recording** | Cable disconnected or loose connector | Backend marks recording `interrupted`, clears buffers, and enters bounded reconnect attempts. Plug back in, verify connected state, and start a fresh recording. |

---

## 7. Verification Status

- **Software & Protocol**: Tested and verified end-to-end via automated unit tests and simulated API flows.
- **Physical Hardware**: Flashing, skin preparation, and electrode impedances must be verified by the operator with the physical device connected.

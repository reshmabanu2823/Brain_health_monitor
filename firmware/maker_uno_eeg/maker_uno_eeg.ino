// BHM raw serial v1. Maker UNO / ATmega328P, one BioAmp EXG Pill.
// VCC->5V, GND->GND, OUT->A0. Do not swap supply polarity.
// Raw ADC counts only. This sketch is NOT Chords firmware.
// SAMPLE_RATE must match BHM_EEG_SAMPLE_RATE on the host.
#ifndef SAMPLE_RATE
#define SAMPLE_RATE 250UL
#endif
#if SAMPLE_RATE < 100 || SAMPLE_RATE > 250
#error "Supported sample rate: 100 to 250 Hz"
#endif
const uint8_t INPUT_PIN = A0;
const uint32_t PERIOD_US = 1000000UL / SAMPLE_RATE;
uint32_t nextSample;
uint32_t sequence = 0;

void setup() {
  Serial.begin(115200);
  analogReference(DEFAULT); // Maker UNO: 10-bit ADC; supply-derived reference.
  Serial.println(F("#BHM,1,raw_adc_counts,10bit"));
  nextSample = micros() + PERIOD_US;
}

void loop() {
  uint32_t now = micros();
  if ((int32_t)(now - nextSample) < 0) return;
  // Skip missed deadlines rather than sending fake catch-up samples.
  uint32_t missed = (now - nextSample) / PERIOD_US;
  sequence += missed;
  nextSample += (missed + 1) * PERIOD_US;
  uint32_t sampledAt = micros();
  uint16_t value = analogRead(INPUT_PIN);
  Serial.print(sequence++);
  Serial.print(',');
  Serial.print(sampledAt);
  Serial.print(',');
  Serial.println(value);
}

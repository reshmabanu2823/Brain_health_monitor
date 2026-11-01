import { FlaskConical, ArrowRight } from "lucide-react";
import { colors } from "../charts";
import { Card, Note } from "../ui";

export function Methods() {
  return (
    <>
      <div className="insight-banner">
        <FlaskConical size={26} />
        <div>
          <h2>Every result should be explainable.</h2>
          <p>
            Signal measurements, derived indicators, predictions, and
            explanations have different limits. CORTIA keeps those limits
            visible.
          </p>
        </div>
      </div>
      <div className="two-column">
        <Card
          title="Processing pipeline"
          subtitle="cortia-eeg-1 · one-channel acquisition"
        >
          <ol className="pipeline-list">
            {[
              "Receive and validate hardware samples",
              "Check counters, missing samples, and ADC range",
              "Screen raw flatline, clipping, and abrupt steps",
              "Segment into eight-second windows",
              "Apply 0.5–29.5 Hz fourth-order bandpass",
              "Compute Welch PSD and Hann-windowed FFT",
              "Integrate band power and calculate ratios",
              "Compare matched session means with baseline",
            ].map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
        </Card>
        <Card title="What quality checks mean">
          <p className="padded-text muted">
            A usable window passes configured heuristics: standard deviation
            ≥0.5 ADC counts, no excessive repeated samples, ≤1% rail clipping,
            no large abrupt steps, and no detected discontinuities.
          </p>
          <Note>
            Thresholds are engineering choices, not validated clinical criteria.
            Eye, muscle, and movement artifacts can remain. CORTIA excludes
            flagged windows; it does not claim to reconstruct clean brain
            activity.
          </Note>
          <p className="padded-text muted">
            50/60 Hz lies outside the retained passband. Bandpass attenuation
            applies; no additional notch is claimed. Hardware filtering and ADC
            scaling must be verified for your setup.
          </p>
        </Card>
      </div>
      <Card
        title="Metric reference"
        subtitle="Calculations are signal descriptors. Interpretation requires recording context."
      >
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Measurement</th>
                <th>Formula</th>
                <th>Meaning & limitations</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Band power</td>
                <td>
                  <code>Pᵦ = ∫ PSD(f) df</code>
                </td>
                <td>
                  Integrated spectral energy. ADC² without gain calibration; not
                  absolute brain voltage.
                </td>
              </tr>
              <tr>
                <td>Relative power</td>
                <td>
                  <code>Rᵦ = Pᵦ / Σ Pᵦ</code>
                </td>
                <td>
                  Share of 0.5–29.5 Hz power. Other bands changing also changes
                  this share.
                </td>
              </tr>
              <tr>
                <td>Alpha / Theta</td>
                <td>
                  <code>Pα / Pθ</code>
                </td>
                <td>
                  Exploratory spectral balance. No direct measure of
                  intelligence or relaxation.
                </td>
              </tr>
              <tr>
                <td>Theta / Beta</td>
                <td>
                  <code>Pθ / Pβ</code>
                </td>
                <td>
                  Exploratory. No standalone attention, ADHD, or psychiatric
                  diagnosis.
                </td>
              </tr>
              <tr>
                <td>Beta / Alpha</td>
                <td>
                  <code>Pβ / Pα</code>
                </td>
                <td>
                  Exploratory balance; sensitive to muscle activity. Not anxiety
                  or stress measurement.
                </td>
              </tr>
              <tr>
                <td>Baseline z-score</td>
                <td>
                  <code>z = (x − μ) / s</code>
                </td>
                <td>
                  Matched-session deviation. Undefined for near-zero SD. |z| ≥3
                  flags exploratory change, not clinical significance.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
      <div className="two-column">
        <Card title="Frequency boundaries">
          <div className="scope-list">
            {[
              ["Delta", "0.5–4 Hz"],
              ["Theta", "4–8 Hz"],
              ["Alpha", "8–13 Hz"],
              ["Beta", "13–29.5 Hz"],
              ["Gamma", "Unavailable"],
            ].map(([band, range]) => (
              <div key={band}>
                <span style={{ color: colors[band.toLowerCase()] || "#999" }}>
                  ●
                </span>
                <strong>{band}</strong>
                <span className="push-right">{range}</span>
              </div>
            ))}
          </div>
          <Note>
            Band edges use interpolated PSD integration without overlapping
            intervals. Filtering attenuates frequencies near cutoff boundaries.
          </Note>
        </Card>
        <Card title="Privacy & operational limits">
          <div className="padded-text muted">
            <p>
              Accounts use Argon2 password hashing and expiring HttpOnly
              sessions. Data access stays scoped to its owner.
            </p>
            <p>
              Raw signals and decoded images stay on this computer. Use
              operating-system disk encryption to protect stored files.
            </p>
            <p>
              Run one backend worker. Hardware integration needs physical
              testing. Neither EEG interpretation nor MRI classification is
              clinically validated here.
            </p>
          </div>
          <a
            className="text-button"
            href="/docs"
            target="_blank"
            rel="noreferrer"
          >
            Explore API documentation <ArrowRight size={14} />
          </a>
        </Card>
      </div>
    </>
  );
}

"""Accelerated test-only packets and storage checks. NEVER physical EEG validation."""
import argparse
import csv
import json
import math
import resource
import struct
import tempfile
import time
from pathlib import Path

from cortia.config import Settings
from cortia.db import setup
from cortia.eeg.acquisition import Acquisition
from cortia.eeg.protocol import ChordsParser
from cortia.models import Recording, Segment, User


def soak(rate, minutes):
    seconds = minutes*60
    expected_samples = rate*seconds
    expected_windows = seconds//8
    waveform = [round(8192+100*math.sin(2*math.pi*10*index/rate)) for index in range(rate)]
    packet = struct.Struct('>2sB6HB')
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='cortia-test-soak-') as temporary:
        root = Path(temporary)
        engine, factory = setup(Settings(data_dir=root, testing=True))
        manager = Acquisition(factory, root)
        try:
            with factory() as db:
                user = User(username='soak-fixture-only', password_hash='fixture-only')
                db.add(user); db.commit(); owner = user.id
            manager.owner, manager.state = owner, 'streaming'
            manager.config = dict(sampling_hz=rate,channel=0,bandwidth=[.5,29.5],units='ADC_count',pipeline='cortia-eeg-1')
            manager.last_sample_at = time.monotonic()
            sid = manager.start_recording(owner,dict(eyes='closed',task='test fixture',montage='test fixture'))['id']
            parser = ChordsParser(0)
            for second in range(seconds):
                payload = b''.join(packet.pack(b'\xc7\x7c',(second*rate+index)%256,*([value]*6),1)
                                   for index,value in enumerate(waveform))
                # Exercise real byte decoding, acquisition, filtering, database and CSV writes.
                manager.accept(parser.feed(payload))
                assert len(manager.samples) <= 2500
                if (second+1)%600 == 0:
                    print(f'{rate} Hz: {second+1}/{seconds} fixture seconds',flush=True)
            manager.stop_recording(owner)
            assert parser.corrupted == 0 and parser.duplicates == 0
            with factory() as db:
                record = db.get(Recording,sid)
                assert record.sample_count == expected_samples
                assert record.missing_samples == record.invalid_windows == 0
                assert record.valid_windows == expected_windows
                assert record.state == 'completed'
                assert record.features['relative_alpha'] > .9
                segments = db.query(Segment).filter_by(session_id=sid).order_by(Segment.start_index).all()
                assert len(segments) == expected_windows
                for index,segment in enumerate(segments):
                    assert segment.start_index == index*rate*8
                    assert segment.end_index == (index+1)*rate*8
                    assert segment.result['quality']['usable']
                raw_path = root/record.raw_path
                raw_bytes = raw_path.stat().st_size
            rows = 0
            with raw_path.open() as file:
                for index,row in enumerate(csv.DictReader(file)):
                    assert int(row['sample_index']) == index
                    assert int(row['device_counter']) == index%256
                    assert abs(float(row['device_time_seconds'])-(index+1)/rate) < 1e-9
                    assert int(row['adc_count']) == waveform[index%rate]
                    assert int(row['missing_before']) == int(row['discontinuity']) == 0
                    rows += 1
            assert rows == expected_samples
            db_bytes = sum(p.stat().st_size for p in root.glob('cortia.db*'))
            elapsed = time.perf_counter()-started
            return dict(sampling_hz=rate,fixture_minutes=minutes,sample_count=rows,valid_windows=expected_windows,
                        raw_bytes=raw_bytes,database_bytes_including_wal=db_bytes,
                        elapsed_seconds=elapsed,samples_per_wall_second=rows/elapsed,
                        peak_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        all_integrity_checks_pass=True)
        finally:
            manager.disconnect()
            engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minutes',type=int,default=60)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.minutes < 1:
        raise ValueError('Positive fixture duration required')
    if args.output.exists():
        raise FileExistsError('Choose a new report path')
    report = dict(kind='accelerated_test_fixture_soak',physical_hardware_test=False,
                  limitation='Generated packets exist only in temporary test directories; not real EEG, real-time serial throughput, or physical signal validation.',
                  results=[soak(rate,args.minutes) for rate in (250,500)])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as file:
        json.dump(report,file,indent=2,allow_nan=False);file.write('\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()

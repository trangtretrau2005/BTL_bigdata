"""Download a pinned Vietnamese Piper voice and retain provenance and attribution."""
import hashlib
import json
from pathlib import Path
import requests

REVISION = '3d796cc2f2c884b3517c527507e084f7bb245aea'
REPO = 'https://huggingface.co/rhasspy/piper-voices'
VOICE_DIR = 'vi/vi_VN/vais1000/medium'
MODEL = 'vi_VN-vais1000-medium.onnx'


def setup(destination: Path = Path('data/models/piper')):
    destination.mkdir(parents=True, exist_ok=True)
    response = requests.get(f'https://huggingface.co/api/models/rhasspy/piper-voices/tree/{REVISION}/{VOICE_DIR}', timeout=20)
    response.raise_for_status()
    expected = {Path(item['path']).name: item for item in response.json()}
    records = []
    for name in [MODEL, MODEL + '.json', 'MODEL_CARD']:
        target = destination / name
        metadata = expected[name]
        digest = metadata.get('lfs', {}).get('oid')
        valid = target.exists() and target.stat().st_size == metadata['size']
        if valid and digest:
            valid = hashlib.sha256(target.read_bytes()).hexdigest() == digest
        url = f'{REPO}/resolve/{REVISION}/{VOICE_DIR}/{name}'
        if not valid:
            temporary = target.with_suffix(target.suffix + '.download')
            with requests.get(url, stream=True, timeout=(10, 60)) as download:
                download.raise_for_status()
                with temporary.open('wb') as stream:
                    for block in download.iter_content(1024 * 1024):
                        stream.write(block)
            if temporary.stat().st_size != metadata['size']:
                raise ValueError(f'Incomplete voice download: {name}')
            if digest and hashlib.sha256(temporary.read_bytes()).hexdigest() != digest:
                raise ValueError(f'Voice checksum mismatch: {name}')
            temporary.replace(target)
        records.append({'file': name, 'source': url, 'size': target.stat().st_size,
                        'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        print(f'Ready: {name}', flush=True)
    (destination / 'provenance.json').write_text(json.dumps({'revision': REVISION, 'files': records}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    setup()

"""Opt-in demo collector: read Docker stdout and atomically replace a bounded snapshot."""
import argparse
import json
import subprocess
from pathlib import Path
from call_logs import MAX_CALLS, parse_logs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', default='accessibility-dataspace-connector-1')
    args = parser.parse_args()
    directory = Path(__file__).parent / '.logs'
    directory.mkdir(mode=0o755, exist_ok=True)
    target = directory / 'calls.jsonl'
    temporary = directory / 'calls.tmp'
    calls = []
    target.write_text('')
    # No Docker socket or daemon permissions are given to the web container.
    process = subprocess.Popen(['docker', 'logs', '--follow', '--tail', '1000', args.container],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print('Collecting connector calls into viewer/.logs/calls.jsonl. Stop with Ctrl+C.', flush=True)
    try:
        for line in process.stdout:
            parsed = parse_logs(line)['calls']
            if not parsed:
                continue
            calls = (calls + parsed)[-MAX_CALLS:]
            temporary.write_text('\n'.join(json.dumps(call, ensure_ascii=False) for call in calls))
            temporary.replace(target)
        if process.wait():
            raise SystemExit('Docker log collection failed. Check the container name and Docker access.')
    except KeyboardInterrupt:
        pass
    finally:
        process.terminate()
        process.wait()


if __name__ == '__main__':
    main()

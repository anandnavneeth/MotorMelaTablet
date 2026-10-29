"""Owned, unattended game processes; no hardware force/input commands.
Run with --model Supra, Heat, or Favourite. Stops only the process it creates.
"""
import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ENGINE = Path('H:/EpicGames/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe')


def call(data):
    request = urllib.request.Request('http://127.0.0.1:18741/tuning', json.dumps(data).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def run(model):
    project = PROJECT if model != 'Favourite' else Path('F:/Work/NoHesiArcade/HeatVersions/Heat-Favourite-FFB-2026-10-29/NoHesiArcade')
    out = PROJECT / 'Saved/SetupValidation/Tablet'
    out.mkdir(parents=True, exist_ok=True)
    route = '/Game/Maps/L_HighwayLab' if model == 'Supra' else '/Game/HeatLab/Maps/L_HeatHighway?HeatBaseline=0'
    env = os.environ.copy()
    env['UE_SKIP_UBT_SDK_SETUP'] = '1'
    # Refuse to touch an existing server. The caller also checks running Unreal processes.
    try:
        call({'action': 'state'})
    except (OSError, urllib.error.URLError):
        pass
    else:
        raise RuntimeError('A tuning game is already running; close it first.')
    process = subprocess.Popen([str(ENGINE), str(project / 'NoHesiArcade.uproject'), route, '-game', '-NoMainMenu', '-TabletTuning',
        '-nullrhi', '-nosound', '-unattended', '-DisablePython', '-NoLiveCoding', f'-abslog={out / (model + "-Runtime.log")}'],
        cwd=project, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    files = []
    checks = []
    def check(name, ok):
        checks.append({'name': name, 'passed': bool(ok)})
        if not ok:
            raise AssertionError(name)
    try:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                state = call({'action': 'catalog'})
                if state.get('ok'):
                    break
            except (OSError, urllib.error.URLError):
                pass
            if process.poll() is not None:
                raise RuntimeError(f'Game exited: {process.returncode}')
            time.sleep(.5)
        else:
            raise RuntimeError('Tuning endpoint did not start')
        (out / (model + '-Catalog.json')).write_text(json.dumps(state, indent=2), encoding='utf-8')
        check('Comprehensive catalog', len(state['parameters']) > 300)
        check('Baseline values inside declared bounds', all(p['min'] <= p['default'] <= p['max'] for p in state['parameters']))
        baseline = state['values'].copy()
        time.sleep(2)  # Let the newly spawned chassis settle before stopped-only checks.
        state = call({'action': 'state'})
        key = 'brakeTorque' if model == 'Supra' else 'Drag'
        def request(action, **extra):
            nonlocal state
            data = dict(action=action, session=state['session'], revision=state['revision'], **extra)
            result = call(data)
            if not result.get('ok'):
                print(json.dumps({'action': action, 'error': result.get('error'), 'speed': state.get('speed')}), flush=True)
            if result.get('ok'):
                state = result
            return result, data
        changed = baseline[key] * .97
        r, stale = request('apply', values={key: changed})
        check('Live value acknowledged by runtime owner', r['ok'] and abs(state['values'][key] - changed) < 1e-5 * max(1, abs(changed)))
        check('Stale replay rejected', not call(stale)['ok'])
        r, _ = request('apply', values={key: baseline[key], 'unknown.parameter': 1})
        check('Invalid transaction rejected', not r['ok'])
        observed = call({'action': 'state'})
        check('No partial application', observed['values'][key] == state['values'][key])
        r, _ = request('undo')
        check('Undo restores baseline', r['ok'] and state['values'][key] == baseline[key])
        mass = 'body.0.mass' if model == 'Supra' else 'MassKg'
        r, _ = request('apply', values={mass: baseline[mass] * 1.01})
        check('Structural edits require explicit stopped permission', not r['ok'])
        # Wait for suspension settle, then exercise the actual geometry/mass commit.
        for _ in range(40):
            state = call({'action': 'state'})
            if state['speed'] < .5:
                break
            time.sleep(.1)
        r, _ = request('apply', values={mass: baseline[mass] * 1.01}, allowStopped=True)
        check('Stopped mass update succeeds', r['ok'])
        time.sleep(.7)
        r, _ = request('undo', allowStopped=True)
        check('Stopped mass undo succeeds', r['ok'] and state['values'][mass] == baseline[mass])
        r, _ = request('save', name='AUTOMATION temporary round-trip')
        check('Preset save', r['ok'])
        preset = [p for p in r['presets'] if p['name'] == 'AUTOMATION temporary round-trip'][-1]
        files.append(project / 'Saved/Config/TabletTunes' / (preset['id'] + '.json'))
        request('apply', values={key: changed})
        r, _ = request('load', id=preset['id'])
        check('Preset loads exact compatible settings', r['ok'] and state['values'] == baseline)
        r, _ = request('defaults', allowStopped=True)
        check('Full baseline restore', r['ok'] and state['values'] == baseline)
        elapsed = []
        for _ in range(20):
            start = time.perf_counter()
            r = call({'action': 'state'})
            elapsed.append((time.perf_counter() - start) * 1000)
        check('Runtime remains healthy after edits', r['ok'])
        report = {'model': model, 'parameters': len(state.get('parameters', baseline)), 'checks': checks,
                  'requestMsMean': sum(elapsed) / len(elapsed), 'requestMsMax': max(elapsed), 'hardwareForcesTested': False}
        (out / (model + '-RuntimeResult.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report), flush=True)
    finally:
        # This unattended, unsaved process was created exclusively by this fixture.
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        for file in files:
            file.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['Supra', 'Heat', 'Favourite'], required=True)
    run(parser.parse_args().model)

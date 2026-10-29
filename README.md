# MotorMela Tablet

Portrait Android passenger tuning console for MotorMela / NoHesiArcade.
A passenger can adjust the running car while the driver concentrates on driving.

## Included

- Android WebView kiosk shell, locked to portrait, with USB/private-network connection.
- Responsive tuning UI: category tabs, search, sliders, numeric values, telemetry,
  Undo, session baseline, named presets and live/stopped-only labels.
- Dependency-free Python bridge with pairing and same-origin checks.
- Android build/install script, bridge tests and game integration helpers.

The Unreal game, simulation adapters, car definitions, purchased assets and saved
user tunes remain in Perforce. This repository cannot run a vehicle simulation
by itself. It requires the game's opt-in `-TabletTuning` endpoint on localhost
port 18741. The current compatible catalogs expose Supra Reference (535 controls),
Heat Skyline (411) and Heat Saved Favourite (361).

This is a portrait companion app, not Android device-owner lockdown. It does not
prevent leaving the app or changing Android settings.

## Connect to the game

1. In the Perforce project launcher, refresh the library and select **Tablet Lab**
   for the desired model. This starts the game endpoint and PC bridge.
2. Connect an authorized Android device by USB. The project launcher automatically
   forwards port 18740 and pairs the installed app when exactly one device is connected.
3. Use `http://127.0.0.1:18740` in the tablet app. Keep the PC bridge running.

To run this checkout's bridge manually (use only one bridge at a time):

```powershell
python Tablet/bridge.py --state Saved/Tablet/connection.json
adb reverse tcp:18740 tcp:18740
```

Use the local pairing code printed by the bridge in the app. For a private LAN,
start the bridge with `--lan` and enter the PC's private IP instead. USB is tested;
physical Wi-Fi operation is not yet verified. Do not expose these ports publicly.
The game endpoint is local-only; the bridge is the paired tablet-facing service.

## Build Android on Windows

Requires PowerShell, JDK 21, Android API 35, Android Build Tools 35.0.0 and platform
tools. No Gradle or third-party app libraries are required. The portable tools
folder expected by the build script contains:

```text
<tools>/
  jdk-21.../bin/
  android-15/          # actual Build Tools 35.0.0 binaries; retained local folder name
  android-35/android.jar
  platform-tools/adb.exe
```

```powershell
./Tablet/build_android.ps1 -Tools 'D:/AndroidTools'
# With exactly one USB-debugging-authorized device:
./Tablet/build_android.ps1 -Tools 'D:/AndroidTools' -Install
```

Output: `Binaries/Tablet/HandlingLab.apk`. The development signing key is created
locally under `Saved/Tablet/` and must remain private. Retain that key to update
an existing installation; a different key cannot replace it without uninstalling.
The APK loads its interface from the PC bridge; it is not an offline application.

`Tablet/start_lab.ps1` and `Tablet/verify_runtime.py` are integration helpers from
the Perforce project. They expect to live inside that Unreal project and retain
its H:/F: paths. Run them there; do not expect them to launch the game from this
standalone checkout. The Android build and Python bridge work from this checkout.

## Tuning behavior

Controls marked **LIVE** apply through the vehicle owner's existing physics
handoff. Chassis, geometry and other structural changes require the stopped-only
checkbox and speed below 0.5 km/h. Invalid/stale requests are rejected; disconnected
changes are not automatically replayed. Presets are stored on the game PC, retain
model/schema compatibility information, and never overwrite original car data.
Changing the simulation contract requires an explicit preset migration.

Hardware force-feedback activation remains with the driver. The tablet does not
calibrate or force-center the wheel. Camera presentation controls remain in the
game's H menu; this app exposes implemented vehicle tuning coefficients, not all
engine constants or transient physics state.

## Checks

```powershell
python -m unittest discover -s Tablet -p test_bridge.py
node --check Tablet/web/app.js
```

Validated on Lenovo TB373FU, Android 16, 1840 x 2944 portrait. The 10 bridge tests
pass. A real tablet input changed Supra steering ratio from 17 to 18; tablet Undo
restored 17. The three game adapters passed 14 runtime checks each in the Perforce
project, separately from physical driving/force-feedback acceptance.

## Source ownership

The initial import matches the Perforce project's `Tablet/` source byte for byte.
Unreal remains a Perforce-only project; this is a separate Git checkout. Future
kiosk edits must be deliberately synchronized with the project's `Tablet/` folder
and tested before deployment. No automatic two-way synchronization is configured.
No game assets, SDKs, APKs, local credentials or signing keys are included.

# Advances Fullscreen Tank Picker (WoT EU 2.4.0.2)

Replaces the small Flash tank popover in the Advances (stronghold) battle room with the
WoT 2.0 full-screen vehicle picker (`gui.impl.lobby.select_vehicle`), limited to the tanks
allowed for the slot (tier range, in garage). Commander multi-select keeps the old popover.

Build: `python3 build.py` (needs `python2.7`), install: copy `dist/*.wotmod` to `<game>/mods/<version>/`.
Log lines: `ADVANCES_PICKER` in `<game>/python.log`.

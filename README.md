# Better Stronghold and Advanced Picker (WoT EU 2.4.1)

Replaces the small Flash tank popover in the Advances (stronghold) battle room with the
WoT 2.0 full-screen vehicle picker (`gui.impl.lobby.select_vehicle`), limited to the tanks
allowed for the slot (tier range, in garage). Commander multi-select keeps the old popover.

Build: `python3 build.py` (needs `python2.7`), install: copy `dist/*.wotmod` to `<game>/mods/<version>/`.
Log lines: `ADVANCES_PICKER` in `<game>/python.log`.

## Dev mode (no game restart)
Create `<game>/mods/configs/advances_picker/dev.json`:

    {"src": "X:/Projekte/wot-advances-picker/src"}

(`X:` is the Proton prefix drive for your home folder.) Then `advances_picker/impl.py`, `app.js` and
`style.css` are read from `src/` every time the picker opens. In the picker, **F5** reopens it with
the current code; in the garage, **Ctrl+Shift+P** opens it (tier X, nothing frozen). Changes to the
loader (`gui/mods/mod_advances_picker.py`), `boot.js`, `index.html` or the gen_resources layout still need
a build + restart. Delete `dev.json` to switch back to the packaged code.

# -*- coding: utf-8 -*-
# Advances full-screen tank picker: loader.
# Replaces the small Flash tank popover in the Advances battle room with the picker
# from advances_picker.impl. Multi-select (commander slot settings) keeps the old popover.
#
# Dev mode: create <game>/mods/configs/advances_picker/dev.json with
#   {"src": "X:/Projekte/wot-advances-picker/src"}
# Then impl.py, app.js and style.css are read fresh from that folder every time the picker
# opens (F5 inside the picker reopens it), and Ctrl+Shift+P opens it in the garage.
import json
import logging
import os
import types

import BigWorld
import Keys
from gui import InputHandler
from gui.Scaleform.daapi.view.lobby.fortifications.fort_vehicle_select_popover import FortVehicleSelectPopover

_logger = logging.getLogger('ADVANCES_PICKER')
_logger.setLevel(logging.INFO)
_DEV_FILE = os.path.join('mods', 'configs', 'advances_picker', 'dev.json')
_IMPL_PATH = 'res/scripts/client/advances_picker/impl.py'
# Python 2 sets a module's globals to None when the module object dies, so every dev-loaded
# impl is kept alive here (open views and callbacks still use its functions).
_devModules = []


def _devConfig():
    try:
        if os.path.isfile(_DEV_FILE):
            with open(_DEV_FILE, 'r') as f:
                config = json.load(f)
            if isinstance(config, dict) and config.get('src'):
                return config
    except Exception:
        _logger.exception('dev: reading %s failed', _DEV_FILE)
    return None


def _impl():
    config = _devConfig()
    if config is not None:
        path = os.path.join(config['src'], _IMPL_PATH)
        try:
            with open(path, 'rb') as f:
                source = f.read()
            module = types.ModuleType('advances_picker_dev_impl')
            module.__file__ = path
            exec compile(source, path, 'exec') in module.__dict__
            module.DEV = {'src': config['src'], 'reopen': _reopen}
            _devModules.append(module)
            _logger.info('dev: loaded impl from %s', path)
            return module
        except Exception:
            _logger.exception('dev: loading %s failed, using packaged impl', path)
    from advances_picker import impl
    return impl


def _reopen(levelsRange, frozen, currentCD):
    try:
        _impl().openPicker(levelsRange, frozen, currentCD)
    except Exception:
        _logger.exception('dev: reopening picker failed')


_origPopulate = FortVehicleSelectPopover._populate


def _populate(self):
    _origPopulate(self)
    if self._isMultiSelect:
        return
    try:
        _impl().openFromPopover(self)
    except Exception:
        _logger.exception('could not open full-screen picker, keeping old popover')
        return
    BigWorld.callback(0.0, self.onWindowClose)


def _onKeyDown(event):
    # dev only: Ctrl+Shift+P opens the picker in the garage (tier X, nothing frozen)
    try:
        if event.key == Keys.KEY_P and event.isCtrlDown() and event.isShiftDown() and _devConfig() is not None:
            _reopen((10,), (), 0)
    except Exception:
        _logger.exception('dev hotkey failed')


FortVehicleSelectPopover._populate = _populate
InputHandler.g_instance.onKeyDown += _onKeyDown
try:
    from advances_picker.impl import __version__
except Exception:
    __version__ = '?'
_logger.info('mod_advances_picker %s loaded%s', __version__, ' (dev mode)' if _devConfig() else '')

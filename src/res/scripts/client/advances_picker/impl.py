# -*- coding: utf-8 -*-
# Advances full-screen tank picker: implementation. Loaded by gui/mods/mod_advances_picker.py,
# either as the packaged module or, in dev mode, straight from the project source.
# View: tank list left, crew / ammo / equipment bar right, "lock in" puts the tank into the slot.
# Needs net.openwg.gameface for the layout ID; fallback is WG's 2.0 picker.
import json
import logging
import os

import adisp
import BigWorld
import nations
from frameworks.wulf import ViewFlags, ViewModel, ViewSettings, WindowFlags, WindowLayer
from gui import SystemMessages
from gui.impl.gen import R
from gui.impl.lobby.common.presenters.vehicles_info_presenter import VehiclesInfoPresenter
from gui.impl.lobby.hangar.base.vehicles_filter_component import VehiclesFilterComponent
from gui.impl.lobby.select_vehicle.select_vehicle import SelectVehicleView, ALL_VEHICLES_CRITERIA
from gui.impl.pub import ViewImpl
from gui.impl.pub.lobby_window import LobbyWindow
from gui.Scaleform.daapi.view.lobby.fortifications.fort_vehicle_select_popover import getVehicleCriteria, convertState
from gui.Scaleform.locale.FORTIFICATIONS import FORTIFICATIONS
from gui.shared import g_eventBus, EVENT_BUS_SCOPE
from gui.shared.events import CSVehicleSelectEvent
from gui.shared.gui_items import GUI_ITEM_TYPE
from gui.shared.gui_items.items_actions import factory as ActionsFactory
from gui.shared.gui_items.processors.tankman import TankmanReturn
from gui.shared.gui_items.Vehicle import VEHICLE_TYPES_ORDER, getIconPath, getIconShopPath, getSmallIconPath
from gui.shared.utils.requesters import REQ_CRITERIA
from helpers import dependency
from helpers.i18n import makeString
from skeletons.gui.game_control import IVehiclePlaylistsController, IWotPlusController
from skeletons.gui.shared import IItemsCache

__version__ = '0.8.0'
_logger = logging.getLogger('ADVANCES_PICKER')
_logger.setLevel(logging.INFO)
_LAYOUT_KEY = 'ez.tank_picker.view'
# set by the loader in dev mode: {'src': 'X:/.../src', 'reopen': callable(levelsRange, frozen, currentCD)}
DEV = None
_UI_DIR = 'res/gui/gameface/mods/advances_picker'


def _devUI():
    if not DEV:
        return u''
    try:
        files = {}
        for name in ('style.css', 'app.js'):
            with open(os.path.join(DEV['src'], _UI_DIR, name), 'rb') as f:
                files[name] = f.read().decode('utf-8')
        return json.dumps({'css': files['style.css'], 'js': files['app.js']})
    except Exception:
        _logger.exception('dev: reading UI files failed')
        return u''
_FILTERS_FILE = os.path.join('mods', 'configs', 'advances_picker', 'filters.json')  # relative to the game folder


def _loadFilters():
    try:
        if os.path.isfile(_FILTERS_FILE):
            with open(_FILTERS_FILE, 'r') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        _logger.exception('reading %s failed', _FILTERS_FILE)
    return {}


def _saveFilters(raw):
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return
        folder = os.path.dirname(_FILTERS_FILE)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with open(_FILTERS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception:
        _logger.exception('writing %s failed', _FILTERS_FILE)


def _u(value):
    if isinstance(value, str):
        return value.decode('utf-8', 'replace')
    return value if value is not None else u''


def _img(path):
    # Flash style '../maps/icons/x.png' -> Gameface 'img://gui/maps/icons/x.png'
    path = _u(path)
    if path.startswith(u'..'):
        return u'img://gui' + path[2:]
    if path.startswith(u'gui/'):
        return u'img://' + path
    return path


def _autoEquip():
    # Z4imon's auto_equipment_return mod (used as-is, never modified): returns (config, apply) or None
    try:
        from gui.mods.auto_equip import config as aeConfig, apply as aeApply
        return (aeConfig, aeApply)
    except Exception:
        return None


def _isFrozen(frozenCDs, intCD):
    return frozenCDs == 'all' or intCD in frozenCDs


def _stateText(vehicle, frozenCDs):
    if not vehicle.isReadyToFight:
        return _u(convertState(vehicle.getState()[0])) or u'Nicht einsatzbereit'
    if _isFrozen(frozenCDs, vehicle.intCD):
        return u'Eingefroren'
    return u''


def _itemIcon(item):
    for getter in (lambda: item.getBonusIcon('small'), lambda: item.icon):
        try:
            icon = getter()
            if icon:
                return _img(icon)
        except Exception:
            pass
    return u''


# --- full-screen custom view ------------------------------------------------------

class AdvancesPickerModel(ViewModel):
    __slots__ = ('onAction',)

    def __init__(self, properties=2, commands=1):
        super(AdvancesPickerModel, self).__init__(properties=properties, commands=commands)

    def setData(self, value):
        self._setString(0, value)

    def setDev(self, value):
        self._setString(1, value)

    def _initialize(self):
        super(AdvancesPickerModel, self)._initialize()
        self._addStringProperty('data', u'{}')
        self._addStringProperty('dev', u'')
        self.onAction = self._addCommand('onAction')


class AdvancesPickerView(ViewImpl):
    _itemsCache = dependency.descriptor(IItemsCache)
    _wotPlus = dependency.descriptor(IWotPlusController)
    _playlistsCtrl = dependency.descriptor(IVehiclePlaylistsController)

    def __init__(self, layoutID, levelsRange, frozenCDs, currentVehicleCD=0):
        settings = ViewSettings(layoutID, flags=ViewFlags.VIEW, model=AdvancesPickerModel())
        super(AdvancesPickerView, self).__init__(settings)
        self._levelsRange = levelsRange
        self._frozenCDs = frozenCDs
        self._criteria = getVehicleCriteria(levelsRange, inHangar=True) | ALL_VEHICLES_CRITERIA | REQ_CRITERIA.INVENTORY
        self._selectedCD = currentVehicleCD
        self._refreshPending = False
        self._filters = _loadFilters()
        self._openArgs = (levelsRange, frozenCDs)
        self._aePolling = False

    @property
    def viewModel(self):
        return super(AdvancesPickerView, self).getViewModel()

    def _onLoading(self, *args, **kwargs):
        super(AdvancesPickerView, self)._onLoading(*args, **kwargs)
        if DEV:
            self.viewModel.setDev(_devUI())
        self._push()

    def _getEvents(self):
        return ((self.viewModel.onAction, self.__onAction),
                (self._itemsCache.onSyncCompleted, self.__onSync))

    # data ----------------------------------------------------------------------

    def _vehicles(self):
        return self._itemsCache.items.getVehicles(self._criteria)

    def _push(self):
        try:
            data = self._pack()
            self.viewModel.setData(json.dumps(data))
        except Exception:
            _logger.exception('packing picker data failed')

    def _pack(self):
        vehicles = self._vehicles()
        if self._selectedCD not in vehicles:
            self._selectedCD = 0
        items = []
        for vehicle in vehicles.itervalues():
            state = _stateText(vehicle, self._frozenCDs)
            items.append({'cd': vehicle.intCD,
             'name': _u(vehicle.shortUserName),
             'fullName': _u(vehicle.userName),
             'nation': nations.NAMES[vehicle.nationID],
             'nationIdx': vehicle.nationID,
             'type': vehicle.type,
             'typeIdx': VEHICLE_TYPES_ORDER.index(vehicle.type) if vehicle.type in VEHICLE_TYPES_ORDER else 9,
             'level': vehicle.level,
             'premium': vehicle.isPremium,
             'favorite': vehicle.isFavorite,
             'icon': _img(getIconPath(vehicle.name) or getSmallIconPath(vehicle.name)),
             'ready': not state,
             'state': state})
        return {'title': _u(makeString(FORTIFICATIONS.STRONGHOLDPOPOVER_HEADER)),
         'version': __version__,
         'dev': bool(DEV),
         'selected': self._selectedCD,
         'vehicles': items,
         'playlists': self._packPlaylists(),
         'filters': self._filters,
         'detail': self._packDetail(vehicles.get(self._selectedCD)) if self._selectedCD else None}

    def _packAutoEquip(self, vehicle):
        ae = _autoEquip()
        if ae is None:
            return None
        aeConfig, aeApply = ae
        try:
            busy = bool(aeApply.is_busy())
            if busy:
                self._pollAutoEquip()
            return {'enabled': bool(aeConfig.is_auto_enabled()),
             'hasSets': bool(aeConfig.has_saved_sets(vehicle.invID)),
             'busy': busy}
        except Exception:
            _logger.exception('auto equip state failed')
            return None

    def _pollAutoEquip(self):
        # the run finishes with item syncs, but its busy flag drops a moment later: re-check
        if not self._aePolling:
            self._aePolling = True
            BigWorld.callback(0.7, self.__aePoll)

    def __aePoll(self):
        self._aePolling = False
        try:
            if self.viewModel is not None:
                self._push()
        except Exception:
            pass

    def _selectInHangar(self, vehicle):
        # auto equip reacts to the garage selection (g_currentVehicle) and checks it while running
        if _autoEquip() is None or vehicle is None or vehicle.isLocked:
            return
        try:
            from CurrentVehicle import g_currentVehicle
            if not g_currentVehicle.isPresent() or g_currentVehicle.item.invID != vehicle.invID:
                g_currentVehicle.selectVehicle(vehicle.invID)
        except Exception:
            _logger.exception('selecting %s in the garage failed', vehicle.intCD)

    def _packPlaylists(self):
        # the game's own 2.0 vehicle playlists: JSON {title, createdAt, modifiedAt, list: [intCD, ...]}
        result = []
        try:
            if not self._playlistsCtrl.isEnabled:
                return result
            for plID, raw in self._playlistsCtrl.iterPlaylists():
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                cds = []
                for value in data.get('list', ()):
                    try:
                        cds.append(int(value))
                    except (TypeError, ValueError):
                        pass
                result.append({'id': _u(plID), 'title': _u(data.get('title', u'')) or u'Playlist', 'cds': cds})
        except Exception:
            _logger.exception('reading vehicle playlists failed')
        result.sort(key=lambda p: p['title'].lower())
        return result

    def _packDetail(self, vehicle):
        if vehicle is None:
            return None
        state = _stateText(vehicle, self._frozenCDs)
        return {'cd': vehicle.intCD,
         'name': _u(vehicle.userName),
         'level': vehicle.level,
         'type': vehicle.type,
         'nation': nations.NAMES[vehicle.nationID],
         'image': _img(getIconShopPath(vehicle.name, '360x270')),
         'ready': not state,
         'state': state,
         'crewLocked': bool(vehicle.isCrewLocked or vehicle.isLocked),
         'canReturnCrew': self._canReturnCrew(vehicle),
         'crew': self._packCrew(vehicle),
         'autoEquip': self._packAutoEquip(vehicle),
         'shells': self._packShells(vehicle),
         'ammoMax': vehicle.ammoMaxSize,
         'devices': self._packDevices(vehicle),
         'consumables': self._packConsumables(vehicle)}

    def _packShells(self, vehicle):
        shots = {}
        try:
            for shot in vehicle.descriptor.gun.shots:
                shots[shot.shell.compactDescr] = shot
        except Exception:
            _logger.exception('gun shots lookup failed')
        result = []
        for shell in vehicle.shells.installed:
            if shell is None:
                continue
            shot = shots.get(shell.intCD)
            stock = self._itemsCache.items.getItemByCD(shell.intCD)
            price = shell.getBuyPrice().price
            currency = price.getCurrency()
            try:
                damage = int(shot.shell.damage[0]) if shot is not None else 0
                pen = int(shot.piercingPower[0]) if shot is not None else 0
            except Exception:
                damage = pen = 0
            result.append({'cd': shell.intCD,
             'name': _u(shell.userName),
             'kind': _u(makeString('#item_types:shell/kinds/%s' % shell.type)),
             'abbr': _u(makeString('#item_types:shell/kindsAbbreviation/%s' % shell.type)),
             'premium': bool(getattr(shell, 'isPremium', False)),
             'icon': _itemIcon(shell),
             'count': shell.count,
             'depot': stock.inventoryCount if stock is not None else 0,
             'price': int(price.get(currency, 0) or 0),
             'currency': currency,
             'damage': damage,
             'pen': pen})
        return result

    def _packItem(self, item):
        removable = bool(getattr(item, 'isRemovable', True))
        wotPlusFree = False
        if not removable and item.itemTypeID == GUI_ITEM_TYPE.OPTIONALDEVICE:
            try:
                wotPlusFree = bool(self._wotPlus.isFreeToDemount(item))  # same check WG's RemoveOptionalDevice uses
            except Exception:
                _logger.exception('WoT Plus demount check failed')
        return {'cd': item.intCD,
         'freeDemount': removable or wotPlusFree,
         'wotPlusFree': wotPlusFree,
         'name': _u(item.userName),
         'icon': _itemIcon(item),
         'depot': item.inventoryCount,
         'removable': removable,
         'trophy': bool(getattr(item, 'isTrophy', False)),
         'deluxe': bool(getattr(item, 'isDeluxe', False)),
         'modernized': bool(getattr(item, 'isModernized', False)),
         'cats': sorted(getattr(item.descriptor, 'categories', ()) or ())}

    def _ownedItems(self, itemTypeID):
        items = self._itemsCache.items.getItems(itemTypeID, REQ_CRITERIA.INVENTORY)
        return [ item for item in items.itervalues() if item.inventoryCount > 0 ]

    def _packDevices(self, vehicle):
        owned = self._ownedItems(GUI_ITEM_TYPE.OPTIONALDEVICE)
        result = []
        for slot, device in enumerate(vehicle.optDevices.installed):
            # test fitting on a copy where this slot is empty
            test = self._itemsCache.items.getVehicleCopy(vehicle)
            if test.descriptor.optionalDevices[slot] is not None:
                test.descriptor.removeOptionalDevice(slot)
            candidates = []
            for item in owned:
                if device is not None and item.intCD == device.intCD:
                    continue
                try:
                    if item.mayInstall(test, slot)[0]:
                        candidates.append(self._packItem(item))
                except Exception:
                    pass
            candidates.sort(key=lambda c: (not c['deluxe'], not c['trophy'], c['name']))
            try:
                slotCats = sorted(vehicle.optDevices.slots[slot].categories or ())
            except Exception:
                slotCats = []
            result.append({'slot': slot,
             'item': self._packItem(device) if device is not None else None,
             'slotCats': slotCats,
             'candidates': candidates})
        return result

    def _packConsumables(self, vehicle):
        owned = self._ownedItems(GUI_ITEM_TYPE.EQUIPMENT)
        installed = list(vehicle.consumables.installed)
        installedCDs = set(c.intCD for c in installed if c is not None)
        result = []
        for slot, item in enumerate(installed):
            candidates = []
            for other in owned:
                if other.intCD in installedCDs:
                    continue
                try:
                    if other.mayInstall(vehicle, slot)[0]:
                        candidates.append(self._packItem(other))
                except Exception:
                    pass
            candidates.sort(key=lambda c: c['name'])
            result.append({'slot': slot,
             'item': self._packItem(item) if item is not None else None,
             'candidates': candidates})
        return result

    def _canReturnCrew(self, vehicle):
        last = [ tid for tid in (vehicle.lastCrew or ()) if tid is not None ]
        if not last:
            return False
        current = set(t.invID for _, t in vehicle.crew if t is not None)
        return not set(last) <= current

    def _packTankman(self, tankman, vehicle):
        native = tankman.vehicleNativeDescr.type.compactDescr == vehicle.intCD
        try:
            eff = int(round(tankman.currentVehicleSkillsEfficiency * 100)) if tankman.vehicleInvID == vehicle.invID else None
        except Exception:
            eff = None
        where = u''
        if tankman.isInTank and tankman.vehicleInvID != vehicle.invID:
            other = self._itemsCache.items.getVehicle(tankman.vehicleInvID)
            where = _u(other.shortUserName) if other is not None else u'?'
        nativeVeh = self._itemsCache.items.getItemByCD(tankman.vehicleNativeDescr.type.compactDescr)
        return {'id': tankman.invID,
         'name': _u(tankman.fullUserName),
         'native': native,
         'nativeName': _u(nativeVeh.shortUserName) if nativeVeh is not None else u'',
         'eff': eff,
         'skills': len(tankman.skills),
         'where': where}

    def _packCrew(self, vehicle):
        roles = vehicle.descriptor.type.crewRoles
        crew = dict(vehicle.crew)
        allTankmen = self._itemsCache.items.getTankmen(REQ_CRITERIA.TANKMAN.ACTIVE | REQ_CRITERIA.NATIONS([vehicle.nationID])).values()
        result = []
        for slot, slotRoles in enumerate(roles):
            role = slotRoles[0]
            tankman = crew.get(slot)
            candidates = []
            for t in allTankmen:
                if t.role != role or (tankman is not None and t.invID == tankman.invID):
                    continue
                if t.vehicleInvID == vehicle.invID:
                    continue
                if t.isInTank:
                    other = self._itemsCache.items.getVehicle(t.vehicleInvID)
                    if other is None or other.isCrewLocked or other.isLocked:
                        continue
                candidates.append(self._packTankman(t, vehicle))
            candidates.sort(key=lambda c: (not c['native'], c['where'] != u'', -c['skills'], c['name']))
            result.append({'slot': slot,
             'role': role,
             'roleName': _u(makeString('#item_types:tankman/roles/%s' % role)),
             'tankman': self._packTankman(tankman, vehicle) if tankman is not None else None,
             'candidates': candidates[:40]})
        return result

    # actions -------------------------------------------------------------------

    def __onAction(self, args=None):
        args = args or {}
        action = args.get('action')
        try:
            if action == 'select':
                self._selectedCD = int(args.get('cd', 0))
                self._selectInHangar(self._selectedVehicle())
                self._push()
            elif action == 'autoEquipApply':
                self._autoEquipApply()
            elif action == 'equip':
                self._equipTankman(int(args.get('tankman')), int(args.get('slot')))
            elif action == 'unload':
                self._unloadTankman(int(args.get('slot')))
            elif action == 'returnCrew':
                self._returnCrew()
            elif action == 'saveFilters':
                self._filters = json.loads(args.get('filters', '{}'))
                _saveFilters(args.get('filters', '{}'))
            elif action == 'setDevice':
                self._setDevice(int(args.get('slot')), int(args.get('cd', 0)))
            elif action == 'setConsumable':
                self._setConsumable(int(args.get('slot')), int(args.get('cd', 0)))
            elif action == 'setAmmo':
                self._applyAmmo(args.get('counts', ''))
            elif action == 'lock':
                self._lockIn()
            elif action == 'close':
                self.destroyWindow()
            elif action == 'devReload' and DEV:
                levelsRange, frozen = self._openArgs
                currentCD = self._selectedCD
                reopen = DEV['reopen']
                self.destroyWindow()
                BigWorld.callback(0.1, lambda: reopen(levelsRange, frozen, currentCD))
        except Exception:
            _logger.exception('action %r failed', args)

    def _selectedVehicle(self):
        return self._vehicles().get(self._selectedCD)

    def _equipTankman(self, tankmanInvID, slot):
        vehicle = self._selectedVehicle()
        if vehicle is not None:
            ActionsFactory.doAction(ActionsFactory.EQUIP_TANKMAN, tankmanInvID, vehicle.invID, slot)

    def _unloadTankman(self, slot):
        vehicle = self._selectedVehicle()
        if vehicle is not None:
            ActionsFactory.doAction(ActionsFactory.UNLOAD_TANKMAN, vehicle.invID, slot)

    def _autoEquipApply(self):
        ae = _autoEquip()
        vehicle = self._selectedVehicle()
        if ae is None or vehicle is None:
            return
        self._selectInHangar(vehicle)
        # the mod's own single-vehicle run (same one its selection trigger uses)
        BigWorld.callback(0.3, lambda: ae[1].apply_saved_sets(vehicle.invID))
        BigWorld.callback(0.4, self._pollAutoEquip)

    def _applyAmmo(self, countsStr):
        vehicle = self._selectedVehicle()
        if vehicle is None:
            return
        counts = {}
        for part in str(countsStr).split(','):
            if ':' in part:
                cd, count = part.split(':', 1)
                counts[int(cd)] = max(0, int(count))
        if sum(counts.values()) > vehicle.ammoMaxSize:
            SystemMessages.pushMessage(u'Zu viel Munition (max. %d)' % vehicle.ammoMaxSize, type=SystemMessages.SM_TYPE.Warning)
            return
        copy = self._itemsCache.items.getVehicleCopy(vehicle)
        layout = copy.shells.layout
        changed = False
        for slotID, shell in enumerate(layout):
            if shell is not None and shell.intCD in counts and shell.count != counts[shell.intCD]:
                shell.count = counts[shell.intCD]
                layout[slotID] = shell
                changed = True
        if changed:
            # credits shown and confirmed in our bar; WG only asks again if gold must be exchanged
            ActionsFactory.doAction(ActionsFactory.BUY_AND_INSTALL_SHELLS, copy, confirmOnlyExchange=True)

    @adisp.adisp_process
    def _setDevice(self, slot, intCD):
        vehicle = self._selectedVehicle()
        if vehicle is None:
            return
        installed = vehicle.optDevices.installed[slot]
        if installed is not None:
            if installed.intCD == intCD:
                return
            # WG's own removal: free for removable devices, otherwise WG shows its gold / demount kit dialog
            everywhere = vehicle.optDevices.setupLayouts.getIntCDs().count(installed.intCD) == 1
            action = ActionsFactory.getAction(ActionsFactory.REMOVE_OPT_DEVICE, vehicle, installed, slot, False, bool(intCD), everywhere)
            if action is None:
                return
            removed = yield action.doAction()
            if not removed:
                return
        if not intCD:
            return
        item = self._itemsCache.items.getItemByCD(intCD)
        vehicle = self._selectedVehicle()
        if item is None or vehicle is None or item.inventoryCount <= 0:
            return
        copy = self._itemsCache.items.getVehicleCopy(vehicle)
        if copy.descriptor.optionalDevices[slot] is not None:
            copy.descriptor.removeOptionalDevice(slot)
        copy.optDevices.layout[slot] = item
        copy.descriptor.installOptionalDevice(item.intCD, slot)
        ActionsFactory.doAction(ActionsFactory.BUY_AND_INSTALL_OPT_DEVICES, copy, confirmOnlyExchange=True)

    def _setConsumable(self, slot, intCD):
        vehicle = self._selectedVehicle()
        if vehicle is None:
            return
        item = self._itemsCache.items.getItemByCD(intCD) if intCD else None
        if item is not None and item.inventoryCount <= 0:
            return  # owned items only, never buy
        copy = self._itemsCache.items.getVehicleCopy(vehicle)
        copy.consumables.layout[slot] = item
        ActionsFactory.doAction(ActionsFactory.BUY_AND_INSTALL_CONSUMABLES, copy, confirmOnlyExchange=True)

    @adisp.adisp_process
    def _returnCrew(self):
        vehicle = self._selectedVehicle()
        if vehicle is None:
            return
        result = yield TankmanReturn(vehicle).request()
        if result.userMsg:
            SystemMessages.pushI18nMessage(result.userMsg, type=result.sysMsgType)

    def _lockIn(self):
        vehicle = self._selectedVehicle()
        if vehicle is None:
            return
        state = _stateText(vehicle, self._frozenCDs)
        if state:
            SystemMessages.pushMessage(u'%s: %s' % (_u(vehicle.shortUserName), state), type=SystemMessages.SM_TYPE.Warning)
            return
        _fireSelected(vehicle.intCD)
        self.destroyWindow()

    def __onSync(self, reason, diff):
        # crew / ammo changes arrive as cache syncs; coalesce bursts into one push
        if diff is not None and GUI_ITEM_TYPE.VEHICLE not in diff and GUI_ITEM_TYPE.TANKMAN not in diff:
            return
        if not self._refreshPending:
            self._refreshPending = True
            BigWorld.callback(0.1, self.__delayedPush)

    def __delayedPush(self):
        self._refreshPending = False
        try:
            if self.viewModel is not None:
                self._push()
        except Exception:
            pass  # view already destroyed


class AdvancesPickerWindow(LobbyWindow):
    __slots__ = ()

    def __init__(self, layoutID, levelsRange, frozenCDs, currentVehicleCD=0):
        super(AdvancesPickerWindow, self).__init__(
            wndFlags=WindowFlags.WINDOW | WindowFlags.WINDOW_FULLSCREEN,
            content=AdvancesPickerView(layoutID, levelsRange, frozenCDs, currentVehicleCD),
            layer=WindowLayer.FULLSCREEN_WINDOW)


# --- fallback: WG 2.0 picker (v0.2) ---------------------------------------------

class StateVehiclesInfoPresenter(VehiclesInfoPresenter):
    # WG's 2.0 picker never renders vehicle states, so put the state into the shown name
    def __init__(self, vehiclesComponent, frozenCDs):
        super(StateVehiclesInfoPresenter, self).__init__(vehiclesComponent)
        self._frozenCDs = frozenCDs

    def _toModelItem(self, vehicle):
        item = super(StateVehiclesInfoPresenter, self)._toModelItem(vehicle)
        try:
            state = _stateText(vehicle, self._frozenCDs)
        except Exception:
            _logger.exception('state lookup failed for %s', vehicle.intCD)
            state = u''
        if state:
            item['shortName'] = u'%s · %s' % (_u(item['shortName']), state)
        return item


class AdvancesSelectVehicleView(SelectVehicleView):
    _itemsCache = dependency.descriptor(IItemsCache)

    def __init__(self, levelsRange, frozenCDs, currentVehicleCD=0):
        super(AdvancesSelectVehicleView, self).__init__(None, _fireSelected, currentVehicleCD)
        criteria = getVehicleCriteria(levelsRange, inHangar=True) | ALL_VEHICLES_CRITERIA | REQ_CRITERIA.INVENTORY
        self._randomVehicleFilter = VehiclesFilterComponent(criteria)
        self._randomInvVehicleFilter = VehiclesFilterComponent(criteria)
        self._frozenCDs = frozenCDs

    def _onLoading(self, *args, **kwargs):
        self._randomVehicleFilter.initialize()
        self._randomInvVehicleFilter.initialize()
        self._accountStyles.initialize()
        self.viewModel.setTitle(makeString(FORTIFICATIONS.STRONGHOLDPOPOVER_HEADER))
        self.viewModel.setCurrentVehicleCD(self._currentVehicleCD)
        self.viewModel.setIsAllVehicles(False)
        super(SelectVehicleView, self)._onLoading(*args, **kwargs)

    def _getChildComponents(self):
        children = super(AdvancesSelectVehicleView, self)._getChildComponents()
        children[R.aliases.select_vehicle.select_vehicle.VehiclesInfo()] = lambda: StateVehiclesInfoPresenter(self._randomVehicleFilter, self._frozenCDs)
        return children

    def _onSelect(self, args):
        intCD = args.get('id', None) if args else None
        if intCD is None:
            return
        vehicle = self._itemsCache.items.getItemByCD(int(intCD))
        state = _stateText(vehicle, self._frozenCDs) if vehicle is not None else u'?'
        if state:
            SystemMessages.pushMessage(u'%s: %s' % (_u(vehicle.shortUserName) if vehicle else intCD, state), type=SystemMessages.SM_TYPE.Warning)
            return
        _fireSelected(int(intCD))
        self.destroyWindow()

    def _finalize(self):
        for f in (self._randomVehicleFilter, self._randomInvVehicleFilter):
            try:
                f.destroy()
            except Exception:
                pass
        super(AdvancesSelectVehicleView, self)._finalize()


class AdvancesSelectVehicleWindow(LobbyWindow):
    __slots__ = ()

    def __init__(self, levelsRange, frozenCDs, currentVehicleCD=0):
        super(AdvancesSelectVehicleWindow, self).__init__(
            wndFlags=WindowFlags.WINDOW | WindowFlags.WINDOW_FULLSCREEN,
            content=AdvancesSelectVehicleView(levelsRange, frozenCDs, currentVehicleCD),
            layer=WindowLayer.FULLSCREEN_WINDOW)


# --- hook -------------------------------------------------------------------------

def _fireSelected(intCD):
    g_eventBus.handleEvent(CSVehicleSelectEvent(CSVehicleSelectEvent.VEHICLE_SELECTED, [intCD]), scope=EVENT_BUS_SCOPE.DEFAULT)


def _frozenCDs(popover):
    try:
        from constants import QUEUE_TYPE
        from gui.clans.stronghold_event_requester import FrozenVehiclesConstants
        entity = popover.prbEntity
        if entity is None or entity.getQueueType() != QUEUE_TYPE.STRONGHOLD_UNITS:
            return ()
        frozen = entity.getEventFrozenVehicles()
        if frozen == FrozenVehiclesConstants.ALL_VEHICLES_FROZEN:
            return 'all'
        return tuple(frozen or ())
    except Exception:
        _logger.exception('frozen vehicles lookup failed')
        return ()


def _customLayoutID():
    try:
        from openwg_gameface import res_id_by_key
        from gui.impl.gen_utils import INVALID_RES_ID
        resID = res_id_by_key(_LAYOUT_KEY)
        return None if resID == INVALID_RES_ID else resID
    except Exception:
        _logger.exception('openwg_gameface not available')
        return None


def openFromPopover(popover):
    selected = list(popover._selectedVehicles or ())
    openPicker(popover._levelsRange, _frozenCDs(popover), selected[0] if selected else 0)


def openPicker(levelsRange, frozen, currentCD):
    layoutID = _customLayoutID()
    if layoutID is not None:
        try:
            AdvancesPickerWindow(layoutID, levelsRange, frozen, currentCD).load()
            return
        except Exception:
            _logger.exception('custom picker failed, using WG picker')
    AdvancesSelectVehicleWindow(levelsRange, frozen, currentCD).load()

# -*- coding: utf-8 -*-
# Advances (stronghold) battle room: replace the small Flash tank popover with a
# full-screen Gameface view: tank list on the left, crew / loadout bar on the right,
# "lock in" puts the tank into the slot. Needs net.openwg.gameface for the layout ID.
# Fallback (layout missing): WG's 2.0 picker (gui.impl.lobby.select_vehicle).
# Multi-select (commander slot settings) keeps the old popover.
import json
import logging

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
from gui.Scaleform.daapi.view.lobby.fortifications.fort_vehicle_select_popover import FortVehicleSelectPopover, getVehicleCriteria, convertState
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
from skeletons.gui.shared import IItemsCache

__version__ = '0.3.0'
_logger = logging.getLogger('ADVANCES_PICKER')
_logger.setLevel(logging.INFO)
_LAYOUT_KEY = 'ez.tank_picker.view'


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

    def __init__(self, properties=1, commands=1):
        super(AdvancesPickerModel, self).__init__(properties=properties, commands=commands)

    def setData(self, value):
        self._setString(0, value)

    def _initialize(self):
        super(AdvancesPickerModel, self)._initialize()
        self._addStringProperty('data', u'{}')
        self.onAction = self._addCommand('onAction')


class AdvancesPickerView(ViewImpl):
    _itemsCache = dependency.descriptor(IItemsCache)

    def __init__(self, layoutID, levelsRange, frozenCDs, currentVehicleCD=0):
        settings = ViewSettings(layoutID, flags=ViewFlags.VIEW, model=AdvancesPickerModel())
        super(AdvancesPickerView, self).__init__(settings)
        self._levelsRange = levelsRange
        self._frozenCDs = frozenCDs
        self._criteria = getVehicleCriteria(levelsRange, inHangar=True) | ALL_VEHICLES_CRITERIA | REQ_CRITERIA.INVENTORY
        self._selectedCD = currentVehicleCD
        self._refreshPending = False

    @property
    def viewModel(self):
        return super(AdvancesPickerView, self).getViewModel()

    def _onLoading(self, *args, **kwargs):
        super(AdvancesPickerView, self)._onLoading(*args, **kwargs)
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
         'selected': self._selectedCD,
         'vehicles': items,
         'detail': self._packDetail(vehicles.get(self._selectedCD)) if self._selectedCD else None}

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
         'shells': [ {'name': _u(s.userName), 'icon': _itemIcon(s), 'count': s.count} for s in vehicle.shells.installed if s is not None ],
         'ammoMax': vehicle.ammoMaxSize,
         'devices': [ ({'name': _u(d.userName), 'icon': _itemIcon(d)} if d is not None else None) for d in vehicle.optDevices.installed ],
         'consumables': [ ({'name': _u(c.userName), 'icon': _itemIcon(c)} if c is not None else None) for c in vehicle.consumables.installed ]}

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
                self._push()
            elif action == 'equip':
                self._equipTankman(int(args.get('tankman')), int(args.get('slot')))
            elif action == 'unload':
                self._unloadTankman(int(args.get('slot')))
            elif action == 'returnCrew':
                self._returnCrew()
            elif action == 'lock':
                self._lockIn()
            elif action == 'close':
                self.destroyWindow()
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


def _openPicker(levelsRange, frozen, currentCD):
    layoutID = _customLayoutID()
    if layoutID is not None:
        try:
            AdvancesPickerWindow(layoutID, levelsRange, frozen, currentCD).load()
            return
        except Exception:
            _logger.exception('custom picker failed, using WG picker')
    AdvancesSelectVehicleWindow(levelsRange, frozen, currentCD).load()


_origPopulate = FortVehicleSelectPopover._populate


def _populate(self):
    _origPopulate(self)
    if self._isMultiSelect:
        return
    try:
        selected = list(self._selectedVehicles or ())
        _openPicker(self._levelsRange, _frozenCDs(self), selected[0] if selected else 0)
    except Exception:
        _logger.exception('could not open full-screen picker, keeping old popover')
        return
    BigWorld.callback(0.0, self.onWindowClose)


FortVehicleSelectPopover._populate = _populate
_logger.info('mod_advances_picker %s loaded', __version__)

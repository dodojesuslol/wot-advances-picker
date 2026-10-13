# -*- coding: utf-8 -*-
# Advances (stronghold) battle room: replace the small Flash tank popover with
# the WoT 2.0 full-screen vehicle picker (gui.impl.lobby.select_vehicle).
# Multi-select (commander slot settings) keeps the old popover.
import logging

import BigWorld
from frameworks.wulf import WindowLayer, WindowFlags
from gui import SystemMessages
from gui.impl.lobby.select_vehicle.select_vehicle import SelectVehicleView, ALL_VEHICLES_CRITERIA
from gui.impl.lobby.hangar.base.vehicles_filter_component import VehiclesFilterComponent
from gui.impl.lobby.common.presenters.vehicles_info_presenter import VehiclesInfoPresenter
from gui.impl.gen import R
from gui.impl.pub.lobby_window import LobbyWindow
from gui.Scaleform.daapi.view.lobby.fortifications.fort_vehicle_select_popover import FortVehicleSelectPopover, getVehicleCriteria, convertState
from gui.Scaleform.locale.FORTIFICATIONS import FORTIFICATIONS
from gui.shared import g_eventBus, EVENT_BUS_SCOPE
from gui.shared.events import CSVehicleSelectEvent
from gui.shared.utils.requesters import REQ_CRITERIA
from helpers import dependency
from helpers.i18n import makeString
from skeletons.gui.shared import IItemsCache

__version__ = '0.2.0'
_logger = logging.getLogger('ADVANCES_PICKER')
_logger.setLevel(logging.INFO)


def _isFrozen(frozenCDs, intCD):
    return frozenCDs == 'all' or intCD in frozenCDs


class StateVehiclesInfoPresenter(VehiclesInfoPresenter):
    # WG's 2.0 picker never renders vehicle states, so put the state into the shown name
    def __init__(self, vehiclesComponent, frozenCDs):
        super(StateVehiclesInfoPresenter, self).__init__(vehiclesComponent)
        self._frozenCDs = frozenCDs

    def _toModelItem(self, vehicle):
        item = super(StateVehiclesInfoPresenter, self)._toModelItem(vehicle)
        state = u''
        try:
            if not vehicle.isReadyToFight:
                state = convertState(vehicle.getState()[0]) or u''
                if isinstance(state, str):
                    state = state.decode('utf-8')
            elif _isFrozen(self._frozenCDs, vehicle.intCD):
                state = u'Eingefroren'
        except Exception:
            _logger.exception('state lookup failed for %s', vehicle.intCD)
        if state:
            name = item['shortName']
            if isinstance(name, str):
                name = name.decode('utf-8')
            item['shortName'] = u'%s \u00b7 %s' % (name, state)
        return item


class AdvancesSelectVehicleView(SelectVehicleView):
    _itemsCache = dependency.descriptor(IItemsCache)

    def __init__(self, levelsRange, frozenCDs, currentVehicleCD=0):
        super(AdvancesSelectVehicleView, self).__init__(None, self.__onPicked, currentVehicleCD)
        criteria = getVehicleCriteria(levelsRange, inHangar=True) | ALL_VEHICLES_CRITERIA | REQ_CRITERIA.INVENTORY
        # both lists (all / garage) show only what may be used in this room
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
        # skip SelectVehicleView._onLoading (it needs a title enum), call its parent
        super(SelectVehicleView, self)._onLoading(*args, **kwargs)

    def _getChildComponents(self):
        children = super(AdvancesSelectVehicleView, self)._getChildComponents()
        children[R.aliases.select_vehicle.select_vehicle.VehiclesInfo()] = lambda: StateVehiclesInfoPresenter(self._randomVehicleFilter, self._frozenCDs)
        return children

    def _onSelect(self, args):
        intCD = args.get('id', None) if args else None
        if intCD is None:
            return
        intCD = int(intCD)
        vehicle = self._itemsCache.items.getItemByCD(intCD)
        if vehicle is None or not vehicle.isReadyToFight:
            SystemMessages.pushMessage(u'%s: nicht einsatzbereit' % (vehicle.shortUserName if vehicle else intCD), type=SystemMessages.SM_TYPE.Warning)
            return
        if _isFrozen(self._frozenCDs, intCD):
            SystemMessages.pushMessage(u'%s ist eingefroren' % vehicle.shortUserName, type=SystemMessages.SM_TYPE.Warning)
            return
        self.__onPicked(intCD)
        self.destroyWindow()

    def _finalize(self):
        for f in (self._randomVehicleFilter, self._randomInvVehicleFilter):
            try:
                f.destroy()
            except Exception:
                pass
        super(AdvancesSelectVehicleView, self)._finalize()

    @staticmethod
    def __onPicked(intCD):
        g_eventBus.handleEvent(CSVehicleSelectEvent(CSVehicleSelectEvent.VEHICLE_SELECTED, [intCD]), scope=EVENT_BUS_SCOPE.DEFAULT)


class AdvancesSelectVehicleWindow(LobbyWindow):
    __slots__ = ()

    def __init__(self, levelsRange, frozenCDs, currentVehicleCD=0):
        super(AdvancesSelectVehicleWindow, self).__init__(
            wndFlags=WindowFlags.WINDOW | WindowFlags.WINDOW_FULLSCREEN,
            content=AdvancesSelectVehicleView(levelsRange, frozenCDs, currentVehicleCD),
            layer=WindowLayer.FULLSCREEN_WINDOW)


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


_origPopulate = FortVehicleSelectPopover._populate


def _populate(self):
    _origPopulate(self)
    if self._isMultiSelect:
        return
    try:
        selected = list(self._selectedVehicles or ())
        window = AdvancesSelectVehicleWindow(self._levelsRange, _frozenCDs(self), selected[0] if selected else 0)
        window.load()
    except Exception:
        _logger.exception('could not open full-screen picker, keeping old popover')
        return
    BigWorld.callback(0.0, self.onWindowClose)


FortVehicleSelectPopover._populate = _populate
_logger.info('mod_advances_picker %s loaded', __version__)

# Browser preview of the picker: mock Gameface engine/model, rem = px, img:// -> extracted game files.
# usage: python3 -I preview.py <src gameface dir> <extracted game root> <out.html> [state]
import json, sys
src, res, out = sys.argv[1], sys.argv[2], sys.argv[3]
state = sys.argv[4] if len(sys.argv) > 4 else 'detail'
css = open(src + '/style.css').read().replace('img://', 'file://' + res + '/')
js = open(src + '/app.js').read().replace('img://', 'file://' + res + '/')

V = [
    ('germany', 'G56_E-100', 'E 100', 'heavyTank', False, True, ''),
    ('ussr', 'R45_IS-7', 'IS-7', 'heavyTank', False, True, ''),
    ('usa', 'A69_T110E5', 'T110E5', 'heavyTank', False, False, 'Besatzung unvollständig'),
    ('france', 'F18_Bat_Chatillon25t', 'B-C 25 t', 'mediumTank', False, True, ''),
    ('uk', 'GB91_Super_Conqueror', 'Super Conqueror', 'heavyTank', False, True, ''),
    ('sweden', 'S16_Kranvagn', 'Kranvagn', 'heavyTank', False, True, ''),
    ('china', 'Ch22_113', '113', 'heavyTank', False, False, 'Zu reparieren'),
    ('czech', 'Cz04_T50_51', 'TVP T 50/51', 'mediumTank', False, True, ''),
    ('japan', 'J16_ST_B1', 'STB-1', 'mediumTank', False, True, ''),
    ('poland', 'Pl15_60TP_Lewandowskiego', '60TP Lewandowskiego', 'heavyTank', False, True, ''),
    ('italy', 'It08_Progetto_M40_mod_65', 'Progetto 65', 'mediumTank', False, True, ''),
    ('germany', 'G89_Leopard1', 'Leopard 1', 'mediumTank', False, True, ''),
    ('ussr', 'R148_Object_430_U', 'Object 430U', 'mediumTank', False, True, ''),
]
vehicles = []
for i, (n, tag, name, typ, prem, ready, st) in enumerate(V):
    vehicles.append({'cd': 1000 + i, 'nation': n, 'name': name, 'fullName': name, 'type': typ, 'level': 10,
                     'premium': i == 4, 'ready': ready, 'state': st,
                     'icon': 'img://gui/maps/icons/vehicle/%s-%s.png' % (n, tag)})
A = 'img://gui/maps/icons/artefact/'
def tm(name, eff, native=True):
    return {'name': name, 'eff': eff, 'native': native, 'nativeName': 'E 100', 'skills': 5}
crew = [
    {'slot': 0, 'roleName': 'Kommandant', 'tankman': tm('Hans Gruber', 100), 'candidates': []},
    {'slot': 1, 'roleName': 'Richtschütze', 'tankman': tm('Karl Weber', 100), 'candidates': [
        {'id': 5, 'name': 'Otto Brandt', 'native': True, 'nativeName': 'E 100', 'where': 'Kaserne', 'skills': 3},
        {'id': 6, 'name': 'Fritz Lang', 'native': False, 'nativeName': 'Maus', 'where': 'Maus', 'skills': 6}]},
    {'slot': 2, 'roleName': 'Fahrer', 'tankman': tm('Max Bauer', 100), 'candidates': []},
    {'slot': 3, 'roleName': 'Funker', 'tankman': None, 'candidates': []},
    {'slot': 4, 'roleName': 'Ladeschütze', 'tankman': tm('Paul Klein', 92), 'candidates': []},
    {'slot': 5, 'roleName': 'Ladeschütze', 'tankman': tm('Jan Novak', 100, False), 'candidates': []},
]
shells = [
    {'cd': 1, 'abbr': 'AP', 'name': 'Pzgr. 39 L/68', 'premium': False, 'pen': 246, 'damage': 750, 'depot': 0, 'count': 28, 'price': 1650, 'currency': 'credits'},
    {'cd': 2, 'abbr': 'HEAT', 'name': 'Hl. Gr. 39 L/68', 'premium': True, 'pen': 334, 'damage': 750, 'depot': 12, 'count': 8, 'price': 4800, 'currency': 'credits'},
    {'cd': 3, 'abbr': 'HE', 'name': 'Sprgr. L/68', 'premium': False, 'pen': 90, 'damage': 950, 'depot': 0, 'count': 4, 'price': 1500, 'currency': 'credits'},
]
def item(name, icon, **kw):
    d = {'name': name, 'icon': A + icon, 'cd': hash(name) % 9999, 'depot': 2, 'cats': []}
    d.update(kw)
    return d
devices = [
    {'slot': 0, 'slotCats': ['firepower'], 'item': item('Ansetzer', 'rammer.png', cats=['firepower'], freeDemount=True), 'candidates': []},
    {'slot': 1, 'slotCats': ['firepower'], 'item': item('Stabilisierung', 'aimingStabilizer.png', cats=['firepower'], trophy=True, freeDemount=True), 'candidates': [
        item('Verbessertes Visier', 'modernizedAimDrivesAimingStabilizer.png', cats=['firepower'], modernized=True),
        item('Stabilisierung', 'aimingStabilizer.png', cats=['firepower'])]},
    {'slot': 2, 'slotCats': ['survivability'], 'item': None, 'candidates': []},
    {'slot': 3, 'slotCats': ['mobility', 'stealth'], 'item': item('Entfernungsmesser', 'stereoscope.png', cats=['stealth'], deluxe=True, freeDemount=True), 'candidates': []},
]
cons = [
    {'slot': 0, 'item': item('Großes Reparaturset', 'largeRepairkit.png'), 'candidates': []},
    {'slot': 1, 'item': item('Großer Erste-Hilfe-Kasten', 'largeMedkit.png'), 'candidates': []},
    {'slot': 2, 'item': item('Feuerlöscher', 'autoExtinguishers.png'), 'candidates': []},
]
detail = {'cd': 1000, 'name': 'E 100', 'level': 10, 'type': 'heavyTank', 'ready': True, 'state': '',
          'crew': crew, 'crewLocked': False, 'canReturnCrew': True, 'shells': shells, 'ammoMax': 40,
          'devices': devices, 'consumables': cons,
          'deviceSetups': {'active': 0, 'group': 'OPTIONAL_DEVICES_AND_BOOSTERS', 'sets': [[], [None, item('Ansetzer', 'rammer.png'), None, None]]},
          'consumableSetups': None,
          'autoEquip': {'enabled': True, 'hasSets': True, 'busy': False}}
data = {'title': 'Fahrzeug wählen', 'vehicles': vehicles, 'selected': 1000 if state != 'empty' else 0,
        'detail': detail if state != 'empty' else None, 'dev': True, 'version': '0.11.0',
        'playlists': [{'id': 'p1', 'title': 'Advances', 'cds': [1000, 1001, 1004]}],
        'filters': {}}
click = {'crewpop': '.member[data-slot="1"]', 'devpop': '[data-dev="1"]'}.get(state, '')
html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
@font-face { font-family: Warhelios; src: url(file://%(res)s/gui/gameface/fonts/Warhelios-Regular.ttf); }
@font-face { font-family: Warhelios; font-weight: bold; src: url(file://%(res)s/gui/gameface/fonts/Warhelios-Bold.ttf); }
@font-face { font-family: PFDINMax; src: url(file://%(res)s/gui/gameface/fonts/pfdinmax/PFDINMax-CompressedMedium.ttf); }
@font-face { font-family: PFDINMax; font-weight: bold; src: url(file://%(res)s/gui/gameface/fonts/pfdinmax/PFDINMax-CompressedBold.ttf); }
html { font-size: 1px; }
%(css)s</style></head><body><div id="root"></div><script>
window.model = { data: %(data)s, dev: "", onAction: function (a) { console.log(JSON.stringify(a)); } };
window.engine = { whenReady: Promise.resolve(), on: function () {} };
window.viewEnv = { addDataChangedCallback: function () {} };
</script><script>%(js)s</script><script>
engine.whenReady.then(function () {}).then(function () { var s = %(click)s; if (s) document.querySelector(s).click(); });
</script></body></html>''' % {'res': res, 'css': css, 'js': js, 'data': json.dumps(json.dumps(data).replace('img://', 'file://' + res + '/')), 'click': json.dumps(click)}
open(out, 'w').write(html)

// Advances full-screen tank picker. Data comes from the Python view as one JSON
// string (model.data); every user action goes back through model.onAction({...}).

const NATION_ORDER = ["germany", "ussr", "usa", "china", "france", "uk", "japan", "czech", "sweden", "poland", "italy"];
const TYPE_ORDER = ["lightTank", "mediumTank", "heavyTank", "AT-SPG", "SPG"];
const TYPE_NAMES = { lightTank: "Leichte Panzer", mediumTank: "Mittlere Panzer", heavyTank: "Schwere Panzer", "AT-SPG": "Jagdpanzer", SPG: "Artillerie" };
const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"];

const ui = {
    nations: new Set(),
    types: new Set(),
    readyOnly: false,
    playlist: "", // id of the game's vehicle playlist used as filter
    autoCrew: true, // return the last crew when a tank is clicked
    search: "",
    openSlot: -1,
    ammo: null, // pending shell counts {cd: count} for data.detail.cd
    openDev: -1,
    openCons: -1,
};

const CAT_NAMES = { firepower: "Feuerkraft", survivability: "Überlebensfähigkeit", mobility: "Mobilität", stealth: "Tarnung" };
let data = { vehicles: [], detail: null, selected: 0 };
let filtersLoaded = false;

// filters are remembered by the Python side in mods/configs/advances_picker/filters.json
function applySavedFilters(f) {
    if (!f) return;
    ui.nations = new Set(f.nations || []);
    ui.types = new Set(f.types || []);
    ui.readyOnly = !!f.readyOnly;
    ui.playlist = f.playlist || "";
    ui.autoCrew = f.autoCrew !== false;
}

let saveTimer = 0;
function saveFilters() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
        saveTimer = 0;
        send({ action: "saveFilters", filters: JSON.stringify({ nations: [...ui.nations], types: [...ui.types], readyOnly: ui.readyOnly, playlist: ui.playlist, autoCrew: ui.autoCrew }) });
    }, 400);
}

const root = document.getElementById("root");

function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function bg(url) {
    return url ? `style="background-image: url(${url});"` : "";
}

function send(args) {
    try {
        window.model.onAction(args);
    } catch (e) {
        console.error("onAction failed", e);
    }
}

function flagUrl(nation) {
    return `img://gui/maps/icons/filters/nations/${nation}.png`;
}

function typeUrl(type) {
    return `img://gui/maps/icons/filters/tanks/${type}.png`;
}

// --- filtering ------------------------------------------------------------------

function playlistHas(id, cd) {
    const pl = (data.playlists || []).find((p) => p.id === id);
    return !pl || pl.cds.indexOf(cd) !== -1;
}

function filtered() {
    const q = ui.search.trim().toLowerCase();
    return data.vehicles
        .filter((v) => !ui.nations.size || ui.nations.has(v.nation))
        .filter((v) => !ui.types.size || ui.types.has(v.type))
        .filter((v) => !ui.readyOnly || v.ready)
        .filter((v) => !ui.playlist || playlistHas(ui.playlist, v.cd))
        .filter((v) => !q || v.name.toLowerCase().includes(q) || v.fullName.toLowerCase().includes(q))
        .sort((a, b) =>
            (b.ready - a.ready) ||
            (a.typeIdx - b.typeIdx) ||
            (b.level - a.level) ||
            (NATION_ORDER.indexOf(a.nation) - NATION_ORDER.indexOf(b.nation)) ||
            a.name.localeCompare(b.name));
}

// --- rendering ------------------------------------------------------------------

function renderHeader() {
    const levels = [...new Set(data.vehicles.map((v) => v.level))].sort((a, b) => a - b).map((l) => ROMAN[l] || l);
    return `
    <div class="header">
        <div class="header-bar"></div>
        <div class="header-title">${esc(data.title || "Fahrzeug wählen")}</div>
        <div class="header-sub">Stufe ${esc(levels.join(", ") || "-")} · ${data.vehicles.length} Fahrzeuge in der Garage</div>
        ${data.dev ? `<div class="dev-badge">DEV ${esc(data.version || "")} · F5 = neu laden</div>` : ""}
        <div class="header-spacer"></div>
        <div class="close-btn" data-act="close"><div class="close-x a"></div><div class="close-x b"></div></div>
    </div>`;
}

function renderFilters(count) {
    const nations = NATION_ORDER.filter((n) => data.vehicles.some((v) => v.nation === n));
    const types = TYPE_ORDER.filter((t) => data.vehicles.some((v) => v.type === t));
    return `
    <div class="filters">
        <div class="fgroup">
            ${nations.map((n) => `<div class="toggle ${ui.nations.has(n) ? "on" : ""}" data-nation="${n}"><div class="img flag" ${bg(flagUrl(n))}></div></div>`).join("")}
        </div>
        <div class="fgroup">
            ${types.map((t) => `<div class="toggle ${ui.types.has(t) ? "on" : ""}" data-type="${t}" title="${esc(TYPE_NAMES[t])}"><div class="img typeicon" ${bg(typeUrl(t))}></div></div>`).join("")}
        </div>
        ${renderPlaylists()}
        <div class="fgroup">
            <div class="toggle ${ui.readyOnly ? "on" : ""}" data-ready="1">Nur einsatzbereit</div>
            ${ui.nations.size || ui.types.size || ui.readyOnly || ui.search || ui.playlist ? `<div class="toggle" data-reset="1">Filter zurücksetzen</div>` : ""}
        </div>
        <div class="fgroup">
            <div class="search-wrap ${ui.search ? "has-text" : ""}" id="searchWrap"><input class="search" id="search" type="text" value="${esc(ui.search)}" /><div class="search-ph">Suchen…</div></div>
            <div class="count">${count} / ${data.vehicles.length}</div>
        </div>
    </div>`;
}

function renderPlaylists() {
    const lists = data.playlists || [];
    if (!lists.length) return "";
    const chips = lists.map((p) => {
        const n = data.vehicles.filter((v) => p.cds.indexOf(v.cd) !== -1).length;
        return `<div class="toggle pl ${ui.playlist === p.id ? "on" : ""} ${n ? "" : "empty"}" data-playlist="${esc(p.id)}">
            <span class="pl-icon">≡</span>${esc(p.title)}<span class="pl-count">${n}</span></div>`;
    }).join("");
    return `<div class="fgroup playlists">${chips}</div>`;
}

function renderCard(v) {
    const sel = v.cd === data.selected;
    return `
    <div class="card ${sel ? "sel" : ""} ${v.ready ? "" : "dim"}" data-cd="${v.cd}">
        <div class="tank" ${bg(v.icon)}></div>
        <div class="flag" ${bg(flagUrl(v.nation))}></div>
        <div class="typeicon" ${bg(typeUrl(v.type))}></div>
        <div class="tier">${ROMAN[v.level] || v.level}</div>
        <div class="name ${v.premium ? "premium" : ""}">${esc(v.name)}</div>
        ${v.ready ? `<div class="badge ok">Einsatzbereit</div>` : `<div class="badge bad">${esc(v.state)}</div>`}
    </div>`;
}

function renderGrid(list) {
    if (!list.length) {
        return `<div class="empty">Keine Fahrzeuge für diese Filter.</div>`;
    }
    return `<div class="grid-inner">${list.map(renderCard).join("")}</div>`;
}

function renderMember(m, d) {
    const t = m.tankman;
    const open = ui.openSlot === m.slot;
    let who;
    if (t) {
        const info = t.native ? (t.skills ? `${t.skills} Fertigkeit${t.skills === 1 ? "" : "en"}` : "ausgebildet") : `nicht ausgebildet · Stammfahrzeug ${esc(t.nativeName)}`;
        who = `<div class="n">${esc(t.name)}</div><div class="d ${t.native ? "" : "warn"}">${info}</div>`;
    } else {
        who = `<div class="n warn">Kein Besatzungsmitglied</div><div class="d">Klicken zum Zuweisen</div>`;
    }
    const eff = t && t.eff != null ? `${t.eff}%` : "";
    let html = `
    <div class="member ${open ? "open" : ""} ${t ? "" : "missing"}" data-slot="${m.slot}">
        <div class="role">${esc(m.roleName)}</div>
        <div class="who">${who}</div>
        <div class="eff">${eff}</div>
        <div class="chev">${open ? "▴" : "▾"}</div>
    </div>`;
    if (open) {
        const rows = m.candidates.map((c) => {
            const tag = c.native ? `<div class="tag native">ausgebildet</div>` : `<div class="tag other">${esc(c.nativeName)}</div>`;
            const where = c.where ? `in ${esc(c.where)}` : "Kaserne";
            return `<div class="pick-row" data-equip="${c.id}" data-slot="${m.slot}">
                <div class="n">${esc(c.name)}</div>${tag}<div class="d">${where}${c.skills ? ` · ${c.skills} Fert.` : ""}</div>
            </div>`;
        });
        if (t) {
            rows.push(`<div class="pick-row remove" data-unload="${m.slot}"><div class="n">In die Kaserne schicken</div></div>`);
        }
        if (!m.candidates.length) {
            rows.unshift(`<div class="pick-row"><div class="n muted">Keine passenden ${esc(m.roleName)} dieser Nation verfügbar</div></div>`);
        }
        html += `<div class="pick" data-scroll="70">${rows.join("")}</div>`;
    }
    return html;
}

function fmt(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function currencyName(c) {
    return c === "gold" ? "Gold" : c === "crystal" ? "Anleihen" : "Credits";
}

function ammoCounts(d) {
    const counts = {};
    d.shells.forEach((s) => { counts[s.cd] = ui.ammo && ui.ammo[s.cd] != null ? ui.ammo[s.cd] : s.count; });
    return counts;
}

function ammoChanged(d) {
    return !!ui.ammo && d.shells.some((s) => ui.ammo[s.cd] != null && ui.ammo[s.cd] !== s.count);
}

function ammoCost(d, counts) {
    const cost = {};
    d.shells.forEach((s) => {
        const buy = Math.max(0, counts[s.cd] - s.count - s.depot);
        if (buy > 0) cost[s.currency] = (cost[s.currency] || 0) + buy * s.price;
    });
    return cost;
}

function renderAmmo(d) {
    const counts = ammoCounts(d);
    const total = d.shells.reduce((sum, s) => sum + counts[s.cd], 0);
    const full = total >= d.ammoMax;
    const changed = ammoChanged(d);
    const cost = ammoCost(d, counts);
    const costText = Object.keys(cost).map((c) => `${fmt(cost[c])} ${currencyName(c)}`).join(" + ");
    const rows = d.shells.map((s) => {
        const n = counts[s.cd];
        const diff = n - s.count;
        const buy = Math.max(0, n - s.count - s.depot);
        const reach = n + Math.max(0, d.ammoMax - total); // highest value this shell can take
        const pct = (v) => (d.ammoMax ? (100 * v / d.ammoMax) : 0).toFixed(2);
        return `
        <div class="shell ${diff ? "changed" : ""}">
            <div class="shell-top">
                <div class="shell-ico" ${bg(s.icon)}></div>
                <div class="shell-info">
                    <div class="shell-name"><div class="abbr ${s.premium ? "prem" : ""}">${esc(s.abbr)}</div><div class="shell-title">${esc(s.name)}</div></div>
                    <div class="shell-stats">Durchschlag ${s.pen} · Schaden ${s.damage} · Lager ${s.depot}${buy ? ` · <span class="accent">${buy} kaufen</span>` : ""}</div>
                </div>
                <div class="shell-val">${n}${diff ? `<span class="shell-diff">${diff > 0 ? "+" : ""}${diff}</span>` : ""}</div>
            </div>
            <div class="slider-row">
                <div class="step ${n <= 0 ? "off" : ""}" data-ammo="${s.cd}" data-delta="-1">-</div>
                <div class="slider" data-slider="${s.cd}">
                    <div class="slider-track"></div>
                    <div class="slider-reach" style="width: ${pct(reach)}%;"></div>
                    <div class="slider-fill" style="width: ${pct(n)}%;"></div>
                    <div class="slider-thumb" style="left: ${pct(n)}%;"></div>
                </div>
                <div class="step ${full ? "off" : ""}" data-ammo="${s.cd}" data-delta="1">+</div>
            </div>
        </div>`;
    }).join("");
    return `
    <div class="section">
        <div class="section-title"><div class="grow">Munition</div><div class="${total < d.ammoMax ? "warn" : "muted"}">${total} / ${d.ammoMax}</div></div>
        ${rows}
        <div class="ammo-tools">
            <div class="btn small ${full ? "off" : ""}" data-ammo-fill="1">Auffüllen</div>
            ${changed ? `<div class="btn small" data-ammo-reset="1">Zurücksetzen</div>` : ""}
            <div class="grow"></div>
            ${costText ? `<div class="ammo-cost">Kosten: <span class="accent">${costText}</span></div>` : changed ? `<div class="ammo-cost muted">Aus dem Lager, kostenlos</div>` : ""}
        </div>
        ${changed ? `<div class="apply" data-ammo-apply="1">Munition übernehmen${costText ? ` · ${costText}` : ""}</div>` : ""}
    </div>`;
}

function renderSideOnly() {
    const side = document.querySelector(".side");
    if (!side) return render();
    const scroll = document.getElementById("sideScroll");
    const top = scroll ? scroll.scrollTop : 0;
    const tmp = document.createElement("div");
    tmp.innerHTML = renderSide();
    side.parentNode.replaceChild(tmp.children[0], side);
    const next = document.getElementById("sideScroll");
    if (next) next.scrollTop = top;
}

function setAmmo(cd, value) {
    const d = data.detail;
    if (!d) return;
    const counts = ammoCounts(d);
    const others = d.shells.reduce((sum, s) => sum + (s.cd === cd ? 0 : counts[s.cd]), 0);
    const next = Math.max(0, Math.min(Math.round(value), d.ammoMax - others));
    if (next === counts[cd]) return;
    ui.ammo = Object.assign({}, counts, { [cd]: next });
    renderSideOnly();
}

let drag = null; // {cd, left, width}

function sliderValue(x) {
    const d = data.detail;
    const ratio = Math.max(0, Math.min(1, (x - drag.left) / drag.width));
    return ratio * d.ammoMax;
}

root.addEventListener("mousedown", (e) => {
    const el = closest(e.target, "data-slider");
    if (!el || !data.detail) return;
    const r = el.getBoundingClientRect();
    drag = { cd: Number(el.getAttribute("data-slider")), left: r.left, width: r.width || 1 };
    setAmmo(drag.cd, sliderValue(e.clientX));
    e.preventDefault();
});

document.addEventListener("mousemove", (e) => {
    if (drag) setAmmo(drag.cd, sliderValue(e.clientX));
});

document.addEventListener("mouseup", () => {
    drag = null;
});

function changeAmmo(cd, delta) {
    const d = data.detail;
    if (!d) return;
    const counts = ammoCounts(d);
    const total = d.shells.reduce((sum, s) => sum + counts[s.cd], 0);
    let next = counts[cd] + delta;
    if (delta > 0) next = counts[cd] + Math.min(delta, d.ammoMax - total);
    next = Math.max(0, next);
    ui.ammo = Object.assign({}, counts, { [cd]: next });
    renderSideOnly();
}

function fillAmmo() {
    const d = data.detail;
    if (!d || !d.shells.length) return;
    const counts = ammoCounts(d);
    const total = d.shells.reduce((sum, s) => sum + counts[s.cd], 0);
    // remaining space goes to the first (standard) shell
    counts[d.shells[0].cd] += Math.max(0, d.ammoMax - total);
    ui.ammo = counts;
    render();
}

function applyAmmo() {
    const d = data.detail;
    if (!d || !ammoChanged(d)) return;
    const counts = ammoCounts(d);
    send({ action: "setAmmo", counts: Object.keys(counts).map((cd) => `${cd}:${counts[cd]}`).join(",") });
    ui.ammo = null;
    render();
}

function itemTag(it) {
    if (it.deluxe) return `<span class="itag deluxe">Deluxe</span>`;
    if (it.modernized) return `<span class="itag trophy">Experimentell</span>`;
    if (it.trophy) return `<span class="itag trophy">Trophäe</span>`;
    return "";
}

function catDots(cats) {
    return (cats || []).filter((c) => CAT_NAMES[c]).map((c) => `<span class="cat cat-${c}" title="${CAT_NAMES[c]}"></span>`).join("");
}

function catBonus(item, slotCats) {
    return !!item && (slotCats || []).some((c) => (item.cats || []).includes(c));
}

function renderPickList(kind, slot, current, candidates, slotCats, emptyText) {
    const rows = candidates.map((c) => `
        <div class="pick-row" data-set${kind}="${c.cd}" data-pslot="${slot}">
            <div class="pick-ico" ${bg(c.icon)}></div>
            <div class="n">${esc(c.name)}</div>${catDots(c.cats)}${catBonus(c, slotCats) ? `<div class="tag native">Bonus</div>` : ""}${itemTag(c)}
            <div class="d">×${c.depot} im Lager</div>
        </div>`);
    if (!candidates.length) {
        rows.push(`<div class="pick-row"><div class="n muted">${emptyText}</div></div>`);
    }
    let note = "";
    if (current) {
        const free = kind === "cons" || current.freeDemount;
        const how = !free ? "kostet Gold oder Demontageset" : current.wotPlusFree ? "kostenlos mit WoT Plus" : "kostenlos, zurück ins Lager";
        rows.push(`<div class="pick-row remove" data-set${kind}="0" data-pslot="${slot}"><div class="n">${esc(current.name)} ausbauen</div><div class="d">${how}</div></div>`);
        if (!free) {
            note = `<div class="pick-note">${esc(current.name)} ist nicht kostenlos ausbaubar. Beim Tauschen zeigt WG vorher den Preis (Gold / Demontageset).</div>`;
        }
    }
    return `<div class="pick" data-scroll="70">${note}${rows.join("")}</div>`;
}

function renderAutoEquip(d) {
    const ae = d.autoEquip;
    if (!ae) return "";
    let state;
    if (ae.busy) state = `<span class="accent">baut gerade ein…</span>`;
    else if (!ae.hasSets) state = `<span class="muted">keine Sets gespeichert</span>`;
    else if (!ae.enabled) state = `<span class="muted">Sets gespeichert · Automatik aus</span>`;
    else state = `<span class="ok-text">Sets gespeichert · Automatik an</span>`;
    return `
    <div class="section">
        <div class="section-title"><div class="grow">Auto-Equip</div>${ae.hasSets && !ae.busy ? `<div class="btn small" data-act="autoEquipApply">Sets jetzt einbauen</div>` : ""}</div>
        <div class="ae-state">${state}</div>
    </div>`;
}

function renderDevices(d) {
    const cards = d.devices.map((s) => {
        const it = s.item;
        const open = ui.openDev === s.slot;
        const stripe = (s.slotCats || []).filter((c) => CAT_NAMES[c]).map((c) => `<div class="stripe cat-${c}"></div>`).join("");
        return `
        <div class="slot dev ${it ? "" : "free"} ${open ? "open" : ""}" data-dev="${s.slot}">
            <div class="stripes">${stripe}</div>
            <div class="ico" ${it ? bg(it.icon) : ""}></div>
            <div class="t">${it ? esc(it.name) : "leer"}</div>
            <div class="slot-tags">${it ? itemTag(it) : ""}${catBonus(it, s.slotCats) ? `<span class="itag bonus">Bonus</span>` : ""}</div>
        </div>`;
    }).join("");
    const openSlot = d.devices.find((s) => s.slot === ui.openDev);
    const ds = d.deviceSetups;
    let setupHead = "";
    let otherSetup = "";
    if (ds) {
        const other = ds.active === 0 ? 1 : 0;
        setupHead = `<div class="setup-head"><span class="setup-tag on">Set ${ds.active + 1} · aktiv</span><span class="muted">bearbeitbar</span></div>`;
        const items = (ds.sets[other] || []).map((it) => `
            <div class="slot mini ${it ? "" : "free"}">
                <div class="ico" ${it ? bg(it.icon) : ""}></div>
                <div class="t">${it ? esc(it.name) : "leer"}</div>
            </div>`).join("");
        otherSetup = `
        <div class="setup-head"><span class="setup-tag">Set ${other + 1}</span><div class="grow"></div><div class="btn small" data-setup="${other}">Set ${other + 1} aktivieren</div></div>
        <div class="slots">${items}</div>`;
    }
    return `
    <div class="section">
        <div class="section-title"><div class="grow">Ausrüstung${ds ? " · 2 Sets" : ""}</div><div class="muted">nur aus dem Lager</div></div>
        ${setupHead}
        <div class="slots">${cards}</div>
        ${openSlot ? renderPickList("dev", openSlot.slot, openSlot.item, openSlot.candidates, openSlot.slotCats, "Keine passende Ausrüstung im Lager") : ""}
        ${otherSetup}
    </div>`;
}

function renderConsumables(d) {
    const cards = d.consumables.map((s) => {
        const it = s.item;
        const open = ui.openCons === s.slot;
        return `
        <div class="slot cons ${it ? "" : "free"} ${open ? "open" : ""}" data-cons="${s.slot}">
            <div class="ico" ${it ? bg(it.icon) : ""}></div>
            <div class="t">${it ? esc(it.name) : "leer"}</div>
        </div>`;
    }).join("");
    const openSlot = d.consumables.find((s) => s.slot === ui.openCons);
    return `
    <div class="section">
        <div class="section-title"><div class="grow">Verbrauchsmaterial</div><div class="muted">nur aus dem Lager</div></div>
        <div class="slots">${cards}</div>
        ${openSlot ? renderPickList("cons", openSlot.slot, openSlot.item, openSlot.candidates, [], "Kein passendes Verbrauchsmaterial im Lager") : ""}
    </div>`;
}

function renderSide() {
    const d = data.detail;
    if (!d) {
        return `
        <div class="side">
            <div class="side-scroll" data-scroll="120"><div class="side-hint">Wähle links ein Fahrzeug aus.<br/><br/>Danach kannst du hier Besatzung, Munition und Ausrüstung prüfen und das Fahrzeug einloggen.</div></div>
            <div class="side-foot"><div class="lock off">Einloggen</div></div>
        </div>`;
    }
    const pendingAmmo = ammoChanged(d);
    const aeBusy = !!(d.autoEquip && d.autoEquip.busy);
    const missing = d.crew.filter((m) => !m.tankman).length;
    return `
    <div class="side">
        <div class="side-scroll" id="sideScroll" data-scroll="120">
            <div class="veh-name">${esc(d.name)}</div>
            <div class="veh-sub">Stufe ${ROMAN[d.level] || d.level} · ${esc(TYPE_NAMES[d.type] || d.type)}</div>
            ${d.ready ? `<div class="state ok">Einsatzbereit</div>` : `<div class="state bad">${esc(d.state)}</div>`}

            <div class="section">
                <div class="section-title"><div class="grow">Besatzung${missing ? ` · <span class="warn">${missing} fehlt</span>` : ""}</div>
                    ${d.canReturnCrew && !d.crewLocked ? `<div class="btn small" data-act="returnCrew">Zurückholen</div>` : ""}
                    <div class="btn small switch ${ui.autoCrew ? "on" : ""}" data-autocrew="1">Letzte Besatzung automatisch: ${ui.autoCrew ? "an" : "aus"}</div>
                </div>
                ${d.crewLocked ? `<div class="muted" style="margin-bottom: 8rem;">Besatzung ist gerade gesperrt (Fahrzeug im Zug/Gefecht).</div>` : ""}
                ${d.crew.map((m) => renderMember(m, d)).join("")}
            </div>

            ${renderAmmo(d)}

            ${renderAutoEquip(d)}
            ${renderDevices(d)}
            ${renderConsumables(d)}
        </div>
        <div class="side-foot">
            <div class="lock ${d.ready && !pendingAmmo && !aeBusy ? "" : "off"}" data-act="lock">Einloggen</div>
            <div class="foot-note">${aeBusy ? "Auto-Equip baut gerade die Ausrüstung ein…" : pendingAmmo ? "Erst die Munitionsänderung übernehmen oder zurücksetzen" : d.ready ? "Setzt das Fahrzeug in deinen Slot" : esc(d.state)}</div>
        </div>
    </div>`;
}

function render() {
    const grid = document.querySelector(".grid");
    const side = document.getElementById("sideScroll");
    const gridScroll = grid ? grid.scrollTop : 0;
    const sideScroll = side ? side.scrollTop : 0;
    const hadFocus = document.activeElement && document.activeElement.id === "search";

    const list = filtered();
    root.innerHTML = `
        ${renderHeader()}
        <div class="main">
            <div class="left">
                ${renderFilters(list.length)}
                <div class="grid" data-scroll="160">${renderGrid(list)}</div>
            </div>
            ${renderSide()}
        </div>`;

    const newGrid = document.querySelector(".grid");
    if (newGrid) newGrid.scrollTop = gridScroll;
    const newSide = document.getElementById("sideScroll");
    if (newSide) newSide.scrollTop = sideScroll;
    const search = document.getElementById("search");
    if (search) {
        search.addEventListener("input", onSearch);
        if (hadFocus) {
            search.focus();
            const n = search.value.length;
            try { search.setSelectionRange(n, n); } catch (e) { /* not supported */ }
        }
    }
}

// --- events ---------------------------------------------------------------------

function onSearch(e) {
    ui.search = e.target.value || "";
    const wrap = document.getElementById("searchWrap");
    if (wrap) wrap.className = `search-wrap ${ui.search ? "has-text" : ""}`;
    // only the grid depends on the search text; keep the input element alive
    const list = filtered();
    document.querySelector(".grid").innerHTML = renderGrid(list);
    const count = document.querySelector(".count");
    if (count) count.textContent = `${list.length} / ${data.vehicles.length}`;
}

function closest(el, attr) {
    while (el && el !== root) {
        if (el.hasAttribute && el.hasAttribute(attr)) return el;
        el = el.parentNode;
    }
    return null;
}

root.addEventListener("click", (e) => {
    let el;
    if ((el = closest(e.target, "data-nation"))) {
        const n = el.getAttribute("data-nation");
        ui.nations.has(n) ? ui.nations.delete(n) : ui.nations.add(n);
        render();
        saveFilters();
    } else if ((el = closest(e.target, "data-type"))) {
        const t = el.getAttribute("data-type");
        ui.types.has(t) ? ui.types.delete(t) : ui.types.add(t);
        render();
        saveFilters();
    } else if (closest(e.target, "data-autocrew")) {
        ui.autoCrew = !ui.autoCrew;
        saveFilters();
        render();
    } else if ((el = closest(e.target, "data-playlist"))) {
        const id = el.getAttribute("data-playlist");
        ui.playlist = ui.playlist === id ? "" : id;
        render();
        saveFilters();
    } else if (closest(e.target, "data-ready")) {
        ui.readyOnly = !ui.readyOnly;
        render();
        saveFilters();
    } else if (closest(e.target, "data-reset")) {
        ui.nations.clear();
        ui.types.clear();
        ui.readyOnly = false;
        ui.playlist = "";
        ui.search = "";
        render();
        saveFilters();
    } else if ((el = closest(e.target, "data-cd"))) {
        const cd = Number(el.getAttribute("data-cd"));
        if (cd !== data.selected) {
            ui.openSlot = -1;
            ui.openDev = -1;
            ui.openCons = -1;
            ui.ammo = null;
            data.selected = cd; // instant highlight, Python sends the details
            render();
            send({ action: "select", cd: cd });
        }
    } else if ((el = closest(e.target, "data-setup"))) {
        ui.openDev = -1;
        send({ action: "switchSetup", idx: Number(el.getAttribute("data-setup")) });
        render();
    } else if ((el = closest(e.target, "data-setdev"))) {
        ui.openDev = -1;
        send({ action: "setDevice", slot: Number(el.getAttribute("data-pslot")), cd: Number(el.getAttribute("data-setdev")) });
        render();
    } else if ((el = closest(e.target, "data-setcons"))) {
        ui.openCons = -1;
        send({ action: "setConsumable", slot: Number(el.getAttribute("data-pslot")), cd: Number(el.getAttribute("data-setcons")) });
        render();
    } else if ((el = closest(e.target, "data-dev"))) {
        const slot = Number(el.getAttribute("data-dev"));
        ui.openDev = ui.openDev === slot ? -1 : slot;
        ui.openCons = -1;
        ui.openSlot = -1;
        render();
    } else if ((el = closest(e.target, "data-cons"))) {
        const slot = Number(el.getAttribute("data-cons"));
        ui.openCons = ui.openCons === slot ? -1 : slot;
        ui.openDev = -1;
        ui.openSlot = -1;
        render();
    } else if ((el = closest(e.target, "data-ammo"))) {
        changeAmmo(Number(el.getAttribute("data-ammo")), Number(el.getAttribute("data-delta")));
    } else if (closest(e.target, "data-ammo-fill")) {
        fillAmmo();
    } else if (closest(e.target, "data-ammo-reset")) {
        ui.ammo = null;
        render();
    } else if (closest(e.target, "data-ammo-apply")) {
        applyAmmo();
    } else if ((el = closest(e.target, "data-equip"))) {
        ui.openSlot = -1;
        send({ action: "equip", tankman: Number(el.getAttribute("data-equip")), slot: Number(el.getAttribute("data-slot")) });
        render();
    } else if ((el = closest(e.target, "data-unload"))) {
        ui.openSlot = -1;
        send({ action: "unload", slot: Number(el.getAttribute("data-unload")) });
        render();
    } else if ((el = closest(e.target, "data-slot"))) {
        if (data.detail && data.detail.crewLocked) return;
        const slot = Number(el.getAttribute("data-slot"));
        ui.openSlot = ui.openSlot === slot ? -1 : slot;
        render();
    } else if ((el = closest(e.target, "data-act"))) {
        const act = el.getAttribute("data-act");
        if (act === "lock" && !(data.detail && data.detail.ready && !ammoChanged(data.detail) && !(data.detail.autoEquip && data.detail.autoEquip.busy))) return;
        send({ action: act });
    }
});

root.addEventListener("dblclick", (e) => {
    const el = closest(e.target, "data-cd");
    if (!el) return;
    const v = data.vehicles.find((x) => x.cd === Number(el.getAttribute("data-cd")));
    if (v && v.ready && v.cd === data.selected) send({ action: "lock" });
});

// Gameface's native wheel scrolling is inverted and slow; scroll like WG's own
// components do: direction from deltaY, fixed step per notch, short ease.
const scrollAnim = new Map();

function animateScroll(el, target) {
    const max = Math.max(0, el.scrollHeight - el.clientHeight);
    target = Math.max(0, Math.min(max, target));
    scrollAnim.set(el, target);
    const step = () => {
        if (scrollAnim.get(el) !== target || !el.parentNode) return;
        const cur = el.scrollTop;
        const diff = target - cur;
        if (Math.abs(diff) < 1) {
            el.scrollTop = target;
            scrollAnim.delete(el);
            return;
        }
        el.scrollTop = cur + diff * 0.35;
        requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}

document.addEventListener("wheel", (e) => {
    const el = closest(e.target, "data-scroll");
    if (!el || e.deltaY === 0) return;
    e.preventDefault();
    e.stopPropagation();
    const stepPx = Number(el.getAttribute("data-scroll")) || 100;
    const base = scrollAnim.has(el) ? scrollAnim.get(el) : el.scrollTop;
    animateScroll(el, base + (e.deltaY > 0 ? -stepPx : stepPx)); // Gameface: deltaY > 0 = wheel up
}, { capture: true, passive: false });

document.addEventListener("keydown", (e) => {
    if (e.keyCode === 116 && data.dev) {
        send({ action: "devReload" });
        return;
    }
    if (e.keyCode === 27) {
        if (ui.openSlot !== -1 || ui.openDev !== -1 || ui.openCons !== -1) {
            ui.openSlot = ui.openDev = ui.openCons = -1;
            render();
        } else {
            send({ action: "close" });
        }
    }
});

// --- model binding --------------------------------------------------------------

function readModel() {
    try {
        const raw = window.model && window.model.data;
        if (!raw) return;
        const next = JSON.parse(raw);
        if (!filtersLoaded) {
            filtersLoaded = true;
            applySavedFilters(next.filters);
        }
        if (ui.playlist && !(next.playlists || []).some((p) => p.id === ui.playlist)) ui.playlist = "";
        if (!next.detail || !data.detail || next.detail.cd !== data.detail.cd) ui.ammo = null;
        data = next;
        render();
    } catch (e) {
        console.error("advances_picker: bad model data", e);
    }
}

engine.whenReady.then(() => {
    engine.on("viewEnv.onDataChanged", readModel);
    viewEnv.addDataChangedCallback("model", 0, true);
    readModel();
});

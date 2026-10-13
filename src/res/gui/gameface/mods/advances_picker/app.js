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
    search: "",
    openSlot: -1,
};
let data = { vehicles: [], detail: null, selected: 0 };

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

function filtered() {
    const q = ui.search.trim().toLowerCase();
    return data.vehicles
        .filter((v) => !ui.nations.size || ui.nations.has(v.nation))
        .filter((v) => !ui.types.size || ui.types.has(v.type))
        .filter((v) => !ui.readyOnly || v.ready)
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
        <div class="header-spacer"></div>
        <div class="close-btn" data-act="close">×</div>
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
        <div class="fgroup">
            <div class="toggle ${ui.readyOnly ? "on" : ""}" data-ready="1">Nur einsatzbereit</div>
            ${ui.nations.size || ui.types.size || ui.readyOnly || ui.search ? `<div class="toggle" data-reset="1">Filter zurücksetzen</div>` : ""}
        </div>
        <div class="fgroup">
            <input class="search" id="search" type="text" placeholder="Suchen…" value="${esc(ui.search)}" />
            <div class="count">${count} / ${data.vehicles.length}</div>
        </div>
    </div>`;
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

function renderSlots(items, total, label) {
    const out = [];
    for (let i = 0; i < total; i++) {
        const it = items[i];
        if (it) {
            out.push(`<div class="slot"><div class="ico" ${bg(it.icon)}></div><div class="t">${esc(it.name)}</div></div>`);
        } else {
            out.push(`<div class="slot free"><div class="ico"></div><div class="t">${label}</div></div>`);
        }
    }
    return `<div class="slots">${out.join("")}</div>`;
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
    const ammoTotal = d.shells.reduce((s, x) => s + x.count, 0);
    const missing = d.crew.filter((m) => !m.tankman).length;
    return `
    <div class="side">
        <div class="side-scroll" id="sideScroll" data-scroll="120">
            <div class="hero" ${bg(d.image)}></div>
            <div class="veh-name">${esc(d.name)}</div>
            <div class="veh-sub">Stufe ${ROMAN[d.level] || d.level} · ${esc(TYPE_NAMES[d.type] || d.type)}</div>
            ${d.ready ? `<div class="state ok">Einsatzbereit</div>` : `<div class="state bad">${esc(d.state)}</div>`}

            <div class="section">
                <div class="section-title"><div class="grow">Besatzung${missing ? ` · <span class="warn">${missing} fehlt</span>` : ""}</div>
                    ${d.canReturnCrew && !d.crewLocked ? `<div class="btn small" data-act="returnCrew">Vorherige Besatzung zurückholen</div>` : ""}
                </div>
                ${d.crewLocked ? `<div class="muted" style="margin-bottom: 8rem;">Besatzung ist gerade gesperrt (Fahrzeug im Zug/Gefecht).</div>` : ""}
                ${d.crew.map((m) => renderMember(m, d)).join("")}
            </div>

            <div class="section">
                <div class="section-title"><div class="grow">Munition</div><div class="${ammoTotal < d.ammoMax ? "warn" : "muted"}">${ammoTotal} / ${d.ammoMax}</div></div>
                <div class="slots">
                    ${d.shells.map((s) => `<div class="slot"><div class="ico" ${bg(s.icon)}></div><div class="cnt">${s.count}</div><div class="t">${esc(s.name)}</div></div>`).join("")}
                </div>
            </div>

            <div class="section">
                <div class="section-title"><div class="grow">Ausrüstung</div></div>
                ${renderSlots(d.devices, d.devices.length, "leer")}
            </div>

            <div class="section">
                <div class="section-title"><div class="grow">Verbrauchsmaterial</div></div>
                ${renderSlots(d.consumables, d.consumables.length, "leer")}
            </div>
        </div>
        <div class="side-foot">
            <div class="lock ${d.ready ? "" : "off"}" data-act="lock">Einloggen</div>
            <div class="foot-note">${d.ready ? "Setzt das Fahrzeug in deinen Slot" : esc(d.state)}</div>
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
    } else if ((el = closest(e.target, "data-type"))) {
        const t = el.getAttribute("data-type");
        ui.types.has(t) ? ui.types.delete(t) : ui.types.add(t);
        render();
    } else if (closest(e.target, "data-ready")) {
        ui.readyOnly = !ui.readyOnly;
        render();
    } else if (closest(e.target, "data-reset")) {
        ui.nations.clear();
        ui.types.clear();
        ui.readyOnly = false;
        ui.search = "";
        render();
    } else if ((el = closest(e.target, "data-cd"))) {
        const cd = Number(el.getAttribute("data-cd"));
        if (cd !== data.selected) {
            ui.openSlot = -1;
            data.selected = cd; // instant highlight, Python sends the details
            render();
            send({ action: "select", cd: cd });
        }
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
        if (act === "lock" && !(data.detail && data.detail.ready)) return;
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
    animateScroll(el, base + (e.deltaY > 0 ? stepPx : -stepPx));
}, { capture: true, passive: false });

document.addEventListener("keydown", (e) => {
    if (e.keyCode === 27) {
        if (ui.openSlot !== -1) {
            ui.openSlot = -1;
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

// Starts the picker UI. Normally loads the packaged style.css + app.js; in dev mode the
// Python side passes fresh CSS/JS from the project folder in model.dev (no game restart).
function loadPackaged() {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "style.css";
    document.head.appendChild(link);
    const script = document.createElement("script");
    script.type = "module";
    script.src = "app.js";
    document.body.appendChild(script);
}

engine.whenReady.then(() => {
    let dev = null;
    try {
        dev = window.model && window.model.dev ? JSON.parse(window.model.dev) : null;
    } catch (e) {
        console.error("advances_picker: bad dev payload", e);
    }
    if (!dev || !dev.js) {
        loadPackaged();
        return;
    }
    const style = document.createElement("style");
    style.textContent = dev.css || "";
    document.head.appendChild(style);
    try {
        new Function(dev.js)();
    } catch (e) {
        console.error("advances_picker: dev app.js failed", e);
        document.getElementById("root").textContent = "DEV: app.js Fehler: " + e;
    }
});

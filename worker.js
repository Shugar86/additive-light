// worker.js - OpenSCAD Rendering Worker (Resilient v2)

self.importScripts('./openscad.min.js');

let instance = null;
let lastErrors = [];

async function init() {
    try {
        const factory = self.OpenSCAD || window.OpenSCAD; 
        if (!factory) throw new Error("OpenSCAD factory not found");

        instance = await factory({
            noInitialRun: true,
            print: (text) => self.postMessage({ type: 'log', message: text }),
            printErr: (text) => {
                console.warn("[Worker Log]", text);
                // Фильтруем информационные сообщения
                const ignoredPatterns = [
                    'Total rendering time', 'Geometries in cache', 'Geometry cache size',
                    'CGAL Cache', 'PolySets in cache', 'Top level object',
                    'Compiling design', 'Rendering Polygon Mesh', 'Number of'
                ];
                const isIgnored = ignoredPatterns.some(p => text.includes(p));
                if (!isIgnored) {
                    lastErrors.push(text);
                }
            },
            locateFile: (path, prefix) => {
                if (path.endsWith('.wasm')) return './openscad.wasm';
                return prefix + path;
            }
        });
        self.postMessage({ type: 'ready' });
    } catch (e) {
        self.postMessage({ type: 'error', message: `Init failed: ${e.message}` });
    }
}

self.onmessage = async (e) => {
    const { command, code } = e.data;

    if (command === 'init') {
        await init();
    } else if (command === 'render') {
        if (!instance) {
            self.postMessage({ type: 'error', message: 'Worker not ready' });
            return;
        }

        try {
            self.postMessage({ type: 'log', message: 'Starting render...' });
            lastErrors = [];
            
            // Чистим старые файлы перед новым рендером
            try { instance.FS.unlink('/input.scad'); } catch(e){}
            try { instance.FS.unlink('output.stl'); } catch(e){}
            
            instance.FS.writeFile('/input.scad', code);
            
            // Запускаем рендеринг
            instance.callMain(['/input.scad', '-o', 'output.stl']);

            // Проверяем результат
            let output;
            try {
                // Проверяем существование файла
                const stat = instance.FS.stat('output.stl');
                if (stat.size === 0) {
                    throw new Error("Output file is empty");
                }
                output = instance.FS.readFile('output.stl');
            } catch (fsErr) {
                const errorMsg = lastErrors.length > 0 
                    ? lastErrors.join('\n') 
                    : fsErr.message || "Unknown render error";
                self.postMessage({ type: 'error', message: "Render Failed:\n" + errorMsg });
                return;
            }

            if (output && output.length > 0) {
                // ВАЖНО: Создаем КОПИЮ буфера перед передачей
                // чтобы избежать проблем с detached buffer при повторных рендерах
                const copy = new Uint8Array(output);
                self.postMessage({ type: 'stl', blob: copy }, [copy.buffer]);
            } else {
                self.postMessage({ type: 'error', message: "Empty STL output" });
            }

            // Чистка после успешного рендера
            try { instance.FS.unlink('/input.scad'); } catch(e){}
            try { instance.FS.unlink('output.stl'); } catch(e){}

        } catch (err) {
            const msg = err && err.message ? err.message : String(err);
            self.postMessage({ type: 'error', message: `Worker Error: ${msg}` });
        }
    }
};

init();

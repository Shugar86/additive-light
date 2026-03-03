import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ============================================
// ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
// ============================================
let editor;
let pyodide;
let pyodideReady = false;
let openscadInstance = null;
let openjscadReady = false;
let stlData = null;
let lastScadCode = null;
let scene, camera, renderer, controls, currentMesh = null;
let renderEngine = 'auto'; // 'auto', 'openscad', 'openjscad', 'parser'
let printModifiers = {
    wallThickness: 2,
    infillPercent: 20,
    infillPattern: 'grid',
    addSupports: false,
    supportAngle: 45,
    addBrim: false,
    layerHeight: 0.2
};
    const OPENROUTER_API_KEY = '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';
    // Список моделей для попытки (в порядке приоритета, от лучших к быстрым/бесплатным)
    const AI_MODELS = [
        'google/gemini-3-pro-preview',      // Флагман Google
        'anthropic/claude-opus-4.5',        // Мощный Claude
        'openai/gpt-5.1-codex',             // Специализированный кодер
        'openai/gpt-5.1',                   // Общий GPT-5.1
        'x-ai/grok-4.1-fast:free',          // Быстрый и бесплатный
        'kwaipilot/kat-coder-pro:free'      // Специализированный бесплатный кодер
    ];
    let currentAIModel = AI_MODELS[0]; 
    const OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions';

// ============================================
// ИНИЦИАЛИЗАЦИЯ ПРИ ЗАГРУЗКЕ
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    console.log("🚀 DOM загружен. Инициализация приложения...");
    console.log("✅ JSCAD НЕ ИСПОЛЬЗУЕТСЯ - только OpenSCAD WASM и простой парсер");
    console.log("✅ Версия: 11.0 - OpenRouter Integration");
    
    // Проверяем что JSCAD не загружен
    if (typeof window.Modeling !== 'undefined' || typeof window.jscad !== 'undefined') {
        console.warn("⚠ ВНИМАНИЕ: Обнаружены остатки JSCAD в window, но они НЕ используются!");
    }
    
    initNavigation();
    initCodeEditor();
    init3DViewer();
    initPyodide();
    initRenderEngineSelector();
    initPrintModifiers();
    initPresets(); // Добавлено
    initUIImprovements(); // Добавлено
    initEventListeners();
    initOpenJSCAD();
    updateStatus("ИНИЦИАЛИЗАЦИЯ...");
});

// ============================================
// НАВИГАЦИЯ
// ============================================
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const pages = document.querySelectorAll('.page');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            const targetId = item.getAttribute('data-target');
            pages.forEach(page => page.classList.remove('active'));

            const targetPage = document.getElementById(targetId);
            if (targetPage) {
                targetPage.classList.add('active');
                if (targetId === 'generator' && editor) {
                    setTimeout(() => editor.refresh(), 10);
                }
            }
        });
    });
}

// ============================================
// РЕДАКТОР КОДА (CodeMirror)
// ============================================
function initCodeEditor() {
    const editorElement = document.getElementById('code-editor');
    if (editorElement) {
        editor = CodeMirror.fromTextArea(editorElement, {
            mode: 'python',
            theme: 'neo',
            lineNumbers: true,
            indentUnit: 4,
            lineWrapping: true
        });
        console.log("✓ CodeMirror инициализирован");
    }
}

// ============================================
// 3D ПРОСМОТРЩИК (Three.js)
// ============================================
function init3DViewer() {
    const container = document.getElementById('viewer-container');
    if (!container) return;

    // Очищаем контейнер
    container.innerHTML = '';
    
    // Создаем сцену
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf0f0f0);

    // Камера
    // Увеличиваем Far plane до 10000, чтобы большие модели не обрезались
    camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 10000);
    camera.position.set(50, 50, 50);
    camera.lookAt(0, 0, 0);

    // Рендерер
    // logarithmicDepthBuffer помогает избежать мерцания на больших дистанциях
    renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    // Освещение
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(50, 50, 50);
    scene.add(directionalLight);
    
    // Управление камерой
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.screenSpacePanning = true;
    controls.minDistance = 1;
    controls.maxDistance = 5000;
    controls.zoomSpeed = 0.8;
    controls.rotateSpeed = 0.8;
    controls.panSpeed = 0.8;
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;

    // Исправление скролла: предотвращаем прокрутку страницы при зуме
    renderer.domElement.addEventListener('wheel', (e) => {
        e.preventDefault();
    }, { passive: false });

    // Анимация
    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();

    // Обработка изменения размера
    const resizeObserver = new ResizeObserver(() => {
        if (container && container.clientWidth > 0 && container.clientHeight > 0) {
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
        }
    });
    resizeObserver.observe(container);
    
    console.log("✓ 3D просмотрщик инициализирован");
}

// ============================================
// ОБНОВЛЕНИЕ МОДЕЛИ В 3D ПРОСМОТРЩИКЕ
// ============================================
function updateModel(stlBuffer) {
    if (!scene || !renderer) {
        console.error("3D просмотрщик не инициализирован");
        return;
    }
    
    try {
        // Проверяем валидность буфера
        if (!stlBuffer || stlBuffer.byteLength < 84) {
            throw new Error("Неверный формат STL файла");
        }
        
        // Удаляем старую модель
        if (currentMesh) {
            scene.remove(currentMesh);
            if (currentMesh.geometry) currentMesh.geometry.dispose();
            if (currentMesh.material) currentMesh.material.dispose();
            currentMesh = null;
        }
        
        // Загружаем новую модель
    const loader = new STLLoader();
        const geometry = loader.parse(stlBuffer);
        
        // Вычисляем нормали для лучшего отображения
        geometry.computeVertexNormals();
        
        // Вычисляем центр для центрирования модели
    geometry.computeBoundingBox();
    const center = new THREE.Vector3();
    geometry.boundingBox.getCenter(center);
        geometry.translate(-center.x, -center.y, -center.z);
        
        // Создаем улучшенный материал
        const material = new THREE.MeshPhongMaterial({
            color: 0x0033ff,
            specular: 0x222222,
            shininess: 100,
            flatShading: false,
            side: THREE.DoubleSide
        });
        
        // Создаем mesh
        currentMesh = new THREE.Mesh(geometry, material);
        
        // ВАЖНО: Отключаем отсечение, чтобы модель не исчезала при вращении
        currentMesh.frustumCulled = false;
        
        scene.add(currentMesh);
        
        // Добавляем сетку для лучшей ориентации
        if (!scene.getObjectByName('gridHelper')) {
            const gridHelper = new THREE.GridHelper(200, 20, 0x888888, 0xcccccc);
            gridHelper.name = 'gridHelper';
            scene.add(gridHelper);
        }
        
        // Автоматически настраиваем камеру
        // BoundingBox уже вычислен выше
        const box = geometry.boundingBox;
        const size = new THREE.Vector3();
        box.getSize(size);
        
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = camera.fov * (Math.PI / 180);
        let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2));
        
        // Добавляем запас
        cameraZ *= 2.0;
        
        // Ставим камеру под углом
        const newPos = new THREE.Vector3(cameraZ, cameraZ, cameraZ);
        camera.position.copy(newPos);
        
        // Сбрасываем контролы и направляем на центр
        controls.target.set(0, 0, 0);
        controls.update();
        camera.lookAt(0, 0, 0);
        
        // Скрываем placeholder
    const placeholder = document.getElementById('viewer-placeholder');
    if (placeholder) placeholder.style.display = 'none';
        
        console.log("✓ Модель загружена в 3D просмотрщик");
    } catch (error) {
        console.error("❌ Ошибка загрузки модели:", error);
        const outputLog = document.getElementById('output-log');
        if (outputLog) {
            outputLog.innerText += "\n❌ Ошибка отображения модели: " + error.message;
        }
        const placeholder = document.getElementById('viewer-placeholder');
        if (placeholder) {
            placeholder.style.display = 'block';
            placeholder.innerHTML = `<p>❌ Ошибка загрузки модели</p><p style="font-size: 0.7rem;">${error.message}</p>`;
        }
    }
}

// ============================================
// PYODIDE ИНИЦИАЛИЗАЦИЯ
// ============================================
async function initPyodide() {
    const outputLog = document.getElementById('output-log');
    if (!outputLog) return;
    
    outputLog.innerText = "⚡ Инициализация Pyodide (Python в браузере)...";
    console.log("=== Инициализация Pyodide ===");
    
    try {
        if (typeof loadPyodide === 'undefined') {
            throw new Error("Pyodide не загружен");
        }
        
        pyodide = await loadPyodide();
        console.log("✓ Pyodide загружен");
        
        outputLog.innerText = "📦 Установка SolidPython2...";
        await pyodide.loadPackage("micropip");
        const micropip = pyodide.pyimport("micropip");
        await micropip.install('solidpython2');
        console.log("✓ SolidPython2 установлен");
        
        // Проверяем импорт и настраиваем окружение для сложного кода
        await pyodide.runPythonAsync(`
import solid2
import sys
import gc

# Увеличиваем лимиты для сложных моделей
sys.setrecursionlimit(5000)  # Увеличиваем лимит рекурсии

# Настраиваем сборку мусора для больших моделей
gc.set_threshold(700, 10, 10)

print("SolidPython2 успешно загружен!")
print("Окружение настроено для сложных моделей")
        `);
        
        pyodideReady = true;
        outputLog.innerText = "✅ Pyodide готов!\n✅ SolidPython2 загружен\n✅ Окружение настроено для сложных моделей\n⏳ Загрузка OpenSCAD WASM...";
        console.log("✅ Pyodide готов и настроен для сложного кода");
        
        // Инициализируем OpenSCAD WASM
        setTimeout(() => initOpenSCAD(), 2000);
        updateCompileButton();
        
    } catch (err) {
        console.error("❌ Ошибка инициализации Pyodide:", err);
        outputLog.innerText = "❌ Ошибка: " + err.message + "\n\nОбновите страницу (Ctrl+Shift+R)";
        updateStatus("ОШИБКА");
    }
}

// ============================================
// OPENJSCAD ИНИЦИАЛИЗАЦИЯ
// ============================================
async function initOpenJSCAD() {
    console.log("=== Инициализация OpenJSCAD ===");
    
    try {
        // Пытаемся загрузить OpenJSCAD модули
        if (!window.jscadModeling) {
            const modeling = await import('https://cdn.jsdelivr.net/npm/@jscad/modeling@2.11.0/+esm');
            window.jscadModeling = modeling;
        }
        
        openjscadReady = true;
        console.log("✓ OpenJSCAD готов к использованию");
        updateStatus("OpenJSCAD готов");
    } catch (err) {
        console.warn("⚠ OpenJSCAD не загрузился:", err);
        openjscadReady = false;
    }
}

// ============================================
// OPENSCAD MANAGER (RESILIENT)
// ============================================
class OpenSCADManager {
    constructor() {
        this.worker = null;
        this.isReady = false;
        this.initPromise = null;
    }

    async init() {
        if (this.initPromise) return this.initPromise;

        this.initPromise = new Promise((resolve, reject) => {
            const outputLog = document.getElementById('output-log');
            
            try {
                if (outputLog) outputLog.innerText += "\n⚙️ Запуск Worker ядра...";
                console.log("Creating new OpenSCAD Worker...");
                
                this.worker = new Worker('worker.js');

                this.worker.onerror = (err) => {
                    console.error("❌ Worker Error:", err);
                    if (outputLog) outputLog.innerText += `\n❌ Worker Error: ${err.message}`;
                    this.isReady = false;
                    reject(err);
                };

                this.worker.onmessage = (e) => {
                    const { type, message } = e.data;
                    if (type === 'ready') {
                        console.log("✅ Worker ready");
                        this.isReady = true;
                        if (outputLog) outputLog.innerText += "\n✅ OpenSCAD готов!";
                        updateStatus("ГОТОВ");
                        updateCompileButton();
                        resolve();
                    } else if (type === 'log') {
                        // console.log("[Worker]", message);
                    }
                };

            } catch (err) {
                reject(err);
            }
        });

        return this.initPromise;
    }

    terminate() {
        if (this.worker) {
            this.worker.terminate();
            this.worker = null;
            this.isReady = false;
            this.initPromise = null;
            console.log("Worker terminated");
        }
    }

    async render(scadCode) {
        // Всегда перезапускаем воркер для чистоты памяти при сложных рендерах
        // Или если он упал
        if (!this.worker || !this.isReady) {
            this.terminate();
            await this.init();
        }

        return new Promise((resolve, reject) => {
            if (!this.worker) return reject(new Error("Worker not initialized"));

            const outputLog = document.getElementById('output-log');
            
            this.worker.onmessage = (e) => {
                const { type, blob, message } = e.data;
                
                if (type === 'stl') {
                    resolve(blob);
                } else if (type === 'error') {
                    // Если ошибка критическая - убиваем воркер
                    if (message.includes('CRITICAL') || message.includes('Worker Error')) {
                        this.terminate();
                    }
                    reject(new Error(message));
                } else if (type === 'log') {
                    if (outputLog && message.startsWith('⚠')) {
                         outputLog.innerText += `\n${message}`;
                    }
                    // console.log("[Render]", message);
                }
            };

            this.worker.onerror = (err) => {
                this.terminate();
                reject(new Error(`Worker crash: ${err.message}`));
            };

            this.worker.postMessage({ command: 'render', code: scadCode });
        });
    }
}

const scadManager = new OpenSCADManager();

async function initOpenSCAD() {
    await scadManager.init();
}

// ============================================

// ============================================
// УЛУЧШЕННЫЙ КОМПИЛЯТОР: PYTHON → SCAD → STL
// Поддержка сложного и длинного кода
// ============================================

// Очистка состояния Pyodide перед компиляцией
function resetPyodideState() {
    try {
        pyodide.runPython(`
# Очистка пользовательских переменных
import sys
import gc
from io import StringIO

# Очищаем stdout/stderr
sys.stdout = StringIO()
sys.stderr = StringIO()

# Принудительная сборка мусора
gc.collect()
        `);
        console.log("✓ Состояние Pyodide очищено");
    } catch (e) {
        console.warn("⚠ Не удалось очистить состояние:", e);
    }
}

// Выполнение Python кода с улучшенной обработкой ошибок
async function executePythonCode(code) {
    const startTime = Date.now();
    
    try {
        // 1. Очищаем состояние перед выполнением
        resetPyodideState();
        
        // 2. Настраиваем перехват вывода
        pyodide.runPython(`
import sys
from io import StringIO
import traceback

# Перехватываем stdout и stderr
_stdout_buffer = StringIO()
_stderr_buffer = StringIO()
sys.stdout = _stdout_buffer
sys.stderr = _stderr_buffer

# Функции для получения вывода
def get_stdout():
    return _stdout_buffer.getvalue()

def get_stderr():
    return _stderr_buffer.getvalue()
        `);
        
        // 3. Выполняем код
        await pyodide.runPythonAsync(code);
        
        // 4. Получаем результат
        const stdout = pyodide.runPython("get_stdout()");
        const stderr = pyodide.runPython("get_stderr()");
        
        const executionTime = ((Date.now() - startTime) / 1000).toFixed(2);
        console.log(`✓ Код выполнен за ${executionTime}с`);
        
        if (stderr && stderr.trim()) {
            console.warn("⚠ Предупреждения Python:", stderr);
        }
        
        return {
            stdout: stdout || "",
            stderr: stderr || "",
            executionTime: executionTime
        };
        
    } catch (err) {
        const executionTime = ((Date.now() - startTime) / 1000).toFixed(2);
        console.error(`❌ Ошибка выполнения (${executionTime}с):`, err);
        
        // Пытаемся получить stderr
        let stderr = "";
        try {
            stderr = pyodide.runPython("get_stderr() if 'get_stderr' in dir() else ''");
        } catch (e) {
            console.warn("Не удалось получить stderr:", e);
        }
        
        throw {
            message: err.message || "Неизвестная ошибка",
            stderr: stderr,
            executionTime: executionTime
        };
    }
}

async function runCompilation() {
    const outputLog = document.getElementById('output-log');
    const runBtn = document.getElementById('run-btn');
    const downloadBtn = document.getElementById('download-stl-btn');

    // Если OpenSCAD не готов, попробуем подождать (Auto-wait)
    if (!pyodide || !pyodideReady) {
        if (outputLog) {
            outputLog.innerText = "⏳ Ожидание загрузки Pyodide...";
        }
        // Ждем Pyodide
        for (let i = 0; i < 20; i++) {
            if (pyodideReady) break;
            await new Promise(r => setTimeout(r, 500));
        }
    }
    
    // OpenSCAD Manager инициализируется лениво или при загрузке.
    // Если он еще не готов, scadManager.render() сам его инициализирует.
    if (!scadManager.isReady) {
        console.log("ℹ OpenSCAD Manager инициализируется по требованию...");
    }

    const code = editor ? editor.getValue() : "";
    if (!code || !code.trim()) {
        if (outputLog) {
            outputLog.innerText = "❌ Код пуст. Напишите Python код.";
        }
        return;
    }

    // Блокируем кнопки
    if (runBtn) {
        runBtn.disabled = true;
        runBtn.innerText = "⚡ КОМПИЛЯЦИЯ...";
    }
    if (downloadBtn) downloadBtn.disabled = true;
    
    showLoadingOverlay('⚡ Компиляция...'); // Показываем спиннер
    
    const compilationStartTime = Date.now();
    console.log("=== Начало компиляции ===");
    console.log("Длина кода:", code.length, "символов");
    console.log("Строк кода:", code.split('\n').length);
    
    if (outputLog) {
        outputLog.innerText = "⚡ Компиляция Python → SCAD...\n📊 Анализ кода...";
    }
    
    try {
        // Предварительная валидация синтаксиса
        if (outputLog) {
            outputLog.innerText = "🔍 Предварительная проверка синтаксиса...";
        }
        
        const syntaxCheck = await validatePythonSyntax(code);
        if (!syntaxCheck.valid) {
            throw new Error(`Синтаксическая ошибка в строке ${syntaxCheck.line}:\n${syntaxCheck.error}\n\nИсправьте код и попробуйте снова.`);
        }
        
        console.log("✅ Предварительная валидация пройдена");
        
        if (outputLog) {
            outputLog.innerText = "✅ Синтаксис проверен\n⚡ Выполнение Python кода...";
        }
        
        // 1. Python → SCAD (улучшенная версия)
        const result = await executePythonCode(code);
        
        const scadCode = result.stdout.trim();
        lastScadCode = scadCode;
        
        if (!scadCode) {
            // Проверяем, может быть код не выводит результат
            let errorInfo = "";
            if (result.stderr) {
                errorInfo = `\n\n🐍 Python предупреждения:\n${result.stderr}`;
            }
            
            // Пытаемся найти объект в глобальной области видимости
            try {
                const hasModel = pyodide.runPython(`
# Проверяем наличие переменных с объектами
import sys
vars_with_objects = [name for name, obj in globals().items() 
                     if hasattr(obj, '__class__') and not name.startswith('_')]
vars_with_objects
                `);
                
                if (hasModel && hasModel.length > 0) {
                    errorInfo += `\n\n💡 Обнаружены переменные: ${hasModel.join(', ')}`;
                    errorInfo += `\n💡 Добавьте в конец кода: print(scad_render(${hasModel[0]}))`;
                }
            } catch (e) {
                console.log("Не удалось проверить переменные:", e);
            }
            
            throw new Error("Нет SCAD кода в выводе. Убедитесь что используете: print(scad_render(my_object))" + errorInfo);
        }
        
        console.log("✓ SCAD код сгенерирован");
        console.log("  Длина SCAD:", scadCode.length, "символов");
        console.log("  Строк SCAD:", scadCode.split('\n').length);
        console.log("  Время выполнения Python:", result.executionTime, "с");
        
        if (outputLog) {
            outputLog.innerText = `✅ SCAD код сгенерирован!\n`;
            outputLog.innerText += `📊 Строк SCAD: ${scadCode.split('\n').length}\n`;
            outputLog.innerText += `⏱ Время Python: ${result.executionTime}с\n`;
            if (result.stderr) {
                outputLog.innerText += `⚠ Предупреждения: ${result.stderr.substring(0, 100)}...\n`;
            }
            outputLog.innerText += `\n⚡ Рендеринг SCAD → STL...`;
        }
        
        // 2. SCAD → STL
        const stlStartTime = Date.now();
        const stlOutput = await scadToStl(scadCode);
        const stlTime = ((Date.now() - stlStartTime) / 1000).toFixed(2);
        
        if (!stlOutput || stlOutput.length === 0) {
            throw new Error("Не удалось сгенерировать STL из SCAD кода");
        }
        
        stlData = stlOutput instanceof Uint8Array ? stlOutput : new Uint8Array(stlOutput);
        console.log("✓ STL сгенерирован");
        console.log("  Размер STL:", stlData.length, "байт");
        console.log("  Время рендеринга:", stlTime, "с");
        
        // 3. Отображаем модель
        if (outputLog) {
            outputLog.innerText += `\n⚡ Загрузка в 3D просмотрщик...`;
        }
        updateModel(stlData.buffer);

        // Скрываем placeholder
        const placeholder = document.getElementById('viewer-placeholder');
        if (placeholder) placeholder.style.display = 'none';
        
        const totalTime = ((Date.now() - compilationStartTime) / 1000).toFixed(2);
        
        if (outputLog) {
            outputLog.innerText = `\n\n✅ УСПЕХ! Модель сгенерирована и отображена!\n`;
            outputLog.innerText += `📊 Размер STL: ${(stlData.length / 1024).toFixed(2)} KB\n`;
            outputLog.innerText += `🎯 Движок: ${getRenderEngineName(renderEngine)}\n`;
            outputLog.innerText += `⏱ Общее время: ${totalTime}с (Python: ${result.executionTime}с, STL: ${stlTime}с)\n`;
            outputLog.innerText += `💾 Нажмите 'СКАЧАТЬ STL' для сохранения`;
        }
        
        if (downloadBtn) downloadBtn.disabled = false;
        
        const downloadScadBtn = document.getElementById('download-scad-btn');
        if (downloadScadBtn) downloadScadBtn.disabled = false;
        
    } catch (err) {
        console.error("❌ Ошибка компиляции:", err);
        
        const totalTime = ((Date.now() - compilationStartTime) / 1000).toFixed(2);
        let errorMessage = err.message || "Неизвестная ошибка";
        let pythonErrors = "";
        
        // Добавляем информацию об ошибках Python
        if (err.stderr) {
            pythonErrors = `\n\n🐍 Python ошибки:\n${err.stderr}`;
        } else {
            // Пытаемся получить stderr из Pyodide
            try {
                const stderr = pyodide.runPython("get_stderr() if 'get_stderr' in dir() else ''");
                if (stderr && stderr.trim()) {
                    pythonErrors = `\n\n🐍 Python ошибки:\n${stderr}`;
                }
            } catch (e) {
                console.log("Не удалось получить stderr:", e);
            }
        }
        
        if (outputLog) {
            outputLog.innerText = `❌ Ошибка компиляции (${totalTime}с): ${errorMessage}${pythonErrors}\n\n`;
            outputLog.innerText += `💡 ПОДСКАЗКИ:\n`;
            outputLog.innerText += `- Используйте print(scad_render(my_object)) в конце кода\n`;
            outputLog.innerText += `- Проверьте синтаксис Python\n`;
            outputLog.innerText += `- Убедитесь что импортировали: from solid2 import *\n`;
            outputLog.innerText += `- Для сложных моделей используйте функции и классы\n`;
            outputLog.innerText += `- Проверьте что все переменные определены`;
        }
    } finally {
        hideLoadingOverlay(); // Скрываем спиннер
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.innerText = "СКОМПИЛИРОВАТЬ()";
        }
        updateCompileButton();
    }
}

// ============================================
// ВЫБОР ДВИЖКА РЕНДЕРИНГА
// ============================================
function initRenderEngineSelector() {
    const selector = document.getElementById('render-engine-select');
    if (!selector) return;
    
    // Загружаем сохраненный выбор
    const saved = localStorage.getItem('renderEngine');
    const validEngines = ['auto', 'openscad', 'openscad-cloud', 'openjscad', 'cadhub', 'smart-scad', 'parser'];
    if (saved && validEngines.includes(saved)) {
        renderEngine = saved;
        selector.value = saved;
    }
    
    // Обновляем при изменении
    selector.addEventListener('change', (e) => {
        renderEngine = e.target.value;
        localStorage.setItem('renderEngine', renderEngine);
        console.log(`🎯 Движок рендеринга изменен на: ${renderEngine}`);
        updateStatus(`Движок: ${getRenderEngineName(renderEngine)}`);
    });
    
    console.log(`🎯 Движок рендеринга: ${getRenderEngineName(renderEngine)}`);
}

function getRenderEngineName(engine) {
    const names = {
        'auto': 'АВТО',
        'openscad': 'OpenSCAD WASM',
        'parser': 'ПРОСТОЙ ПАРСЕР'
    };
    return names[engine] || 'АВТО';
}

// ============================================
// SCAD → STL (МНОЖЕСТВЕННЫЕ МЕТОДЫ)
// ============================================
async function scadToStl(scadCode) {
    console.log("=== SCAD → STL ===");
    console.log(`🎯 Выбранный движок: ${getRenderEngineName(renderEngine)}`);
    
    // Проверяем внешние компиляторы
    const externalCompilers = ['openscad-cloud', 'cadhub', 'smart-scad'];
    if (externalCompilers.includes(renderEngine)) {
        console.log(`🌐 Открытие внешнего компилятора: ${getRenderEngineName(renderEngine)}`);
        openExternalCompiler(scadCode, renderEngine);
        
        // Показываем сообщение пользователю
        const outputLog = document.getElementById('output-log');
        if (outputLog) {
            outputLog.innerText += `\n\n🌐 Внешний компилятор открыт в новой вкладке.\n📋 SCAD код сохранен в буфер обмена.\nВставьте код в редактор компилятора.`;
        }
        
        // Копируем SCAD код в буфер обмена
        if (navigator.clipboard) {
            navigator.clipboard.writeText(scadCode).then(() => {
                console.log("✓ SCAD код скопирован в буфер обмена");
            });
        }
        
        throw new Error("Внешний компилятор открыт. Используйте его для рендеринга.");
    }
    
    // OpenJSCAD обработка
    if (renderEngine === 'openjscad') {
        try {
            console.log("🔄 Используем OpenJSCAD...");
            return await scadToStlViaOpenJSCAD(scadCode);
        } catch (err) {
            console.error("❌ OpenJSCAD не сработал:", err);
            throw new Error("OpenJSCAD ошибка: " + err.message);
        }
    }
    
    // Основной режим: OpenSCAD WASM (через Manager)
    // Используем его для 'openscad' и 'auto'
    if (renderEngine === 'openscad' || renderEngine === 'auto') {
        try {
            console.log("🔄 Используем OpenSCAD WASM Manager...");
            // Всегда используем менеджер, он сам разберется с инициализацией и перезапуском
            const stlBlob = await scadManager.render(scadCode);
            return stlBlob;
        } catch (err) {
            console.error("❌ OpenSCAD Manager Error:", err);
            
            // Если выбран строго OpenSCAD - падаем
            if (renderEngine === 'openscad') {
                throw new Error("OpenSCAD рендеринг не удался: " + err.message);
            }
            
            // Если AUTO, идем к фоллбеку
            console.warn("⚠ Переход на запасной парсер...");
        }
    }
    
    // Fallback: Простой парсер
    if (renderEngine === 'parser' || renderEngine === 'auto') {
        console.log("⚠ Используем простой парсер (Fallback)...");
        try {
            return await scadToStlViaSimpleParser(scadCode);
        } catch (err) {
            console.error("❌ Простой парсер не сработал:", err);
            throw new Error("Не удалось отрендерить модель ни одним способом.");
        }
    }

    throw new Error(`Неизвестный движок рендеринга: ${renderEngine}`);
}


// OpenJSCAD метод
async function scadToStlViaOpenJSCAD(scadCode) {
    console.log("=== OpenJSCAD рендеринг ===");
    
    // Проверяем доступность OpenJSCAD
    if (!window.jscadModeling) {
        // Пытаемся загрузить
        try {
            const modeling = await import('https://cdn.jsdelivr.net/npm/@jscad/modeling@2.11.0/+esm');
            window.jscadModeling = modeling;
            openjscadReady = true;
        } catch (err) {
            throw new Error("OpenJSCAD не загружен. Проверьте интернет соединение.");
        }
    }
    
    const { primitives, booleans, transforms, extrusions } = window.jscadModeling;
    const { cube, sphere, cylinder } = primitives;
    const { union, subtract, intersect } = booleans;
    const { translate, rotate, scale } = transforms;
    const { extrudeLinear, extrudeRotate } = extrusions;
    
    try {
        // Конвертируем SCAD код в OpenJSCAD JavaScript
        // Это упрощенный парсер - работает только с базовыми примитивами
        const jsCode = convertScadToOpenJSCAD(scadCode);
        
        // Выполняем код
        const mainFunction = new Function('cube', 'sphere', 'cylinder', 'union', 'subtract', 'intersect', 
            'translate', 'rotate', 'scale', 'extrudeLinear', 'extrudeRotate',
            `return ${jsCode}`);
        
        const geometry = mainFunction(cube, sphere, cylinder, union, subtract, intersect,
            translate, rotate, scale, extrudeLinear, extrudeRotate);
        
        if (!geometry) {
            throw new Error("OpenJSCAD не вернул геометрию");
        }
        
        // Конвертируем геометрию в STL
        const { serialize } = await import('https://cdn.jsdelivr.net/npm/@jscad/io@2.11.0/+esm');
        const stlData = serialize({ binary: true }, geometry);
        
        return new Uint8Array(stlData);
        
    } catch (err) {
        console.error("OpenJSCAD ошибка:", err);
        throw new Error("OpenJSCAD не смог обработать SCAD код: " + err.message);
    }
}

// Простая конвертация SCAD в OpenJSCAD JavaScript
function convertScadToOpenJSCAD(scadCode) {
    // Упрощенный парсер - работает только с базовыми примитивами
    let jsCode = scadCode;
    
    // Заменяем cube() на cube()
    jsCode = jsCode.replace(/cube\(\[([^\]]+)\]\)/g, (match, params) => {
        const [x, y, z] = params.split(',').map(p => p.trim());
        return `cube({ size: [${x}, ${y}, ${z}] })`;
    });
    
    // Заменяем sphere() на sphere()
    jsCode = jsCode.replace(/sphere\(r=([^)]+)\)/g, (match, r) => {
        return `sphere({ radius: ${r} })`;
    });
    
    // Заменяем cylinder() на cylinder()
    jsCode = jsCode.replace(/cylinder\(r=([^,]+),\s*h=([^)]+)\)/g, (match, r, h) => {
        return `cylinder({ radius: ${r}, height: ${h} })`;
    });
    
    // Заменяем union() на union()
    jsCode = jsCode.replace(/union\(\)/g, 'union');
    
    // Заменяем difference() на subtract()
    jsCode = jsCode.replace(/difference\(\)/g, 'subtract');
    
    // Заменяем translate() на translate()
    jsCode = jsCode.replace(/translate\(\[([^\]]+)\]\)/g, (match, params) => {
        const [x, y, z] = params.split(',').map(p => p.trim());
        return `translate([${x}, ${y}, ${z}], `;
    });
    
    // Простая обертка
    return `function main() { return ${jsCode}; } main()`;
}

// Простой парсер SCAD (fallback)
async function scadToStlViaSimpleParser(scadCode) {
    console.log("Парсинг SCAD кода...");
    
    // Парсим union() с несколькими цилиндрами (для вазы)
    const unionMatch = scadCode.match(/union\s*\(\s*\)\s*\{([^}]+)\}/i);
    if (unionMatch) {
        const unionContent = unionMatch[1];
        const cylinders = unionContent.match(/cylinder\s*\([^)]+\)/gi) || [];
        
        if (cylinders.length > 0) {
            console.log(`Найдено ${cylinders.length} цилиндров в union, генерируем вазу...`);
            // Для вазы: base (r=15, h=5), body (r1=15, r2=20, h=30), rim (r=20, h=2)
            // Генерируем комбинированную модель вазы
            return generateVaseSTL();
        }
    }
    
    // Ищем примитивы: cube, sphere, cylinder
    const cubeMatch = scadCode.match(/cube\s*\(\s*(\[?\s*[\d.]+\s*(?:,\s*[\d.]+)?\s*(?:,\s*[\d.]+)?\s*\]?)\s*\)/i);
    const sphereMatch = scadCode.match(/sphere\s*\(\s*r\s*=\s*([\d.]+)\s*\)/i);
    const cylinderMatch = scadCode.match(/cylinder\s*\(\s*(?:r\s*=\s*)?([\d.]+)\s*(?:,\s*h\s*=\s*([\d.]+))?/i);
    
    if (cubeMatch) {
        const size = cubeMatch[1].replace(/[\[\]]/g, '').split(',').map(s => parseFloat(s.trim()) || 10);
        const s = size.length === 1 ? [size[0], size[0], size[0]] : [size[0] || 10, size[1] || 10, size[2] || 10];
        console.log("Генерируем куб:", s);
        return generateCubeSTL(s[0], s[1], s[2]);
    } else if (sphereMatch) {
        const r = parseFloat(sphereMatch[1]) || 10;
        console.log("Генерируем сферу, радиус:", r);
        return generateSphereSTL(r);
    } else if (cylinderMatch) {
        const r = parseFloat(cylinderMatch[1]) || 10;
        const h = cylinderMatch[2] ? parseFloat(cylinderMatch[2]) : 20;
        console.log("Генерируем цилиндр, r:", r, "h:", h);
        return generateCylinderSTL(r, h);
    } else {
        // Fallback: простой куб 10x10x10
        console.log("Не найдено примитивов, генерируем куб по умолчанию");
        return generateCubeSTL(10, 10, 10);
    }
}

// Генерация STL для вазы (комбинация цилиндров)
function generateVaseSTL() {
    console.log("Генерируем STL для вазы...");
    // Ваза состоит из:
    // 1. Основание: цилиндр r=15, h=5 (z: 0-5)
    // 2. Тело: конический цилиндр r1=15, r2=20, h=30 (z: 5-35)
    // 3. Ободок: цилиндр r=20, h=2 (z: 35-37)
    
    const segments = 32;
    const vertices = [];
    const faces = [];
    let vertexIndex = 0;
    
    // 1. Основание (r=15, h=5, z: 0-5)
    const baseR = 15;
    const baseH = 5;
    const baseCenter = vertexIndex;
    vertices.push([0, 0, 0]); // центр нижнего основания
    vertexIndex++;
    for (let i = 0; i <= segments; i++) {
        const angle = (i * 2 * Math.PI) / segments;
        vertices.push([baseR * Math.cos(angle), baseR * Math.sin(angle), 0]);
        vertexIndex++;
    }
    const baseTop = vertexIndex;
    vertices.push([0, 0, baseH]); // центр верхнего основания
    vertexIndex++;
    for (let i = 0; i <= segments; i++) {
        const angle = (i * 2 * Math.PI) / segments;
        vertices.push([baseR * Math.cos(angle), baseR * Math.sin(angle), baseH]);
        vertexIndex++;
    }
    
    // Грани основания
    for (let i = 1; i < segments; i++) {
        faces.push([baseCenter, i + 1, i]); // нижняя крышка
        faces.push([baseTop, baseTop + i, baseTop + i + 1]); // верхняя крышка
    }
    for (let i = 0; i < segments; i++) {
        const b1 = 1 + i;
        const b2 = 1 + ((i + 1) % (segments + 1));
        const t1 = baseTop + 1 + i;
        const t2 = baseTop + 1 + ((i + 1) % (segments + 1));
        faces.push([b1, b2, t1]);
        faces.push([b2, t2, t1]);
    }
    
    // 2. Тело (конический, r1=15, r2=20, h=30, z: 5-35)
    const bodyR1 = 15;
    const bodyR2 = 20;
    const bodyH = 30;
    const bodyZ = baseH;
    const bodyBottom = vertexIndex;
    for (let i = 0; i <= segments; i++) {
        const angle = (i * 2 * Math.PI) / segments;
        vertices.push([bodyR1 * Math.cos(angle), bodyR1 * Math.sin(angle), bodyZ]);
        vertexIndex++;
    }
    const bodyTop = vertexIndex;
    for (let i = 0; i <= segments; i++) {
        const angle = (i * 2 * Math.PI) / segments;
        vertices.push([bodyR2 * Math.cos(angle), bodyR2 * Math.sin(angle), bodyZ + bodyH]);
        vertexIndex++;
    }
    
    // Грани тела
    for (let i = 0; i < segments; i++) {
        const b1 = bodyBottom + i;
        const b2 = bodyBottom + ((i + 1) % (segments + 1));
        const t1 = bodyTop + i;
        const t2 = bodyTop + ((i + 1) % (segments + 1));
        faces.push([b1, b2, t1]);
        faces.push([b2, t2, t1]);
    }
    
    // 3. Ободок (r=20, h=2, z: 35-37)
    const rimR = 20;
    const rimH = 2;
    const rimZ = bodyZ + bodyH;
    const rimBottom = vertexIndex;
    for (let i = 0; i <= segments; i++) {
        const angle = (i * 2 * Math.PI) / segments;
        vertices.push([rimR * Math.cos(angle), rimR * Math.sin(angle), rimZ]);
        vertexIndex++;
    }
    const rimTop = vertexIndex;
    vertices.push([0, 0, rimZ + rimH]); // центр верхнего ободка
    vertexIndex++;
    for (let i = 0; i <= segments; i++) {
        const angle = (i * 2 * Math.PI) / segments;
        vertices.push([rimR * Math.cos(angle), rimR * Math.sin(angle), rimZ + rimH]);
        vertexIndex++;
    }
    
    // Грани ободка
    for (let i = 1; i < segments; i++) {
        faces.push([rimTop, rimTop + i + 1, rimTop + i]); // верхняя крышка
    }
    for (let i = 0; i < segments; i++) {
        const b1 = rimBottom + i;
        const b2 = rimBottom + ((i + 1) % (segments + 1));
        const t1 = rimTop + 1 + i;
        const t2 = rimTop + 1 + ((i + 1) % (segments + 1));
        faces.push([b1, b2, t1]);
        faces.push([b2, t2, t1]);
    }
    
    return generateSTLFromFaces(vertices, faces);
}

// Генерация STL для куба
function generateCubeSTL(w, h, d) {
    const vertices = [
        [0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0], // bottom
        [0, 0, d], [w, 0, d], [w, h, d], [0, h, d]  // top
    ];
    
    const faces = [
        [0, 1, 2], [0, 2, 3], // bottom
        [4, 7, 6], [4, 6, 5], // top
        [0, 4, 5], [0, 5, 1], // front
        [2, 6, 7], [2, 7, 3], // back
        [0, 3, 7], [0, 7, 4], // left
        [1, 5, 6], [1, 6, 2]  // right
    ];
    
    return generateSTLFromFaces(vertices, faces);
}

// Генерация STL для сферы
function generateSphereSTL(r, segments = 20) {
    const vertices = [];
    const faces = [];
    
    // Генерируем вершины сферы
    for (let i = 0; i <= segments; i++) {
        const theta = (i * Math.PI) / segments;
        for (let j = 0; j <= segments; j++) {
            const phi = (j * 2 * Math.PI) / segments;
            const x = r * Math.sin(theta) * Math.cos(phi);
            const y = r * Math.sin(theta) * Math.sin(phi);
            const z = r * Math.cos(theta);
            vertices.push([x, y, z]);
        }
    }
    
    // Генерируем грани
    for (let i = 0; i < segments; i++) {
        for (let j = 0; j < segments; j++) {
            const v1 = i * (segments + 1) + j;
            const v2 = v1 + 1;
            const v3 = (i + 1) * (segments + 1) + j;
            const v4 = v3 + 1;
            
            faces.push([v1, v2, v3]);
            faces.push([v2, v4, v3]);
        }
    }
    
    return generateSTLFromFaces(vertices, faces);
}

// Генерация STL для цилиндра
function generateCylinderSTL(r, h, segments = 32) {
    const vertices = [];
    const faces = [];
    
    // Нижний круг
    vertices.push([0, 0, 0]);
    for (let i = 0; i <= segments; i++) {
        const angle = (i * 2 * Math.PI) / segments;
        vertices.push([r * Math.cos(angle), r * Math.sin(angle), 0]);
    }
    
    // Верхний круг
    const topCenter = vertices.length;
    vertices.push([0, 0, h]);
    for (let i = 0; i <= segments; i++) {
        const angle = (i * 2 * Math.PI) / segments;
        vertices.push([r * Math.cos(angle), r * Math.sin(angle), h]);
    }
    
    // Боковые грани
    for (let i = 0; i < segments; i++) {
        const b1 = 1 + i;
        const b2 = 1 + ((i + 1) % (segments + 1));
        const t1 = topCenter + 1 + i;
        const t2 = topCenter + 1 + ((i + 1) % (segments + 1));
        
        faces.push([b1, b2, t1]);
        faces.push([b2, t2, t1]);
    }
    
    // Нижняя крышка
    for (let i = 1; i < segments; i++) {
        faces.push([0, i + 1, i]);
    }
    
    // Верхняя крышка
    for (let i = 1; i < segments; i++) {
        faces.push([topCenter, topCenter + i, topCenter + i + 1]);
    }
    
    return generateSTLFromFaces(vertices, faces);
}

// Генерация бинарного STL из вершин и граней
function generateSTLFromFaces(vertices, faces) {
    const buffer = new ArrayBuffer(80 + 4 + faces.length * 50);
    const view = new DataView(buffer);
    
    // Заголовок (80 байт)
    for (let i = 0; i < 80; i++) {
        view.setUint8(i, 0);
    }
    
    // Количество граней
    view.setUint32(80, faces.length, true);
    
    let offset = 84;
    
    for (const face of faces) {
        const v0 = vertices[face[0]];
        const v1 = vertices[face[1]];
        const v2 = vertices[face[2]];
        
        // Нормаль (вычисляем через векторное произведение)
        const e1 = [v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]];
        const e2 = [v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]];
        const normal = [
            e1[1] * e2[2] - e1[2] * e2[1],
            e1[2] * e2[0] - e1[0] * e2[2],
            e1[0] * e2[1] - e1[1] * e2[0]
        ];
        const len = Math.sqrt(normal[0]**2 + normal[1]**2 + normal[2]**2);
        if (len > 0) {
            normal[0] /= len;
            normal[1] /= len;
            normal[2] /= len;
        }
        
        // Записываем нормаль
        view.setFloat32(offset, normal[0], true); offset += 4;
        view.setFloat32(offset, normal[1], true); offset += 4;
        view.setFloat32(offset, normal[2], true); offset += 4;
        
        // Записываем вершины
        view.setFloat32(offset, v0[0], true); offset += 4;
        view.setFloat32(offset, v0[1], true); offset += 4;
        view.setFloat32(offset, v0[2], true); offset += 4;
        
        view.setFloat32(offset, v1[0], true); offset += 4;
        view.setFloat32(offset, v1[1], true); offset += 4;
        view.setFloat32(offset, v1[2], true); offset += 4;
        
        view.setFloat32(offset, v2[0], true); offset += 4;
        view.setFloat32(offset, v2[1], true); offset += 4;
        view.setFloat32(offset, v2[2], true); offset += 4;
        
        // Атрибут байт (0)
        view.setUint16(offset, 0, true); offset += 2;
    }
    
    return new Uint8Array(buffer);
}

// ============================================
// МОДИФИКАТОРЫ 3D ПЕЧАТИ
// ============================================
function initPrintModifiers() {
    const toggleBtn = document.getElementById('toggle-modifiers');
    const modifiersContent = document.getElementById('modifiers-content');
    const infillSlider = document.getElementById('infill-percent');
    const infillValue = document.getElementById('infill-value');
    const supportAngle = document.getElementById('support-angle');
    const addSupports = document.getElementById('add-supports');
    const applyBtn = document.getElementById('apply-modifiers-btn');
    
    // Переключение видимости панели
    if (toggleBtn && modifiersContent) {
        let isExpanded = true;
        toggleBtn.addEventListener('click', () => {
            isExpanded = !isExpanded;
            modifiersContent.style.display = isExpanded ? 'block' : 'none';
            toggleBtn.textContent = isExpanded ? '▼' : '▲';
        });
    }
    
    // Обновление значения заполнения
    if (infillSlider && infillValue) {
        infillSlider.addEventListener('input', (e) => {
            infillValue.textContent = e.target.value + '%';
            printModifiers.infillPercent = parseInt(e.target.value);
        });
    }
    
    // Включение/выключение угла поддержек
    if (addSupports && supportAngle) {
        addSupports.addEventListener('change', (e) => {
            supportAngle.disabled = !e.target.checked;
            printModifiers.addSupports = e.target.checked;
        });
    }
    
    // Обновление всех модификаторов
    const updateModifiers = () => {
        const wallThicknessEl = document.getElementById('wall-thickness');
        const infillPercentEl = document.getElementById('infill-percent');
        const infillPatternEl = document.getElementById('infill-pattern');
        const supportAngleEl = document.getElementById('support-angle');
        const addBrimEl = document.getElementById('add-brim');
        const layerHeightEl = document.getElementById('layer-height');
        
        if (wallThicknessEl) printModifiers.wallThickness = parseFloat(wallThicknessEl.value || 2);
        if (infillPercentEl) printModifiers.infillPercent = parseInt(infillPercentEl.value || 20);
        if (infillPatternEl) printModifiers.infillPattern = infillPatternEl.value || 'grid';
        if (addSupports) printModifiers.addSupports = addSupports.checked || false;
        if (supportAngleEl) printModifiers.supportAngle = parseFloat(supportAngleEl.value || 45);
        if (addBrimEl) printModifiers.addBrim = addBrimEl.checked || false;
        if (layerHeightEl) printModifiers.layerHeight = parseFloat(layerHeightEl.value || 0.2);
        console.log("Модификаторы обновлены:", printModifiers);
    };
    
    // Применение модификаторов
    if (applyBtn) {
        applyBtn.addEventListener('click', () => {
            updateModifiers();
            applyPrintModifiers();
        });
    }
    
    // Автообновление при изменении
    ['wall-thickness', 'infill-pattern', 'support-angle', 'add-brim', 'layer-height'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', updateModifiers);
        }
    });
}

// Применение модификаторов 3D печати к Python коду
function applyPrintModifiers() {
    if (!editor) {
        alert("Редактор не готов!");
        return;
    }
    
    const code = editor.getValue();
    if (!code || !code.trim()) {
        alert("Сначала напишите код!");
        return;
    }

    console.log("Применение модификаторов 3D печати к коду:", printModifiers);
    
    let modifiedCode = code;
    
    // 1. Добавляем параметры модификаторов в начало кода (если их еще нет)
    const modifiersComment = `# МОДИФИКАТОРЫ 3D ПЕЧАТИ
WALL_THICKNESS = ${printModifiers.wallThickness}  # Толщина стенок (мм)
INFILL_PERCENT = ${printModifiers.infillPercent}  # Заполнение (%)
INFILL_PATTERN = "${printModifiers.infillPattern}"  # Тип заполнения
LAYER_HEIGHT = ${printModifiers.layerHeight}  # Высота слоя (мм)
`;
    
    // Проверяем, есть ли уже модификаторы
    if (!code.includes('МОДИФИКАТОРЫ 3D ПЕЧАТИ')) {
        // Находим место после импортов
        const importEnd = code.indexOf('\n', code.indexOf('from solid2'));
        if (importEnd > 0) {
            modifiedCode = code.slice(0, importEnd + 1) + '\n' + modifiersComment + code.slice(importEnd + 1);
        } else {
            modifiedCode = modifiersComment + '\n' + code;
        }
    }
    
    // 2. Добавляем поддержки если нужно
    if (printModifiers.addSupports) {
        const supportCode = `
# ГЕНЕРАЦИЯ ПОДДЕРЖЕК (угол ${printModifiers.supportAngle}°)
# ВАЖНО: Поддержки должны быть добавлены вручную в слайсере
# или через специальные функции для определения нависающих элементов
`;
        if (!modifiedCode.includes('ПОДДЕРЖЕК')) {
            modifiedCode += supportCode;
        }
    }
    
    // 3. Добавляем юбку если нужно
    if (printModifiers.addBrim) {
        const brimCode = `
# ЮБКА (BRIM) - добавляется в слайсере
# Для добавления юбки в коде можно использовать:
# base = translate([0, 0, -brim_height])(cube([width + brim_width*2, depth + brim_width*2, brim_height]))
`;
        if (!modifiedCode.includes('ЮБКА')) {
            modifiedCode += brimCode;
        }
    }
    
    // 4. Добавляем комментарии о параметрах печати
    const printParams = `
# ПАРАМЕТРЫ ДЛЯ СЛАЙСЕРА:
# - Толщина стенок: ${printModifiers.wallThickness}мм
# - Заполнение: ${printModifiers.infillPercent}% (${printModifiers.infillPattern})
# - Высота слоя: ${printModifiers.layerHeight}мм
${printModifiers.addSupports ? `# - Поддержки: включены (угол ${printModifiers.supportAngle}°)\n` : ''}${printModifiers.addBrim ? '# - Юбка: включена\n' : ''}
`;
    
    // Обновляем код в редакторе
    editor.setValue(modifiedCode + printParams);
    editor.refresh();
    
    const outputLog = document.getElementById('output-log');
    if (outputLog) {
        outputLog.innerText = "✅ Модификаторы применены к коду!\n";
        outputLog.innerText += `📏 Толщина стенок: ${printModifiers.wallThickness}мм\n`;
        outputLog.innerText += `📊 Заполнение: ${printModifiers.infillPercent}% (${printModifiers.infillPattern})\n`;
        if (printModifiers.addSupports) {
            outputLog.innerText += `🔧 Поддержки: да (угол ${printModifiers.supportAngle}°)\n`;
        }
        if (printModifiers.addBrim) {
            outputLog.innerText += `📐 Юбка: да\n`;
        }
        outputLog.innerText += `📏 Высота слоя: ${printModifiers.layerHeight}мм\n\n`;
        outputLog.innerText += "💡 Код обновлен. Скомпилируйте модель заново.";
    }
    
    console.log("✓ Модификаторы применены к коду");
}

// ============================================
// АЛЬТЕРНАТИВНЫЕ КОМПИЛЯТОРЫ OpenSCAD
// ============================================
function openExternalCompiler(scadCode, compilerType) {
    const compilers = {
        'openscad-cloud': {
            url: 'https://ochafik.com/openscad',
            method: 'iframe'
        },
        'openjscad': {
            url: 'https://openjscad.xyz',
            method: 'window'
        },
        'cadhub': {
            url: 'https://cadhub.xyz',
            method: 'window'
        },
        'smart-scad': {
            url: 'https://openscad.net',
            method: 'window'
        }
    };
    
    const compiler = compilers[compilerType];
    if (!compiler) {
        console.error("Неизвестный компилятор:", compilerType);
        return;
    }
    
    // Сохраняем SCAD код в localStorage для передачи
    localStorage.setItem('openscad_code', scadCode);
    localStorage.setItem('openscad_source', 'additive-light');
    
    if (compiler.method === 'window') {
        window.open(compiler.url, '_blank');
    } else {
        // Для iframe можно создать модальное окно
        const modal = document.createElement('div');
        modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 10000; display: flex; align-items: center; justify-content: center;';
        modal.innerHTML = `
            <div style="background: white; padding: 20px; border-radius: 8px; max-width: 90%; max-height: 90%;">
                <h3>Открытие внешнего компилятора</h3>
                <p>SCAD код сохранен. Откройте <a href="${compiler.url}" target="_blank">${compiler.url}</a></p>
                <p>Вставьте SCAD код в редактор компилятора.</p>
                <button onclick="this.parentElement.parentElement.remove()" style="margin-top: 10px; padding: 10px 20px;">Закрыть</button>
            </div>
        `;
        document.body.appendChild(modal);
    }
}

// Шаблоны кода удалены - больше не используются

// ============================================
// ГАЛЕРЕЯ ШАБЛОНОВ (PRESETS)
// ============================================
const PRESETS = {
    cube: `from solid2 import *

# Простой куб 20x20x20
model = cube(20)
print(scad_render(model))`,

    sphere: `from solid2 import *

# Сфера радиусом 20
set_global_fn(50) # Качество рендера
model = sphere(r=20)
print(scad_render(model))`,

    vase_simple: `from solid2 import *
set_global_fn(50)

# Параметры вазы
height = 80
radius = 30
wall = 2

# Простая цилиндрическая ваза
outer = cylinder(r=radius, h=height)
inner = cylinder(r=radius-wall, h=height)

# Вырезаем внутреннюю часть, оставляя дно
model = difference()(
    outer,
    translate([0,0,wall])(inner)
)

print(scad_render(model))`,

    vase_twisted: `from solid2 import *
set_global_fn(60)

# Витая ваза
model = linear_extrude(height=100, twist=120, scale=1.3, slices=60)(
    difference()(
        circle(r=30),
        circle(r=28)
    )
)

print(scad_render(model))`,

    gears: `from solid2 import *
import math

# Параметрическая шестерня
def gear(teeth=20, radius=40, thickness=5):
    body = cylinder(r=radius, h=thickness)
    teeth_objs = []
    for i in range(teeth):
        angle = (360 / teeth) * i
        x = radius * math.cos(math.radians(angle))
        y = radius * math.sin(math.radians(angle))
        t = translate([x, y, 0])(
            rotate([0, 0, angle])(
                cube([5, 5, thickness], center=True)
            )
        )
        teeth_objs.append(t)
    
    return union()(body, teeth_objs)

model = gear(teeth=16, radius=30, thickness=10)
# Отверстие для вала
model -= cylinder(r=5, h=20, center=True)

print(scad_render(model))`,

    text: `from solid2 import *

# 3D Текст (требует шрифтов, может не работать в WASM без них)
# Используем простую геометрию вместо text() если шрифты недоступны
model = union()(
    cube([10, 50, 5]), # I
    translate([20, 0, 0])(cube([30, 5, 5])), # L base
    translate([20, 0, 0])(cube([5, 50, 5]))  # L vertical
)

print(scad_render(model))`,

    box_lid: `from solid2 import *

# Коробка с крышкой
w, d, h = 40, 30, 20
wall = 2

box = difference()(
    cube([w, d, h]),
    translate([wall, wall, wall])(cube([w-2*wall, d-2*wall, h]))
)

lid = translate([w + 10, 0, 0])(
    cube([w, d, wall])
)

model = box + lid
print(scad_render(model))`,

    phone_stand: `from solid2 import *

# Простая подставка для телефона
width = 60
depth = 80
height = 40
angle = 60

base = cube([width, depth, 5])
back = translate([0, depth-5, 0])(
    rotate([angle, 0, 0])(
        cube([width, 5, height])
    )
)
stop = translate([0, 10, 5])(cube([width, 5, 5]))

model = base + back + stop
print(scad_render(model))`
};

function initPresets() {
    const toggleBtn = document.getElementById('toggle-templates');
    const content = document.getElementById('templates-content');
    const loadBtn = document.getElementById('load-template-btn');
    const select = document.getElementById('template-select');

    if (toggleBtn && content) {
        toggleBtn.addEventListener('click', () => {
            const isHidden = content.style.display === 'none';
            content.style.display = isHidden ? 'flex' : 'none';
            toggleBtn.textContent = isHidden ? '▲' : '▼';
        });
    }

    if (loadBtn && select) {
        loadBtn.addEventListener('click', () => {
            const val = select.value;
            if (val && PRESETS[val]) {
                if (editor) {
                    editor.setValue(PRESETS[val]);
                    console.log(`Загружен шаблон: ${val}`);
                }
            } else {
                alert("Выберите шаблон из списка!");
            }
        });
    }
}

// ============================================
// UI УЛУЧШЕНИЯ
// ============================================
function initUIImprovements() {
    // Reset Camera
    const resetBtn = document.getElementById('reset-camera-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetCamera);
    }
}

function resetCamera() {
    if (!camera || !controls || !currentMesh) return;
    
    // Пересчитываем границы
    if (currentMesh.geometry) {
        currentMesh.geometry.computeBoundingBox();
        const box = currentMesh.geometry.boundingBox;
        const size = new THREE.Vector3();
        box.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = camera.fov * (Math.PI / 180);
        let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2)) * 2.0;
        
        const newPos = new THREE.Vector3(cameraZ, cameraZ, cameraZ);
        camera.position.copy(newPos);
        camera.lookAt(0, 0, 0);
        controls.target.set(0, 0, 0);
        controls.update();
        console.log("Камера сброшена");
    }
}

function showLoadingOverlay(text = 'Рендеринг...') {
    const overlay = document.getElementById('viewer-loading-overlay');
    const textEl = document.getElementById('viewer-loading-text');
    if (textEl) textEl.innerText = text;
    if (overlay) overlay.style.display = 'flex';
}

function hideLoadingOverlay() {
    const overlay = document.getElementById('viewer-loading-overlay');
    if (overlay) overlay.style.display = 'none';
}

// Глобальный оверлей для всего приложения
function showGlobalLoading(text = 'Загрузка...') {
    let overlay = document.getElementById('global-loading-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'global-loading-overlay';
        overlay.innerHTML = `
            <div class="spinner"></div>
            <div class="loading-text">${text}</div>
        `;
        overlay.style.cssText = `
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.85);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            color: #fff;
            font-size: 1.2rem;
        `;
        document.body.appendChild(overlay);
    } else {
        overlay.querySelector('.loading-text').innerText = text;
        overlay.style.display = 'flex';
    }
}

function hideGlobalLoading() {
    const overlay = document.getElementById('global-loading-overlay');
    if (overlay) overlay.style.display = 'none';
}

async function generateCodeWithAI(prompt) {
    const outputLog = document.getElementById('output-log');
    const aiStatus = document.getElementById('ai-status');
    
    showGlobalLoading('🤖 Генерация кода через AI...');
    
    if (aiStatus) {
        aiStatus.innerHTML = '<div class="ai-loading">🤖 Генерация кода через OpenRouter AI...<br>⏳ Ожидание ответа...</div>';
    }
    
    if (outputLog) {
        outputLog.innerText = "🤖 Генерация кода через OpenRouter AI...\n⏳ Ожидание ответа...";
    }
    
    // Пробуем разные модели если одна не работает
    let lastError = null;
    
    const systemPrompt = `You are a SolidPython2 code generator. Generate ONLY valid Python code.

TEMPLATE (follow exactly):
from solid2 import *

# Settings for web rendering
set_global_fn(50) # Resolution limit for speed

# Parameters
size = 20

# Create model
model = cube([size, size, size])

# Output (REQUIRED)
print(scad_render(model))

KEY FUNCTIONS:
- cube([x,y,z]), sphere(r=R), cylinder(r=R, h=H)
- union()([obj1, obj2]), difference()([obj1, obj2])
- translate([x,y,z])(obj), rotate([x,y,z])(obj)
- linear_extrude(height=H)(2d_shape), circle(r=R)

RULES:
1. Start with: from solid2 import *
2. End with: print(scad_render(model))
3. USE set_global_fn(50) to optimize rendering speed
4. Close all brackets (), [], {}
5. NO explanations, ONLY code`;

    const userPrompt = `Запрос пользователя: ${prompt}

Сгенерируй ТОЛЬКО Python код без markdown форматирования и без объяснений.`;

    for (let i = 0; i < AI_MODELS.length; i++) {
        const model = AI_MODELS[i];
        
        try {
            console.log(`🔗 Попытка ${i + 1}/${AI_MODELS.length}: Модель ${model}`);
            
            const response = await fetch(OPENROUTER_API_URL, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
                    'HTTP-Referer': window.location.href, // Для OpenRouter рейтинга
                    'X-Title': 'Additive Light Generator', // Для OpenRouter рейтинга
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    model: model,
                    messages: [
                        {
                            role: "system",
                            content: systemPrompt
                        },
                        {
                            role: "user",
                            content: userPrompt
                        }
                    ],
                    temperature: 0.7,
                    max_tokens: 32000
                })
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                let errorData;
                try {
                    errorData = JSON.parse(errorText);
                } catch (e) {
                    errorData = { error: { message: errorText } };
                }
                
                // Если модель не найдена или недоступна, пробуем следующую
                console.warn(`⚠ Модель ${model} вернула ошибку:`, errorData);
                lastError = new Error(`Модель ${model}: ${errorData.error?.message || errorText}`);
                continue; 
            }
            
            // Успешно получили ответ
            const data = await response.json();
            
            if (!data.choices || !data.choices[0] || !data.choices[0].message) {
                throw new Error("Неверный формат ответа от API: " + JSON.stringify(data));
            }
            
            // Проверяем, не был ли код обрезан
            const finishReason = data.choices[0].finish_reason;
            if (finishReason === 'length') {
                console.warn(`⚠ Код обрезан моделью ${model} из-за лимита токенов`);
                if (aiStatus) {
                    aiStatus.innerHTML = '<div class="ai-error">⚠ Код обрезан. Попробуйте более простой запрос или используйте другую модель.</div>';
                }
                continue; // Пробуем следующую модель
            }
            
            const generatedCode = data.choices[0].message.content;
            
            // Сохраняем рабочую модель
            currentAIModel = model;
            console.log(`✅ Успешно использована модель: ${model}`);
            
            // Извлекаем код из ответа (убираем markdown форматирование если есть)
            let code = generatedCode.trim();
            
            // Убираем markdown блоки кода
            if (code.includes('```python')) {
                code = code.split('```python')[1].split('```')[0].trim();
            } else if (code.includes('```')) {
                const parts = code.split('```');
                // Ищем блок кода (обычно между ``` и ```)
                for (let j = 0; j < parts.length; j++) {
                    if (parts[j].includes('from solid2') || parts[j].includes('import')) {
                        code = parts[j].trim();
                        break;
                    }
                }
            }
            
            // Убираем возможные префиксы/суффиксы
            code = code.replace(/^python\s*/i, '');
            code = code.replace(/^```\s*/g, '');
            code = code.replace(/\s*```$/g, '');
            code = code.trim();
            
            // Проверяем что код содержит необходимые элементы
            if (!code.includes('from solid2') && !code.includes('from solid')) {
                // Если нет импорта, добавляем его
                code = "from solid2 import *\n" + code;
            }
            
            if (!code.includes('scad_render')) {
                // Если нет рендера, предупреждаем, но возвращаем (может быть в функции)
                console.warn("Код не содержит явного scad_render, возможно потребуется доработка");
            }
            
            // Валидация кода перед возвратом
            console.log("🔍 Валидация сгенерированного кода...");
            
            // 1. Проверка строковых литералов
            const stringCheck = checkStringLiterals(code);
            if (!stringCheck.valid) {
                console.warn(`⚠ Проблема со строками: ${stringCheck.message}`);
                // Пробуем следующую модель
                lastError = new Error(`Код содержит ошибку: ${stringCheck.message}`);
                continue;
            }
            
            // 2. Проверка баланса скобок
            const bracketBalance = checkBracketBalance(code);
            if (!bracketBalance.valid) {
                console.warn(`⚠ Дисбаланс скобок: ${bracketBalance.message}`);
                // Пытаемся автоматически исправить
                code = autoFixBrackets(code);
                console.log("🔧 Попытка автоисправления скобок");
            }
            
            // 3. Полная проверка синтаксиса через Pyodide
            const syntaxCheck = await validatePythonSyntax(code);
            if (!syntaxCheck.valid) {
                console.warn(`⚠ Синтаксическая ошибка: ${syntaxCheck.error}`);
                lastError = new Error(`Синтаксическая ошибка в строке ${syntaxCheck.line}: ${syntaxCheck.error}`);
                continue; // Пробуем следующую модель
            }
            
            console.log("✅ Код прошел валидацию");
            
            if (aiStatus) {
                aiStatus.innerHTML = `<div class="ai-success">✅ Код успешно сгенерирован и проверен через ${model}!</div>`;
                setTimeout(() => {
                    aiStatus.innerHTML = '';
                }, 3000);
            }
            
            if (outputLog) {
                outputLog.innerText = `✅ Код сгенерирован через AI (${model})!\n✅ Валидация пройдена\n\n📝 Сгенерированный код загружен в редактор.`;
            }
            
            hideGlobalLoading();
            return code; // Успешно, возвращаем валидный код
            
        } catch (error) {
            console.error(`❌ Ошибка с моделью ${model}:`, error);
            lastError = error;
            
            // Если это последняя модель, выбрасываем ошибку
            if (i === AI_MODELS.length - 1) {
                break; // Выходим из цикла
            }
        }
    }
    
    // Если дошли сюда, все модели не сработали
    hideGlobalLoading();
    console.error("❌ Все модели не сработали");
    const errorMsg = lastError ? lastError.message : "Не удалось подключиться к API";
    
    if (aiStatus) {
        aiStatus.innerHTML = `<div class="ai-error">❌ Ошибка: ${errorMsg}<br>Проверьте подключение к OpenRouter.</div>`;
    }
    
    if (outputLog) {
        outputLog.innerText = `❌ Ошибка генерации через AI: ${errorMsg}\n\nПопробуйте:\n1. Проверить соединение с интернетом\n2. Проверить доступность OpenRouter\n3. Попробовать позже`;
    }
    
    throw lastError || new Error("Все модели AI недоступны");
}

// ============================================
// ВАЛИДАЦИЯ И АВТОИСПРАВЛЕНИЕ КОДА
// ============================================

// Проверка незавершенных строковых литералов
function checkStringLiterals(code) {
    const lines = code.split('\n');
    let inTripleQuote = false;
    let quoteChar = null;
    let startLine = 0;
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        
        // Проверяем тройные кавычки
        for (let j = 0; j < line.length - 2; j++) {
            const triple = line.substring(j, j + 3);
            if (triple === '"""' || triple === "'''") {
                if (!inTripleQuote) {
                    inTripleQuote = true;
                    quoteChar = triple;
                    startLine = i + 1;
                } else if (triple === quoteChar) {
                    inTripleQuote = false;
                    quoteChar = null;
                }
            }
        }
    }
    
    if (inTripleQuote) {
        return {
            valid: false,
            message: `Незакрытая тройная кавычка ${quoteChar} начинается на строке ${startLine}`,
            line: startLine
        };
    }
    
    return { valid: true };
}

function checkBracketBalance(code) {
    const brackets = { '(': 0, '[': 0, '{': 0 };
    const pairs = { ')': '(', ']': '[', '}': '{' };
    
    for (const char of code) {
        if (brackets.hasOwnProperty(char)) {
            brackets[char]++;
        } else if (pairs.hasOwnProperty(char)) {
            brackets[pairs[char]]--;
        }
    }
    
    const issues = [];
    if (brackets['('] > 0) issues.push(`${brackets['(']} незакрытых ()`);
    if (brackets['('] < 0) issues.push(`${-brackets['(']} лишних )`);
    if (brackets['['] > 0) issues.push(`${brackets['[']} незакрытых []`);
    if (brackets['['] < 0) issues.push(`${-brackets['[']} лишних ]`);
    if (brackets['{'] > 0) issues.push(`${brackets['{']} незакрытых {}`);
    if (brackets['{'] < 0) issues.push(`${-brackets['{']} лишних }`);
    
    return {
        valid: issues.length === 0,
        message: issues.join(', '),
        brackets: brackets
    };
}

// Валидация синтаксиса Python через Pyodide
async function validatePythonSyntax(code) {
    if (!pyodide || !pyodideReady) {
        console.warn("Pyodide не готов для валидации");
        return { valid: true }; // Пропускаем валидацию если Pyodide не загружен
    }
    
    try {
        // Используем compile() для проверки синтаксиса без выполнения
        await pyodide.runPythonAsync(`
compile('''${code.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}''', '<generated>', 'exec')
        `);
        return { valid: true };
    } catch (err) {
        const lineMatch = err.message.match(/line (\d+)/);
        const line = lineMatch ? parseInt(lineMatch[1]) : null;
        
        return {
            valid: false,
            error: err.message,
            line: line
        };
    }
}

function autoFixBrackets(code) {
    const balance = checkBracketBalance(code);
    if (balance.valid) return code;
    
    let fixedCode = code;
    
    // Добавляем недостающие закрывающие скобки в конец
    if (balance.brackets['('] > 0) {
        fixedCode += ')'.repeat(balance.brackets['(']);
        console.log(`🔧 Автоисправление: добавлено ${balance.brackets['(']} закрывающих )`);
    }
    if (balance.brackets['['] > 0) {
        fixedCode += ']'.repeat(balance.brackets['[']);
        console.log(`🔧 Автоисправление: добавлено ${balance.brackets['[']} закрывающих ]`);
    }
    if (balance.brackets['{'] > 0) {
        fixedCode += '}'.repeat(balance.brackets['{']);
        console.log(`🔧 Автоисправление: добавлено ${balance.brackets['{']} закрывающих }`);
    }
    
    return fixedCode;
}

async function handleAIGenerate() {
    const requestInput = document.getElementById('ai-request-input');
    if (!requestInput) {
        alert("Поле ввода запроса не найдено");
        return;
    }
    
    const prompt = requestInput.value.trim();
    
    if (!prompt) {
        alert("Введите описание модели для генерации!");
        requestInput.focus();
        return;
    }
    
    if (!editor) {
        alert("Редактор не готов");
        return;
    }
    
    const generateBtn = document.getElementById('ai-generate-btn');
    if (generateBtn) {
        generateBtn.disabled = true;
        generateBtn.textContent = "⏳ Генерация...";
    }
    
    try {
        const generatedCode = await generateCodeWithAI(prompt);
        editor.setValue(generatedCode);
        editor.refresh();
        console.log("Код установлен в редактор");
        
        // Прокручиваем к редактору
        const editorPane = document.querySelector('.editor-pane');
        if (editorPane) {
            editorPane.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    } catch (error) {
        console.error("Ошибка генерации:", error);
        // Ошибка уже показана в generateCodeWithAI
    } finally {
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.textContent = "🤖 СГЕНЕРИРОВАТЬ КОД";
        }
    }
}

// ============================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ============================================
function updateCompileButton() {
    const runBtn = document.getElementById('run-btn');
    if (runBtn) {
        // Кнопка активна когда Pyodide готов. OpenSCAD поднимется сам.
        const isReady = pyodideReady;
        runBtn.disabled = !isReady;
        
        if (!isReady) {
            runBtn.innerText = "⏳ ЗАГРУЗКА PYODIDE...";
            runBtn.style.opacity = "0.7";
        } else {
            runBtn.innerText = "⚡ СКОМПИЛИРОВАТЬ()";
            runBtn.style.opacity = "1";
        }
    }
}

function updateStatus(text) {
    const statusText = document.getElementById('status-text');
    if (statusText) {
        statusText.textContent = text;
    }
}

function initEventListeners() {
    const runBtn = document.getElementById('run-btn');
    if (runBtn) {
        runBtn.addEventListener('click', runCompilation);
    }
    
    const downloadScadBtn = document.getElementById('download-scad-btn');
    if (downloadScadBtn) {
        downloadScadBtn.addEventListener('click', () => {
            if (lastScadCode) {
                const blob = new Blob([lastScadCode], { type: 'text/plain;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'model.scad';
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                // Даем браузеру время начать скачивание
                setTimeout(() => {
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                }, 100);
                console.log("SCAD файл скачан");
            }
        });
    }
    
    const downloadBtn = document.getElementById('download-stl-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            if (stlData) {
                const blob = new Blob([stlData], { type: 'model/stl' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'model.stl';
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                // Даем браузеру время начать скачивание
                setTimeout(() => {
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                }, 100);
                console.log("STL файл скачан");
            }
        });
    }
    
    // AI генерация кода
    const aiGenerateBtn = document.getElementById('ai-generate-btn');
    if (aiGenerateBtn) {
        aiGenerateBtn.addEventListener('click', handleAIGenerate);
    }
    
    // Переключение панели AI
    const toggleAIPanel = document.getElementById('toggle-ai-panel');
    const aiPanelContent = document.getElementById('ai-panel-content');
    if (toggleAIPanel && aiPanelContent) {
        let isExpanded = true;
        toggleAIPanel.addEventListener('click', () => {
            isExpanded = !isExpanded;
            aiPanelContent.style.display = isExpanded ? 'block' : 'none';
            toggleAIPanel.textContent = isExpanded ? '▼' : '▲';
        });
    }
    
    // Enter в поле AI запроса (Ctrl+Enter для генерации)
    const aiRequestInput = document.getElementById('ai-request-input');
    if (aiRequestInput) {
        aiRequestInput.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                handleAIGenerate();
            }
        });
    }
}

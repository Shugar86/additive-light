// === НАСТРОЙКИ ===
$fn = 120; // Качество

// === ПАРАМЕТРЫ МОДЕЛИ ===
main_width = 40;       // Общая ширина
main_height = 60;      // Общая высота
main_depth = 25;       // Глубина/выпуклость

lip_openness = 4;      // Насколько "раскрыты" губы (ширина щели)
lip_depth = 20;        // Глубина основной щели

inner_lip_height = 25; // Высота малых губ
inner_lip_twist = 45;  // Скрученность малых губ

clit_size = 2.5;       // Размер головки клитора

canal_depth = 50;      // Глубина канала
canal_radius = 12;

// === ГЕНЕРАЦИЯ МОДЕЛИ ===

module vulva_realistic() {
    
    // Используем difference() как основной инструмент для "лепки"
    difference() {
        
        // 1. ОСНОВА (Лобковый бугорок и большие губы)
        // Создаем мягкую, выпуклую основу. Щели вырежутся позже.
        hull() {
            translate([0, 0, -main_depth*0.5])
                scale([main_width/40, main_height/50, main_depth/30])
                sphere(r = 30);
            
            translate([0, main_height*0.3, -main_depth*0.2])
                sphere(r = main_width * 0.5);
        }
        
        // --- ОБЪЕКТЫ ДЛЯ ВЫЧИТАНИЯ ---
        
        // 2. РЕЗАК ДЛЯ ОСНОВНОЙ ЩЕЛИ (Формирует большие губы)
        // Этот объект "прорежет" основу и создаст главную складку.
        translate([0, main_height * 0.1, -main_depth])
            linear_extrude(height = main_depth * 2, scale = 1.1)
                polygon(points=[
                    [-lip_openness/2, 0],
                    [0, -10], // Сужение книзу
                    [lip_openness/2, 0],
                    [lip_openness*1.5, main_height*0.8], // Расширение кверху
                    [-lip_openness*1.5, main_height*0.8]
                ]);
        
        // 3. РЕЗАК ДЛЯ КАНАЛА (Вход во влагалище)
        translate([0, 10, -canal_depth * 0.8])
            rotate([80, 0, 0])
            cylinder(h = canal_depth, r1 = canal_radius, r2 = canal_radius*0.5, center=true);
    }
    
    // --- ОБЪЕКТЫ ДЛЯ ДОБАВЛЕНИЯ ---
    
    // 4. МАЛЫЕ ГУБЫ И КЛИТОР
    // Они добавляются внутрь уже вырезанной щели.
    union() {
        // Размещаем их чуть глубже
        translate([0, main_height*0.3, -lip_depth*0.2]) {
            
            // Левая малая губа
            inner_lip();
            
            // Правая малая губа (зеркальная копия)
            mirror([1, 0, 0])
                inner_lip();

            // 5. КЛИТОР И КАПЮШОН
            translate([0, inner_lip_height * 1.1, 2]) {
                // Головка клитора
                sphere(r = clit_size);
                
                // Капюшон (с помощью hull)
                hull() {
                    sphere(r = clit_size * 1.1);
                    // Точки крепления к малым губам
                    translate([-3, -5, -2]) sphere(r=1);
                    translate([3, -5, -2]) sphere(r=1);
                }
            }
        }
    }
}

// Модуль для создания одной малой губы
module inner_lip() {
    translate([lip_openness/2, 0, 0])
        rotate([0, -10, 0])
        linear_extrude(height = inner_lip_height, twist
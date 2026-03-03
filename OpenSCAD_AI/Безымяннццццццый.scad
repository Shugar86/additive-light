// === НАСТРОЙКИ ДЕТАЛИЗАЦИИ ===
$fn = 100; // Высокая детализация для плавных складок

// === ПАРАМЕТРЫ (Размеры в мм) ===
overall_length = 80;    // Общая длина
overall_width = 50;     // Общая ширина
depth = 15;             // Глубина рельефа

// Размеры деталей
majora_thickness = 12;  // Толщина больших губ
minora_thickness = 5;   // Толщина малых губ
clit_size = 4;          // Размер клитора
canal_depth = 40;       // Глубина канала

module vulva_realistic() {
    difference() {
        union() {
            // 1. ОСНОВА (Mons pubis - лобок)
            // Сплюснутая сфера, создающая общий холмик
            translate([0, overall_length * 0.1, -depth * 0.5])
                scale([overall_width * 0.9, overall_length, depth])
                sphere(r = 1);

            // 2. БОЛЬШИЕ ГУБЫ (Labia Majora)
            // Используем mirror для создания симметричной пары
            mirror_x() {
                hull() {
                    // Верхняя точка (сходятся у лобка)
                    translate([2, overall_length * 0.45, 0]) 
                        sphere(r = majora_thickness * 0.6);
                    // Центральная точка (самая широкая часть)
                    translate([overall_width * 0.25, 0, majora_thickness * 0.2]) 
                        scale([1, 1.5, 0.8]) sphere(r = majora_thickness);
                    // Нижняя точка (сходятся у промежности)
                    translate([3, -overall_length * 0.4, -2]) 
                        sphere(r = majora_thickness * 0.7);
                }
            }

            // 3. МАЛЫЕ ГУБЫ (Labia Minora)
            mirror_x() {
                hull() {
                    // Вершина (Капюшон клитора)
                    translate([clit_size * 0.5, overall_length * 0.25, majora_thickness * 0.5]) 
                        sphere(r = minora_thickness);
                    // Центр (выступающая часть)
                    translate([overall_width * 0.12, -overall_length * 0.05, majora_thickness * 0.3]) 
                        scale([0.8, 1, 1]) sphere(r = minora_thickness);
                    // Низ (слияние)
                    translate([overall_width * 0.05, -overall_length * 0.3, 0]) 
                        sphere(r = minora_thickness * 0.5);
                }
            }

            // 4. КЛИТОР (Glans clitoridis)
            // Маленькая сфера, чуть выглядывающая из-под соединения малых губ
            translate([0, overall_length * 0.23, majora_thickness * 0.5 - clit_size * 0.3])
                scale([1, 0.8, 1]) // Чуть сплюснут
                sphere(r = clit_size);
        }

        // --- ВЫЧИТАНИЕ (Негативное пространство) ---

        // 5. ВАГИНАЛЬНЫЙ КАНАЛ (Introitus)
        // Канал уходит внутрь и немного назад
        translate([0, -overall_length * 0.1, 0])
        rotate([-15, 0, 0]) // Угол наклона канала
        scale([0.6, 1.2, 1]) // Овальное сечение
        cylinder(h = canal_depth, r = overall_width * 0.15, center=false);

        // 6. УРЕТРА (Urethral opening)
        // Маленькое отверстие между клитором и каналом
        translate([0, overall_length * 0.08, majora_thickness * 0.2])
        cylinder(h = 10, r = 2, center=true);

        // 7. СГЛАЖИВАНИЕ ЩЕЛИ (Вход в преддверие)
        // Делаем плавный переход между губами и каналом
        hull() {
            translate([0, overall_length * 0.2, majora_thickness * 0.5]) sphere(r=1);
            translate([0, -overall_length * 0.3, majora_thickness * 0.1]) sphere(r=1);
            translate([0, -overall_length * 0.1, -canal_depth * 0.2]) sphere(r=overall_width * 0.15);
        }
    }
}

// Вспомогательная функция для симметрии
module mirror_x() {
    children();
    mirror([1, 0, 0]) children();
}

// Рендер
vulva_realistic();
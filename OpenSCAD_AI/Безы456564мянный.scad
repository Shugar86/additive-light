// === НАСТРОЙКИ ===
$fn = 100;              // Качество (детализация)

// Размеры
ball_radius = 20;       // Размер яиц
shaft_base_width = 16;  // Толщина ствола снизу
shaft_top_width = 15;   // Толщина ствола сверху (чуть уже для реализма)
shaft_length = 90;      // Высота
curve_amount = 20;      // Изгиб ствола (смещение головки по оси X)

head_radius = 22;       // Размер головки
head_flatness = 0.7;    // Сплюснутость головки (меньше 1 = более плоская)

module penis_v2() {
    
    // Координаты начала и конца ствола
    base_point = [0, 0, ball_radius * 0.5]; 
    top_point = [curve_amount, 0, shaft_length];

    // 1. ОСНОВАНИЕ (Яички)
    // Объединяем их в одну группу
    union() {
        // Левое
        translate([-ball_radius * 0.9, 0, 0]) 
            sphere(r = ball_radius);
        // Правое
        translate([ball_radius * 0.9, 0, 0]) 
            sphere(r = ball_radius);
        
        // Центральная "подушка", чтобы ствол не висел в воздухе
        translate([0, 0, ball_radius * 0.2])
            sphere(r = ball_radius * 0.8);
    }

    // 2. СТВОЛ (Метод HULL)
    // Мы создаем две сферы (внизу и вверху) и обтягиваем их кожей.
    // Это гарантирует, что разрывов быть не может.
    hull() {
        // Нижняя точка ствола (внутри яиц)
        translate(base_point)
            sphere(r = shaft_base_width);

        // Верхняя точка ствола (вход в головку)
        translate(top_point)
            sphere(r = shaft_top_width);
    }

    // 3. ГОЛОВКА
    // Размещаем её точно в верхней точке ствола
    translate(top_point)
    // Поворачиваем головку в сторону изгиба
    rotate([0, curve_amount * 0.5, 0]) 
    {
        difference() {
            // Сама головка (сплюснутая сфера)
            union() {
                scale([1, 1, head_flatness])
                    sphere(r = head_radius);
                
                // Добавляем скругление снизу головки (переход в ствол)
                translate([0,0, -head_radius * 0.3])
                    sphere(r = head_radius * 0.6);
            }

            // Отрезаем нижнюю лишнюю часть, чтобы создать "юбочку"
            translate([0, 0, -head_radius])
                cube([head_radius * 3, head_radius * 3, head_radius], center=true);
        }
    }
}

// Генерация
penis_v2();
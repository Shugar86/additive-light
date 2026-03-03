# ИСПРАВЛЕННЫЙ КОД ДЛЯ ГЕНЕРАТОРА
# Используйте этот код в генераторе вместо оригинального

from solid2 import *

def generate_vase():
    # --- НАСТРОЙКИ ВАЗЫ ---
    vase_height = 150       # Высота вазы в мм
    base_radius = 40        # Радиус дна
    wall_thickness = 2      # Толщина стенок
    twist_degrees = 90      # На сколько градусов закрутить вазу
    top_scale = 1.2         # Масштаб верха (1.0 = цилиндр, 1.5 = расширение)
    sides = 6               # Количество граней (6 = гайка, 60 = круг)
    
    # Качество рендера (количество слоев по высоте)
    # Чем больше, тем более гладкая спираль, но дольше рендер
    slices_count = 150      

    # 1. Создаем внешнюю форму
    # Берем 2D круг (или многоугольник) и вытягиваем его (extrude) с поворотом и масштабом
    outer_shape = linear_extrude(
        height=vase_height, 
        twist=twist_degrees, 
        scale=top_scale, 
        slices=slices_count
    )(
        circle(r=base_radius, _fn=sides)
    )

    # 2. Создаем внутреннюю полость
    # Она чуть меньше радиусом и чуть выше (чтобы прорезать верх), но начинается выше дна
    inner_shape = linear_extrude(
        height=vase_height + 10, # Делаем чуть выше, чтобы точно прорезать крышку
        twist=twist_degrees, 
        scale=top_scale, 
        slices=slices_count
    )(
        circle(r=base_radius - wall_thickness, _fn=sides)
    )

    # Сдвигаем внутреннюю часть вверх, чтобы оставить дно
    # Используем translate вместо .up() для совместимости
    inner_shape = translate([0, 0, wall_thickness])(inner_shape)

    # 3. Вычитаем внутреннюю часть из внешней
    final_vase = difference()([outer_shape, inner_shape])

    return final_vase

# ГЛАВНАЯ ЧАСТЬ - ОБЯЗАТЕЛЬНО ДЛЯ ГЕНЕРАТОРА
model = generate_vase()

# ВАЖНО: Используем print(scad_render()) вместо save_as_scad()
# Это выводит SCAD код в stdout, который перехватывается генератором
print(scad_render(model))


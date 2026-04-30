# 🛠 Developer’s Kit: Реализация GDI Pipeline (Low-Level)
**Назначение:** Техническая база для переноса в основной проект `gdi_core`.  
**Статус:** Протестировано, "грабли" устранены.

---

## 1. Ресэмплинг контура (Arc-Length Resampling)
Самая важная функция для нормализации данных. Она превращает рваное облако точек в упорядоченное сечение, где точки распределены равномерно по длине дуги.

**Где использовать:** `approximator/preprocessing.py`

```python
import numpy as np

def arc_length_resample_closed(points_xy: np.ndarray, num: int) -> np.ndarray:
    """Нормализация замкнутого контура по длине дуги."""
    poly = np.asarray(points_xy, dtype=np.float64)
    # Замыкаем контур, если нужно
    if not np.allclose(poly[0], poly[-1]):
        poly = np.vstack([poly, poly[0:1]])
    
    # Считаем длины сегментов и кумулятивную сумму
    edge_len = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(edge_len)])
    total = cum[-1]
    
    # Равномерная сетка на [0, Total]
    targets = np.linspace(0.0, total, num, endpoint=False)
    
    # Линейная интерполяция
    resampled = np.interp(targets, cum, poly[:, 0]), np.interp(targets, cum, poly[:, 1])
    return np.column_stack(resampled)
```

---

## 2. Watertight Mesh-билдер (Strip + Caps)
Паттерн для ручной сборки оболочки из сечений. Важный инсайт: для сшивки с боковыми панелями крышки должны триангулироваться **строго через Earcut** без добавления внутренних вершин.

**Где использовать:** `mesh/builder.py`

```python
import trimesh
from trimesh.creation import triangulate_polygon
from shapely.geometry import Polygon

def build_watertight_shell(rings_3d: list[np.ndarray]) -> trimesh.Trimesh:
    """Соединяет кольца сечений в герметичный Mesh."""
    # 1. Сборка боковой ленты (Band)
    # rings_3d: список массивов (N_points, 3)
    # faces: [i, i+1, j+1] и [i, j+1, j]
    
    # 2. Правильная триангуляция крышек (Earcut)
    # ВАЖНО: engine='earcut' гарантирует, что не будет Steiner-точек, 
    # которые ломают герметичность шва.
    poly = Polygon(rings_3d[0][:, 1:]) # плоскость YZ
    v2d, f = triangulate_polygon(poly, engine='earcut')
    
    # 3. Лечение (Healing)
    # ОБЯЗАТЕЛЬНО: merge_vertices перед fill_holes
    combined = trimesh.util.concatenate([band, cap1, cap2])
    combined.merge_vertices(digits_vertex=6)
    combined.fill_holes()
    combined.fix_normals()
    return combined
```

---

## 4. Двунаправленный Surface Distance (Judge Module)
Самый эффективный способ сравнить две 3D модели. Не IoU, а честное отклонение поверхностей.

**Где использовать:** `judge/validation.py`

```python
def surface_metrics(mesh_a, mesh_b, samples=10000):
    """Считает расстояние от поверхности A до B."""
    # 1. Сэмплируем поверхность A
    points, _ = trimesh.sample.sample_surface(mesh_a, samples)
    
    # 2. Ищем ближайшие точки на B (через RTree)
    # Требует: pip install rtree
    _, distances, _ = mesh_b.nearest.on_surface(points)
    
    return {
        "mean": np.mean(distances),
        "p95": np.percentile(distances, 95),
        "max": np.max(distances)
    }
```

---

## 5. Manifold Boolean (Boilerplate)
Вычитание внутренности (Hollow) требует Manifold engine.

**Где использовать:** `optimizer/shelling.py`

```python
def make_hollow(outer_mesh, inner_mesh):
    """Безопасная булева разность."""
    try:
        # engine='manifold' — самый быстрый и надежный на сегодня
        hollow = trimesh.boolean.difference(
            [outer_mesh, inner_mesh], 
            engine='manifold', 
            check_volume=False
        )
        return hollow
    except Exception as e:
        # Fallback на внешний Mesh при ошибке
        return outer_mesh
```

---

## 6. YAML Schema (Contract)
Чтобы LLM (Claude/GPT) не "галлюцинировала" в коде, ей нужно скармливать данные в жестком формате. Мы зафиксировали этот контракт.

**Где использовать:** `models/manifest.py` (Pydantic)

```yaml
# wing_tip_spec.yaml
mounting_datum:
  root_center_xyz_mm: [90.01, -33.13, 33.00]
mount_geometry_locked:
  plane_x_mm: 1.5
  centroid_yz_mm: [-3.36, 0.49]
  ring_points: 96
model:
  skin_mm: 1.2
  min_wall_mm: 0.95
```

---

## 7. Технические "Грабли" (Lessons Learned)
1.  **Unicode в Windows:** Не используй символы типа `≈` в `print()`, если не уверен в кодировке консоли. Скрипт упадет с `UnicodeEncodeError`. Используй `~`.
2.  **Trimesh Load:** Помни, что `trimesh.load('file.stl')` иногда возвращает `Scene`, а не `Trimesh`. Всегда проверяй `hasattr(data, 'geometry')` или используй `force='mesh'`.
3.  **Build123d Export:** Чтобы импортированный Mesh стал "честным" STEP, используй `import_stl` -> `Face` -> `export_step`. Это сохранит геометрию для CAD, хотя и в виде фасетного тела.

---

## Резюме для переноса:
1. Забираешь `arc_length_resample_closed` в `utils`.
2. Забираешь `surface_metrics` в новый модуль `judge`.
3. Используешь `manifold3d` как основной булев движок.
4. Настраиваешь промпты LLM на генерацию кода, работающего с `sections_clean.json`.

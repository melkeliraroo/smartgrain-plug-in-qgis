from pathlib import Path

import numpy as np
from qgis.core import (
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsProject,
    QgsRasterLayer,
)


class LineGenerator:
    """Gera linhas de plantio/pulverização acompanhando curvas de nível."""

    def __init__(self):
        self.dem_layer = None
        self.field_layer = None
        self.spacing = 10.0  # metros
        self.smoothing_strength = 0.5  # 0-1

    def set_dem_layer(self, dem_path):
        """Carrega camada DEM (raster de elevação)."""
        if not dem_path:
            return False

        self.dem_layer = QgsRasterLayer(dem_path, "dem_temporal")
        return self.dem_layer.isValid()

    def set_field_layer(self, field_layer):
        """Define camada de talhões."""
        self.field_layer = field_layer
        return field_layer is not None

    def set_spacing(self, spacing):
        """Define espaçamento entre linhas em metros."""
        self.spacing = max(1.0, float(spacing))

    def set_smoothing_strength(self, strength):
        """Define intensidade de suavização (0-1)."""
        self.smoothing_strength = max(0.0, min(1.0, float(strength)))

    def generate_lines_for_field(self, field_feature):
        """Gera linhas paralelas para um talhão."""
        if not self.field_layer or not field_feature.geometry():
            return []

        geometry = field_feature.geometry()
        bbox = geometry.boundingBox()

        # Determinar direção de curva de nível
        direction = self._estimate_contour_direction(geometry)

        # Gerar linhas paralelas
        lines = self._generate_parallel_lines(geometry, direction)

        return lines

    def _estimate_contour_direction(self, geometry):
        """Estima a direção de curva de nível usando DEM."""
        if not self.dem_layer:
            # Fallback: usar direção aleatória
            return {"angle": 45.0, "method": "fallback"}

        # Calcular gradiente médio dentro do talhão
        bbox = geometry.boundingBox()
        center_x = (bbox.xMinimum() + bbox.xMaximum()) / 2
        center_y = (bbox.yMinimum() + bbox.yMaximum()) / 2

        try:
            point = QgsPoint(center_x, center_y)
            value, ok = self.dem_layer.dataProvider().sample(point, 1)

            if ok:
                # Calcular gradiente em pontos adjacentes
                offset = 10.0  # metros
                p_east = QgsPoint(center_x + offset, center_y)
                p_north = QgsPoint(center_x, center_y + offset)

                val_east, _ = self.dem_layer.dataProvider().sample(p_east, 1)
                val_north, _ = self.dem_layer.dataProvider().sample(p_north, 1)

                # Ângulo perpendicular ao gradiente
                gradient_angle = np.arctan2(val_north - value, val_east - value)
                contour_angle = np.degrees(gradient_angle + np.pi / 2)

                return {
                    "angle": float(contour_angle % 360),
                    "method": "dem",
                    "gradient": float(gradient_angle),
                }
        except Exception:
            pass

        return {"angle": 45.0, "method": "fallback"}

    def _generate_parallel_lines(self, geometry, direction):
        """Gera linhas paralelas perpendiculares à direção."""
        lines = []
        bbox = geometry.boundingBox()

        angle_rad = np.radians(direction["angle"])
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        # Calcular distância total perpendicular à direção
        min_x, max_x = bbox.xMinimum(), bbox.xMaximum()
        min_y, max_y = bbox.yMinimum(), bbox.yMaximum()

        # Projetar canto no eixo perpendicular
        corners = [
            (min_x, min_y),
            (max_x, min_y),
            (max_x, max_y),
            (min_x, max_y),
        ]

        projections = [
            x * cos_a + y * sin_a for x, y in corners
        ]

        proj_min = min(projections)
        proj_max = max(projections)

        # Gerar linhas com espaçamento
        current_proj = proj_min
        line_count = 0

        while current_proj <= proj_max and line_count < 1000:  # limite de segurança
            line = self._create_line_at_projection(
                current_proj,
                direction["angle"],
                geometry,
            )

            if line and len(line) >= 2:
                lines.append(line)

            current_proj += self.spacing
            line_count += 1

        return lines

    def _create_line_at_projection(self, projection, angle, geometry):
        """Cria uma linha na projeção dada."""
        angle_rad = np.radians(angle)

        # Direção da linha (perpendicular à projeção)
        line_angle = angle_rad + np.pi / 2
        line_cos = np.cos(line_angle)
        line_sin = np.sin(line_angle)

        bbox = geometry.boundingBox()
        min_x, max_x = bbox.xMinimum(), bbox.xMaximum()
        min_y, max_y = bbox.yMinimum(), bbox.yMaximum()

        # Pontos extremos da linha
        coords = [
            (min_x + t * (max_x - min_x), min_y + t * (max_y - min_y))
            for t in np.linspace(0, 1, 100)
        ]

        # Encontrar interseções com o talhão
        line_points = []

        for i in range(len(coords) - 1):
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]

            p1 = QgsPoint(x1, y1)
            p2 = QgsPoint(x2, y2)
            line_seg = QgsGeometry.fromPolyline([p1, p2])

            if geometry.intersects(line_seg):
                intersection = geometry.intersection(line_seg)

                if intersection.type() == 1:  # LineString
                    points = intersection.asPolyline()
                    line_points.extend(points)

        if line_points:
            return line_points

        return None

    def smooth_line(self, points, strength=None):
        """Suaviza uma linha usando Catmull-Rom."""
        if strength is None:
            strength = self.smoothing_strength

        if len(points) < 4:
            return points

        try:
            coords = np.array([(p.x(), p.y()) for p in points])

            smoothed = self._catmull_rom_spline(coords, strength)

            return [QgsPoint(x, y) for x, y in smoothed]
        except Exception:
            return points

    def _catmull_rom_spline(self, points, strength):
        """Implementa interpolação Catmull-Rom."""
        if len(points) < 4:
            return points

        result = []

        for i in range(1, len(points) - 2):
            p0 = points[i - 1]
            p1 = points[i]
            p2 = points[i + 1]
            p3 = points[i + 2]

            # Número de pontos intermediários baseado em intensidade
            steps = int(max(2, 5 * strength))

            for t_frac in np.linspace(0, 1, steps, endpoint=(i == len(points) - 3)):
                t = t_frac
                t2 = t * t
                t3 = t2 * t

                # Fórmula Catmull-Rom
                q = 0.5 * (
                    (2.0 * p1)
                    + (-p0 + p2) * t
                    + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                    + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
                )

                result.append(q)

        result.append(points[-1])
        return result

    def lines_to_dict(self, lines):
        """Converte linhas para dicionário para salvar."""
        data = []

        for i, line_points in enumerate(lines):
            coords = [(p.x(), p.y()) for p in line_points]
            data.append({
                "id": i,
                "coordinates": coords,
            })

        return data

    def dict_to_lines(self, data):
        """Reconstrói linhas a partir de dicionário."""
        lines = []

        for line_data in data:
            points = [
                QgsPoint(x, y) for x, y in line_data.get("coordinates", [])
            ]
            if points:
                lines.append(points)

        return lines

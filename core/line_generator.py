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
        """Cria uma linha na projeção dada e a intersecta com o talhão.

        Retorna o maior segmento (lista de QgsPoint) resultante da interseção.
        """
        angle_rad = np.radians(angle)

        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        # ponto base na linha definida por 'projection'
        x0 = projection * cos_a
        y0 = projection * sin_a

        # direção da linha (perpendicular ao eixo de projeção)
        dir_x = np.cos(angle_rad + np.pi / 2)
        dir_y = np.sin(angle_rad + np.pi / 2)

        bbox = geometry.boundingBox()
        diag = ((bbox.width() ** 2 + bbox.height() ** 2) ** 0.5) * 2.0

        p1 = QgsPoint(x0 - dir_x * diag, y0 - dir_y * diag)
        p2 = QgsPoint(x0 + dir_x * diag, y0 + dir_y * diag)

        line_geom = QgsGeometry.fromPolyline([p1, p2])
        try:
            intersection = geometry.intersection(line_geom)
        except Exception:
            return None

        if intersection is None or intersection.isEmpty():
            return None

        segments = []

        # Multi-part or single polyline
        try:
            if intersection.isMultipart():
                multi = intersection.asMultiPolyline()
                for part in multi:
                    pts = [QgsPoint(pt.x(), pt.y()) for pt in part]
                    if len(pts) >= 2:
                        segments.append(pts)
            else:
                poly = intersection.asPolyline()
                if poly and len(poly) >= 2:
                    pts = [QgsPoint(pt.x(), pt.y()) for pt in poly]
                    segments.append(pts)
        except Exception:
            # fallback: try asWkt parsing or ignore
            return None

        if not segments:
            return None

        # escolher o segmento mais longo (por comprimento geométrico)
        def seg_length(pts):
            length = 0.0
            for i in range(1, len(pts)):
                dx = pts[i].x() - pts[i - 1].x()
                dy = pts[i].y() - pts[i - 1].y()
                length += (dx * dx + dy * dy) ** 0.5
            return length

        longest = max(segments, key=seg_length)
        return longest

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

    def smooth_line_extended(self, points, strength=None, method='catmull', iterations=3, max_points=None):
        """Suaviza uma linha usando o método especificado.

        method: 'catmull' | 'chaikin'
        iterations: número de iterações para Chaikin
        max_points: se definido, reduz o número de amostras finais para esse valor
        """
        if strength is None:
            strength = self.smoothing_strength

        if method == 'chaikin':
            # Chaikin corner-cutting
            try:
                pts = np.array([(p.x(), p.y()) for p in points])
            except Exception:
                pts = np.array(points)

            for _ in range(max(1, int(iterations))):
                if len(pts) < 2:
                    break
                new_pts = []
                for i in range(len(pts) - 1):
                    p0 = pts[i]
                    p1 = pts[i + 1]
                    Q = 0.75 * p0 + 0.25 * p1
                    R = 0.25 * p0 + 0.75 * p1
                    new_pts.append(Q)
                    new_pts.append(R)
                pts = np.array(new_pts)

            if max_points and len(pts) > max_points:
                idx = np.linspace(0, len(pts) - 1, max_points).astype(int)
                pts = pts[idx]

            return [QgsPoint(float(x), float(y)) for x, y in pts]

        # fallback para Catmull-Rom
        return self.smooth_line(points, strength)

    def _catmull_rom_spline(self, points, strength):
        """Implementa interpolação Catmull-Rom."""
        if len(points) < 4:
            return points

        # Ajuste da resolução baseado no tamanho da linha e intensidade
        # calcula comprimento total aproximado
        total_len = 0.0
        for i in range(1, len(points)):
            dx = points[i][0] - points[i - 1][0]
            dy = points[i][1] - points[i - 1][1]
            total_len += (dx * dx + dy * dy) ** 0.5

        # base steps on length and strength, bounded
        base_steps = int(max(3, min(200, int(0.1 * total_len * (0.5 + strength)))))

        result = []
        for i in range(1, len(points) - 2):
            p0 = points[i - 1]
            p1 = points[i]
            p2 = points[i + 1]
            p3 = points[i + 2]

            for t_frac in np.linspace(0, 1, base_steps, endpoint=(i == len(points) - 3)):
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

    def smooth_and_clip_line(self, points, field_geometry, strength=None, method='catmull', iterations=3, max_points=None):
        """Suaviza uma linha e reaplica clipping com o talhão, retornando segmentos válidos.

        Retorna lista de segmentos (cada segmento é lista de QgsPoint).
        """
        if strength is None:
            strength = self.smoothing_strength

        smoothed_pts = self.smooth_line_extended(points, strength, method=method, iterations=iterations, max_points=max_points)

        if not smoothed_pts:
            return []

        try:
            geom = QgsGeometry.fromPolyline(smoothed_pts)
            intersection = field_geometry.intersection(geom)
        except Exception:
            return []

        if intersection is None or intersection.isEmpty():
            return []

        segments = []
        try:
            if intersection.isMultipart():
                multi = intersection.asMultiPolyline()
                for part in multi:
                    pts = [QgsPoint(pt.x(), pt.y()) for pt in part]
                    if len(pts) >= 2:
                        segments.append(pts)
            else:
                poly = intersection.asPolyline()
                if poly and len(poly) >= 2:
                    pts = [QgsPoint(pt.x(), pt.y()) for pt in poly]
                    segments.append(pts)
        except Exception:
            return []

        return segments

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

    def merge_segments(self, segments, tolerance=1.0, angle_threshold_deg=45.0):
        """Funde segmentos próximos em linhas contínuas com checagem de orientação.

        segments: lista de listas de QgsPoint
        tolerance: distância máxima (unidades do CRS) para conectar extremidades
        angle_threshold_deg: diferença máxima de ângulo entre direções dos extremos
        Retorna: lista de listas de QgsPoint (linhas fundidas)
        """
        from math import hypot, atan2, degrees

        # converter para listas de tuplas para operações numéricas
        segs = []
        for seg in segments:
            coords = []
            for p in seg:
                try:
                    coords.append((p.x(), p.y()))
                except Exception:
                    coords.append((float(p[0]), float(p[1])))
            if len(coords) >= 2:
                segs.append(coords)

        if not segs:
            return []

        def dist(u, v):
            return hypot(u[0] - v[0], u[1] - v[1])

        def direction(a, b):
            # vector from a to b
            return (b[0] - a[0], b[1] - a[1])

        def angle_between(u, v):
            # compute signed angle between vectors u and v in degrees
            ang1 = atan2(u[1], u[0])
            ang2 = atan2(v[1], v[0])
            diff = abs(degrees(ang1 - ang2))
            if diff > 180:
                diff = 360 - diff
            return diff

        merged_any = True
        while merged_any:
            merged_any = False
            i = 0
            while i < len(segs):
                a = segs[i]
                ai_start = a[0]
                ai_end = a[-1]
                # direction vectors near ends
                a_end_dir = direction(a[-2], a[-1])
                a_start_dir = direction(a[0], a[1])

                j = i + 1
                while j < len(segs):
                    b = segs[j]
                    bj_start = b[0]
                    bj_end = b[-1]
                    b_start_dir = direction(b[0], b[1])
                    b_end_dir = direction(b[-2], b[-1])

                    merged = None

                    # cases to consider with angle checks
                    if dist(ai_end, bj_start) <= tolerance and angle_between(a_end_dir, b_start_dir) <= angle_threshold_deg:
                        merged = a + b
                    elif dist(ai_end, bj_end) <= tolerance and angle_between(a_end_dir, (-b_end_dir[0], -b_end_dir[1])) <= angle_threshold_deg:
                        merged = a + b[::-1]
                    elif dist(ai_start, bj_end) <= tolerance and angle_between(a_start_dir, b_end_dir) <= angle_threshold_deg:
                        merged = b + a
                    elif dist(ai_start, bj_start) <= tolerance and angle_between(a_start_dir, (-b_start_dir[0], -b_start_dir[1])) <= angle_threshold_deg:
                        merged = b[::-1] + a

                    if merged is not None:
                        segs[i] = merged
                        segs.pop(j)
                        merged_any = True
                        continue

                    j += 1
                i += 1

        # remover pontos duplicados consecutivos e reconstruir QgsPoint
        cleaned = []
        for seg in segs:
            newseg = [seg[0]]
            for pt in seg[1:]:
                if pt != newseg[-1]:
                    newseg.append(pt)
            if len(newseg) >= 2:
                cleaned.append([QgsPoint(x, y) for x, y in newseg])

        return cleaned

# Silhouette 数学与几何工具库

> 分类: API与参数手册
> 更新日期: 2026-07-11
> 概述: 包括向量运算、矩阵变换、贝塞尔曲线计算、点在多边形内判断、距离计算、插值函数等数学工具

## 目录

- [一、向量运算](#一向量运算)
- [二、矩阵变换](#二矩阵变换)
- [三、贝塞尔曲线计算](#三贝塞尔曲线计算)
- [四、点在多边形内判断](#四点在多边形内判断)
- [五、距离计算](#五距离计算)
- [六、插值函数](#六插值函数)
- [七、角度与旋转](#七角度与旋转)
- [八、边界框计算](#八边界框计算)
- [九、噪声与随机](#九噪声与随机)
- [十、实用工具函数](#十实用工具函数)
- [十一、最佳实践](#十一最佳实践)

---

## 一、向量运算

### 1.1 2D 向量

```python
import math

class Vec2:
    """2D 向量类"""

    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)

    # 基本运算
    def __add__(self, other):
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return Vec2(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar):
        return Vec2(self.x / scalar, self.y / scalar)

    def __repr__(self):
        return f"Vec2({self.x:.3f}, {self.y:.3f})"

    # 向量属性
    def length(self):
        """向量长度"""
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def lengthSquared(self):
        """长度平方（避免开方，性能优化）"""
        return self.x ** 2 + self.y ** 2

    def normalize(self):
        """归一化"""
        l = self.length()
        if l > 0:
            return Vec2(self.x / l, self.y / l)
        return Vec2(0, 0)

    # 向量操作
    def dot(self, other):
        """点积"""
        return self.x * other.x + self.y * other.y

    def cross(self, other):
        """叉积（2D返回标量）"""
        return self.x * other.y - self.y * other.x

    def perpendicular(self):
        """垂直向量"""
        return Vec2(-self.y, self.x)

    def angle(self):
        """向量角度（弧度）"""
        return math.atan2(self.y, self.x)

    def rotate(self, angle_rad):
        """旋转向量"""
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return Vec2(
            self.x * cos_a - self.y * sin_a,
            self.x * sin_a + self.y * cos_a
        )

    def lerp(self, other, t):
        """线性插值"""
        return Vec2(
            self.x + (other.x - self.x) * t,
            self.y + (other.y - self.y) * t
        )

    def distance(self, other):
        """到另一个向量的距离"""
        return (self - other).length()

    def to_tuple(self):
        return (self.x, self.y)
```

### 1.2 3D 向量

```python
class Vec3:
    """3D 向量类"""

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __add__(self, other):
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar):
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def length(self):
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalize(self):
        l = self.length()
        if l > 0:
            return Vec3(self.x/l, self.y/l, self.z/l)
        return Vec3(0, 0, 0)

    def dot(self, other):
        return self.x*other.x + self.y*other.y + self.z*other.z

    def cross(self, other):
        """3D 叉积"""
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x
        )

    def lerp(self, other, t):
        return Vec3(
            self.x + (other.x - self.x) * t,
            self.y + (other.y - self.y) * t,
            self.z + (other.z - self.z) * t
        )
```

### 1.3 使用示例

```python
# 创建向量
v1 = Vec2(3, 4)
v2 = Vec2(1, 2)

# 运算
v3 = v1 + v2        # Vec2(4, 6)
v4 = v1 - v2        # Vec2(2, 2)
v5 = v1 * 2         # Vec2(6, 8)

# 属性
print(f"v1长度: {v1.length()}")        # 5.0
print(f"v1归一化: {v1.normalize()}")   # Vec2(0.6, 0.8)
print(f"点积: {v1.dot(v2)}")           # 11.0
print(f"叉积: {v1.cross(v2)}")         # 2.0
print(f"距离: {v1.distance(v2)}")      # 2.828...
```

---

## 二、矩阵变换

### 2.1 3x3 变换矩阵（2D）

```python
import math

class Matrix3:
    """3x3 仿射变换矩阵（2D）"""

    def __init__(self):
        # 单位矩阵
        self.m = [
            1, 0, 0,  # 行1
            0, 1, 0,  # 行2
            0, 0, 1   # 行3
        ]

    @staticmethod
    def identity():
        return Matrix3()

    @staticmethod
    def translation(x, y):
        m = Matrix3()
        m.m[2] = x
        m.m[5] = y
        return m

    @staticmethod
    def rotation(angle_rad):
        m = Matrix3()
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        m.m[0] = cos_a
        m.m[1] = -sin_a
        m.m[3] = sin_a
        m.m[4] = cos_a
        return m

    @staticmethod
    def scale(sx, sy):
        m = Matrix3()
        m.m[0] = sx
        m.m[4] = sy
        return m

    @staticmethod
    def skew(angle_x_rad, angle_y_rad):
        m = Matrix3()
        m.m[1] = math.tan(angle_x_rad)
        m.m[3] = math.tan(angle_y_rad)
        return m

    def multiply(self, other):
        """矩阵乘法"""
        result = Matrix3()
        a = self.m
        b = other.m
        for i in range(3):
            for j in range(3):
                result.m[i*3 + j] = (
                    a[i*3 + 0] * b[0*3 + j] +
                    a[i*3 + 1] * b[1*3 + j] +
                    a[i*3 + 2] * b[2*3 + j]
                )
        return result

    def transform_point(self, x, y):
        """变换点"""
        nx = self.m[0]*x + self.m[1]*y + self.m[2]
        ny = self.m[3]*x + self.m[4]*y + self.m[5]
        return (nx, ny)

    def determinant(self):
        """行列式"""
        return (
            self.m[0] * (self.m[4]*self.m[8] - self.m[5]*self.m[7]) -
            self.m[1] * (self.m[3]*self.m[8] - self.m[5]*self.m[6]) +
            self.m[2] * (self.m[3]*self.m[7] - self.m[4]*self.m[6])
        )

    def inverse(self):
        """逆矩阵"""
        det = self.determinant()
        if abs(det) < 1e-10:
            return Matrix3.identity()

        inv_det = 1.0 / det
        m = self.m
        result = Matrix3()

        result.m[0] = (m[4]*m[8] - m[5]*m[7]) * inv_det
        result.m[1] = (m[2]*m[7] - m[1]*m[8]) * inv_det
        result.m[2] = (m[1]*m[5] - m[2]*m[4]) * inv_det
        result.m[3] = (m[5]*m[6] - m[3]*m[8]) * inv_det
        result.m[4] = (m[0]*m[8] - m[2]*m[6]) * inv_det
        result.m[5] = (m[2]*m[3] - m[0]*m[5]) * inv_det
        result.m[6] = (m[3]*m[7] - m[4]*m[6]) * inv_det
        result.m[7] = (m[1]*m[6] - m[0]*m[7]) * inv_det
        result.m[8] = (m[0]*m[4] - m[1]*m[3]) * inv_det

        return result
```

### 2.2 组合变换

```python
# 创建组合变换：先缩放，再旋转，再平移
transform = (Matrix3.translation(100, 50)
             .multiply(Matrix3.rotation(math.radians(30)))
             .multiply(Matrix3.scale(2, 2)))

# 变换点
x, y = transform.transform_point(10, 10)
print(f"变换后: ({x:.2f}, {y:.2f})")

# 逆变换
inverse = transform.inverse()
orig_x, orig_y = inverse.transform_point(x, y)
print(f"逆变换: ({orig_x:.2f}, {orig_y:.2f})")
```

### 2.3 Silhouette 节点变换应用

```python
from fx import *

def apply_matrix_to_transform_node(matrix, transform_node, frame=0):
    """将矩阵应用到 TransformNode"""
    # 提取平移
    tx = matrix.m[2]
    ty = matrix.m[5]
    transform_node.property("translate").setValue([tx, ty], frame)

    # 提取旋转（从矩阵的旋转部分）
    angle = math.atan2(matrix.m[3], matrix.m[0])
    transform_node.property("rotate").setValue(math.degrees(angle), frame)

    # 提取缩放
    sx = math.sqrt(matrix.m[0]**2 + matrix.m[3]**2)
    sy = math.sqrt(matrix.m[1]**2 + matrix.m[4]**2)
    transform_node.property("scale").setValue([sx, sy], frame)
```

---

## 三、贝塞尔曲线计算

### 3.1 二次贝塞尔曲线

```python
import math

def quadratic_bezier(p0, p1, p2, t):
    """二次贝塞尔曲线点计算
    p0, p1, p2: 控制点 (x, y)
    t: 参数 [0, 1]
    """
    x = (1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0]
    y = (1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1]
    return (x, y)

def quadratic_bezier_derivative(p0, p1, p2, t):
    """二次贝塞尔曲线导数（切线方向）"""
    dx = 2*(1-t)*(p1[0]-p0[0]) + 2*t*(p2[0]-p1[0])
    dy = 2*(1-t)*(p1[1]-p0[1]) + 2*t*(p2[1]-p1[1])
    return (dx, dy)
```

### 3.2 三次贝塞尔曲线

```python
def cubic_bezier(p0, p1, p2, p3, t):
    """三次贝塞尔曲线点计算"""
    x = ((1-t)**3 * p0[0] +
         3*(1-t)**2*t * p1[0] +
         3*(1-t)*t**2 * p2[0] +
         t**3 * p3[0])
    y = ((1-t)**3 * p0[1] +
         3*(1-t)**2*t * p1[1] +
         3*(1-t)*t**2 * p2[1] +
         t**3 * p3[1])
    return (x, y)

def cubic_bezier_derivative(p0, p1, p2, p3, t):
    """三次贝塞尔曲线导数"""
    dx = (3*(1-t)**2*(p1[0]-p0[0]) +
          6*(1-t)*t*(p2[0]-p1[0]) +
          3*t**2*(p3[0]-p2[0]))
    dy = (3*(1-t)**2*(p1[1]-p0[1]) +
          6*(1-t)*t*(p2[1]-p1[1]) +
          3*t**2*(p3[1]-p2[1]))
    return (dx, dy)

def cubic_bezier_length(p0, p1, p2, p3, segments=20):
    """近似计算贝塞尔曲线长度"""
    length = 0
    prev = p0
    for i in range(1, segments + 1):
        t = i / segments
        curr = cubic_bezier(p0, p1, p2, p3, t)
        length += math.sqrt((curr[0]-prev[0])**2 + (curr[1]-prev[1])**2)
        prev = curr
    return length
```

### 3.3 贝塞尔曲线采样

```python
def sample_bezier_curve(p0, p1, p2, p3, num_samples=10):
    """采样贝塞尔曲线上的点"""
    points = []
    for i in range(num_samples + 1):
        t = i / num_samples
        pt = cubic_bezier(p0, p1, p2, p3, t)
        points.append(pt)
    return points

# 使用
p0 = (0, 0)
p1 = (100, 200)
p2 = (300, 200)
p3 = (400, 0)

samples = sample_bezier_curve(p0, p1, p2, p3, 20)
for i, pt in enumerate(samples):
    print(f"t={i/20:.2f}: ({pt[0]:.1f}, {pt[1]:.1f})")

length = cubic_bezier_length(p0, p1, p2, p3, 50)
print(f"曲线长度: {length:.1f}")
```

---

## 四、点在多边形内判断

### 4.1 射线法

```python
def point_in_polygon(point, polygon):
    """判断点是否在多边形内（射线法）
    point: (x, y)
    polygon: [(x1,y1), (x2,y2), ...]
    返回: True/False
    """
    x, y = point
    n = len(polygon)
    inside = False

    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        # 检查射线是否与边相交
        if ((yi > y) != (yj > y)) and \
           (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i

    return inside
```

### 4.2 交叉数法

```python
def point_in_polygon_crossing(point, polygon):
    """交叉数法判断点在多边形内"""
    x, y = point
    n = len(polygon)
    crossing = 0

    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]

        # 检查边是否跨越水平线
        if (y1 <= y < y2) or (y2 <= y < y1):
            # 计算交点x坐标
            x_intersect = x1 + (y - y1) / (y2 - y1) * (x2 - x1)
            if x < x_intersect:
                crossing += 1

    return crossing % 2 == 1
```

### 4.3 点在多边形边上判断

```python
def point_on_polygon_edge(point, polygon, tolerance=0.001):
    """判断点是否在多边形边上"""
    x, y = point
    n = len(polygon)

    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]

        # 点到线段的距离
        dist = point_to_segment_distance(point, (x1, y1), (x2, y2))
        if dist < tolerance:
            return True

    return False

def point_to_segment_distance(point, seg_start, seg_end):
    """点到线段的距离"""
    px, py = point
    x1, y1 = seg_start
    x2, y2 = seg_end

    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx*dx + dy*dy

    if length_sq == 0:
        return math.sqrt((px-x1)**2 + (py-y1)**2)

    t = ((px - x1) * dx + (py - y1) * dy) / length_sq
    t = max(0, min(1, t))

    closest_x = x1 + t * dx
    closest_y = y1 + t * dy

    return math.sqrt((px - closest_x)**2 + (py - closest_y)**2)
```

### 4.4 Silhouette 形状应用

```python
from fx import *

def get_shape_polygon(shape):
    """从 Silhouette 形状获取多边形顶点"""
    points = []
    for i in range(shape.numPoints):
        p = shape.point(i)
        points.append((p.x, p.y))
    return points

def is_point_inside_shape(point, shape):
    """判断点是否在形状内"""
    polygon = get_shape_polygon(shape)
    if shape.closed and len(polygon) >= 3:
        return point_in_polygon(point, polygon)
    return False
```

---

## 五、距离计算

### 5.1 各种距离公式

```python
import math

def distance_2d(p1, p2):
    """2D 欧几里得距离"""
    return math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

def distance_squared_2d(p1, p2):
    """2D 距离平方（避免开方）"""
    return (p2[0]-p1[0])**2 + (p2[1]-p1[1])**2

def distance_3d(p1, p2):
    """3D 欧几里得距离"""
    return math.sqrt(
        (p2[0]-p1[0])**2 +
        (p2[1]-p1[1])**2 +
        (p2[2]-p1[2])**2
    )

def manhattan_distance(p1, p2):
    """曼哈顿距离"""
    return abs(p2[0]-p1[0]) + abs(p2[1]-p1[1])

def chebyshev_distance(p1, p2):
    """切比雪夫距离"""
    return max(abs(p2[0]-p1[0]), abs(p2[1]-p1[1]))
```

### 5.2 点到线段距离

```python
def point_to_line_distance(point, line_p1, line_p2):
    """点到直线的距离"""
    px, py = point
    x1, y1 = line_p1
    x2, y2 = line_p2

    # 直线方程: Ax + By + C = 0
    A = y2 - y1
    B = x1 - x2
    C = x2 * y1 - x1 * y2

    return abs(A * px + B * py + C) / math.sqrt(A*A + B*B)

def point_to_segment_distance(point, seg_p1, seg_p2):
    """点到线段的距离（考虑端点）"""
    px, py = point
    x1, y1 = seg_p1
    x2, y2 = seg_p2

    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy

    if length_sq == 0:
        return distance_2d(point, seg_p1)

    t = ((px - x1) * dx + (py - y1) * dy) / length_sq
    t = max(0.0, min(1.0, t))

    closest_x = x1 + t * dx
    closest_y = y1 + t * dy

    return math.sqrt((px - closest_x)**2 + (py - closest_y)**2)
```

### 5.3 最近点查找

```python
def find_closest_point(target, points):
    """在点列表中查找最近点"""
    min_dist = float('inf')
    closest = None
    closest_idx = -1

    for i, pt in enumerate(points):
        dist = distance_squared_2d(target, pt)  # 用平方距离避免开方
        if dist < min_dist:
            min_dist = dist
            closest = pt
            closest_idx = i

    return closest, closest_idx, math.sqrt(min_dist)
```

---

## 六、插值函数

### 6.1 基础插值

```python
import math

def lerp(a, b, t):
    """线性插值"""
    return a + (b - a) * t

def lerp_2d(p1, p2, t):
    """2D 点线性插值"""
    return (
        p1[0] + (p2[0] - p1[0]) * t,
        p1[1] + (p2[1] - p1[1]) * t
    )

def lerp_color(c1, c2, t):
    """颜色线性插值"""
    return (
        c1[0] + (c2[0] - c1[0]) * t,
        c1[1] + (c2[1] - c1[1]) * t,
        c1[2] + (c2[2] - c1[2]) * t
    )
```

### 6.2 缓动函数

```python
def smoothstep(edge0, edge1, x):
    """平滑阶跃"""
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3 - 2 * t)

def smootherstep(edge0, edge1, x):
    """更平滑的阶跃"""
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * t * (t * (t * 6 - 15) + 10)

def ease_in(t):
    """缓入"""
    return t * t

def ease_out(t):
    """缓出"""
    return 1 - (1 - t) * (1 - t)

def ease_in_out(t):
    """缓入缓出"""
    if t < 0.5:
        return 2 * t * t
    else:
        return 1 - 2 * (1 - t) * (1 - t)

def ease_in_cubic(t):
    return t ** 3

def ease_out_cubic(t):
    return 1 - (1 - t) ** 3

def ease_in_out_cubic(t):
    if t < 0.5:
        return 4 * t ** 3
    else:
        return 1 - 4 * (1 - t) ** 3

def ease_in_elastic(t):
    """弹性缓入"""
    if t == 0 or t == 1:
        return t
    return -(2 ** (10 * t - 10)) * math.sin((t * 10 - 10.75) * (2 * math.pi / 3))

def ease_out_bounce(t):
    """弹跳缓出"""
    if t < 1/2.75:
        return 7.5625 * t * t
    elif t < 2/2.75:
        t -= 1.5/2.75
        return 7.5625 * t * t + 0.75
    elif t < 2.5/2.75:
        t -= 2.25/2.75
        return 7.5625 * t * t + 0.9375
    else:
        t -= 2.625/2.75
        return 7.5625 * t * t + 0.984375
```

### 6.3 Catmull-Rom 样条插值

```python
def catmull_rom(p0, p1, p2, p3, t):
    """Catmull-Rom 样条插值
    适用于通过控制点的平滑曲线
    """
    t2 = t * t
    t3 = t2 * t

    x = 0.5 * (
        (2 * p1[0]) +
        (-p0[0] + p2[0]) * t +
        (2*p0[0] - 5*p1[0] + 4*p2[0] - p3[0]) * t2 +
        (-p0[0] + 3*p1[0] - 3*p2[0] + p3[0]) * t3
    )
    y = 0.5 * (
        (2 * p1[1]) +
        (-p0[1] + p2[1]) * t +
        (2*p0[1] - 5*p1[1] + 4*p2[1] - p3[1]) * t2 +
        (-p0[1] + 3*p1[1] - 3*p2[1] + p3[1]) * t3
    )
    return (x, y)

def catmull_rom_spline(points, segments_per_segment=10):
    """生成 Catmull-Rom 样条曲线"""
    if len(points) < 2:
        return points

    result = []
    n = len(points)

    # 添加首尾镜像点
    extended = [points[0]] + points + [points[-1]]

    for i in range(1, len(extended) - 2):
        p0 = extended[i - 1]
        p1 = extended[i]
        p2 = extended[i + 1]
        p3 = extended[i + 2]

        for j in range(segments_per_segment + 1):
            t = j / segments_per_segment
            result.append(catmull_rom(p0, p1, p2, p3, t))

    return result
```

---

## 七、角度与旋转

### 7.1 角度工具

```python
import math

def degrees_to_radians(deg):
    """度转弧度"""
    return deg * math.pi / 180.0

def radians_to_degrees(rad):
    """弧度转度"""
    return rad * 180.0 / math.pi

def normalize_angle(angle):
    """归一化角度到 [0, 360)"""
    return angle % 360

def angle_between(p1, p2):
    """两点之间的角度（度）"""
    return math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))

def angle_between_vectors(v1, v2):
    """两向量之间的角度（度）"""
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
    mag2 = math.sqrt(v2[0]**2 + v2[1]**2)
    if mag1 == 0 or mag2 == 0:
        return 0
    cos_angle = dot / (mag1 * mag2)
    cos_angle = max(-1, min(1, cos_angle))  # 钳制避免数值误差
    return math.degrees(math.acos(cos_angle))

def shortest_angle_diff(a1, a2):
    """最短角度差 [-180, 180]"""
    diff = (a2 - a1) % 360
    if diff > 180:
        diff -= 360
    return diff

def lerp_angle(a1, a2, t):
    """角度插值（考虑最短路径）"""
    diff = shortest_angle_diff(a1, a2)
    return a1 + diff * t
```

### 7.2 旋转工具

```python
def rotate_point(point, angle_deg, center=(0, 0)):
    """绕中心点旋转"""
    angle_rad = degrees_to_radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    dx = point[0] - center[0]
    dy = point[1] - center[1]

    return (
        center[0] + dx * cos_a - dy * sin_a,
        center[1] + dx * sin_a + dy * cos_a
    )

def rotate_points(points, angle_deg, center=(0, 0)):
    """批量旋转点"""
    return [rotate_point(p, angle_deg, center) for p in points]
```

---

## 八、边界框计算

### 8.1 边界框类

```python
class BoundingBox:
    """2D 边界框"""

    def __init__(self):
        self.min_x = float('inf')
        self.min_y = float('inf')
        self.max_x = float('-inf')
        self.max_y = float('-inf')

    def add_point(self, x, y):
        self.min_x = min(self.min_x, x)
        self.min_y = min(self.min_y, y)
        self.max_x = max(self.max_x, x)
        self.max_y = max(self.max_y, y)

    def add_points(self, points):
        for p in points:
            self.add_point(p[0], p[1])

    @property
    def width(self):
        return self.max_x - self.min_x

    @property
    def height(self):
        return self.max_y - self.min_y

    @property
    def center(self):
        return ((self.min_x + self.max_x) / 2,
                (self.min_y + self.max_y) / 2)

    @property
    def area(self):
        return self.width * self.height

    def contains(self, x, y):
        return (self.min_x <= x <= self.max_x and
                self.min_y <= y <= self.max_y)

    def intersects(self, other):
        return not (self.max_x < other.min_x or
                    self.min_x > other.max_x or
                    self.max_y < other.min_y or
                    self.min_y > other.max_y)

    def expand(self, amount):
        """扩展边界框"""
        self.min_x -= amount
        self.min_y -= amount
        self.max_x += amount
        self.max_y += amount

    def to_tuple(self):
        return (self.min_x, self.min_y, self.max_x, self.max_y)
```

### 8.2 使用示例

```python
from fx import *

def get_shape_bounding_box(shape):
    """获取形状的边界框"""
    bbox = BoundingBox()
    for i in range(shape.numPoints):
        p = shape.point(i)
        bbox.add_point(p.x, p.y)
    return bbox

# 使用
roto = session.findNode("Main_Roto")
if roto and roto.numObjects > 0:
    shape = roto.object(0)
    bbox = get_shape_bounding_box(shape)
    print(f"边界框: {bbox.to_tuple()}")
    print(f"尺寸: {bbox.width:.1f} x {bbox.height:.1f}")
    print(f"中心: ({bbox.center[0]:.1f}, {bbox.center[1]:.1f})")
```

---

## 九、噪声与随机

### 9.1 Perlin 噪声（简化版）

```python
import math
import random

class SimpleNoise:
    """简化 Perlin 噪声"""

    def __init__(self, seed=0):
        random.seed(seed)
        self.permutation = list(range(256))
        random.shuffle(self.permutation)
        self.permutation *= 2  # 重复一次方便索引

    def fade(self, t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    def lerp(self, a, b, t):
        return a + t * (b - a)

    def grad(self, hash_val, x, y):
        h = hash_val & 3
        u = x if h < 2 else y
        v = y if h < 2 else x
        return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)

    def noise2d(self, x, y):
        """2D Perlin 噪声 [-1, 1]"""
        X = int(math.floor(x)) & 255
        Y = int(math.floor(y)) & 255

        x -= math.floor(x)
        y -= math.floor(y)

        u = self.fade(x)
        v = self.fade(y)

        p = self.permutation
        A = p[X] + Y
        B = p[X + 1] + Y

        return self.lerp(
            self.lerp(self.grad(p[A], x, y),
                      self.grad(p[B], x - 1, y), u),
            self.lerp(self.grad(p[A + 1], x, y - 1),
                      self.grad(p[B + 1], x - 1, y - 1), u),
            v
        )

noise = SimpleNoise(seed=42)

# 生成噪声值
for i in range(5):
    n = noise.noise2d(i * 0.1, 0)
    print(f"noise({i*0.1:.1f}, 0) = {n:.4f}")
```

### 9.2 随机工具

```python
import random

def random_point_in_bbox(bbox):
    """在边界框内随机生成点"""
    return (
        random.uniform(bbox.min_x, bbox.max_x),
        random.uniform(bbox.min_y, bbox.max_y)
    )

def random_color():
    """随机颜色"""
    return [random.random(), random.random(), random.random()]

def jitter_point(point, amount):
    """点抖动"""
    return (
        point[0] + random.uniform(-amount, amount),
        point[1] + random.uniform(-amount, amount)
    )
```

---

## 十、实用工具函数

### 10.1 形状面积计算

```python
def polygon_area(points):
    """多边形面积（Shoelace公式）"""
    n = len(points)
    if n < 3:
        return 0

    area = 0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1

    return abs(area) / 2

def polygon_centroid(points):
    """多边形重心"""
    n = len(points)
    if n < 3:
        if n == 0:
            return (0, 0)
        return points[0]

    cx = 0
    cy = 0
    area = 0

    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross

    area = area / 2
    if area == 0:
        return points[0]

    cx = cx / (6 * area)
    cy = cy / (6 * area)

    return (cx, cy)
```

### 10.2 线段相交

```python
def segments_intersect(p1, p2, p3, p4):
    """判断两线段是否相交"""
    def ccw(A, B, C):
        return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])

    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and \
           ccw(p1, p2, p3) != ccw(p1, p2, p4)

def line_intersection(p1, p2, p3, p4):
    """计算两直线交点"""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(denom) < 1e-10:
        return None  # 平行

    t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom
    u = -((x1-x2)*(y1-y3) - (y1-y2)*(x1-x3)) / denom

    if 0 <= t <= 1 and 0 <= u <= 1:
        return (x1 + t*(x2-x1), y1 + t*(y2-y1))
    return None
```

### 10.3 简化多边形

```python
def simplify_polygon(points, tolerance=1.0):
    """Douglas-Peucker 多边形简化"""
    if len(points) < 3:
        return points

    # 找到距离起止点连线最远的点
    start = points[0]
    end = points[-1]
    max_dist = 0
    max_idx = 0

    for i in range(1, len(points) - 1):
        d = point_to_segment_distance(points[i], start, end)
        if d > max_dist:
            max_dist = d
            max_idx = i

    if max_dist > tolerance:
        # 递归简化
        left = simplify_polygon(points[:max_idx+1], tolerance)
        right = simplify_polygon(points[max_idx:], tolerance)
        return left[:-1] + right
    else:
        return [start, end]
```

---

## 十一、最佳实践

### 11.1 数值精度

```python
# 避免浮点数比较
EPSILON = 1e-6

def approx_equal(a, b, epsilon=EPSILON):
    return abs(a - b) < epsilon

def clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))
```

### 11.2 性能优化

```python
# 使用平方距离比较，避免不必要的开方
def find_nearest_shape(point, shapes):
    """查找最近的形状"""
    min_dist_sq = float('inf')
    nearest = None

    for shape in shapes:
        for i in range(shape.numPoints):
            p = shape.point(i)
            dx = p.x - point[0]
            dy = p.y - point[1]
            dist_sq = dx*dx + dy*dy
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                nearest = shape

    return nearest, math.sqrt(min_dist_sq)
```

### 11.3 Silhouette 集成工具

```python
from fx import *
import math

class ShapeMathUtils:
    """Silhouette 形状数学工具集"""

    @staticmethod
    def get_shape_points(shape):
        """获取形状所有控制点"""
        return [(shape.point(i).x, shape.point(i).y)
                for i in range(shape.numPoints)]

    @staticmethod
    def get_shape_area(shape):
        """计算形状面积"""
        points = ShapeMathUtils.get_shape_points(shape)
        return polygon_area(points)

    @staticmethod
    def get_shape_centroid(shape):
        """计算形状重心"""
        points = ShapeMathUtils.get_shape_points(shape)
        return polygon_centroid(points)

    @staticmethod
    def get_shape_bbox(shape):
        """计算形状边界框"""
        bbox = BoundingBox()
        bbox.add_points(ShapeMathUtils.get_shape_points(shape))
        return bbox

    @staticmethod
    def move_shape(shape, dx, dy):
        """平移形状"""
        for i in range(shape.numPoints):
            p = shape.point(i)
            p.x += dx
            p.y += dy

    @staticmethod
    def scale_shape(shape, sx, sy, center=None):
        """缩放形状"""
        if center is None:
            center = ShapeMathUtils.get_shape_centroid(shape)

        for i in range(shape.numPoints):
            p = shape.point(i)
            p.x = center[0] + (p.x - center[0]) * sx
            p.y = center[1] + (p.y - center[1]) * sy

    @staticmethod
    def rotate_shape(shape, angle_deg, center=None):
        """旋转形状"""
        if center is None:
            center = ShapeMathUtils.get_shape_centroid(shape)

        for i in range(shape.numPoints):
            p = shape.point(i)
            new_pos = rotate_point((p.x, p.y), angle_deg, center)
            p.x = new_pos[0]
            p.y = new_pos[1]
```

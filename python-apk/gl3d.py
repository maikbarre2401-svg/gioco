"""Piccolo motore 3D in OpenGL per Kivy: logo Maik 3D e grafico a ciambella 3D.

Ogni scena viene disegnata in un Fbo (con depth buffer e supersampling 2x) e poi
mostrata come texture dentro un normale widget, quindi si può mettere ovunque.
"""
import math

from kivy.clock import Clock
from kivy.graphics import (Callback, ClearBuffers, ClearColor, Color, Fbo, Mesh, PopMatrix, PushMatrix,
                           Rectangle, Rotate, Scale, Translate, UpdateNormalMatrix)
from kivy.graphics.opengl import GL_DEPTH_TEST, glDisable, glEnable
from kivy.graphics.transformation import Matrix
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex

VS = """
#ifdef GL_ES
    precision highp float;
#endif
attribute vec3 v_pos;
attribute vec3 v_normal;
attribute vec4 v_color;
uniform mat4 modelview_mat;
uniform mat4 projection_mat;
varying vec4 normal_vec;
varying vec4 vertex_pos;
varying vec4 frag_color;
void main(void) {
    vec4 pos = modelview_mat * vec4(v_pos, 1.0);
    vertex_pos = pos;
    normal_vec = vec4(v_normal, 0.0);
    frag_color = v_color;
    gl_Position = projection_mat * pos;
}
"""

FS = """
#ifdef GL_ES
    precision highp float;
#endif
varying vec4 normal_vec;
varying vec4 vertex_pos;
varying vec4 frag_color;
uniform mat4 normal_mat;
void main(void) {
    vec3 n = normalize((normal_mat * normal_vec).xyz);
    vec3 l = normalize(vec3(-0.45, 0.65, 1.0));
    vec3 v = normalize(-vertex_pos.xyz);
    vec3 h = normalize(l + v);
    float diff = max(dot(n, l), 0.0);
    float spec = pow(max(dot(n, h), 0.0), 40.0);
    float rim = pow(1.0 - max(dot(n, v), 0.0), 3.0);
    vec3 c = frag_color.rgb * (0.38 + 0.72 * diff) + vec3(0.45) * spec + vec3(0.12) * rim;
    gl_FragColor = vec4(c, frag_color.a);
}
"""

FMT = [(b"v_pos", 3, "float"), (b"v_normal", 3, "float"), (b"v_color", 4, "float")]


def rgba(c, a=1.0):
    if isinstance(c, str):
        r, g, b = get_color_from_hex(c)[:3]
        return (r, g, b, a)
    return tuple(c[:3]) + (a,)


def mix(c1, c2, t):
    return tuple(c1[i] + (c2[i] - c1[i]) * t for i in range(4))


class MeshBuilder:
    """Accumula vertici (posizione, normale, colore) e triangoli."""

    def __init__(self):
        self.vertices = []
        self.indices = []
        self.count = 0

    def vertex(self, p, n, c):
        self.vertices.extend((p[0], p[1], p[2], n[0], n[1], n[2], c[0], c[1], c[2], c[3]))
        self.count += 1
        return self.count - 1

    def quad(self, a, b, c, d, n, col):
        i = [self.vertex(p, n, col) for p in (a, b, c, d)]
        self.indices.extend((i[0], i[1], i[2], i[0], i[2], i[3]))

    def box(self, p0, p1, hw, z0, z1, col):
        """Barra 3D tra due punti 2D (spessore 2*hw, profondità z0..z1)."""
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln * hw, dx / ln * hw
        a = (p0[0] + nx, p0[1] + ny)
        b = (p1[0] + nx, p1[1] + ny)
        c = (p1[0] - nx, p1[1] - ny)
        d = (p0[0] - nx, p0[1] - ny)
        self.quad((a[0], a[1], z1), (d[0], d[1], z1), (c[0], c[1], z1), (b[0], b[1], z1), (0, 0, 1), col)
        self.quad((a[0], a[1], z0), (b[0], b[1], z0), (c[0], c[1], z0), (d[0], d[1], z0), (0, 0, -1), col)
        side = (nx / hw, ny / hw, 0)
        self.quad((a[0], a[1], z0), (a[0], a[1], z1), (b[0], b[1], z1), (b[0], b[1], z0), side, col)
        self.quad((d[0], d[1], z0), (c[0], c[1], z0), (c[0], c[1], z1), (d[0], d[1], z1), (-side[0], -side[1], 0), col)

    def cylinder(self, cx, cy, r, z0, z1, col, seg=28):
        """Cilindro lungo z: fa da giunto arrotondato tra le barre."""
        top = self.vertex((cx, cy, z1), (0, 0, 1), col)
        bot = self.vertex((cx, cy, z0), (0, 0, -1), col)
        for i in range(seg):
            a0 = 2 * math.pi * i / seg
            a1 = 2 * math.pi * (i + 1) / seg
            p0 = (cx + r * math.cos(a0), cy + r * math.sin(a0))
            p1 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
            t0 = self.vertex((p0[0], p0[1], z1), (0, 0, 1), col)
            t1 = self.vertex((p1[0], p1[1], z1), (0, 0, 1), col)
            self.indices.extend((top, t0, t1))
            b0 = self.vertex((p0[0], p0[1], z0), (0, 0, -1), col)
            b1 = self.vertex((p1[0], p1[1], z0), (0, 0, -1), col)
            self.indices.extend((bot, b1, b0))
            n0 = (math.cos(a0), math.sin(a0), 0)
            n1 = (math.cos(a1), math.sin(a1), 0)
            s = [self.vertex((p0[0], p0[1], z0), n0, col), self.vertex((p1[0], p1[1], z0), n1, col),
                 self.vertex((p1[0], p1[1], z1), n1, col), self.vertex((p0[0], p0[1], z1), n0, col)]
            self.indices.extend((s[0], s[1], s[2], s[0], s[2], s[3]))

    def sphere(self, c, r, col, rings=16, segs=24):
        base = self.count
        for i in range(rings + 1):
            th = math.pi * i / rings
            for j in range(segs + 1):
                ph = 2 * math.pi * j / segs
                n = (math.sin(th) * math.cos(ph), math.cos(th), math.sin(th) * math.sin(ph))
                self.vertex((c[0] + r * n[0], c[1] + r * n[1], c[2] + r * n[2]), n, col)
        for i in range(rings):
            for j in range(segs):
                a = base + i * (segs + 1) + j
                b = a + segs + 1
                self.indices.extend((a, a + 1, b, a + 1, b + 1, b))

    def rounded_slab(self, half, radius, z0, z1, col_a, col_b, seg=8):
        """Quadrato arrotondato in rilievo con sfumatura (col_a in alto a sinistra, col_b in basso a destra)."""
        pts = []
        for cx, cy, start in ((half - radius, half - radius, 0), (-half + radius, half - radius, 90),
                              (-half + radius, -half + radius, 180), (half - radius, -half + radius, 270)):
            for i in range(seg + 1):
                a = math.radians(start + 90 * i / seg)
                pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))

        def color_at(x, y):
            return mix(col_a, col_b, max(0.0, min(1.0, ((x - y) / (2 * half) + 1) / 2)))

        for z, nz in ((z1, 1), (z0, -1)):
            center = self.vertex((0, 0, z), (0, 0, nz), color_at(0, 0))
            ring = [self.vertex((x, y, z), (0, 0, nz), color_at(x, y)) for x, y in pts]
            for i in range(len(ring)):
                j = (i + 1) % len(ring)
                self.indices.extend((center, ring[i], ring[j]) if nz > 0 else (center, ring[j], ring[i]))
        for i in range(len(pts)):
            p0, p1 = pts[i], pts[(i + 1) % len(pts)]
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            ln = math.hypot(p1[1] - p0[1], p0[0] - p1[0]) or 1
            n = ((p1[1] - p0[1]) / ln, (p0[0] - p1[0]) / ln, 0)
            if n[0] * mx + n[1] * my < 0:
                n = (-n[0], -n[1], 0)
            col = mix(color_at(mx, my), (0, 0, 0, 1), 0.15)
            self.quad((p0[0], p0[1], z0), (p1[0], p1[1], z0), (p1[0], p1[1], z1), (p0[0], p0[1], z1), n, col)

    def ring_sector(self, a0, a1, r_in, r_out, z0, z1, col, seg=None):
        """Fetta di ciambella in rilievo (angoli in radianti)."""
        seg = seg or max(3, int(abs(a1 - a0) / (2 * math.pi) * 72))
        side = mix(col, (0, 0, 0, 1), 0.12)
        for i in range(seg):
            t0 = a0 + (a1 - a0) * i / seg
            t1 = a0 + (a1 - a0) * (i + 1) / seg
            c0, s0, c1, s1 = math.cos(t0), math.sin(t0), math.cos(t1), math.sin(t1)
            self.quad((r_in * c0, r_in * s0, z1), (r_out * c0, r_out * s0, z1), (r_out * c1, r_out * s1, z1),
                      (r_in * c1, r_in * s1, z1), (0, 0, 1), col)
            self.quad((r_in * c0, r_in * s0, z0), (r_in * c1, r_in * s1, z0), (r_out * c1, r_out * s1, z0),
                      (r_out * c0, r_out * s0, z0), (0, 0, -1), col)
            i0 = self.vertex((r_out * c0, r_out * s0, z0), (c0, s0, 0), side)
            i1 = self.vertex((r_out * c1, r_out * s1, z0), (c1, s1, 0), side)
            i2 = self.vertex((r_out * c1, r_out * s1, z1), (c1, s1, 0), side)
            i3 = self.vertex((r_out * c0, r_out * s0, z1), (c0, s0, 0), side)
            self.indices.extend((i0, i1, i2, i0, i2, i3))
            j0 = self.vertex((r_in * c0, r_in * s0, z0), (-c0, -s0, 0), side)
            j1 = self.vertex((r_in * c1, r_in * s1, z0), (-c1, -s1, 0), side)
            j2 = self.vertex((r_in * c1, r_in * s1, z1), (-c1, -s1, 0), side)
            j3 = self.vertex((r_in * c0, r_in * s0, z1), (-c0, -s0, 0), side)
            self.indices.extend((j0, j2, j1, j0, j3, j2))
        for t, sign in ((a0, -1), (a1, 1)):
            c, s = math.cos(t), math.sin(t)
            n = (-s * sign, c * sign, 0)
            self.quad((r_in * c, r_in * s, z0), (r_out * c, r_out * s, z0), (r_out * c, r_out * s, z1),
                      (r_in * c, r_in * s, z1), n, side)

    def mesh(self):
        return Mesh(vertices=self.vertices, indices=self.indices, fmt=FMT, mode="triangles")


# Percorso della "M" del logo, in coordinate centrate (-1..1).
M_POINTS = [(-0.46, -0.42), (-0.46, 0.30), (0.0, -0.14), (0.46, 0.30), (0.46, -0.42)]


def build_logo():
    b = MeshBuilder()
    b.rounded_slab(1.0, 0.30, -0.16, 0.0, rgba("#A98DFF"), rgba("#5134F0"))
    white = rgba("#FFFFFF")
    hw = 0.1
    for p0, p1 in zip(M_POINTS, M_POINTS[1:]):
        b.box(p0, p1, hw, 0.0, 0.16, white)
    for p in M_POINTS:
        b.cylinder(p[0], p[1], hw, 0.0, 0.16, white)
    b.sphere((0.56, 0.56, 0.12), 0.17, rgba("#C8FF3D"))
    return b.mesh()


class Scene3D(Widget):
    """Widget che disegna una scena 3D animata. Le sottoclassi riempiono build_scene() e animate()."""

    distance = NumericProperty(4.2)
    supersample = 2

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.t = 0.0
        self.fbo = None
        self._event = None
        self.bind(size=self._rebuild, pos=self._place)
        self._rebuild()

    def on_parent(self, *_):
        if self.parent and not self._event:
            self._event = Clock.schedule_interval(self._tick, 1 / 60.0)
        elif not self.parent and self._event:
            self._event.cancel()
            self._event = None

    def _rebuild(self, *_):
        w = max(2, min(2048, int(self.width * self.supersample)))
        h = max(2, min(2048, int(self.height * self.supersample)))
        self.canvas.clear()
        self.fbo = Fbo(size=(w, h), with_depthbuffer=True, compute_normal_mat=True, vs=VS, fs=FS)
        with self.fbo:
            ClearColor(0, 0, 0, 0)
            ClearBuffers(clear_color=True, clear_depth=True)
            Callback(lambda *_: glEnable(GL_DEPTH_TEST))
            PushMatrix()
            Translate(0, 0, -self.distance)
            self.build_scene()
            PopMatrix()
            Callback(lambda *_: glDisable(GL_DEPTH_TEST))
        asp = w / float(h)
        self.fbo["projection_mat"] = Matrix().view_clip(-asp, asp, -1, 1, 2, 100, 1)
        self.fbo.texture.mag_filter = "linear"
        self.fbo.texture.min_filter = "linear"
        self.canvas.add(self.fbo)
        self.canvas.add(Color(1, 1, 1, 1))
        self.rect = Rectangle(texture=self.fbo.texture, pos=self.pos, size=self.size)
        self.canvas.add(self.rect)
        self.animate(0)

    def _place(self, *_):
        if self.fbo:
            self.rect.pos = self.pos

    def _tick(self, dt):
        self.t += dt
        self.animate(dt)
        if self.fbo:
            self.fbo.ask_update()

    def build_scene(self):
        pass

    def animate(self, dt):
        pass


class Logo3D(Scene3D):
    """Logo Maik in 3D che oscilla e, con spin(), fa un giro completo."""

    tilt = NumericProperty(28)
    speed = NumericProperty(1.0)

    def __init__(self, **kwargs):
        self._spin = 0.0
        super().__init__(**kwargs)

    def build_scene(self):
        self.r_bob = Translate(0, 0, 0)
        self.r_y = Rotate(0, 0, 1, 0)
        self.r_x = Rotate(0, 1, 0, 0)
        self.scale = Scale(1)
        UpdateNormalMatrix()
        build_logo()
        # Il Mesh è già stato aggiunto al contesto dal costruttore nel blocco "with".

    def spin(self, turns=1):
        self._spin += 360 * turns

    def animate(self, dt):
        if not hasattr(self, "r_y"):
            return
        self._spin *= max(0.0, 1 - dt * 3.2)
        t = self.t * self.speed
        self.r_y.angle = self.tilt * math.sin(t * 1.1) + self._spin
        self.r_x.angle = 10 * math.sin(t * 0.8 + 1.0)
        self.r_bob.y = 0.06 * math.sin(t * 1.6)


class Donut3D(Scene3D):
    """Grafico a ciambella 3D: fette in rilievo che crescono e ruotano lentamente."""

    data = ListProperty([])  # [(valore, "#colore"), ...]
    distance = NumericProperty(3.2)

    def __init__(self, **kwargs):
        self.grow = 0.0
        super().__init__(**kwargs)
        self.bind(data=self._rebuild)

    def build_scene(self):
        self.r_tilt = Rotate(-58, 1, 0, 0)
        self.r_spin = Rotate(0, 0, 0, 1)
        self.s = Scale(1, 1, 0.01)
        UpdateNormalMatrix()
        total = sum(v for v, _ in self.data) or 1.0
        a = math.pi / 2
        gap = 0.035 if len(self.data) > 1 else 0
        biggest = max(range(len(self.data)), key=lambda i: self.data[i][0]) if self.data else -1
        for i, (v, col) in enumerate(self.data):
            span = 2 * math.pi * v / total
            b = MeshBuilder()
            height = 0.28 + (0.18 if i == biggest else 0)
            b.ring_sector(a + gap / 2, a + span - gap / 2, 0.55, 1.2, 0, height, rgba(col))
            mid = a + span / 2
            push = 0.09 if i == biggest else 0
            PushMatrix()
            Translate(push * math.cos(mid), push * math.sin(mid), 0)
            UpdateNormalMatrix()
            b.mesh()
            PopMatrix()
            a += span
        if not self.data:
            b = MeshBuilder()
            b.ring_sector(0, 2 * math.pi - 0.001, 0.55, 1.2, 0, 0.2, rgba("#C9C9D6"))
            b.mesh()
        self.grow = 0.0

    def animate(self, dt):
        if not hasattr(self, "r_spin"):
            return
        self.grow = min(1.0, self.grow + dt * 1.4)
        ease = 1 - (1 - self.grow) ** 3
        self.s.z = max(0.01, ease)
        self.r_spin.angle = -self.t * 14
        self.r_tilt.angle = -58 + 6 * math.sin(self.t * 0.7)

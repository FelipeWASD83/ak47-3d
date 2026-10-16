"""Gera o modelo 3D de uma AK-47 (no padrão AKM, a mesma arma da AK-47 do CS2), com as animações de tiro e de
recarga.

Roda dentro do Blender (o mesmo caminho do deagle-3d):

    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup --python gerar.py

Opções depois de `--`: `--sem-render` pula as imagens; `--rapido` faz as imagens em meia resolução e poucas
amostras; `--leve` é o rápido com só 4 vistas, 4 núcleos e prioridade mínima do Windows (dá para rodar com o PC
ocupado); `--vistas a,b` escolhe as imagens do modo leve.

Tudo em milímetros, 1 unidade do Blender = 1 mm. Eixos: X para a frente (a boca do cano aponta para +X), Y
largura (o lado direito de quem atira é -Y, onde ficam a janela de ejeção, a alavanca de manejo e o seletor), Z
para cima. O eixo do cano é Z = 0 e X = 0 é a frente da caixa da culatra.

As peças de perfil (caixa da culatra, tampa, ferrolho, gatilho, miras, alavancas) são "almofadas": o perfil visto
de lado, com os cantos arredondados, extrudado em Y com a borda arredondada. As peças de madeira (coronha, punho e
guarda-mão de baixo) são sólidos de fatias ovais, como o cabo do revolver-3d. O pente curvo é uma haste de seção
quase retangular varrida ao longo de um arco.
"""

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "modelo"
RENDER = PASTA / "render"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

NOME = "ak47"
X_BOCA = 384.0                     # a boca do quebra-chamas (cano de 415 mm, 32 mm dentro da caixa)
R_ALMA = 3.95                      # calibre 7,62
MEIA_CAIXA = 14.5                  # a caixa da culatra tem 29 mm de largura
CURSO = 85.0                       # quanto o ferrolho recua
# o pente curvo é um arco: centro, raio da linha do meio e os ângulos do topo (dentro da caixa) e do fundo
CENTRO_PENTE = Vector((137.9, 0, 1.7))
R_PENTE = 218.0
ANG_TOPO, ANG_FUNDO = math.radians(185.2), math.radians(235.5)
AVISOS = []

# ---------------------------------------------------------------- perfis 2D (x, z)

def _area(pts):
    n = len(pts)
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))


def _sem_repetidos(pts):
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-4:
            out.append((p[0], p[1]))
    if len(out) > 2 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-4:
        out.pop()
    return out


def arredondar(pts, raio_padrao, raio_min=0.0, passo_ang=math.radians(10)):
    """Arredonda cada canto do polígono fechado. Ponto pode ser (x, z) ou (x, z, raio)."""
    P = [(p[0], p[1], max(p[2] if len(p) > 2 else raio_padrao, raio_min)) for p in pts]
    n = len(P)
    out = []
    for i in range(n):
        x, z, r = P[i]
        ax, az = P[i - 1][:2]
        bx, bz = P[(i + 1) % n][:2]
        ux, uz = ax - x, az - z
        vx, vz = bx - x, bz - z
        la, lb = math.hypot(ux, uz), math.hypot(vx, vz)
        if la < 1e-6 or lb < 1e-6:
            continue
        ux, uz, vx, vz = ux / la, uz / la, vx / lb, vz / lb
        ang = math.acos(max(-1.0, min(1.0, ux * vx + uz * vz)))
        if r <= 0 or ang > math.radians(165):
            out.append((x, z))
            continue
        t = min(r / math.tan(ang / 2), 0.48 * la, 0.48 * lb)
        re = t * math.tan(ang / 2)
        bxv, bzv = ux + vx, uz + vz
        lbv = math.hypot(bxv, bzv)
        bxv, bzv = bxv / lbv, bzv / lbv
        d = re / math.sin(ang / 2)
        cx, cz = x + bxv * d, z + bzv * d
        sx, sz, ex, ez = x + ux * t, z + uz * t, x + vx * t, z + vz * t
        a0 = math.atan2(sz - cz, sx - cx)
        a1 = math.atan2(ez - cz, ex - cx)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        m = max(2, math.ceil(abs(da) / passo_ang))
        for k in range(m + 1):
            a = a0 + da * k / m
            out.append((cx + re * math.cos(a), cz + re * math.sin(a)))
    return _sem_repetidos(out)


def recuar(pts, o):
    """Desloca o polígono para dentro em `o` (miter limitado)."""
    if o <= 0:
        return list(pts)
    n = len(pts)
    s = 1.0 if _area(pts) > 0 else -1.0
    out = []
    for i in range(n):
        px, pz = pts[i - 1]
        x, z = pts[i]
        qx, qz = pts[(i + 1) % n]
        d1x, d1z, d2x, d2z = x - px, z - pz, qx - x, qz - z
        l1, l2 = math.hypot(d1x, d1z), math.hypot(d2x, d2z)
        n1 = (-d1z * s / l1, d1x * s / l1)
        n2 = (-d2z * s / l2, d2x * s / l2)
        mx, mz = n1[0] + n2[0], n1[1] + n2[1]
        lm = math.hypot(mx, mz)
        if lm < 1e-9:
            mx, mz = n1
        else:
            mx, mz = mx / lm, mz / lm
        c = max(mx * n1[0] + mz * n1[1], 0.35)
        out.append((x + mx * o / c, z + mz * o / c))
    return out


def _cruza(pts):
    """True se o polígono fechado se cruza (O(n²), só para conferência)."""
    n = len(pts)

    def lado(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = pts[j], pts[(j + 1) % n]
            if lado(a, b, c) * lado(a, b, d) < 0 and lado(c, d, a) * lado(c, d, b) < 0:
                return True
    return False


def bez3(p0, p1, p2, p3, n=16):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def _sgnpow(v, e):
    return math.copysign(abs(v) ** e, v)


def _suave(a, b, t):
    t = max(0.0, min(1.0, (t - a) / (b - a)))
    return t * t * (3 - 2 * t)


def chaikin(pts, vezes=2):
    """Suaviza um caminho aberto mantendo as pontas."""
    for _ in range(vezes):
        novo = [pts[0]]
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            novo += [(0.75 * ax + 0.25 * bx, 0.75 * az + 0.25 * bz), (0.25 * ax + 0.75 * bx, 0.25 * az + 0.75 * bz)]
        novo.append(pts[-1])
        pts = novo
    return pts


def _normais(caminho, lado):
    ns = []
    n = len(caminho)
    for i in range(n):
        ax, az = caminho[max(i - 1, 0)]
        bx, bz = caminho[min(i + 1, n - 1)]
        dx, dz = bx - ax, bz - az
        c = math.hypot(dx, dz)
        ns.append((lado * dz / c, -lado * dx / c))
    return ns


def _solido_de_aneis(nome, aneis, mat):
    bm = bmesh.new()
    vs = [[bm.verts.new(p) for p in anel] for anel in aneis]
    m = len(aneis[0])
    bm.faces.new(vs[0])
    bm.faces.new(vs[-1])
    for a, b in zip(vs, vs[1:]):
        for k in range(m):
            k2 = (k + 1) % m
            bm.faces.new([a[k], a[k2], b[k2], b[k]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4],
                          quad_method='BEAUTY', ngon_method='EAR_CLIP')
    return objeto(nome, bm, mat)


def varrer(nome, caminho, lado, meia_y, meia_n, mat, desloc=0.0, expoente=2.6, m=28):
    """Haste de seção oval arredondada correndo ao longo de um caminho (x, z).
    meia_y / meia_n: meia largura (em Y) e meia espessura (na normal), número ou função de t (0 a 1)."""
    fy = meia_y if callable(meia_y) else (lambda t: meia_y)
    fn = meia_n if callable(meia_n) else (lambda t: meia_n)
    ns = _normais(caminho, lado)
    aneis = []
    for i, ((x, z), (nx, nz)) in enumerate(zip(caminho, ns)):
        t = i / (len(caminho) - 1)
        wy, wn = fy(t), fn(t)
        cx, cz = x + nx * desloc, z + nz * desloc
        anel = []
        for k in range(m):
            a = 2 * math.pi * k / m
            dy = wy * _sgnpow(math.cos(a), 2 / expoente)
            dn = wn * _sgnpow(math.sin(a), 2 / expoente)
            anel.append((cx + nx * dn, dy, cz + nz * dn))
        aneis.append(anel)
    return _solido_de_aneis(nome, aneis, mat)


def _tampa_redonda(anel, f, b, centro_vizinho, w, raio, n):
    """Fatias extras que encolhem e se afastam da peça, arredondando uma ponta do cabo."""
    meio = (f + b) / 2
    eixo = (b - f).normalized()
    fora = Vector((eixo.y, -eixo.x))
    if fora.dot(meio - centro_vizinho) < 0:
        fora = -fora
    meio_l = (b - f).length / 2
    extras = []
    for k in range(1, n + 1):
        th = (math.pi / 2) * k / n
        enc, anda = raio * (1 - math.cos(th)), raio * math.sin(th)
        su, sy = max(1 - enc / meio_l, 0.05), max(1 - enc / w, 0.05)
        novo = []
        for (x, y, z) in anel:
            du = (Vector((x, z)) - meio).dot(eixo)
            pt = meio + eixo * du * su + fora * anda
            novo.append((pt.x, y * sy, pt.y))
        extras.append(novo)
    return extras


def cabo_solido(nome, frente, costas, largura, mat, m=64, expoente=2.0, raio_fundo=5.0, raio_topo=3.0,
                aneis_tampa=6, sulcos=None, alcance=0.42):
    """Cabo de madeira como sólido de fatias: cada fatia vai da linha da frente (lisa) à de trás e tem
    seção oval, com o volume puxado para trás (onde a palma encosta). `sulcos` (um valor por fatia,
    negativo = para dentro) afunda só a parte da frente da fatia, até `alcance` dela, para os sulcos
    dos dedos não ondularem os lados nem as costas. As duas pontas são arredondadas."""
    aneis = []
    for i, (f, b) in enumerate(zip(frente, costas)):
        t = i / (len(frente) - 1)
        w = largura(t)
        eixo = Vector((b[0] - f[0], b[1] - f[1])).normalized()
        sulco = sulcos[i] if sulcos else 0.0
        anel = []
        for k in range(m):
            a = 2 * math.pi * k / m
            u = 0.5 - 0.5 * _sgnpow(math.cos(a), 2 / expoente)
            u = u ** 0.86
            y = w * _sgnpow(math.sin(a), 2 / expoente)
            x, z = f[0] + (b[0] - f[0]) * u, f[1] + (b[1] - f[1]) * u
            if sulco and u < alcance:
                peso = (1 - u / alcance) ** 2
                x, z = x - eixo.x * sulco * peso, z - eixo.y * sulco * peso
            anel.append((x, y, z))
        aneis.append(anel)
    c = lambda i: (Vector(frente[i]) + Vector(costas[i])) / 2
    fundo = _tampa_redonda(aneis[-1], Vector(frente[-1]), Vector(costas[-1]), c(-2), largura(1.0),
                           raio_fundo, aneis_tampa)
    topo = _tampa_redonda(aneis[0], Vector(frente[0]), Vector(costas[0]), c(1), largura(0.0),
                          raio_topo, aneis_tampa)
    return _solido_de_aneis(nome, topo[::-1] + aneis + fundo, mat)


# ---------------------------------------------------------------- malhas

def objeto(nome, bm, mat=None):
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    return ob


def almofada(nome, pts, meia, r, mat, raio_canto=None, aneis=6):
    """Perfil (x, z) extrudado de -meia a +meia em Y com a borda arredondada de raio r."""
    base = arredondar(pts, raio_canto if raio_canto is not None else r * 1.3, raio_min=r * 1.15)
    niveis = []
    for k in range(aneis, -1, -1):
        th = (math.pi / 2) * k / aneis
        niveis.append((-(meia - r + r * math.sin(th)), r * (1 - math.cos(th))))
    for k in range(aneis + 1):
        th = (math.pi / 2) * k / aneis
        niveis.append((meia - r + r * math.sin(th), r * (1 - math.cos(th))))
    if _cruza(recuar(base, r)):
        AVISOS.append(f"{nome}: o contorno se cruza depois de recuar {r} mm (raio da borda grande demais)")
    bm = bmesh.new()
    aneis_v = []
    for y, o in niveis:
        aneis_v.append([bm.verts.new((x, y, z)) for x, z in recuar(base, o)])
    n = len(base)
    bm.faces.new(aneis_v[0])
    bm.faces.new(aneis_v[-1])
    for a, b in zip(aneis_v, aneis_v[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([a[i], a[j], b[j], b[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4],
                          quad_method='BEAUTY', ngon_method='EAR_CLIP')
    return objeto(nome, bm, mat)


def tornear(nome, pts, mat, pos=(0, 0, 0), eixo='x', seg=64, fechado=False):
    """Sólido de revolução: pts = [(posição no eixo, raio)]; raio 0 vira ponta.
    `fechado` liga o último anel ao primeiro (tubos ocos)."""
    bm = bmesh.new()
    aneis = []
    for t, r in pts:
        if r < 1e-9:
            aneis.append([bm.verts.new((t, 0, 0))])
        else:
            aneis.append([bm.verts.new((t, r * math.cos(2 * math.pi * k / seg),
                                        r * math.sin(2 * math.pi * k / seg))) for k in range(seg)])
    pares = list(zip(aneis, aneis[1:]))
    if fechado:
        pares.append((aneis[-1], aneis[0]))
    for a, b in pares:
        for k in range(seg):
            k2 = (k + 1) % seg
            vs = []
            for v in (a[k % len(a)], a[k2 % len(a)], b[k2 % len(b)], b[k % len(b)]):
                if v not in vs:
                    vs.append(v)
            if len(vs) >= 3:
                bm.faces.new(vs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if eixo == 'y':
        bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Z'))
    elif eixo == 'z':
        bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(-math.pi / 2, 3, 'Y'))
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=pos)
    return objeto(nome, bm, mat)


def caixa(nome, x0, x1, y0, y1, z0, z1, mat=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = ((x1 if v.co.x > 0 else x0), (y1 if v.co.y > 0 else y0), (z1 if v.co.z > 0 else z0))
    return objeto(nome, bm, mat)


def aplicar(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    novo = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    velho = ob.data
    nome = velho.name
    ob.modifiers.clear()
    ob.data = novo
    bpy.data.meshes.remove(velho)
    novo.name = nome


def booleano(base, ferramentas, op='DIFFERENCE'):
    if not ferramentas:
        return base
    col = bpy.data.collections.new("_ferramentas")
    bpy.context.scene.collection.children.link(col)
    for f in ferramentas:
        for c in list(f.users_collection):
            c.objects.unlink(f)
        col.objects.link(f)
    mod = base.modifiers.new("bool", 'BOOLEAN')
    mod.operation = op
    mod.solver = 'MANIFOLD'
    mod.operand_type = 'COLLECTION'
    mod.collection = col
    aplicar(base)
    for f in list(col.objects):
        malha = f.data
        bpy.data.objects.remove(f)
        bpy.data.meshes.remove(malha)
    bpy.data.collections.remove(col)
    return base


def acabar(ob, bisel=0.0, segmentos=3, angulo=36):
    """Chanfro opcional nas quinas vivas e sombreamento liso só onde a curva é suave."""
    if bisel > 0:
        m = ob.modifiers.new("bisel", 'BEVEL')
        m.width = bisel
        m.segments = segmentos
        m.limit_method = 'ANGLE'
        m.angle_limit = math.radians(50)
        aplicar(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lim = math.radians(angulo)
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(ob.data)
    bm.free()
    m = ob.modifiers.new("normais", 'WEIGHTED_NORMAL')
    m.mode = 'FACE_AREA'
    m.keep_sharp = True
    aplicar(ob)
    return ob


def girar(ob, rot, loc):
    ob.rotation_euler = rot
    ob.location = loc
    return ob



# ---------------------------------------------------------------- materiais e texturas

def material(nome, cor, metal=0.0, rug=0.5, imagem=None, verniz=0.0):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*cor, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rug
    if verniz:
        b.inputs["Coat Weight"].default_value = verniz
        b.inputs["Coat Roughness"].default_value = 0.12
    if imagem:
        t = m.node_tree.nodes.new("ShaderNodeTexImage")
        t.image = imagem
        m.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return m


def ruido(linhas, colunas, celulas_y, celulas_x, rng):
    g = rng.random((celulas_y + 2, celulas_x + 2))
    ty = np.linspace(0, celulas_y, linhas, endpoint=False)
    tx = np.linspace(0, celulas_x, colunas, endpoint=False)
    iy, ix = ty.astype(int), tx.astype(int)
    fy, fx = ty - iy, tx - ix
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    iy, fy, ix, fx = iy[:, None], fy[:, None], ix[None, :], fx[None, :]
    v00, v10 = g[iy, ix], g[iy, ix + 1]
    v01, v11 = g[iy + 1, ix], g[iy + 1, ix + 1]
    return (v00 * (1 - fx) + v10 * fx) * (1 - fy) + (v01 * (1 - fx) + v11 * fx) * fy


def _normalizar(t):
    return (t - t.min()) / (t.max() - t.min())


def _salvar_imagem(nome, rgb):
    n = rgb.shape[0]
    px = np.concatenate([rgb, np.ones((n, n, 1))], axis=2).astype(np.float32)
    img = bpy.data.images.new(nome, n, n)
    img.pixels.foreach_set(px.ravel())
    SAIDA.mkdir(exist_ok=True)
    img.filepath_raw = str(SAIDA / f"{nome}.png")
    img.file_format = 'PNG'
    img.save()
    return img


def uv_caixa(ob, escala=1 / 200.0):
    """Projeção de caixa (cada face pelo eixo dominante da normal), para a têmpera."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal
        eixo = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            c = l.vert.co
            u, v = ((c.y, c.z), (c.x, c.z), (c.x, c.y))[eixo]
            l[uv].uv = (u * escala + 0.5, v * escala + 0.5)
    bm.to_mesh(ob.data)
    bm.free()


def _juntar(base, extra, mat):
    """Põe a malha de `extra` dentro de `base`, com o material dado, e apaga `extra`. O índice é procurado pelo
    material: o booleano deixa espaços vazios na lista de materiais da peça."""
    nomes = [m.name if m else None for m in base.data.materials]
    if mat.name not in nomes:
        base.data.materials.append(mat)
        nomes.append(mat.name)
    indice_material = nomes.index(mat.name)
    bm = bmesh.new()
    bm.from_mesh(extra.data)
    for f in bm.faces:
        f.material_index = indice_material
    tmp = bpy.data.meshes.new("_tmp")
    bm.to_mesh(tmp)
    bm.free()
    bm = bmesh.new()
    bm.from_mesh(base.data)
    bm.from_mesh(tmp)
    bm.to_mesh(base.data)
    bm.free()
    malha = extra.data
    bpy.data.objects.remove(extra)
    bpy.data.meshes.remove(malha)
    bpy.data.meshes.remove(tmp)


def _pivo(ob, ponto):
    """Muda a origem da peça para o ponto em que ela gira, sem mexer na forma (peça sem transformação)."""
    p = Vector(ponto)
    ob.data.transform(Matrix.Translation(-p))
    ob.location = p


def _prender(filho, pai):
    mw = filho.matrix_world.copy()
    filho.parent = pai
    filho.matrix_world = mw


class Faixa:
    """Uma animação com nome (vira uma faixa de NLA e uma animação no GLB). As chaves de cada peça vão
    de 1 a `fim`, para todas começarem e acabarem juntas."""

    def __init__(self, nome, inicio, fim, extrapolacao='NOTHING'):
        self.nome, self.inicio, self.fim, self.extrapolacao = nome, inicio, fim, extrapolacao
        self.chaves = {}

    def k(self, ob, prop, quadro, valor, interp='BEZIER'):
        self.chaves.setdefault(ob, []).append((quadro, prop, tuple(valor), interp))

    def gravar(self, repouso):
        from bpy_extras import anim_utils
        for ob, lista in self.chaves.items():
            por_prop = {}
            for c in lista:
                por_prop.setdefault(c[1], []).append(c)
            ob.animation_data_create()
            ob.animation_data.action = None
            interps = {}
            for prop, cs in por_prop.items():
                cs.sort(key=lambda c: c[0])
                if cs[0][0] > 1:
                    cs.insert(0, (1, prop, cs[0][2], 'CONSTANT'))
                if cs[-1][0] < self.fim:
                    cs.append((self.fim, prop, cs[-1][2], 'CONSTANT'))
                for quadro, _, valor, interp in cs:
                    setattr(ob, prop, valor)
                    ob.keyframe_insert(prop, frame=quadro)
                    interps[(prop, quadro)] = interp
            acao = ob.animation_data.action
            # o keyframe_insert ignora a interpolação pedida: grava chave por chave na curva
            canais = anim_utils.action_get_channelbag_for_slot(acao, ob.animation_data.action_slot)
            for fc in canais.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = interps.get((fc.data_path, round(kp.co.x)), 'BEZIER')
            acao.name = f"{self.nome}|{ob.name}"
            trilha = ob.animation_data.nla_tracks.new()
            trilha.name = self.nome
            faixa = trilha.strips.new(self.nome, self.inicio, acao)
            faixa.extrapolation = self.extrapolacao
            ob.animation_data.action = None
            for prop, valor in repouso[ob].items():
                setattr(ob, prop, valor)


def luz_de_estudio(nome, pos, alvo, tam, forca):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    for v in bm.verts:
        v.co = (v.co.x * tam[0] * 2, v.co.y * tam[1] * 2, 0)
    ob = objeto(nome, bm)
    d = Vector(alvo) - Vector(pos)
    ob.rotation_euler = d.to_track_quat('Z', 'Y' if abs(d.normalized().z) < 0.9 else 'X').to_euler()
    ob.location = pos
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = forca
    saida = nodes.new("ShaderNodeOutputMaterial")
    m.node_tree.links.new(em.outputs["Emission"], saida.inputs["Surface"])
    ob.data.materials.append(m)
    ob.visible_camera = False
    ob.visible_shadow = False
    return ob




# ---------------------------------------------------------------- a AK-47

def textura_madeira(nome, escuro, claro, semente):
    """Madeira laqueada (como a da AK do CS2): anéis largos com veios escuros finos e fibras."""
    n = 1024
    rng = np.random.default_rng(semente)
    v = np.linspace(0, 1, n, endpoint=False)[:, None]
    fase = v * 9 + 3.2 * ruido(n, n, 3, 2, rng) + 1.3 * ruido(n, n, 8, 4, rng) + 0.35 * ruido(n, n, 24, 10, rng)
    aneis = (0.5 + 0.5 * np.sin(2 * np.pi * fase)) ** 1.8
    veios = np.exp(-(((fase % 1.0) - 0.5) ** 2) / 0.0007)
    fibras = ruido(n, n, 320, 6, rng) * 0.6 + ruido(n, n, 90, 3, rng) * 0.4
    manchas = ruido(n, n, 3, 3, rng)
    t = _normalizar(0.14 * aneis + 0.56 * fibras + 0.30 * manchas - 0.06 * veios)
    escuro, claro = np.array(escuro), np.array(claro)
    return _salvar_imagem(nome, escuro + (claro - escuro) * t[..., None])


def uv_ao_longo(ob, eixo='x', comprimento=300.0, altura=70.0):
    """Uma projeção só, contínua (sem emenda): o veio corre ao longo de X (coronha e guarda-mãos) ou de Z (punho)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for l in f.loops:
            c = l.vert.co
            if eixo == 'x':
                l[uv].uv = (c.x / comprimento, (c.z + 0.6 * c.y) / altura)
            else:
                l[uv].uv = (c.z / comprimento, (c.x + 0.6 * c.y) / altura)
    bm.to_mesh(ob.data)
    bm.free()


def prisma_x(nome, pts_yz, x0, x1, r, mat):
    """Seção vista de frente (y, z), cantos arredondados, extrudada em X de x0 a x1 com a borda de raio r."""
    ob = almofada(nome, pts_yz, (x1 - x0) / 2, r, mat)
    ob.data.transform(Matrix.Translation(((x0 + x1) / 2, 0, 0)) @ Matrix.Rotation(-math.pi / 2, 4, 'Z'))
    return ob


def deslocar(ob, v):
    ob.data.transform(Matrix.Translation(v))
    return ob


def girar_malha(ob, angulo, pivo):
    """Gira a malha em volta do eixo Y que passa por `pivo` (peça parada, montada numa posição só)."""
    p = Vector(pivo)
    ob.data.transform(Matrix.Translation(p) @ Matrix.Rotation(angulo, 4, 'Y') @ Matrix.Translation(-p))
    return ob


def pino(nome, x, z, raio, meia, mat):
    perfil = [(-meia, 0), (-meia, raio * 0.8), (-meia + 0.5, raio), (meia - 0.5, raio), (meia, raio * 0.8), (meia, 0)]
    return acabar(tornear(nome, perfil, mat, pos=(x, 0, z), eixo='y', seg=32))


def reamostrar(linha, n):
    """n+1 pontos igualmente espaçados (pelo comprimento) ao longo de uma linha (x, z)."""
    comp = [0.0]
    for (ax, az), (bx, bz) in zip(linha, linha[1:]):
        comp.append(comp[-1] + math.hypot(bx - ax, bz - az))
    out = []
    for i in range(n + 1):
        alvo = comp[-1] * i / n
        k = max(j for j in range(len(comp) - 1) if comp[j] <= alvo + 1e-9) if alvo > 0 else 0
        k = min(k, len(linha) - 2)
        f = (alvo - comp[k]) / max(comp[k + 1] - comp[k], 1e-9)
        (ax, az), (bx, bz) = linha[k], linha[k + 1]
        out.append((ax + (bx - ax) * f, az + (bz - az) * f))
    return out


def no_arco(ang, raio):
    """Ponto (x, z) no arco do pente."""
    return (CENTRO_PENTE.x + raio * math.cos(ang), CENTRO_PENTE.z + raio * math.sin(ang))


def construir():
    """Proporções de uma AK-47 de coronha fixa (870 mm), medidas numa foto de lado da arma real e conferidas com a
    AK-47 do CS2: cano comprido com a massa de mira em torre, bloco de gás inclinado e tubo de gás por cima; guarda-mão
    de madeira em duas partes; bloco da alça com a alça tangente; caixa da culatra estampada com a tampa por cima;
    pente curvo de 30; punho inclinado 20°; coronha de madeira caída 23° embaixo, com a soleira de aço."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    aco = material("aco", (0.20, 0.205, 0.20), metal=0.65, rug=0.55)
    escuro = material("aco_escuro", (0.14, 0.14, 0.145), metal=0.6, rug=0.6)
    aco_pente = material("aco_pente", (0.17, 0.17, 0.18), metal=0.65, rug=0.55)
    madeira = material("madeira", (1, 1, 1), rug=0.4, verniz=0.4,
                       imagem=textura_madeira("madeira", (0.20, 0.075, 0.025), (0.46, 0.20, 0.07), 47))
    madeira_punho = material("madeira_punho", (1, 1, 1), rug=0.45, verniz=0.3,
                             imagem=textura_madeira("madeira_punho", (0.10, 0.032, 0.016), (0.24, 0.085, 0.045), 91))
    P = {}

    # ---- cano, quebra-chamas (o compensador inclinado da AKM), massa de mira em torre, bloco e tubo de gás
    cano = tornear("cano", [(-4, 0), (-4, 10), (46, 10), (46, 9.2), (226, 9.2), (226, 8.2), (330, 8.2), (330, 7.6),
                            (352, 7.6), (352, 0)], aco, seg=48)
    booleano(cano, [tornear("_alma", [(300, 0), (300, R_ALMA), (360, R_ALMA), (360, 0)], None, seg=32)])
    P["cano"] = acabar(cano)

    qc = tornear("quebra_chamas", [(349, 0), (349, 9.6), (350, 10.2), (X_BOCA - 0.8, 10.2), (X_BOCA, 9.6),
                                   (X_BOCA, 0)], aco, seg=48)
    rampa = girar(caixa("_rampa", 0, 40, -16, 16, -40, 40), (0, math.radians(-31), 0), (377.5, 0, 0))
    booleano(qc, [tornear("_alma_qc", [(340, 0), (340, 4.6), (X_BOCA + 6, 4.6), (X_BOCA + 6, 0)], None, seg=32),
                  rampa])
    P["quebra_chamas"] = acabar(qc, 0.25, 2)

    torre = almofada("massa_mira", [(337, 8), (349, 8), (349, 44, 3), (347.5, 51, 3), (338.5, 51, 3), (337, 44)],
                     7.5, 1.0, aco)
    booleano(torre, [almofada("_base_mira", [(328, -16, 2), (355, -16, 2), (355, 4, 2), (351, 12, 3), (334, 12, 3),
                                             (328, 8)], 10.0, 1.2, None)], 'UNION')
    booleano(torre, [caixa("_janela_mira", 330, 360, -4.6, 4.6, 25, 60)])
    acabar(torre, 0.25, 2)
    _juntar(torre, acabar(almofada("_poste", [(341, 20), (344.5, 20), (344, 45), (341.5, 45)], 1.2, 0.4, None)),
            escuro)
    P["massa_mira"] = torre

    P["bloco_gas"] = acabar(almofada("bloco_gas", [(225, -15), (258, -15), (263, -8), (263, 9), (258, 13),
                                                   (237, 35), (225, 35)], 10.5, 1.5, aco), 0.3, 2)
    tubo = tornear("tubo_gas", [(40, 0), (40, 9.5), (232, 9.5), (232, 0)], aco, pos=(0, 0, 25), seg=40)
    booleano(tubo, [tornear(f"_respiro{k}", [(-12, 0), (-12, 2.3), (12, 2.3), (12, 0)], None,
                            pos=(196 + 9 * k, 0, 25), eixo='y', seg=20) for k in range(3)])
    P["tubo_gas"] = acabar(tubo)
    P["vareta"] = acabar(tornear("vareta", [(0, 0), (0, 3), (338, 3), (340, 2.4), (340, 0)], escuro,
                                 pos=(0, 0, -12), seg=20))
    P["anel_guarda_mao"] = acabar(tornear("anel_guarda_mao", [(170, 0), (170, 13.5), (171, 14.2), (180, 14.2),
                                                              (181, 13.5), (181, 0)], aco, pos=(0, 0, -4), seg=40))

    # ---- guarda-mãos de madeira: o de cima em volta do tubo de gás, o de baixo com a barriga para a palma
    sup = prisma_x("guarda_mao_superior", [(13.5, 15, 2), (13.5, 32, 4), (8, 42.5, 6), (-8, 42.5, 6), (-13.5, 32, 4),
                                           (-13.5, 15, 2)], 46, 150, 2.5, madeira)
    uv_ao_longo(acabar(sup, angulo=40))
    P["guarda_mao_superior"] = sup
    xs = [174 - 162 * i / 26 for i in range(27)]
    fundo = lambda x: -18 - 7 * (174 - x) / 162 - 2.5 * math.sin(math.pi * (174 - x) / 162)
    inf = cabo_solido("guarda_mao_inferior", [(x, 13.5) for x in xs], [(x, fundo(x)) for x in xs],
                      lambda t: 13.5 + 3.5 * math.sin(math.pi * min(t / 0.6, 1) * 0.5) - 1.0 * max(0, t - 0.6) / 0.4,
                      madeira, m=56, expoente=3.2, raio_fundo=2.0, raio_topo=3.5, aneis_tampa=5)
    uv_ao_longo(acabar(inf, angulo=40))
    P["guarda_mao_inferior"] = inf
    P["retentor"] = acabar(almofada("retentor", [(-1, -26), (13, -26), (13, 13), (-1, 13)], 16.0, 1.6, aco), 0.25, 2)

    # ---- bloco da alça e a alça tangente (folha com o cursor e o entalhe atrás)
    P["bloco_alca"] = acabar(almofada("bloco_alca", [(0, 10), (45, 10), (45, 20, 3), (38, 31, 4), (28, 36, 3),
                                                     (0, 36)], 12.0, 1.5, aco), 0.3, 2)
    folha = almofada("alca_mira", [(30, 36), (30, 39.5, 1.5), (-21, 43.8, 1.5), (-24, 43.8, 1), (-24, 40.2, 1),
                                   (24, 36)], 6.2, 0.6, escuro)
    booleano(folha, [caixa("_entalhe", -26, -16, -1.2, 1.2, 41.6, 46)])
    acabar(folha, 0.15, 2)
    _juntar(folha, acabar(almofada("_cursor", [(9, 35.5), (17, 35.5), (17, 42.8), (9, 42.6)], 7.4, 0.8, None)),
            escuro)
    P["alca_mira"] = folha

    # ---- caixa da culatra estampada: canal do ferrolho por dentro (aberto em cima, embaixo da tampa), janela de
    # ejeção e fenda da alavanca de manejo à direita, poço do pente, fendas do gatilho e do retém, e a covinha da AKM
    # dos dois lados em cima do poço
    caixa_c = almofada("caixa", [(0, -29), (0, 18), (-264, 18), (-264, -33), (-112, -33), (-104, -29)], MEIA_CAIXA,
                       1.6, aco)
    cortes = [caixa("_canal", -258, -6, -10.5, 10.5, -17.5, 25),
              caixa("_poco", -110.5, -47.5, -13.2, 13.2, -45, -13),
              caixa("_janela", -118, -45, -20, -8, 0, 14),
              caixa("_fenda_manejo", -258, -30, -20, -8, 10, 25),
              caixa("_fenda_gatilho", -142, -120, -3.2, 3.2, -45, -15),
              caixa("_fenda_botao", -119, -108, -5.8, 5.8, -45, -15)]
    for lado in (-1, 1):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=8.0)
        esfera = objeto(f"_covinha{lado}", bm)
        esfera.location = (-78, lado * (MEIA_CAIXA + 6.5), -10)
        cortes.append(esfera)
    booleano(caixa_c, cortes)
    P["caixa"] = acabar(caixa_c, 0.3, 2)
    rebites = None
    for k, (x, z, raio) in enumerate([(-9, -4, 2.2), (-9, -21, 2.2), (-24, -21, 2.2), (-36, -24, 2.2),
                                      (-129, -23, 2.6), (-160, -18, 2.6), (-222, -14, 2.2), (-246, -14, 2.2),
                                      (-246, -26, 2.2)]):
        p = pino(f"rebite{k}", x, z, raio, MEIA_CAIXA + 0.6, escuro)
        if rebites is None:
            rebites = p
            rebites.name = rebites.data.name = "rebites"
        else:
            _juntar(rebites, p, escuro)
    P["rebites"] = rebites

    # ---- tampa da caixa, oca por baixo, com o botão da guia da mola atrás
    tampa = almofada("tampa", [(-6, 14), (-6, 33), (-11, 37.6), (-246, 37.6), (-258, 31), (-263, 22), (-263, 14)],
                     15.3, 2.0, aco)
    booleano(tampa, [caixa("_oco", -257, -9, -12.2, 12.2, 8, 34)])
    acabar(tampa, 0.3, 2)
    _juntar(tampa, acabar(tornear("_botao_mola", [(0, 0), (0, 3.6), (2.6, 3.3), (3.4, 2.2), (3.4, 0)], None,
                                  pos=(-252, 0, 36.2), eixo='z', seg=24)), escuro)
    P["tampa"] = tampa

    # ---- seletor grande à direita, na posição de rajada (meio caminho); o pivô fica atrás
    seletor = almofada("seletor", [(-238, -4, 5), (-232, 6, 3), (-142, 6, 2), (-142, -1, 1.5), (-128, -1, 1.5),
                                   (-128, 15.5, 2), (-240, 15.5, 4), (-248, 6, 4)], 0.8, 0.5, escuro)
    deslocar(seletor, (0, -(MEIA_CAIXA + 0.75), 0))
    _juntar(seletor, acabar(tornear("_eixo_seletor", [(0, 0), (0, 6.5), (-2.2, 6.0), (-2.6, 4.5), (-2.6, 0)], None,
                                    pos=(-238, -(MEIA_CAIXA + 1.5), 5), eixo='y', seg=32)), escuro)
    girar_malha(seletor, math.radians(5), (-238, 0, 5))
    P["seletor"] = acabar(seletor)

    # ---- ferrolho: transportador, cabeça do ferrolho no eixo do cano e a alavanca de manejo à direita
    fer = almofada("ferrolho", [(-38, 1), (-38, 17.5), (-160, 17.5), (-160, 1)], 9.8, 1.5, aco)
    acabar(fer, 0.3, 2)
    _juntar(fer, acabar(tornear("_cabeca", [(-60, 0), (-60, 8.4), (-7.5, 8.4), (-7, 7.8), (-7, 0)], None, seg=40)),
            aco)
    _juntar(fer, acabar(caixa("_braco", -49, -38, -27, -8, 10.5, 13.5), 0.5, 2), aco)
    _juntar(fer, acabar(tornear("_bola", [(0, 0), (0, 4.6), (-5, 5.6), (-10, 5.3), (-13.5, 3.2), (-14, 0)], None,
                                pos=(-43.5, -24, 12.5), eixo='y', seg=32)), aco)
    P["ferrolho"] = fer

    # ---- gatilho, guarda-mato de chapa, retém do pente (a alavanca atrás do poço), punho e coronha
    P["gatilho"] = acabar(almofada("gatilho", [(-126, -20), (-132, -20), (-133, -32), (-136, -42), (-138, -49, 1.5),
                                               (-134, -50, 1.5), (-131.5, -42), (-127.5, -31)], 2.6, 0.9, escuro))
    linha = chaikin([(-121, -28), (-122, -48), (-125, -62), (-133, -67), (-168, -67), (-178, -62), (-183, -50),
                     (-184, -34)], 2)
    P["guarda_mato"] = acabar(varrer("guarda_mato", linha, -1, 5.5, 1.5, aco, expoente=3.0), angulo=40)
    P["botao_pente"] = acabar(almofada("botao_pente", [(-110, -24), (-116.5, -24), (-117, -38), (-119, -47, 1.5),
                                                       (-113, -48, 1.5), (-111.5, -38)], 4.5, 1.0, escuro))

    frente = reamostrar([(-181, -28), (-189, -55), (-205, -100), (-222, -139)], 24)
    costas = reamostrar([(-234, -28), (-243, -58), (-255, -100), (-257, -134)], 24)
    punho = cabo_solido("punho", frente, costas, lambda t: 13 + 1.6 * math.sin(math.pi * t), madeira_punho, m=56,
                        expoente=2.2, raio_fundo=6.0, raio_topo=2.0)
    uv_ao_longo(acabar(punho, angulo=40), eixo='z', comprimento=150, altura=60)
    P["punho"] = punho

    topo = reamostrar([(-262, 5), (-305, -0.5), (-382, -3.2), (-421, -9.3), (-460, -16.4), (-501, -23)], 30)
    baixo = reamostrar([(-262, -37.7), (-305, -53.4), (-344, -69.4), (-382, -87.4), (-421, -104.6), (-460, -123.4),
                        (-478, -130)], 30)
    coronha = cabo_solido("coronha", topo, baixo, lambda t: 12.5 + 6 * t ** 0.8, madeira, m=64, expoente=2.6,
                          raio_fundo=1.5, raio_topo=2.0, aneis_tampa=5)
    uv_ao_longo(acabar(coronha, angulo=40), comprimento=320, altura=90)
    P["coronha"] = coronha
    f1, b1 = Vector(topo[-1]), Vector(baixo[-1])
    s = (b1 - f1).normalized()
    n = Vector((s.y, -s.x))                      # para trás, saindo da coronha
    if n.x > 0:
        n = -n
    sol_f = [tuple(f1 + n * o - s * 1.0) for o in (-0.6, 1.5, 3.6)]
    sol_b = [tuple(b1 + n * o + s * 1.0) for o in (-0.6, 1.5, 3.6)]
    P["soleira"] = acabar(cabo_solido("soleira", sol_f, sol_b, lambda t: 19.0, escuro, m=64, expoente=2.6,
                                      raio_fundo=1.2, raio_topo=0.6, aneis_tampa=3))

    P["pente"] = construir_pente(aco_pente)
    municao(P)
    clarao(P)
    return P


def construir_pente(mat):
    """Pente curvo de 30 de aço: haste de seção quase retangular varrida ao longo do arco (mais funda em cima), com
    duas nervuras de cada lado e a base. A origem é o centro do fundo (embaixo da base)."""
    n = 44
    caminho = [no_arco(ANG_TOPO + (ANG_FUNDO - ANG_TOPO) * i / n, R_PENTE) for i in range(n + 1)]
    pente = varrer("pente", caminho, 1, 12.5, lambda t: 29.5 - 3.5 * t, mat, expoente=7, m=40)
    acabar(pente, angulo=40)
    for lado in (-1, 1):
        for desloc in (-13.0, 11.0):
            a0, a1 = math.radians(191.5), ANG_FUNDO - math.radians(3)
            nervura = [no_arco(a0 + (a1 - a0) * i / 30, R_PENTE + desloc) for i in range(31)]
            _juntar(pente, acabar(deslocar(varrer("_nervura", nervura, 1, 0.8, 2.2, None, m=16),
                                           (0, lado * 12.6, 0))), mat)
    rad = Vector((math.cos(ANG_FUNDO), 0, math.sin(ANG_FUNDO)))
    tan = Vector((-math.sin(ANG_FUNDO), 0, math.cos(ANG_FUNDO)))
    fx, fz = no_arco(ANG_FUNDO, R_PENTE)
    fim = Vector((fx, 0, fz))
    cantos = [fim + rad * a + tan * b for a, b in ((-30, -1.5), (30, -1.5), (30, 3.5), (-30, 3.5))]
    base = almofada("_base", [(c.x, c.z, 2.0) for c in cantos], 14.0, 1.2, None)
    _juntar(pente, acabar(base), mat)
    _pivo(pente, fim + tan * 3.5)
    return pente


def municao(P):
    """Cartucho 7,62x39: estojo de latão garrafinha (com o canal do extrator) e espoleta, ponta encamisada de cobre.
    O mesmo estojo aparece duas vezes: o que sai pela janela no tiro (escondido em repouso, na câmara) e o de cima do
    pente, com a ponta, deitado em cima do pente."""
    latao = material("latao", (0.80, 0.6, 0.34), metal=1.0, rug=0.3)
    espoleta = material("espoleta", (0.62, 0.6, 0.56), metal=1.0, rug=0.35)
    cobre = material("cobre", (0.72, 0.42, 0.26), metal=1.0, rug=0.32)
    estojo = tornear("estojo_ejetado", [(0, 0), (0, 5.4), (0.4, 5.67), (1.4, 5.67), (1.6, 4.6), (2.6, 4.6),
                                        (3.1, 5.62), (30.0, 5.0), (32.5, 4.3), (38.7, 4.3), (38.7, 0)], latao, seg=40)
    _juntar(estojo, tornear("_espoleta", [(-0.1, 0), (-0.1, 2.7), (0.2, 2.7), (0.2, 0)], None, seg=24), espoleta)
    acabar(estojo)
    estojo.location = (-7, 0, 0)
    bala = acabar(tornear("bala_topo", [(33, 0), (33, 3.96), (42, 3.96), (47, 3.5), (52, 2.3), (55.4, 0.8), (56, 0)],
                          cobre, seg=40))
    topo = bpy.data.objects.new("estojo_topo", estojo.data)
    bpy.context.scene.collection.objects.link(topo)
    deitado = Matrix.Translation(POS_BALA_TOPO)
    topo.matrix_world = deitado
    bala.matrix_world = deitado
    P["estojo_ejetado"], P["estojo_topo"], P["bala_topo"] = estojo, topo, bala


def clarao(P):
    """O clarão da boca: um cone de fogo e uma estrela de oito pontas, com a origem na boca."""
    mat = material("clarao", (1.0, 0.78, 0.4))
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (1.0, 0.62, 0.22, 1)
    b.inputs["Emission Strength"].default_value = 40.0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=9.0, radius2=0.0, depth=60)
    bmesh.ops.rotate(bm, verts=bm.verts[:], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=(30.0, 0, 0))
    pontas = []
    for i in range(16):
        r = 34.0 if i % 2 == 0 else 7.0
        a = 2 * math.pi * i / 16
        pontas.append((r * math.cos(a), r * math.sin(a)))
    frente = [bm.verts.new((1.8, y, z)) for y, z in pontas]
    tras = [bm.verts.new((0.6, y, z)) for y, z in pontas]
    bm.faces.new(frente)
    bm.faces.new(tras)
    for i in range(16):
        j = (i + 1) % 16
        bm.faces.new([frente[i], frente[j], tras[j], tras[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    ob = objeto("clarao", bm, mat)
    ob.location = (X_BOCA + 0.4, 0, 0)
    P["clarao"] = ob


# ---------------------------------------------------------------- animações

# onde cada faixa começa na linha do tempo do .blend (30 qps) e quantos quadros ela tem
TIRO_INICIO, TIRO_FIM = 1, 4
REC_INICIO, REC_FIM = 10, 75
EVENTOS = {"tiro": {"disparo": 2},
           "recarregar": {"pente_sai": 18, "troca": 35, "pente_entra": 54, "ferrolho": 64}}
RECUO = (-212.0, 0.0, -78.0)          # onde a mão segura (no punho): o coice gira a arma em volta daqui
POS_BALA_TOPO = Vector((-106.0, 3.0, -15.0))  # base do cartucho de cima, deitado em cima do pente
PIVO_GATILHO = (-129.0, 0.0, -23.0)
PIVO_BOTAO = (-113.0, 0.0, -25.0)
PIVO_PENTE = Vector((-50.0, 0.0, -30.0))   # o dente da frente do pente: ele gira em volta dali para sair e entrar
GATILHO_PUXADO = math.radians(12)
BOTAO_APERTADO = math.radians(-10)
INCLINADA = (math.radians(-22), math.radians(-8), 0.0)   # deitada para a direita aparecer, boca um pouco para cima
VISTAS_ANIMACAO = {}


def no_quadro(inicio, q):
    """Quadro da cena para o quadro q de uma faixa (q = 1 é o primeiro)."""
    return inicio + q - 1


def animar(P):
    """Pivôs, hierarquia e as faixas: repouso, tiro (4 quadros, o mod repete na rajada) e recarregar."""
    cena = bpy.context.scene
    cena.render.fps = 30
    _pivo(P["gatilho"], PIVO_GATILHO)
    _pivo(P["botao_pente"], PIVO_BOTAO)
    raiz = bpy.data.objects.new(NOME, None)
    raiz.empty_display_size = 60
    cena.collection.objects.link(raiz)
    raiz.location = RECUO
    bpy.context.view_layer.update()
    for nome, ob in P.items():
        if nome not in ("estojo_topo", "bala_topo"):
            _prender(ob, raiz)
    bpy.context.view_layer.update()
    for nome in ("estojo_topo", "bala_topo"):
        _prender(P[nome], P["pente"])
    bpy.context.view_layer.update()
    P["clarao"].scale = (0, 0, 0)
    P["estojo_ejetado"].scale = (0, 0, 0)

    fer, gat, botao, pente, flash, ejet = (P[n] for n in (
        "ferrolho", "gatilho", "botao_pente", "pente", "clarao", "estojo_ejetado"))
    animados = [raiz, fer, gat, botao, pente, flash, ejet]
    repouso = {ob: {"location": tuple(ob.location), "rotation_euler": tuple(ob.rotation_euler),
                    "scale": tuple(ob.scale)} for ob in animados}
    loc0 = {ob: Vector(repouso[ob]["location"]) for ob in animados}
    aberto = loc0[fer] + Vector((-CURSO, 0, 0))
    R = math.radians

    base = Faixa("repouso", 1, 2, 'HOLD')
    for ob in animados:
        for prop, valor in repouso[ob].items():
            base.k(ob, prop, 1, valor)
            base.k(ob, prop, 2, valor)
    base.gravar(repouso)

    # ---- tiro: 4 quadros, começa e termina parada para a rajada repetir sem pulo. Quadro 2: o dedo puxa, clarão
    # cheio, o ferrolho no meio do caminho e o estojo saindo pela janela; quadro 3: ferrolho atrás, o estojo uns
    # centímetros para fora e o clarão acabando; quadro 4: tudo no lugar e o estojo some
    t = Faixa("tiro", TIRO_INICIO, TIRO_FIM)
    for q, a in [(1, 0), (2, GATILHO_PUXADO), (3, GATILHO_PUXADO), (4, 0)]:
        t.k(gat, "rotation_euler", q, (0, a, 0), 'LINEAR')
    for q, dx in [(1, 0), (2, -0.55 * CURSO), (3, -CURSO), (4, 0)]:
        t.k(fer, "location", q, loc0[fer] + Vector((dx, 0, 0)), 'LINEAR')
    for q, esc in [(1, 0), (2, 1.0), (3, 0.45), (4, 0)]:
        t.k(flash, "scale", q, (esc * 1.15, esc, esc), 'CONSTANT')
    for q, rot in [(1, 0), (2, 0), (3, 0.55), (4, 0)]:
        t.k(flash, "rotation_euler", q, (rot, 0, 0), 'CONSTANT')
    camara = Vector((-7, 0, 0))
    for q, esc, onde, rot in [(1, 0, camara, (0, 0, 0)), (2, 1, Vector((-86, -12, 7)), (0, 0, -0.6)),
                              (3, 1, Vector((-96, -56, 30)), (1.2, 0.4, -1.7)), (4, 0, camara, (0, 0, 0))]:
        t.k(ejet, "scale", q, (esc, esc, esc), 'CONSTANT')
        t.k(ejet, "location", q, loc0[ejet] + (onde - camara), 'CONSTANT')
        t.k(ejet, "rotation_euler", q, rot, 'CONSTANT')
    for q, giro, desl in [(1, 0, (0, 0, 0)), (2, -2.2, (-5, 0, 1.5)), (3, -1.2, (-3, 0, 1)), (4, 0, (0, 0, 0))]:
        t.k(raiz, "rotation_euler", q, (0, R(giro), 0), 'LINEAR')
        t.k(raiz, "location", q, loc0[raiz] + Vector(desl), 'LINEAR')
    t.gravar(repouso)
    VISTAS_ANIMACAO["anim-tiro"] = no_quadro(TIRO_INICIO, 3)

    # ---- recarregar: deita a arma, aperta o retém, o pente velho gira para a frente em volta do dente da frente e
    # cai, o novo engata o dente e gira para trás até travar, puxa e solta o ferrolho
    r = Faixa("recarregar", REC_INICIO, REC_FIM)
    alto = loc0[raiz] + Vector((0, 0, 12))
    for q, rot, loc in [(1, (0, 0, 0), loc0[raiz]), (12, INCLINADA, alto), (53, INCLINADA, alto),
                        (55, INCLINADA, alto + Vector((0, 0, -3))), (57, INCLINADA, alto), (64, INCLINADA, alto),
                        (66, (INCLINADA[0], INCLINADA[1] - R(2), 0), alto + Vector((-3, 0, 0))),
                        (73, (0, 0, 0), loc0[raiz])]:
        r.k(raiz, "rotation_euler", q, rot)
        r.k(raiz, "location", q, loc)
    for q, a in [(14, 0), (17, BOTAO_APERTADO), (23, BOTAO_APERTADO), (26, 0)]:
        r.k(botao, "rotation_euler", q, (0, a, 0))

    pivo = PIVO_PENTE - Vector(RECUO)          # o dente da frente, no espaço da raiz

    def pose(graus, desl=(0, 0, 0)):
        rot = Matrix.Rotation(R(graus), 3, 'Y')
        return pivo + rot @ (loc0[pente] - pivo) + Vector(desl), (0, R(graus), 0)

    chaves = [(18, 0, (0, 0, 0), 'BEZIER'), (20, -6, (0, 0, 0), 'LINEAR'), (22, -13, (0, 0, 0), 'LINEAR'),
              (24, -20, (0, 0, 0), 'BEZIER'), (29, -28, (25, 0, -70), 'LINEAR'), (32, -38, (40, 0, -160), 'CONSTANT'),
              (37, -30, (40, 0, -130), 'BEZIER'), (44, -22, (6, 0, -14), 'BEZIER'), (48, -20, (0, 0, 0), 'LINEAR'),
              (50, -13.3, (0, 0, 0), 'LINEAR'), (52, -6.7, (0, 0, 0), 'LINEAR'), (54, 0, (0, 0, 0), 'BEZIER')]
    for q, graus, desl, interp in chaves:
        loc, rot = pose(graus, desl)
        r.k(pente, "location", q, loc, interp)
        r.k(pente, "rotation_euler", q, rot, interp)
    for q, esc in [(32, 1), (33, 0), (36, 0), (37, 1)]:
        r.k(pente, "scale", q, (esc, esc, esc), 'CONSTANT')
    for q, pos, interp in [(56, loc0[fer], 'BEZIER'), (60, aberto, 'LINEAR'), (62, aberto, 'LINEAR'),
                           (64, loc0[fer], 'BEZIER')]:
        r.k(fer, "location", q, pos, interp)
    r.gravar(repouso)
    VISTAS_ANIMACAO["anim-recarga"] = no_quadro(REC_INICIO, 46)

    cena.frame_start, cena.frame_end = 1, REC_INICIO + REC_FIM + 4
    for nome, quadro in [("tiro", TIRO_INICIO), ("recarregar", REC_INICIO)]:
        cena.timeline_markers.new(nome, frame=quadro)
    cena.frame_set(0)
    return raiz


def conferir_movimento(P):
    """Mede, em momentos das animações, quantos triângulos de cada par de peças se cruzam, comparado com o
    repouso: número que cresce muito é peça atravessando outra."""
    from mathutils.bvhtree import BVHTree
    cena = bpy.context.scene
    pares = [("ferrolho", "caixa"), ("ferrolho", "tampa"), ("ferrolho", "cano"), ("ferrolho", "seletor"),
             ("ferrolho", "bala_topo"), ("ferrolho", "estojo_topo"), ("gatilho", "caixa"), ("gatilho", "guarda_mato"),
             ("pente", "caixa"), ("pente", "botao_pente"), ("pente", "guarda_mato"), ("pente", "guarda_mao_inferior"),
             ("botao_pente", "caixa"), ("botao_pente", "guarda_mato"), ("estojo_ejetado", "caixa"),
             ("estojo_ejetado", "seletor")]
    momentos = [("tiro, ferrolho no meio", no_quadro(TIRO_INICIO, 2)),
                ("tiro, ferrolho atrás", no_quadro(TIRO_INICIO, 3)),
                ("recarga, pente girando para sair", no_quadro(REC_INICIO, 22)),
                ("recarga, pente saindo", no_quadro(REC_INICIO, 27)),
                ("recarga, pente novo engatando", no_quadro(REC_INICIO, 47)),
                ("recarga, pente novo girando", no_quadro(REC_INICIO, 51)),
                ("recarga, ferrolho atrás", no_quadro(REC_INICIO, 61))]

    def arvore(ob):
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        t = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        ev.to_mesh_clear()
        return t

    def contar():
        return {(a, b): len(arvore(P[a]).overlap(arvore(P[b]))) for a, b in pares}

    cena.frame_set(0)
    base = contar()
    linhas = ["", "Animações (30 qps): " + ", ".join(f"{n} {i} a {i + q - 1}" for n, i, q in [
        ("tiro", TIRO_INICIO, TIRO_FIM), ("recarregar", REC_INICIO, REC_FIM)]),
              "Eventos (quadro da faixa, 1 = primeiro): " + "; ".join(
                  f"{f}: " + ", ".join(f"{e} {q}" for e, q in ev.items()) for f, ev in EVENTOS.items()),
              "Cruzamentos entre peças (triângulos que se tocam; repouso -> no momento):"]
    for nome, quadro in momentos:
        cena.frame_set(quadro)
        agora = contar()
        mudou = [f"{a} x {b}: {base[(a, b)]} -> {agora[(a, b)]}" for a, b in pares
                 if agora[(a, b)] > base[(a, b)] + 10]
        linhas.append(f"  {nome} (quadro {quadro}): " + ("; ".join(mudou) if mudou else "nada novo"))
    cena.frame_set(0)
    linhas.append("No repouso: " + "; ".join(f"{a} x {b}: {n}" for (a, b), n in base.items() if n))
    return linhas


def relatorio(P, extra=()):
    linhas = ["AK-47 3D: relatório", ""]
    todos_x, todos_y, todos_z = [], [], []
    tris_total = 0
    abertas = []
    for nome, ob in P.items():
        if ob.matrix_world.to_scale().length < 1e-6:
            continue
        cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        x0, x1 = min(c.x for c in cs), max(c.x for c in cs)
        y0, y1 = min(c.y for c in cs), max(c.y for c in cs)
        z0, z1 = min(c.z for c in cs), max(c.z for c in cs)
        todos_x += [x0, x1]
        todos_y += [y0, y1]
        todos_z += [z0, z1]
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        abertas_ob = sum(1 for e in bm.edges if len(e.link_faces) != 2)
        tris = sum(len(f.verts) - 2 for f in bm.faces)
        bm.free()
        tris_total += tris
        if abertas_ob:
            abertas.append(nome)
        linhas.append(f"{nome:<22} {x1 - x0:7.1f} x {y1 - y0:5.1f} x {z1 - z0:6.1f} mm  {tris:6d} triângulos"
                      f"  {'MALHA ABERTA: ' + str(abertas_ob) + ' arestas' if abertas_ob else 'fechada'}")
    linhas += ["", f"Total: {len(P)} peças, {tris_total} triângulos (sem contar as escondidas)",
               f"Comprimento {max(todos_x) - min(todos_x):.0f} mm, altura {max(todos_z) - min(todos_z):.0f} mm "
               f"(com o pente), largura {max(todos_y) - min(todos_y):.0f} mm",
               "Texturas: madeira.png e madeira_punho.png, geradas por código; o resto é cor lisa.",
               "As peças se sobrepõem de propósito nas junções: cada uma é um sólido fechado, não uma malha única."]
    linhas += list(extra)
    if abertas:
        linhas.append("ATENÇÃO, malha aberta em: " + ", ".join(abertas))
    for aviso in AVISOS:
        linhas.append("ATENÇÃO, " + aviso)
    texto = "\n".join(linhas)
    (SAIDA / "relatorio.txt").write_text(texto, encoding="utf-8")
    print(texto)


# ---------------------------------------------------------------- imagens

def renderizar():
    leve = "--leve" in ARGS
    vistas_leves = ("lateral-direita", "tres-quartos", "anim-tiro", "anim-recarga")
    if "--vistas" in ARGS:
        vistas_leves = tuple(ARGS[ARGS.index("--vistas") + 1].split(","))
    rapido = "--rapido" in ARGS or leve
    cena = bpy.context.scene
    if leve:
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x40)   # IDLE_PRIORITY_CLASS
        except Exception:
            pass
        cena.render.threads_mode = 'FIXED'
        cena.render.threads = 4
    cena.unit_settings.system = 'METRIC'
    cena.unit_settings.scale_length = 0.001
    cena.render.engine = 'CYCLES'
    cena.cycles.device = 'CPU'
    cena.cycles.samples = 16 if leve else (24 if rapido else 256)
    cena.cycles.use_denoising = True
    cena.cycles.denoiser = 'OPENIMAGEDENOISE'
    cena.render.resolution_x, cena.render.resolution_y = 1920, 1200
    cena.render.resolution_percentage = 50 if rapido else 100
    cena.view_settings.view_transform = 'AgX'
    cena.view_settings.look = 'None'
    cena.view_settings.exposure = -0.8

    mundo = bpy.data.worlds.new("mundo")
    mundo.use_nodes = True
    mundo.node_tree.nodes["Background"].inputs["Color"].default_value = (0.12, 0.12, 0.125, 1)
    cena.world = mundo

    chao = -300.0
    perfil = [(chao, 0), (chao, 3400)]
    for i in range(1, 13):
        a = math.radians(90 * i / 12)
        perfil.append((chao + 1400 - 1400 * math.cos(a), 3400 + 1400 * math.sin(a)))
    perfil += [(9000, 4800), (9000, 0)]
    fundo = tornear("fundo", perfil, material("fundo", (0.36, 0.355, 0.35), rug=0.8), pos=(-60, 0, 0), eixo='z',
                    seg=128)
    acabar(fundo, angulo=60)

    alvo = (-60, 0, -40)
    luz_de_estudio("luz_topo", (-60, 0, 1300), alvo, (950, 520), 3.5)
    luz_de_estudio("luz_principal", (-560, -1400, 700), alvo, (640, 420), 10)
    luz_de_estudio("luz_faixa", (120, -700, 1050), (0, 0, 0), (1200, 90), 20)
    luz_de_estudio("luz_contra", (820, 1000, 280), alvo, (420, 620), 12)
    luz_de_estudio("luz_recorte", (-1200, 800, 130), alvo, (360, 560), 9)
    luz_de_estudio("luz_baixa", (400, -1050, -260), alvo, (560, 170), 3)

    cam_ob = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam_ob.data.clip_start, cam_ob.data.clip_end = 5, 30000
    cena.collection.objects.link(cam_ob)
    cena.camera = cam_ob
    mira = bpy.data.objects.new("mira_camera", None)
    cena.collection.objects.link(mira)
    trava = cam_ob.constraints.new('TRACK_TO')
    trava.target = mira
    trava.track_axis = 'TRACK_NEGATIVE_Z'
    trava.up_axis = 'UP_Y'

    RENDER.mkdir(exist_ok=True)
    for velho in RENDER.glob("*.png"):
        velho.unlink()

    def foto(nome, local, ponto, lente, f=None, foco=None, quadro=0):
        if leve and nome not in vistas_leves:
            return
        cena.frame_set(quadro)
        cam_ob.location = local
        mira.location = ponto
        cam_ob.data.lens = lente
        cam_ob.data.dof.use_dof = f is not None
        if f is not None:
            cam_ob.data.dof.aperture_fstop = f
            cam_ob.data.dof.focus_distance = (Vector(local) - Vector(foco or ponto)).length
        cena.render.filepath = str(RENDER / f"{nome}.png")
        bpy.ops.render.render(write_still=True)

    foto("lateral-direita", (-60, -2600, -70), (-60, 0, -72), 85)
    foto("lateral-esquerda", (-60, 2600, -70), (-60, 0, -72), 85)
    foto("tres-quartos", (700, -1250, 480), (-60, 0, -60), 45, f=16, foco=(-80, -15, -10))
    foto("detalhe-caixa", (-30, -760, 160), (-110, 0, -10), 70, f=8, foco=(-100, -15, 0))
    foto("anim-tiro", (-40, -1150, 120), (-80, 0, -10), 70, quadro=VISTAS_ANIMACAO["anim-tiro"])
    foto("anim-recarga", (250, -1500, -260), (-90, 0, -110), 55, quadro=VISTAS_ANIMACAO["anim-recarga"])
    cena.frame_set(0)
    cena.unit_settings.scale_length = 1.0


# ---------------------------------------------------------------- exportação

def gravar_animacoes(P):
    pecas = ["ferrolho", "gatilho", "botao_pente", "pente", "estojo_topo", "bala_topo", "clarao", "estojo_ejetado"]
    dados = {"raiz": NOME, "fps": 30,
             "faixas": {"repouso": {"inicio": 1, "quadros": 2, "eventos": {}},
                        "tiro": {"inicio": TIRO_INICIO, "quadros": TIRO_FIM, "eventos": EVENTOS["tiro"]},
                        "recarregar": {"inicio": REC_INICIO, "quadros": REC_FIM, "eventos": EVENTOS["recarregar"]}},
             "pecas": [p for p in pecas if p in P]}
    (SAIDA / "animacoes.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def exportar(raiz):
    SAIDA.mkdir(exist_ok=True)
    cena = bpy.context.scene
    cena.frame_set(0)
    bpy.context.preferences.filepaths.save_version = 0
    for ob in bpy.data.objects:
        ob.select_set(False)
    bpy.ops.wm.save_as_mainfile(filepath=str(SAIDA / f"{NOME}.blend"))
    # OBJ em milímetros, parado e carregado, sem o clarão nem o estojo que voa (escondidos)
    for velho in SAIDA.glob(f"{NOME}.obj*"):
        velho.unlink()
    for ob in bpy.data.objects:
        ob.select_set(ob.type == 'MESH' and ob.name not in ("clarao", "estojo_ejetado"))
    bpy.ops.wm.obj_export(filepath=str(SAIDA / f"{NOME}.obj"), export_materials=True, path_mode='COPY',
                          forward_axis='NEGATIVE_Z', up_axis='Y', apply_modifiers=True,
                          export_selected_objects=True)
    # GLB em metros, com uma animação por faixa, todas começando no zero
    for ob in bpy.data.objects:
        if ob.animation_data:
            for trilha in ob.animation_data.nla_tracks:
                for faixa in trilha.strips:
                    faixa.frame_start_ui = 1
    escala = bpy.data.objects.new("escala_metros", None)
    cena.collection.objects.link(escala)
    escala.scale = (0.001, 0.001, 0.001)
    raiz.parent = escala
    bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(filepath=str(SAIDA / f"{NOME}.glb"), export_format='GLB', use_selection=False,
                              export_apply=True, export_animations=True, export_animation_mode='NLA_TRACKS')


def principal():
    P = construir()
    raiz = animar(P)
    relatorio(P, conferir_movimento(P))
    gravar_animacoes(P)
    if "--sem-render" not in ARGS:
        renderizar()
        for o in list(bpy.data.objects):
            if o.name.startswith(("luz_", "fundo", "camera", "mira_camera")):
                bpy.data.objects.remove(o)
    exportar(raiz)
    print("pronto")


principal()

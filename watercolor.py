"""Paint engine for Passing Ships.

A Canvas with a small set of primitives (wash, line, opaque paint, reserve,
gradient) that the scene painters compose into a picture. Pure NumPy + OpenCV:
no image model, no image assets, deterministic for a given seed.

The sheet starts as paper colour and transparent paint multiplies it, so layers
glaze and the brightest thing in any picture is paper nobody painted. No water is
simulated: each mark that drying water leaves has a cheap stand-in here.
docs/HOW-THE-PAINT-WORKS.md explains every one and where it comes from.
"""
import numpy as np
import cv2

PAPER_RGB = np.array([0.965, 0.950, 0.915], dtype=np.float32)  # paper white


def _rng(seed):
    return np.random.default_rng(seed)


def fbm(h, w, octaves=4, scale=96.0, seed=7):
    """Fractal noise in [0,1], fixed by seed: random grids at doubling resolution
    and halving strength, stretched to size and summed."""
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gh = max(2, int(h / scale * (2 ** o)) + 1)
        gw = max(2, int(w / scale * (2 ** o)) + 1)
        g = _rng(seed * 1013 + o).random((gh, gw), dtype=np.float32)
        out += amp * cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)
        tot += amp
        amp *= 0.5
    out /= tot
    lo, hi = out.min(), out.max()
    return (out - lo) / max(hi - lo, 1e-6)


def absorption(rgb):
    """Pigment colour -> K, how strongly it absorbs red, green and blue. A film of
    density D over the sheet lets exp(-K*D) through, so at D=1 the paper shows
    exactly this colour."""
    rgb = np.asarray(rgb, np.float32)
    return -np.log(np.clip(rgb / PAPER_RGB, 0.015, 1.0))


def _resample(poly, step=6.0, k=1.0):
    """Add points along polygon edges, so the outline has something to wobble."""
    pts = np.asarray(poly, np.float32)
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        d = np.linalg.norm(b - a)
        n_ = max(1, int(d / (step * k)))
        for t in np.linspace(0, 1, n_, endpoint=False):
            out.append(a + (b - a) * t)
    return np.array(out, np.float32)


class Canvas:
    def __init__(self, w, h, seed=11, k=1.0):
        self.w, self.h = w, h
        self.k = float(k)                    # stroke scale: k=3 paints a 3x master
        self.img = np.ones((h, w, 3), np.float32) * PAPER_RGB
        self.relief = fbm(h, w, octaves=5, scale=9.0 * k, seed=seed)        # fine texture field
        self.varieg = fbm(h, w, octaves=4, scale=140.0 * k, seed=seed + 5)  # broad texture field
        self.reserve = np.zeros((h, w), np.float32)                     # areas kept clear
        self.seed = seed
        self._paper_shading()

    def _paper_shading(self):
        tone = 1.0 - 0.035 * (self.relief[..., None] - 0.5)
        self.img *= tone

    def add_reserve(self, poly, feather=2.0):
        m = np.zeros((self.h, self.w), np.float32)
        cv2.fillPoly(m, [np.round(np.asarray(poly)).astype(np.int32)], 1.0)
        feather *= self.k
        if feather > 0:
            m = cv2.GaussianBlur(m, (0, 0), feather)
        self.reserve = np.maximum(self.reserve, m)

    def clear_reserves(self):
        self.reserve[:] = 0.0

    def _dry_keep(self, dry):
        """Dry brush: a starved brush touches only the peaks of the paper. 1 where
        the relief stands above `dry`, 0 in the hollows, a short ramp between."""
        return np.clip((self.relief - dry) * 7.0 + 0.5, 0.0, 1.0)

    def _density(self, poly, jitter, feather, edge_dark, granulation, variegation, seed,
                 dry=0.0):
        """How much pigment lies on each pixel. Wobbled outline -> feathered edge ->
        dark rim (pigment migrates to a drying edge; here, a ring that decays with
        distance from it) -> granulation (pigment settles in the paper's hollows) ->
        variegation (no wash goes down evenly) -> dry-brush breakup."""
        jitter, feather = jitter * self.k, feather * self.k
        pts = _resample(poly, k=self.k)
        if jitter > 0:
            n = len(pts)
            r = _rng(seed)
            wob = np.stack([
                np.interp(np.arange(n), np.linspace(0, n, 24), r.standard_normal(24)),
                np.interp(np.arange(n), np.linspace(0, n, 24), r.standard_normal(24)),
            ], axis=1).astype(np.float32)
            fine = r.standard_normal((n, 2)).astype(np.float32) * 0.35
            pts = pts + jitter * (wob + fine)
        m = np.zeros((self.h, self.w), np.float32)
        cv2.fillPoly(m, [np.round(pts * 16).astype(np.int32)], 1.0,
                     lineType=cv2.LINE_AA, shift=4)
        if feather > 0:
            m = cv2.GaussianBlur(m, (0, 0), feather)
        D = m.copy()
        if edge_dark > 0:
            hard = (m > 0.5).astype(np.uint8)
            dist = cv2.distanceTransform(hard, cv2.DIST_L2, 3)
            ring = np.exp(-dist / max(2.5 * feather + 2.0, 3.0)).astype(np.float32) * hard
            D *= 1.0 + edge_dark * ring
        if granulation > 0:
            D *= 1.0 + granulation * (self.relief - 0.5) * 2.0
        if variegation > 0:
            D *= 1.0 + variegation * (self.varieg - 0.5) * 2.0
        if dry > 0:
            D *= self._dry_keep(dry)
        return np.clip(D, 0, None)

    def wash(self, poly, masstone, density=0.55, jitter=3.0, feather=2.5,
             edge_dark=0.7, granulation=0.35, variegation=0.35, seed=None,
             respect_reserve=True, dry=0.0):
        """Transparent layer of colour inside poly: multiplies the sheet, so it
        glazes over whatever is already there and leaves the reserves bare."""
        seed = self.seed if seed is None else seed
        D = self._density(poly, jitter, feather, edge_dark, granulation, variegation,
                          seed, dry)
        if respect_reserve:
            D *= (1.0 - self.reserve)
        K = absorption(masstone)
        self.img *= np.exp(-K[None, None, :] * (D * density)[..., None])

    def gouache(self, poly, rgb, alpha=0.9, jitter=2.0, feather=1.2, seed=None,
                respect_reserve=False, dry=0.0):
        """Opaque colour inside poly (body colour: covers instead of staining).
        For the few light-over-dark accents transparent paint cannot make."""
        seed = self.seed if seed is None else seed
        D = self._density(poly, jitter, feather, 0.0, 0.1, 0.0, seed, dry)
        if respect_reserve:
            D *= (1.0 - self.reserve)
        a = np.clip(D * alpha, 0, 1)[..., None]
        col = np.asarray(rgb, np.float32)
        self.img = self.img * (1 - a) + col * a

    def lift_mask(self, mask, amount=0.6):
        """Pull colour back toward paper where mask > 0, as a damp brush lifts
        pigment off a dry wash."""
        a = np.clip(mask * amount, 0, 1)[..., None]
        self.img = self.img + (PAPER_RGB - self.img) * a

    def bloom(self, cx, cy, r, masstone, strength=0.5, seed=None):
        """Bloom: water pushed back into a damp wash leaves a pale centre and a
        dark irregular rim. Unused by the scenes; at this size it reads as a stain."""
        seed = self.seed if seed is None else seed
        rr = _rng(seed)
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        ang = np.arctan2(yy - cy, xx - cx)
        k = rr.uniform(3, 6)
        warp = 1.0 + 0.22 * np.sin(ang * k + rr.uniform(0, 6)) \
                   + 0.12 * np.sin(ang * (k + 3) + rr.uniform(0, 6))
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (r * warp)
        interior = np.clip(1.0 - d, 0, 1) ** 1.4
        ring = np.exp(-((d - 1.0) ** 2) / 0.010).astype(np.float32)
        self.lift_mask(interior * (1.0 - self.reserve), amount=0.45 * strength)
        K = absorption(masstone)
        self.img *= np.exp(-K[None, None, :] * (ring * 0.55 * strength)[..., None])

    def soften_band(self, y0, y1, sigma):
        """Blur a horizontal band (e.g. a foggy horizon)."""
        if sigma <= 0:
            return
        y0, y1 = int(max(0, y0)), int(min(self.h, y1))
        blurred = cv2.GaussianBlur(self.img, (0, 0), sigmaX=sigma * 0.35, sigmaY=sigma)
        band = np.zeros(self.h, np.float32)
        band[y0:y1] = 1.0
        soft = cv2.GaussianBlur(band[:, None], (0, 0), max(3.0, (y1 - y0) / 4))[:, 0]
        self.img = self.img * (1 - soft[:, None, None]) + blurred * soft[:, None, None]

    def line(self, pts, masstone, width=2.0, density=0.8, jitter=1.0, seed=None,
             feather=0.7):
        """Transparent stroke along pts."""
        seed = self.seed if seed is None else seed
        width, jitter, feather = width * self.k, jitter * self.k, feather * self.k
        pts = np.asarray(pts, np.float32)
        if jitter > 0:
            r = _rng(seed)
            # long strokes get a slight wander; short ones stay straight
            seglen = np.linalg.norm(np.diff(pts, axis=0), axis=1).sum() if len(pts) > 1 else 0.0
            if seglen > 40 * self.k:
                dense = []
                for i in range(len(pts) - 1):
                    a, b = pts[i], pts[i + 1]
                    d = np.linalg.norm(b - a)
                    nseg = max(1, int(d / (14 * self.k)))
                    for t in np.linspace(0, 1, nseg, endpoint=False):
                        dense.append(a + (b - a) * t)
                dense.append(pts[-1])
                pts = np.array(dense, np.float32)
                n = len(pts)
                amp = jitter * min(1.0, seglen / (220.0 * self.k))    # ~1 px at 1x, no more
                wob = np.stack([
                    np.interp(np.arange(n), np.linspace(0, n, 5), r.standard_normal(5)),
                    np.interp(np.arange(n), np.linspace(0, n, 5), r.standard_normal(5)),
                ], axis=1).astype(np.float32)
                env = np.sin(np.linspace(0, np.pi, n)).astype(np.float32)[:, None]  # pin the ends
                pts = pts + amp * wob * env
            pts = pts + r.standard_normal(pts.shape).astype(np.float32) * jitter * 0.45
        m = np.zeros((self.h, self.w), np.float32)
        cv2.polylines(m, [np.round(pts * 16).astype(np.int32)], False, 1.0,
                      thickness=max(1, int(round(width))), lineType=cv2.LINE_AA, shift=4)
        if feather > 0:
            m = cv2.GaussianBlur(m, (0, 0), feather)
        m *= 1.0 + 0.5 * (self.relief - 0.5)
        K = absorption(masstone)
        self.img *= np.exp(-K[None, None, :] * (m * density)[..., None])

    def gouache_line(self, pts, rgb, width=3.0, alpha=0.95, jitter=0.3, seed=None):
        """Opaque stroke along pts (light over dark)."""
        seed = self.seed if seed is None else seed
        width, jitter = width * self.k, jitter * self.k
        pts = np.asarray(pts, np.float32)
        if jitter > 0:
            r = _rng(seed)
            pts = pts + r.standard_normal(pts.shape).astype(np.float32) * jitter
        m = np.zeros((self.h, self.w), np.float32)
        cv2.polylines(m, [np.round(pts * 16).astype(np.int32)], False, 1.0,
                      thickness=max(1, int(round(width))), lineType=cv2.LINE_AA, shift=4)
        m = cv2.GaussianBlur(m, (0, 0), 0.5 * self.k)
        a = np.clip(m * alpha, 0, 1)[..., None]
        col = np.asarray(rgb, np.float32)
        self.img = self.img * (1 - a) + col * a

    def mask_wash(self, mask, masstone, density=0.8):
        """Transparent colour through a float mask (text, stamps)."""
        K = absorption(masstone)
        self.img *= np.exp(-K[None, None, :] * (mask * density)[..., None])

    def spatter(self, box, masstone, n=60, size=(1, 3), density=0.5, seed=None):
        seed = self.seed if seed is None else seed
        r = _rng(seed)
        x0, y0, x1, y1 = box
        m = np.zeros((self.h, self.w), np.float32)
        for _ in range(int(n * self.k)):
            x, y = r.uniform(x0, x1), r.uniform(y0, y1)
            cv2.circle(m, (int(x), int(y)), max(0, int(r.uniform(*size) * self.k)), 1.0, -1)
        m = cv2.GaussianBlur(m, (0, 0), 0.6 * self.k) * (1.0 - self.reserve)
        K = absorption(masstone)
        self.img *= np.exp(-K[None, None, :] * (m * density)[..., None])

    def graded_pour(self, y0, y1, stops, drag=0.15, seed=None):
        """Vertical colour gradient across the full width.
        stops: list of (t, colour, density) with t in [0,1]."""
        seed = self.seed if seed is None else seed
        ys = np.arange(self.h, dtype=np.float32)
        t = np.clip((ys - y0) / max(y1 - y0, 1), 0, 1)
        Dcol = np.zeros((self.h, 3), np.float32)  # K*density per row
        ts = np.array([s[0] for s in stops], np.float32)
        Ks = np.stack([absorption(s[1]) * s[2] for s in stops])
        for c in range(3):
            Dcol[:, c] = np.interp(t, ts, Ks[:, c])
        field = np.repeat(Dcol[:, None, :], self.w, axis=1)
        if drag > 0:
            field *= (1.0 + drag * (self.varieg - 0.5) * 2.0)[..., None]
        band = ((ys >= y0 - 40) & (ys <= y1 + 40)).astype(np.float32)
        soft = cv2.GaussianBlur(band[:, None], (0, 0), 12)[:, 0]
        field *= soft[:, None, None]
        field *= (1.0 - self.reserve)[..., None]
        self.img *= np.exp(-field)

    def save(self, path):
        out = np.clip(self.img, 0, 1)
        cv2.imwrite(path, cv2.cvtColor((out * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
        return path

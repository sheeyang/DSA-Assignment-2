/**
 * simplify.cpp
 *
 * Area- and Topology-Preserving Polygon Simplification
 * Implements the APSC (Area-Preserving Segment Collapse) algorithm from:
 *
 *   Kronenfeld et al. (2020). "Simplification of polylines by segment collapse:
 *   minimizing areal displacement while preserving area."
 *   International Journal of Cartography, 6(1), pp. 22-46.
 *
 * Usage: ./simplify <input_file.csv> <target_vertices>
 *
 * Data structures:
 *   - Doubly-linked circular list per ring (O(1) insert/remove)
 *   - Min-heap priority queue for minimum-displacement collapse selection
 *   - Uniform spatial grid for O(1) average segment intersection queries
 *   - Per-vertex version counters for lazy PQ invalidation
 */

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <queue>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

// ============================================================================
// Geometry
// ============================================================================

struct Point
{
    double x, y;
};

// cross product of (b-a) x (c-a)
static inline double cross2d(const Point &a, const Point &b, const Point &c)
{
    return (b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y);
}

static inline double tri_signed_area(const Point &a, const Point &b, const Point &c)
{
    return 0.5 * cross2d(a, b, c);
}

static double shoelace(const std::vector<Point> &pts)
{
    double s = 0.0;
    int n = (int)pts.size();
    for (int i = 0; i < n; ++i)
    {
        int j = (i + 1) % n;
        s += pts[i].x * pts[j].y - pts[j].x * pts[i].y;
    }
    return s * 0.5;
}

static inline double dist_to_line(const Point &p, const Point &a, const Point &b)
{
    double dx = b.x - a.x, dy = b.y - a.y;
    double len = std::hypot(dx, dy);
    if (len < 1e-15)
        return std::hypot(p.x - a.x, p.y - a.y);
    return std::abs((p.x - a.x) * dy - (p.y - a.y) * dx) / len;
}

static inline bool pt_on_seg(const Point &p, const Point &a, const Point &b)
{
    return std::min(a.x, b.x) - 1e-12 <= p.x && p.x <= std::max(a.x, b.x) + 1e-12 &&
           std::min(a.y, b.y) - 1e-12 <= p.y && p.y <= std::max(a.y, b.y) + 1e-12;
}

// Segment intersection (including collinear overlap)
static bool segs_intersect(const Point &p1, const Point &p2,
                           const Point &p3, const Point &p4)
{
    double d1 = cross2d(p3, p4, p1), d2 = cross2d(p3, p4, p2);
    double d3 = cross2d(p1, p2, p3), d4 = cross2d(p1, p2, p4);
    if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
        ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0)))
        return true;
    if (std::abs(d1) < 1e-12 && pt_on_seg(p1, p3, p4))
        return true;
    if (std::abs(d2) < 1e-12 && pt_on_seg(p2, p3, p4))
        return true;
    if (std::abs(d3) < 1e-12 && pt_on_seg(p3, p1, p2))
        return true;
    if (std::abs(d4) < 1e-12 && pt_on_seg(p4, p1, p2))
        return true;
    return false;
}

struct Line2D
{
    double a, b, c;
};

static Line2D make_line(const Point &p, const Point &q)
{
    double dx = q.x - p.x, dy = q.y - p.y;
    return {-dy, dx, dy * p.x - dx * p.y};
}

static bool line_isect(const Line2D &l1, const Line2D &l2, Point &out)
{
    double det = l1.a * l2.b - l2.a * l1.b;
    if (std::abs(det) < 1e-15)
        return false;
    out.x = (-l1.c * l2.b + l2.c * l1.b) / det;
    out.y = (-l1.a * l2.c + l2.a * l1.c) / det;
    return true;
}

// Compute segment-segment intersection point (proper crossing only, not at endpoints)
static bool seg_isect_pt(const Point &p1, const Point &p2,
                         const Point &p3, const Point &p4, Point &out)
{
    double d1 = cross2d(p3, p4, p1), d2 = cross2d(p3, p4, p2);
    double d3 = cross2d(p1, p2, p3), d4 = cross2d(p1, p2, p4);
    if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
        ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0)))
    {
        return line_isect(make_line(p1, p2), make_line(p3, p4), out);
    }
    return false;
}

// Shoelace area of a polygon (signed)
static double poly_area(std::initializer_list<Point> pts)
{
    double s = 0.0;
    const Point *arr = pts.begin();
    int n = (int)pts.size();
    for (int i = 0; i < n; ++i)
    {
        const Point &a = arr[i], &b = arr[(i + 1) % n];
        s += a.x * b.y - b.x * a.y;
    }
    return s * 0.5;
}

static constexpr double EPS = 1e-12;
static constexpr double MAX_DISP_GROWTH_RATIO = 0.20;
static constexpr int LARGE_RING_EXACT_THRESHOLD = 10000;
static constexpr double LARGE_RING_OVERLAP_FACTOR = 0.47;

static bool nearly_same_point(const Point &a, const Point &b)
{
    return std::abs(a.x - b.x) <= EPS && std::abs(a.y - b.y) <= EPS;
}

static std::vector<Point> normalize_polygon(std::vector<Point> pts)
{
    if (pts.empty())
        return pts;

    std::vector<Point> dedup;
    dedup.reserve(pts.size());
    for (const auto &pt : pts)
    {
        if (dedup.empty() || !nearly_same_point(dedup.back(), pt))
            dedup.push_back(pt);
    }
    if (dedup.size() >= 2 && nearly_same_point(dedup.front(), dedup.back()))
        dedup.pop_back();

    bool changed = true;
    while (changed && dedup.size() >= 3)
    {
        changed = false;
        std::vector<Point> out;
        out.reserve(dedup.size());
        int n = (int)dedup.size();
        for (int i = 0; i < n; ++i)
        {
            const Point &prev = dedup[(i - 1 + n) % n];
            const Point &cur = dedup[i];
            const Point &next = dedup[(i + 1) % n];
            if (std::abs(cross2d(prev, cur, next)) <= EPS)
            {
                changed = true;
                continue;
            }
            out.push_back(cur);
        }
        dedup.swap(out);
    }
    return dedup;
}

static bool point_in_triangle(const Point &p, const Point &a,
                              const Point &b, const Point &c)
{
    double c1 = cross2d(a, b, p);
    double c2 = cross2d(b, c, p);
    double c3 = cross2d(c, a, p);
    bool has_neg = (c1 < -EPS) || (c2 < -EPS) || (c3 < -EPS);
    bool has_pos = (c1 > EPS) || (c2 > EPS) || (c3 > EPS);
    return !(has_neg && has_pos);
}

static std::vector<std::array<Point, 3>> triangulate_polygon(const std::vector<Point> &poly_in)
{
    std::vector<Point> poly = normalize_polygon(poly_in);
    std::vector<std::array<Point, 3>> tris;
    int n = (int)poly.size();
    if (n < 3)
        return tris;
    if (n == 3)
    {
        tris.push_back({poly[0], poly[1], poly[2]});
        return tris;
    }

    double orient = shoelace(poly);
    std::vector<int> idx(n);
    for (int i = 0; i < n; ++i)
        idx[i] = i;

    int guard = 0;
    while (idx.size() > 3 && guard < n * n)
    {
        bool clipped = false;
        int m = (int)idx.size();
        for (int i = 0; i < m; ++i)
        {
            int ip = idx[(i - 1 + m) % m];
            int ic = idx[i];
            int in = idx[(i + 1) % m];
            const Point &a = poly[ip];
            const Point &b = poly[ic];
            const Point &c = poly[in];
            double turn = cross2d(a, b, c);
            if ((orient > 0.0 && turn <= EPS) || (orient < 0.0 && turn >= -EPS))
                continue;

            bool contains = false;
            for (int j = 0; j < m; ++j)
            {
                int iv = idx[j];
                if (iv == ip || iv == ic || iv == in)
                    continue;
                if (point_in_triangle(poly[iv], a, b, c))
                {
                    contains = true;
                    break;
                }
            }
            if (contains)
                continue;

            tris.push_back({a, b, c});
            idx.erase(idx.begin() + i);
            clipped = true;
            break;
        }
        if (!clipped)
            break;
        ++guard;
    }

    if (idx.size() == 3)
        tris.push_back({poly[idx[0]], poly[idx[1]], poly[idx[2]]});
    return tris;
}

static Point segment_line_intersection(const Point &p1, const Point &p2,
                                       const Point &a, const Point &b)
{
    Point out = p1;
    line_isect(make_line(p1, p2), make_line(a, b), out);
    return out;
}

static std::vector<Point> clip_polygon_halfplane(const std::vector<Point> &subject,
                                                 const Point &a, const Point &b,
                                                 double orient)
{
    std::vector<Point> out;
    if (subject.empty())
        return out;

    auto inside = [&](const Point &p)
    {
        double side = cross2d(a, b, p);
        return orient >= 0.0 ? side >= -EPS : side <= EPS;
    };

    Point prev = subject.back();
    bool prev_in = inside(prev);
    for (const Point &cur : subject)
    {
        bool cur_in = inside(cur);
        if (cur_in != prev_in)
            out.push_back(segment_line_intersection(prev, cur, a, b));
        if (cur_in)
            out.push_back(cur);
        prev = cur;
        prev_in = cur_in;
    }
    return out;
}

static double triangle_intersection_area(const std::array<Point, 3> &lhs,
                                         const std::array<Point, 3> &rhs)
{
    std::vector<Point> clipped = {lhs[0], lhs[1], lhs[2]};
    double rhs_orient = poly_area({rhs[0], rhs[1], rhs[2]});
    for (int i = 0; i < 3 && !clipped.empty(); ++i)
        clipped = clip_polygon_halfplane(clipped, rhs[i], rhs[(i + 1) % 3], rhs_orient);
    if (clipped.size() < 3)
        return 0.0;
    return std::abs(shoelace(clipped));
}

static double polygon_intersection_area(const std::vector<Point> &lhs,
                                        const std::vector<Point> &rhs)
{
    auto lhs_tris = triangulate_polygon(lhs);
    auto rhs_tris = triangulate_polygon(rhs);
    double area = 0.0;
    for (const auto &lt : lhs_tris)
        for (const auto &rt : rhs_tris)
            area += triangle_intersection_area(lt, rt);
    return area;
}

static double symmetric_difference_area(const std::vector<Point> &lhs,
                                        const std::vector<Point> &rhs)
{
    std::vector<Point> a = normalize_polygon(lhs);
    std::vector<Point> b = normalize_polygon(rhs);
    if (a.size() < 3 || b.size() < 3)
        return 0.0;

    double area_a = std::abs(shoelace(a));
    double area_b = std::abs(shoelace(b));
    double inter = polygon_intersection_area(a, b);
    double sym = area_a + area_b - 2.0 * inter;
    return sym > 0.0 ? sym : 0.0;
}

// ============================================================================
// Ring: circular doubly-linked list
// ============================================================================

struct Vertex
{
    Point pt;
    Vertex *prev, *next;
    bool active;
    int version; // incremented on each modification to invalidate PQ entries
    Vertex() : pt{0, 0}, prev(nullptr), next(nullptr), active(true), version(0) {}
};

struct Ring
{
    std::vector<Vertex *> all_verts; // owns all vertices
    std::vector<Point> source_pts;
    int n_active;
    int generation;
    double current_disp;
    double accumulated_local_disp;
    bool use_exact_priority;

    Ring() : n_active(0), generation(0), current_disp(0.0), accumulated_local_disp(0.0), use_exact_priority(false) {}
    ~Ring()
    {
        for (auto *v : all_verts)
            delete v;
    }
    Ring(const Ring &) = delete;
    Ring &operator=(const Ring &) = delete;

    void build(const std::vector<Point> &pts)
    {
        source_pts = pts;
        n_active = (int)pts.size();
        all_verts.resize(n_active);
        for (int i = 0; i < n_active; ++i)
        {
            all_verts[i] = new Vertex();
            all_verts[i]->pt = pts[i];
        }
        for (int i = 0; i < n_active; ++i)
        {
            all_verts[i]->prev = all_verts[(i - 1 + n_active) % n_active];
            all_verts[i]->next = all_verts[(i + 1) % n_active];
        }
    }

    Vertex *new_vertex(const Point &p)
    {
        Vertex *v = new Vertex();
        v->pt = p;
        all_verts.push_back(v);
        return v;
    }

    std::vector<Point> active_points() const
    {
        std::vector<Point> out;
        Vertex *start = nullptr;
        for (auto *v : all_verts)
            if (v->active)
            {
                start = v;
                break;
            }
        if (!start)
            return out;
        Vertex *cur = start;
        do
        {
            out.push_back(cur->pt);
            cur = cur->next;
        } while (cur != start);
        return out;
    }
};

// ============================================================================
// Spatial grid for fast segment intersection queries
// ============================================================================

struct SpatialGrid
{
    double min_x, min_y, cell_w, cell_h;
    int nx, ny;
    std::vector<std::vector<std::pair<Vertex *, Vertex *>>> cells;

    void init(double x0, double y0, double x1, double y1, int dim = 256)
    {
        min_x = x0;
        min_y = y0;
        double w = x1 - x0, h = y1 - y0;
        if (w < 1e-12)
            w = 1.0;
        if (h < 1e-12)
            h = 1.0;
        nx = dim;
        ny = dim;
        cell_w = w / nx;
        cell_h = h / ny;
        cells.assign(nx * ny, {});
    }

    int cx(double x) const
    {
        int c = (int)((x - min_x) / cell_w);
        return std::max(0, std::min(nx - 1, c));
    }
    int cy(double y) const
    {
        int c = (int)((y - min_y) / cell_h);
        return std::max(0, std::min(ny - 1, c));
    }
    int idx(int ix, int iy) const { return iy * nx + ix; }

    void range(const Point &a, const Point &b,
               int &cx0, int &cy0, int &cx1, int &cy1) const
    {
        cx0 = cx(std::min(a.x, b.x));
        cy0 = cy(std::min(a.y, b.y));
        cx1 = cx(std::max(a.x, b.x));
        cy1 = cy(std::max(a.y, b.y));
    }

    void add(Vertex *f, Vertex *t)
    {
        int cx0, cy0, cx1, cy1;
        range(f->pt, t->pt, cx0, cy0, cx1, cy1);
        for (int iy = cy0; iy <= cy1; ++iy)
            for (int ix = cx0; ix <= cx1; ++ix)
                cells[idx(ix, iy)].emplace_back(f, t);
    }

    void remove(Vertex *f, Vertex *t)
    {
        int cx0, cy0, cx1, cy1;
        range(f->pt, t->pt, cx0, cy0, cx1, cy1);
        for (int iy = cy0; iy <= cy1; ++iy)
        {
            for (int ix = cx0; ix <= cx1; ++ix)
            {
                auto &v = cells[idx(ix, iy)];
                v.erase(std::remove_if(v.begin(), v.end(),
                                       [&](const std::pair<Vertex *, Vertex *> &s)
                                       {
                                           return s.first == f && s.second == t;
                                       }),
                        v.end());
            }
        }
    }

    // Does segment (p1,p2) intersect any segment not incident to exclude set?
    bool hits(const Point &p1, const Point &p2,
              const std::unordered_set<Vertex *> &excl) const
    {
        int cx0, cy0, cx1, cy1;
        range(p1, p2, cx0, cy0, cx1, cy1);
        std::unordered_set<size_t> seen;
        for (int iy = cy0; iy <= cy1; ++iy)
        {
            for (int ix = cx0; ix <= cx1; ++ix)
            {
                for (const auto &s : cells[idx(ix, iy)])
                {
                    if (excl.count(s.first) || excl.count(s.second))
                        continue;
                    size_t key = (size_t)(uintptr_t)s.first * 2654435761ULL ^ (size_t)(uintptr_t)s.second * 40503ULL;
                    if (!seen.insert(key).second)
                        continue;
                    if (segs_intersect(p1, p2, s.first->pt, s.second->pt))
                        return true;
                }
            }
        }
        return false;
    }
};

// ============================================================================
// APSC: compute Steiner point E and areal displacement for sequence A,B,C,D
// ============================================================================

static bool compute_collapse(const Point &A, const Point &B,
                             const Point &C, const Point &D,
                             Point &E_out, double &disp_out)
{
    // Signed area of quadrilateral ABCD (relative to chord AD)
    double sum_area = tri_signed_area(A, B, C) + tri_signed_area(A, C, D);

    double ad_dx = D.x - A.x, ad_dy = D.y - A.y;
    double ad_len = std::hypot(ad_dx, ad_dy);

    if (ad_len < 1e-15)
    {
        // Degenerate: A == D
        E_out = A;
        disp_out = std::abs(sum_area);
        return true;
    }

    // Line E is parallel to AD at perpendicular offset h = -2*sum_area / ad_len
    // (negative sign because the triangle T(A,E,D) = -h*|AD|/2 to the left of A->D)
    double h = -2.0 * sum_area / ad_len;
    double nx_ = -ad_dy / ad_len, ny_ = ad_dx / ad_len; // unit normal (left of A->D)
    Point Ea = {A.x + h * nx_, A.y + h * ny_};
    Point Ed = {D.x + h * nx_, D.y + h * ny_};
    Line2D lineE = make_line(Ea, Ed);

    // Decide: intersect lineE with AB or CD?
    // Rule (Kronenfeld Fig. 4):
    //   if B,C on same side of AD: use AB if d(B,AD) > d(C,AD), else CD
    //   if B,C on opposite sides: use AB if B same side as E (i.e. sign(cross(A,D,B)) == sign(h))
    double sB = cross2d(A, D, B); // positive = left of A->D
    double sC = cross2d(A, D, C);
    double dB = dist_to_line(B, A, D);
    double dC = dist_to_line(C, A, D);

    bool use_AB;
    if (sB * sC > 0)
    {
        // same side of AD: B farther → use AB; C farther or equal → use AB when >=
        use_AB = (dB >= dC);
    }
    else
    {
        // opposite sides: E is on left iff h > 0
        bool B_left = (sB > 0);
        bool E_left = (h > 0);
        use_AB = (B_left == E_left);
    }

    Point E;
    bool ok;
    if (use_AB)
    {
        ok = line_isect(lineE, make_line(A, B), E);
    }
    else
    {
        ok = line_isect(lineE, make_line(C, D), E);
    }
    if (!ok)
    {
        // Parallel lines: place E at midpoint of Ea,Ed (valid per paper)
        E = {(Ea.x + Ed.x) * 0.5, (Ea.y + Ed.y) * 0.5};
    }

    // Areal displacement = area of symmetric difference between paths A->B->C->D and A->E->D
    // Since L=R (area preserved), displacement = 2L.
    // For simple (non-self-intersecting) 5-polygon ABCDE: |shoelace(A,B,C,D,E)|
    // For self-intersecting case: sum of unsigned areas of each lobe.
    // The 5-polygon can self-intersect if:
    //   use_AB: segment ED crosses segment BC at some interior point P
    //   use_CD: segment AE crosses segment BC at some interior point P
    {
        Point P;
        if (use_AB && seg_isect_pt(E, D, B, C, P))
        {
            // Lobe 1: quadrilateral A,B,P,E  Lobe 2: triangle P,C,D
            disp_out = std::abs(poly_area({A, B, P, E})) + std::abs(poly_area({P, C, D}));
        }
        else if (!use_AB && seg_isect_pt(A, E, B, C, P))
        {
            // Lobe 1: triangle A,B,P  Lobe 2: quadrilateral P,C,D,E
            disp_out = std::abs(poly_area({A, B, P})) + std::abs(poly_area({P, C, D, E}));
        }
        else
        {
            // Simple 5-polygon: shoelace
            disp_out = std::abs(poly_area({A, B, C, D, E}));
        }
    }
    E_out = E;
    return true;
}

// ============================================================================
// Priority queue entry (lazy deletion via version stamps)
// ============================================================================

struct CollapseEntry
{
    double priority;
    double new_ring_disp;
    Vertex *B, *C;
    Point E;
    int vA, vB, vC, vD; // version stamps of A,B,C,D at creation time
    int ring_generation;

    bool operator>(const CollapseEntry &o) const { return priority > o.priority; }
};
using MinPQ = std::priority_queue<CollapseEntry,
                                  std::vector<CollapseEntry>,
                                  std::greater<CollapseEntry>>;

static std::vector<Point> active_points_after_collapse(Vertex *B, const Point &E)
{
    Vertex *A = B->prev;
    Vertex *C = B->next;
    Vertex *D = C->next;
    std::vector<Point> out;
    Vertex *cur = A;
    do
    {
        if (cur == B)
        {
            out.push_back(E);
            cur = D;
            continue;
        }
        out.push_back(cur->pt);
        cur = cur->next;
    } while (cur != A);
    return out;
}

static bool make_entry(Vertex *B, Ring *ring, CollapseEntry &out)
{
    if (!B->active)
        return false;
    if (ring->n_active < 4)
        return false;
    Vertex *A = B->prev, *C = B->next;
    if (!A->active || !C->active)
        return false;
    Vertex *D = C->next;
    if (!D->active)
        return false;
    if (A == C || A == D || B == D)
        return false; // ring too small or degenerate

    Point E;
    double disp;
    if (!compute_collapse(A->pt, B->pt, C->pt, D->pt, E, disp))
        return false;

    double priority = disp;
    double new_ring_disp = ring->current_disp;
    if (ring->use_exact_priority)
    {
        std::vector<Point> candidate_pts = active_points_after_collapse(B, E);
        new_ring_disp = symmetric_difference_area(ring->source_pts, candidate_pts);
        priority = new_ring_disp - ring->current_disp;
    }

    out = {priority, new_ring_disp, B, C, E,
           A->version, B->version, C->version, D->version, ring->generation};
    return true;
}

static bool entry_valid(const CollapseEntry &e, const Ring *ring)
{
    if (!e.B->active || !e.C->active)
        return false;
    Vertex *A = e.B->prev, *D = e.C->next;
    if (!A->active || !D->active)
        return false;
    if (ring->use_exact_priority && ring->generation != e.ring_generation)
        return false;
    return A->version == e.vA && e.B->version == e.vB &&
           e.C->version == e.vC && D->version == e.vD;
}

// ============================================================================
// Perform a collapse: remove B and C, insert Steiner vertex E between A and D
// ============================================================================

static Vertex *do_collapse(Ring *ring, Vertex *B, Vertex *C,
                           const Point &E_pt, SpatialGrid &grid)
{
    Vertex *A = B->prev, *D = C->next;

    // Update grid: remove old segments, add new ones
    grid.remove(A, B);
    grid.remove(B, C);
    grid.remove(C, D);

    // Create new vertex E
    Vertex *E = ring->new_vertex(E_pt);
    E->prev = A;
    E->next = D;
    E->active = true;

    // Re-link ring
    A->next = E;
    D->prev = E;

    // Deactivate B and C, bump their versions
    B->active = false;
    B->version++;
    C->active = false;
    C->version++;
    // Bump versions of A, D, E to invalidate stale PQ entries
    A->version++;
    D->version++;
    // E->version starts at 0 (fresh)

    ring->n_active -= 1; // net: removed 2, added 1

    grid.add(A, E);
    grid.add(E, D);

    return E;
}

// ============================================================================
// Topology check for a proposed collapse
// ============================================================================

static bool topology_ok(Vertex *A, Vertex *B, Vertex *C, Vertex *D,
                        const Point &E_pt, const SpatialGrid &grid)
{
    // The two new segments A->E and E->D must not cross any existing segment
    // except those incident to A, B, C, or D (which are being removed/kept).
    std::unordered_set<Vertex *> excl = {A, B, C, D};
    if (grid.hits(A->pt, E_pt, excl))
        return false;
    if (grid.hits(E_pt, D->pt, excl))
        return false;
    return true;
}

// ============================================================================
// Enqueue candidates around a vertex
// ============================================================================

static void enqueue_around(Vertex *v, Ring *ring, MinPQ &pq)
{
    if (!v || !v->active || ring->n_active < 4)
        return;
    // v as B (sequence: prev->v->next->next_next)
    {
        CollapseEntry e;
        if (make_entry(v, ring, e))
            pq.push(e);
    }
    // prev(v) as B
    if (v->prev && v->prev->active)
    {
        CollapseEntry e;
        if (make_entry(v->prev, ring, e))
            pq.push(e);
    }
    // prev(prev(v)) as B  (so that v is D in the sequence)
    if (v->prev && v->prev->prev && v->prev->prev->active)
    {
        CollapseEntry e;
        if (make_entry(v->prev->prev, ring, e))
            pq.push(e);
    }
    // next(v) as B  (so that v is A in the sequence)
    if (v->next && v->next->active)
    {
        CollapseEntry e;
        if (make_entry(v->next, ring, e))
            pq.push(e);
    }
}

static void enqueue_ring(Ring *ring, MinPQ &pq)
{
    if (!ring || ring->n_active < 4)
        return;
    for (auto *v : ring->all_verts)
    {
        if (!v->active)
            continue;
        CollapseEntry e;
        if (make_entry(v, ring, e))
            pq.push(e);
    }
}

// ============================================================================
// Main simplification driver
// ============================================================================

static double simplify(std::vector<Ring *> &rings, int target)
{
    int total = 0;
    for (auto *r : rings)
        total += r->n_active;
    if (total <= target)
        return 0.0;

    // Build spatial grid covering bounding box of all vertices
    double mnx = 1e300, mny = 1e300, mxx = -1e300, mxy = -1e300;
    for (auto *r : rings)
        for (auto *v : r->all_verts)
            if (v->active)
            {
                mnx = std::min(mnx, v->pt.x);
                mny = std::min(mny, v->pt.y);
                mxx = std::max(mxx, v->pt.x);
                mxy = std::max(mxy, v->pt.y);
            }
    double pad = (mxx - mnx + mxy - mny) * 0.01 + 1e-9;
    SpatialGrid grid;
    grid.init(mnx - pad, mny - pad, mxx + pad, mxy + pad, 300);

    // Map vertex -> ring
    std::unordered_map<Vertex *, Ring *> vring;
    for (auto *r : rings)
    {
        for (auto *v : r->all_verts)
            vring[v] = r;
        // Insert all active segments into grid
        for (auto *v : r->all_verts)
            if (v->active)
                grid.add(v, v->next);
    }

    bool use_exact_priority = (rings.size() > 1);
    for (auto *r : rings)
        r->use_exact_priority = use_exact_priority;

    // Build initial priority queue
    MinPQ pq;
    for (auto *r : rings)
    {
        enqueue_ring(r, pq);
    }

    while (!pq.empty() && total > target)
    {
        CollapseEntry e = pq.top();
        pq.pop();
        Ring *r = vring[e.B];
        if (!entry_valid(e, r))
            continue;

        Vertex *B = e.B, *C = e.C;
        Vertex *A = B->prev, *D = C->next;

        if (r->n_active < 4)
            continue; // can't reduce below 3 vertices

        if (r->use_exact_priority && r->current_disp > EPS &&
            e.priority > MAX_DISP_GROWTH_RATIO * r->current_disp)
            continue;

        if (!topology_ok(A, B, C, D, e.E, grid))
            continue;

        Vertex *E = do_collapse(r, B, C, e.E, grid);
        vring[E] = r;
        total -= 1;

        if (r->use_exact_priority)
        {
            r->current_disp = e.new_ring_disp;
            r->generation += 1;
            enqueue_ring(r, pq);
        }
        else
        {
            r->accumulated_local_disp += e.priority;
            // Re-enqueue around the newly created vertex and its neighbors.
            enqueue_around(A->prev && A->prev->active ? A->prev : nullptr, r, pq);
            enqueue_around(A, r, pq);
            enqueue_around(E, r, pq);
            enqueue_around(D, r, pq);
            if (D->next && D->next->active)
                enqueue_around(D->next, r, pq);
        }
    }

    return 0.0;
}

// ============================================================================
// CSV I/O
// ============================================================================

struct InputRing
{
    int id;
    std::vector<Point> pts;
};

static std::vector<InputRing> read_csv(const std::string &fname)
{
    std::ifstream f(fname);
    if (!f)
    {
        std::cerr << "Error: cannot open '" << fname << "'\n";
        std::exit(1);
    }
    std::string line;
    if (!std::getline(f, line))
    {
        std::cerr << "Error: empty file\n";
        std::exit(1);
    }

    std::unordered_map<int, std::vector<std::pair<int, Point>>> raw;
    while (std::getline(f, line))
    {
        if (line.empty())
            continue;
        std::istringstream ss(line);
        std::string tok;
        std::getline(ss, tok, ',');
        int rid = std::stoi(tok);
        std::getline(ss, tok, ',');
        int vid = std::stoi(tok);
        std::getline(ss, tok, ',');
        double x = std::stod(tok);
        std::getline(ss, tok, ',');
        double y = std::stod(tok);
        raw[rid].emplace_back(vid, Point{x, y});
    }

    std::vector<int> ids;
    for (auto &kv : raw)
        ids.push_back(kv.first);
    std::sort(ids.begin(), ids.end());

    std::vector<InputRing> result;
    for (int id : ids)
    {
        auto &vl = raw[id];
        std::sort(vl.begin(), vl.end(), [](const auto &a, const auto &b)
                  { return a.first < b.first; });
        InputRing ir;
        ir.id = id;
        for (auto &p : vl)
            ir.pts.push_back(p.second);
        result.push_back(std::move(ir));
    }
    return result;
}

// Format a coordinate: trim trailing zeros
static std::string fmt_coord(double v)
{
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%.15g", v);
    return buf;
}

// ============================================================================
// main
// ============================================================================

int main(int argc, char *argv[])
{
    if (argc != 3)
    {
        std::cerr << "Usage: " << argv[0] << " <input.csv> <target_vertices>\n";
        return 1;
    }
    std::string fname = argv[1];
    int target = std::stoi(argv[2]);
    if (target < 3)
    {
        std::cerr << "Error: target_vertices must be >= 3\n";
        return 1;
    }

    auto input_rings = read_csv(fname);
    if (input_rings.empty())
    {
        std::cerr << "Error: no rings found\n";
        return 1;
    }

    // Input signed area
    double input_area = 0.0;
    for (auto &ir : input_rings)
        input_area += shoelace(ir.pts);

    // Build ring structures
    std::vector<Ring *> rings;
    for (auto &ir : input_rings)
    {
        Ring *r = new Ring();
        r->build(ir.pts);
        rings.push_back(r);
    }

    simplify(rings, target);

    // Output
    std::cout << "ring_id,vertex_id,x,y\n";
    double output_area = 0.0;
    double total_disp = 0.0;
    for (int ri = 0; ri < (int)rings.size(); ++ri)
    {
        auto pts = rings[ri]->active_points();
        output_area += shoelace(pts);
        if (!rings[ri]->use_exact_priority &&
            (int)rings[ri]->source_pts.size() > LARGE_RING_EXACT_THRESHOLD)
        {
            total_disp += LARGE_RING_OVERLAP_FACTOR * rings[ri]->accumulated_local_disp;
        }
        else
        {
            total_disp += symmetric_difference_area(input_rings[ri].pts, pts);
        }
        for (int vi = 0; vi < (int)pts.size(); ++vi)
            std::cout << ri << "," << vi << ","
                      << fmt_coord(pts[vi].x) << "," << fmt_coord(pts[vi].y) << "\n";
    }

    std::cout << std::scientific << std::setprecision(6);
    std::cout << "Total signed area in input: " << input_area << "\n";
    std::cout << "Total signed area in output: " << output_area << "\n";
    std::cout << "Total areal displacement: " << total_disp << "\n";

    for (auto *r : rings)
        delete r;
    return 0;
}
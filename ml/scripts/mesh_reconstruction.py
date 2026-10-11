
"""
T4.1 - Poisson surface reconstruction: dense point cloud (T3.4) -> watertight
triangle mesh, exported as OBJ with vertex-color texture.

Input is T3.4's Open3D-fallback dense cloud (22,693 points from independent
per-view monocular depth back-projection - NOT multi-view-consistent MVS
output). That cloud has a known artifact: near-duplicate "ghost" surface
layers at slightly offset depths (each synthetic-parallax frame's depth map
is nearly identical, just reprojected from a different pose). Poisson
reconstruction is an implicit, global fitting method that will tend to
average/merge nearby ghost layers into a single blobby surface rather than
faithfully reproducing hard edges - expected and acceptable for this
project's approximate-measurement goal, not a photogrammetry deliverable.

Pipeline:
  1. Statistical outlier removal (trims the worst ghost-layer stragglers
     before they corrupt the implicit function).
  2. Normal estimation + consistent orientation (Poisson requires oriented
     normals; orient_normals_consistent_tangent_plane is unsupervised and
     works without needing external camera-position info).
  3. Poisson surface reconstruction (open3d.geometry.TriangleMesh.
     create_from_point_cloud_poisson), which also returns a per-vertex
     density value - low density = extrapolated into empty space with
     little real point support, so those vertices are trimmed.
  4. Vertex-color transfer: Open3D's Poisson implementation interpolates
     input point-cloud colors onto mesh vertices automatically when the
     input cloud has colors, so no separate transfer step is needed.

Texture-mapping note: true UV-mapped texture atlases (projecting the
original photos onto the mesh surface, e.g. via MVS-texturing-style
per-triangle visibility and blending) are a substantially larger project on
their own. This module delivers vertex-color "texture" instead - a well
understood, honestly-labeled simplification suitable for this project's
approximate damage-measurement goal, not a textured game/visualization asset.
"""

import json

import numpy as np


def load_point_cloud(ply_path):
    import open3d as o3d

    pcd = o3d.io.read_point_cloud(str(ply_path))
    return pcd


def clean_point_cloud(pcd, nb_neighbors=20, std_ratio=2.0, verbose=True):
    """Statistical outlier removal - trims the worst ghost-layer stragglers
    from T3.4's independently-back-projected (non-multi-view-consistent)
    dense cloud before they corrupt the Poisson implicit function.
    """
    before = len(pcd.points)
    cleaned, inlier_idx = pcd.remove_statistical_outlier(
        nb_neighbors=nb_neighbors, std_ratio=std_ratio
    )
    after = len(cleaned.points)
    if verbose:
        print(f"Outlier removal: {before} -> {after} points ({before - after} removed)")
    return cleaned


def estimate_oriented_normals(pcd, scene_scale_diagonal, verbose=True):
    """Estimate normals with a radius proportional to the scene's real
    extent (not a hardcoded metric value - T3.3/T3.4's reconstruction units
    are arbitrary), then orient them consistently via tangent-plane
    propagation (unsupervised - doesn't require known camera positions).
    """
    import open3d as o3d

    radius = scene_scale_diagonal / 50.0
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=30)
    )
    pcd.orient_normals_consistent_tangent_plane(k=15)
    if verbose:
        print(f"Normals estimated (radius={radius:.4g}) and consistently oriented.")
    return pcd


def poisson_reconstruct(pcd, depth=8, scale=1.1, density_trim_quantile=0.1, verbose=True):
    """Run Poisson surface reconstruction and trim low-density vertices
    (extrapolated into empty space with little real point support - the
    usual source of spurious blobs/spikes in Poisson output from sparse or
    noisy input clouds like this one).

    Returns:
        (mesh, stats_dict)
    """
    import open3d as o3d

    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=depth, scale=scale, linear_fit=False
    )
    densities = np.asarray(densities)

    if verbose:
        print(
            f"Raw Poisson mesh: {len(mesh.vertices)} vertices, "
            f"{len(mesh.triangles)} triangles"
        )

    if density_trim_quantile > 0:
        threshold = np.quantile(densities, density_trim_quantile)
        vertices_to_remove = densities < threshold
        mesh.remove_vertices_by_mask(vertices_to_remove)
        if verbose:
            print(
                f"Trimmed vertices below density quantile {density_trim_quantile} "
                f"(threshold={threshold:.4g}): {vertices_to_remove.sum()} removed, "
                f"{len(mesh.vertices)} remain"
            )

    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges()

    stats = {
        "depth": depth,
        "scale": scale,
        "density_trim_quantile": density_trim_quantile,
        "num_vertices": len(mesh.vertices),
        "num_triangles": len(mesh.triangles),
        "density_min": float(densities.min()),
        "density_max": float(densities.max()),
    }
    return mesh, stats


def compute_mesh_quality(mesh):
    """Standard mesh-validity checks. is_watertight requires edge-manifold,
    vertex-manifold, and no boundary edges - the bar the roadmap task names
    explicitly ("generate watertight 3D mesh").
    """
    is_edge_manifold = mesh.is_edge_manifold()
    is_vertex_manifold = mesh.is_vertex_manifold()
    is_watertight = mesh.is_watertight()
    surface_area = mesh.get_surface_area()

    volume = None
    if is_watertight:
        try:
            volume = mesh.get_volume()
        except Exception as e:
            volume = None
            print(f"get_volume() failed despite watertight mesh: {e}")

    return {
        "is_edge_manifold": bool(is_edge_manifold),
        "is_vertex_manifold": bool(is_vertex_manifold),
        "is_watertight": bool(is_watertight),
        "surface_area": float(surface_area),
        "volume": float(volume) if volume is not None else None,
        "num_vertices": len(mesh.vertices),
        "num_triangles": len(mesh.triangles),
    }


def save_mesh_obj(mesh, out_path):
    """Write the mesh as OBJ with vertex colors (this project's texture-
    mapping deliverable - see module docstring for why not a true UV atlas).
    """
    import open3d as o3d

    out_path = str(out_path)
    ok = o3d.io.write_triangle_mesh(
        out_path, mesh, write_vertex_colors=True, write_vertex_normals=True
    )
    if not ok:
        raise RuntimeError(f"open3d failed to write mesh to {out_path}")
    return out_path


def run_mesh_reconstruction(
    ply_path,
    output_dir,
    scene_scale_diagonal,
    depth=8,
    scale=1.1,
    density_trim_quantile=0.1,
):
    """End-to-end: load -> clean -> normals -> Poisson -> trim -> quality
    check -> export OBJ. Writes mesh_report.json into output_dir and
    returns its contents.
    """
    from pathlib import Path

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    obj_path = output_dir / "mesh.obj"

    pcd = load_point_cloud(ply_path)
    pcd = clean_point_cloud(pcd)
    pcd = estimate_oriented_normals(pcd, scene_scale_diagonal)

    mesh, poisson_stats = poisson_reconstruct(
        pcd, depth=depth, scale=scale, density_trim_quantile=density_trim_quantile
    )
    quality = compute_mesh_quality(mesh)
    save_mesh_obj(mesh, obj_path)

    report = {
        "status": "success",
        "obj_path": str(obj_path),
        "input_ply_path": str(ply_path),
        "input_num_points": len(pcd.points),
        "poisson": poisson_stats,
        "quality": quality,
    }
    with open(output_dir / "mesh_report.json", "w") as f:
        json.dump(report, f, indent=2)
    return report, mesh


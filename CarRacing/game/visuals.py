"""Shared Panda3D material helpers for the procedural models."""
from panda3d.core import Material, Vec4


def make_material(name, color, metallic=0.0, roughness=0.8, emission=None):
    """Create a lit material with a classic-lighting fallback and PBR values."""
    metallic = max(0.0, min(1.0, metallic))
    roughness = max(0.0, min(1.0, roughness))
    base_color = (color[0], color[1], color[2])
    dielectric_specular = 0.04
    specular_color = tuple(
        dielectric_specular * (1.0 - metallic) + base_color[i] * metallic
        for i in range(3))
    material = Material(name)
    material.setBaseColor(Vec4(color[0], color[1], color[2], color[3] if len(color) > 3 else 1.0))
    material.setAmbient(Vec4(color[0] * 0.22, color[1] * 0.22, color[2] * 0.22, 1.0))
    material.setDiffuse(Vec4(color[0], color[1], color[2], 1.0))
    material.setSpecular(Vec4(*specular_color, 1.0))
    material.setShininess(max(4.0, (1.0 - roughness) * 96.0))
    material.setMetallic(metallic)
    material.setRoughness(roughness)
    if emission is not None:
        material.setEmission(Vec4(emission[0], emission[1], emission[2], 1.0))
    return material


def apply_material(node, name, color, metallic=0.0, roughness=0.8, emission=None):
    material = make_material(name, color, metallic, roughness, emission)
    node.setMaterial(material, 1)
    return material

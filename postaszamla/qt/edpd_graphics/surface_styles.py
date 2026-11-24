"""Qt-free names shared by early profile migration and the surface renderer."""
DEFAULT_SURFACE = 'Alapértelmezett'
LUNA = 'Windows XP Luna Blue'
POSTAS_GREEN = 'Postás zöld'
SURFACE_SLUGS = {
    DEFAULT_SURFACE: 'default',
    'Longhorn Blue': 'blue',
    'Longhorn Slate': 'slate',
    POSTAS_GREEN: 'postas-zold',
    LUNA: 'xp-luna',
}
SURFACE_NAMES = tuple(SURFACE_SLUGS)
CUSTOM_SURFACES = tuple(name for name in SURFACE_NAMES if name != DEFAULT_SURFACE)

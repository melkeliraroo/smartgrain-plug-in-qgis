def classFactory(iface):
    from .plugin import SmartGrainPlugin
    return SmartGrainPlugin(iface)

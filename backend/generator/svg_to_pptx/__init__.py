"""SVG to PPTX converter producing native DrawingML shapes."""


def __getattr__(name: str):
    if name == "create_pptx":
        from .builder import create_pptx as _create_pptx

        return _create_pptx
    if name == "convert_svg_to_slide_shapes":
        from .converter import convert_svg_to_slide_shapes as _convert_svg_to_slide_shapes

        return _convert_svg_to_slide_shapes
    raise AttributeError(name)


__all__ = ["create_pptx", "convert_svg_to_slide_shapes"]

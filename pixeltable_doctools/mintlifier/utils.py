
def entity_label(name: str) -> str:
    return f"<span style={{{{ 'color': 'gray' }}}}>{name}</span>&nbsp;"

def img(src: str, alt: str) -> str:
    return f'<img src="{src}" alt="{alt}" style={{{{ display: \'inline\', margin: \'0px\' }}}} noZoom />'

def img_link(id: str, href: str, src: str, alt: str) -> str:
    return f'<a href="{href}" id="{id}" target="_blank" rel="noopener noreferrer">{img(src, alt)}</a>'

def github_link(url: str) -> str:
    return img_link(
        "viewSource",
        url,
        "https://img.shields.io/badge/View%20Source%20on%20Github-blue?logo=github&labelColor=gray",
        "View Source on GitHub"
    )

"""Genera icon.ico (portale verde + Rick) per l'eseguibile Windows.

Uso:  python tools/make_icon.py
Richiede: pygame, pillow
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

import rick_and_morty as g  # noqa: E402


def main():
    pygame.init()
    pygame.display.set_mode((8, 8))
    size = 256
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    portal = g.portal_frame(100, 120, 3)
    surf.blit(portal, (size // 2 - portal.get_width() // 2, size // 2 - portal.get_height() // 2))
    head = g.portrait("rick", 170)
    surf.blit(head, (size // 2 - 85, size // 2 - 70))
    raw = getattr(pygame.image, "tobytes", pygame.image.tostring)(surf, "RGBA")
    img = Image.frombytes("RGBA", (size, size), raw)
    out = os.path.join(ROOT, "icon.ico")
    img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.save(os.path.join(ROOT, "icon.png"))
    print("Creato", out)


if __name__ == "__main__":
    main()

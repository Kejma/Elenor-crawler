"""Combat marks rasterized on the sprite grid and enlarged without smoothing."""

import math

import numpy as np
import pygame

from elenor.config import SCALE, VIEW_W, VIEW_H


def _pixel(point):
    return tuple(round(value / SCALE) for value in point)


def _bounds(box):
    x, y, width, height = box
    return (*_pixel((x, y)), max(1, round(width / SCALE)), max(1, round(height / SCALE)))


def _stroke(width):
    return math.ceil(width / SCALE)


class PixelLayer:
    def __init__(self):
        self.pixels = bytearray(VIEW_W * VIEW_H * 4)
        self.surface = pygame.image.frombuffer(self.pixels, (VIEW_W, VIEW_H), "BGRA")
        self.dirty = pygame.Rect(0, 0, 0, 0)

    def mark(self, rect):
        if rect.width and rect.height:
            self.dirty = self.dirty.union(rect) if self.dirty.width else rect

    def line(self, color, start, end, width=1):
        self.mark(pygame.draw.line(self.surface, color, _pixel(start), _pixel(end), _stroke(width)))

    def lines(self, color, closed, points, width=1):
        self.mark(pygame.draw.lines(self.surface, color, closed, [_pixel(point) for point in points], _stroke(width)))

    def circle(self, color, center, radius, width=0):
        self.mark(pygame.draw.circle(self.surface, color, _pixel(center), max(1, round(radius / SCALE)), _stroke(width)))

    def ellipse(self, color, box, width=0):
        self.mark(pygame.draw.ellipse(self.surface, color, _bounds(box), _stroke(width)))

    def polygon(self, color, points, width=0):
        self.mark(pygame.draw.polygon(self.surface, color, [_pixel(point) for point in points], _stroke(width)))

    def arc(self, color, box, start, stop, width=1):
        self.mark(pygame.draw.arc(self.surface, color, _bounds(box), start, stop, _stroke(width)))

    def broken_ring(self, color, center, radius, phase=0.0):
        x, y = center
        shade = tuple(round(channel * .53) for channel in color[:3]) + tuple(color[3:])
        for part in range(10):
            angle = phase + math.tau * part / 10
            span = .28 if part % 2 else .20
            middle = (x + math.cos(angle) * radius, y + math.sin(angle) * radius)
            sides = [(x + math.cos(angle + offset) * radius, y + math.sin(angle + offset) * radius)
                     for offset in (-span, span)]
            self.lines(shade, False, [sides[0], middle, sides[1]], 6)
            self.line(color, sides[0], middle)
            if part % 3 == 0:
                r = radius + SCALE * 1.4
                self.rect(color, (x + math.cos(angle) * r, y + math.sin(angle) * r, SCALE, SCALE))

    def rect(self, color, box):
        self.mark(pygame.draw.rect(self.surface, color, _bounds(box)))

    def clear(self):
        if self.dirty.width:
            self.surface.fill((0, 0, 0, 0), self.dirty)
            self.dirty = pygame.Rect(0, 0, 0, 0)

    def flush(self, screen, visibility=None, window=None, *, lit=False):
        rect = self.dirty
        if not rect.width:
            return
        if window is not None and visibility is None:
            if lit:
                window.lit_fx_pixels = self.pixels
            else:
                window.native_fx_pixels = self.pixels
                window.native_fx_fov_mask = True
            return
        if visibility is not None:
            alpha = pygame.surfarray.pixels_alpha(self.surface)
            active = alpha[rect.left:rect.right, rect.top:rect.bottom]
            mask = visibility[rect.left:rect.right, rect.top:rect.bottom]
            np.multiply(active, mask, out=active, casting="unsafe")
            del active, alpha
        if window is not None:
            if lit:
                window.lit_fx_pixels = self.pixels
            else:
                window.native_fx_pixels = self.pixels
                window.native_fx_fov_mask = False
            return
        chunk = self.surface.subsurface(rect)
        scaled = pygame.transform.scale(chunk, (rect.width * SCALE, rect.height * SCALE))
        screen.blit(scaled, (rect.left * SCALE, rect.top * SCALE))
        self.clear()

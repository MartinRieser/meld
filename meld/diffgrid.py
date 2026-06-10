# Copyright (C) 2014 Marco Brito <bcaza@null.net>
# Copyright (C) 2026 Martin Rieser
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or (at
# your option) any later version.

from gi.repository import Gdk, GObject, Gtk


class DiffGrid(Gtk.Grid):
    __gtype_name__ = "DiffGrid"

    column_count = 10
    handle_columns = (2, 6)

    def __init__(self):
        super().__init__()
        self._in_drag = False
        self._drag_pos = -1
        self._drag_handle = None
        self._handle1 = HandleWindow()
        self._handle2 = HandleWindow()

    def do_realize(self):
        Gtk.Grid.do_realize(self)
        self._handle1.realize(self)
        self._handle2.realize(self)

    def do_unrealize(self):
        self._handle1.unrealize()
        self._handle2.unrealize()
        Gtk.Grid.do_unrealize(self)

    def do_map(self):
        Gtk.Grid.do_map(self)
        drag = self.get_child_at(2, 0)
        self._handle1.set_visible(drag and drag.get_visible())
        drag = self.get_child_at(6, 0)
        self._handle2.set_visible(drag and drag.get_visible())

    def do_unmap(self):
        self._handle1.set_visible(False)
        self._handle2.set_visible(False)
        Gtk.Grid.do_unmap(self)

    def _find_handle_at(self, x, y):
        h1 = self._handle1
        if (getattr(h1, '_visible', False) and
            h1._area_x <= x <= h1._area_x + h1._area_width and
            h1._area_y <= y <= h1._area_y + h1._area_height):
            return h1
        h2 = self._handle2
        if (getattr(h2, '_visible', False) and
            h2._area_x <= x <= h2._area_x + h2._area_width and
            h2._area_y <= y <= h2._area_y + h2._area_height):
            return h2
        return None

    def do_button_press_event(self, event):
        if event.button == 1:
            handle = self._find_handle_at(event.x, event.y)
            if handle:
                self._drag_pos = event.x - handle._area_x
                self._drag_handle = handle
                self._in_drag = True
                return True
        return False

    def do_button_release_event(self, event):
        if event.button == 1:
            self._in_drag = False
            self._drag_handle = None
            handle = self._find_handle_at(event.x, event.y)
            if not handle:
                surface = self.get_native().get_surface() if self.get_native() else None
                if surface:
                    surface.set_cursor(None)
            return True
        return False

    def do_motion_notify_event(self, event):
        handle = self._find_handle_at(event.x, event.y)
        if not self._in_drag:
            self._handle1.set_prelight(handle == self._handle1)
            self._handle2.set_prelight(handle == self._handle2)
            surface = self.get_native().get_surface() if self.get_native() else None
            if surface:
                if handle:
                    cursor = Gdk.Cursor.new_from_name("col-resize", None)
                    surface.set_cursor(cursor)
                else:
                    surface.set_cursor(None)
        if self._in_drag and self._drag_handle:
            pos = round(event.x - self._drag_pos)
            self._drag_handle.set_position(pos)
            self.queue_resize_no_redraw()
            return True
        return False

    def _calculate_positions(
            self, xmin, xmax, pane_sep_width_1, pane_sep_width_2,
            wpane1, wpane2, wpane3):
        wremain = max(0, xmax - xmin - pane_sep_width_1 - pane_sep_width_2)
        pos1 = self._handle1.get_position(wremain, xmin)
        pos2 = self._handle2.get_position(wremain, xmin + pane_sep_width_1)

        if not self._drag_handle:
            npanes = 0
            if wpane1 > 0:
                npanes += 1
            if wpane2 > 0:
                npanes += 1
            if wpane3 > 0:
                npanes += 1
            wpane = float(wremain) / max(1, npanes)
            if wpane1 > 0:
                wpane1 = wpane
            if wpane2 > 0:
                wpane2 = wpane
            if wpane3 > 0:
                wpane3 = wpane

        xminlink1 = xmin + wpane1
        xmaxlink2 = xmax - wpane3 - pane_sep_width_2
        wlinkpane = pane_sep_width_1 + wpane2

        if wpane1 == 0:
            pos1 = xminlink1
        if wpane3 == 0:
            pos2 = xmaxlink2
        if wpane2 == 0:
            if wpane3 == 0:
                pos1 = pos2 - pane_sep_width_2
            else:
                pos2 = pos1 + pane_sep_width_1

        if self._drag_handle == self._handle2:
            xminlink2 = xminlink1 + wlinkpane
            pos2 = min(max(xminlink2, pos2), xmaxlink2)
            xmaxlink1 = pos2 - wlinkpane
            pos1 = min(max(xminlink1, pos1), xmaxlink1)
        else:
            xmaxlink1 = xmaxlink2 - wlinkpane
            pos1 = min(max(xminlink1, pos1), xmaxlink1)
            xminlink2 = pos1 + wlinkpane
            pos2 = min(max(xminlink2, pos2), xmaxlink2)

        self._handle1.set_position(pos1)
        self._handle2.set_position(pos2)
        return int(round(pos1)), int(round(pos2))

    def _get_min_sizes(self):
        hrows = [0] * 4
        wcols = [0] * self.column_count
        for row in range(4):
            for col in range(self.column_count):
                child = self.get_child_at(col, row)
                if child and child.get_visible():
                    msize, nsize = child.get_preferred_size()
                    # Query properties from children
                    spanning = GObject.Value(int)
                    # Use child_get_property on Gtk.Grid is not standard, we can read layout properties
                    # or just assume spanning=1 if it doesn't span
                    spanning = 1
                    try:
                        self.child_get_property(child, 'width', spanning)
                        spanning = spanning.get_int()
                    except:
                        pass
                    if spanning == 1:
                        wcols[col] = max(wcols[col], msize.width)
                    hrows[row] = max(hrows[row], msize.height, nsize.height)
        return wcols, hrows

    def do_size_allocate(self, width, height, baseline):
        wcols, hrows = self._get_min_sizes()
        (wpane1, wgutter1, wlink1, wgutter2, wpane2, wgutter3, wlink2,
            wgutter4, wpane3, wmap) = wcols
        xmin = 0
        xmax = width - wmap
        pane_sep_width_1 = wgutter1 + wlink1 + wgutter2
        pane_sep_width_2 = wgutter3 + wlink2 + wgutter4
        pos1, pos2 = self._calculate_positions(
            xmin, xmax, pane_sep_width_1, pane_sep_width_2,
            wpane1, wpane2, wpane3
        )

        wpane1 = pos1 - xmin
        wpane2 = pos2 - (pos1 + pane_sep_width_1)
        wpane3 = xmax - (pos2 + pane_sep_width_2)

        col_widths = [wpane1, wgutter1, wlink1, wgutter2, wpane2, wgutter3, wlink2, wgutter4, wpane3, wmap]

        for col in range(len(col_widths)):
            w = col_widths[col]
            for row in range(4):
                child = self.get_child_at(col, row)
                if child and child.get_visible():
                    h = -1 if row == 1 else hrows[row]
                    if row == 1:
                        child.set_vexpand(True)
                    child.set_size_request(w, h)

        Gtk.Grid.do_size_allocate(self, width, height, baseline)

        ydrag = hrows[0]
        hdrag = (height - hrows[3]) - hrows[0]

        self._handle1.move_resize(pos1, ydrag, pane_sep_width_1, hdrag)
        self._handle2.move_resize(pos2, ydrag, pane_sep_width_2, hdrag)

    def do_draw(self, context):
        self._handle1.draw(context)
        self._handle2.draw(context)


class HandleWindow():
    handle_width = 10

    def __init__(self):
        self._widget = None
        self._area_x = -1
        self._area_y = -1
        self._area_width = 1
        self._area_height = 1
        self._prelit = False
        self._pos = 0.0
        self._transform = (0, 0)
        self._visible = False

    def get_position(self, width, xtrans):
        self._transform = (width, xtrans)
        return float(self._pos * width) + xtrans

    def set_position(self, pos):
        width, xtrans = self._transform
        self._pos = float(pos - xtrans) / width

    def realize(self, widget):
        self._widget = widget

    def unrealize(self):
        self._widget = None

    def set_visible(self, visible):
        self._visible = visible

    def move_resize(self, x, y, width, height):
        self._area_x = x
        self._area_y = y
        self._area_width = width
        self._area_height = height

    def set_prelight(self, flag):
        self._prelit = flag
        if self._widget:
            self._widget.queue_draw()

    def draw(self, cairocontext):
        if not self._widget or not self._visible:
            return

        padding = 5
        x = self._area_x + padding
        y = self._area_y + padding
        width = max(0, self._area_width - 2 * padding)
        height = max(0, self._area_height - 2 * padding)

        if width == 0 or height == 0:
            return

        stylecontext = self._widget.get_style_context()
        state = stylecontext.get_state()
        if self._widget.is_focus():
            state |= Gtk.StateFlags.SELECTED
        if self._prelit:
            state |= Gtk.StateFlags.PRELIGHT

        stylecontext.save()
        stylecontext.set_state(state)
        xcenter = x + width / 2.0
        cairocontext.save()
        cairocontext.set_source_rgba(0.5, 0.5, 0.5, 0.8)
        cairocontext.set_line_width(2.0)
        cairocontext.move_to(xcenter, y)
        cairocontext.line_to(xcenter, y + height)
        cairocontext.stroke()

        ymid = y + height / 2.0
        cairocontext.arc(xcenter, ymid - 10, 1.5, 0, 2 * 3.14159)
        cairocontext.arc(xcenter, ymid, 1.5, 0, 2 * 3.14159)
        cairocontext.arc(xcenter, ymid + 10, 1.5, 0, 2 * 3.14159)
        cairocontext.fill()
        cairocontext.restore()
        stylecontext.restore()

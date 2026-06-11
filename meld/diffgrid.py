# Copyright (C) 2014 Marco Brito <bcaza@null.net>
# Copyright (C) 2026 Martin Rieser
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or (at
# your option) any later version.

from gi.repository import Gdk, GObject, Gtk, Gsk, Graphene


class DiffGridLayoutChild(Gtk.LayoutChild):
    """Layout child for DiffGrid, storing grid position and span.

    We use a custom LayoutChild (not GtkGridLayoutChild) because
    DiffGridLayout subclasses Gtk.LayoutManager directly rather
    than Gtk.GridLayout.
    """

    column = GObject.Property(type=int, default=0)
    row = GObject.Property(type=int, default=0)
    column_span = GObject.Property(type=int, default=1)
    row_span = GObject.Property(type=int, default=1)

    def get_column(self):
        return self.props.column

    def set_column(self, value):
        self.props.column = value

    def get_row(self):
        return self.props.row

    def set_row(self, value):
        self.props.row = value

    def get_column_span(self):
        return self.props.column_span

    def set_column_span(self, value):
        self.props.column_span = value

    def get_row_span(self):
        return self.props.row_span

    def set_row_span(self, value):
        self.props.row_span = value


class DiffGridLayout(Gtk.LayoutManager):
    """Custom layout manager for DiffGrid.

    We subclass Gtk.LayoutManager directly (not Gtk.GridLayout) because
    PyGObject cannot override do_allocate on Gtk.GridLayout subclasses:
    the C-level vtable entry takes precedence over the Python override,
    causing our custom allocation logic to be silently skipped.
    """

    def do_create_layout_child(self, widget, for_child):
        return DiffGridLayoutChild(
            layout_manager=self, child_widget=for_child)

    def do_measure(self, widget, orientation, for_size):
        wcols, hrows = widget._get_min_sizes()
        if orientation == Gtk.Orientation.HORIZONTAL:
            total = sum(wcols)
            return total, max(total, 1), -1, -1
        else:
            total = sum(hrows)
            return total, max(total, 1), -1, -1

    def do_allocate(self, widget, width, height, baseline):
        wcols, hrows = widget._get_min_sizes()
        (wpane1, wgutter1, wlink1, wgutter2, wpane2, wgutter3, wlink2,
            wgutter4, wpane3, wmap) = wcols
        xmin = 0
        xmax = width - wmap
        pane_sep_width_1 = wgutter1 + wlink1 + wgutter2
        pane_sep_width_2 = wgutter3 + wlink2 + wgutter4
        pos1, pos2 = widget._calculate_positions(
            xmin, xmax, pane_sep_width_1, pane_sep_width_2,
            wpane1, wpane2, wpane3
        )

        wpane1 = pos1 - xmin
        wpane2 = pos2 - (pos1 + pane_sep_width_1)
        wpane3 = xmax - (pos2 + pane_sep_width_2)

        col_widths = [wpane1, wgutter1, wlink1, wgutter2, wpane2, wgutter3, wlink2, wgutter4, wpane3, wmap]

        col_xs = [0] * len(col_widths)
        cur_x = 0
        for i, w in enumerate(col_widths):
            col_xs[i] = cur_x
            cur_x += w

        row_ys = [0] * 4
        cur_y = 0
        for i, h in enumerate(hrows):
            row_ys[i] = cur_y
            cur_y += h

        layout = widget.get_layout_manager()
        child = widget.get_first_child()
        while child:
            if child.get_visible():
                layout_child = layout.get_layout_child(child)
                if layout_child:
                    col = layout_child.get_column()
                    row = layout_child.get_row()
                    colspan = layout_child.get_column_span()
                    rowspan = layout_child.get_row_span()

                    child_w = sum(col_widths[col:col+colspan])

                    if row == 1:
                        child_h = height - hrows[0] - hrows[2] - hrows[3]
                    else:
                        child_h = sum(hrows[row:row+rowspan])

                    child_x = col_xs[col]
                    if row > 1:
                        row1_h = height - hrows[0] - hrows[2] - hrows[3]
                        if row == 2:
                            child_y = hrows[0] + row1_h
                        else:  # row == 3
                            child_y = hrows[0] + row1_h + hrows[2]
                    else:
                        child_y = row_ys[row]

                    p = Graphene.Point()
                    p.x = child_x
                    p.y = child_y
                    transform = Gsk.Transform.new().translate(p)
                    child.allocate(child_w, child_h, baseline, transform)
            child = child.get_next_sibling()

        ydrag = hrows[0]
        hdrag = (height - hrows[3]) - hrows[0]

        widget._handle1.move_resize(pos1, ydrag, pane_sep_width_1, hdrag)
        widget._handle2.move_resize(pos2, ydrag, pane_sep_width_2, hdrag)


class DiffGrid(Gtk.Widget):
    __gtype_name__ = "DiffGrid"

    column_count = 10
    handle_columns = (2, 6)

    def __init__(self):
        super().__init__()
        self.set_layout_manager(DiffGridLayout())
        self._in_drag = False
        self._drag_pos = -1
        self._drag_handle = None
        self._handle1 = HandleWindow()
        self._handle2 = HandleWindow()

    def attach(self, child, col, row, width, height):
        child.set_parent(self)
        layout = self.get_layout_manager()
        layout_child = layout.get_layout_child(child)
        layout_child.set_column(col)
        layout_child.set_row(row)
        layout_child.set_column_span(width)
        layout_child.set_row_span(height)

    def get_child_at(self, col, row):
        layout = self.get_layout_manager()
        child = self.get_first_child()
        while child:
            layout_child = layout.get_layout_child(child)
            if layout_child:
                if layout_child.get_column() == col and layout_child.get_row() == row:
                    return child
            child = child.get_next_sibling()
        return None

    def child_get_property(self, child, property_name, value):
        layout = self.get_layout_manager()
        layout_child = layout.get_layout_child(child)
        if layout_child:
            prop_map = {
                'left-attach': 'column',
                'top-attach': 'row',
                'width': 'column-span',
                'height': 'row-span',
            }
            mapped_name = prop_map.get(property_name, property_name)
            val = layout_child.get_property(mapped_name)
            if hasattr(value, 'set_int'):
                value.set_int(val)
            elif hasattr(value, 'set_boolean'):
                value.set_boolean(val)
            else:
                value = val

    def do_realize(self):
        Gtk.Widget.do_realize(self)
        self._handle1.realize(self)
        self._handle2.realize(self)

    def do_unrealize(self):
        self._handle1.unrealize()
        self._handle2.unrealize()
        Gtk.Widget.do_unrealize(self)

    def do_map(self):
        Gtk.Widget.do_map(self)
        drag = self.get_child_at(2, 0)
        self._handle1.set_visible(drag and drag.get_visible())
        drag = self.get_child_at(6, 0)
        self._handle2.set_visible(drag and drag.get_visible())

    def do_unmap(self):
        self._handle1.set_visible(False)
        self._handle2.set_visible(False)
        Gtk.Widget.do_unmap(self)

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
            self.queue_allocate()
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
                    min_w, nat_w, _, _ = child.measure(Gtk.Orientation.HORIZONTAL, -1)
                    min_h, nat_h, _, _ = child.measure(Gtk.Orientation.VERTICAL, -1)
                    spanning = 1
                    try:
                        lc = self.get_layout_manager().get_layout_child(
                            child)
                        if lc:
                            spanning = lc.get_column_span()
                    except Exception:
                        pass
                    if spanning == 1:
                        wcols[col] = max(wcols[col], min_w)
                    hrows[row] = max(hrows[row], min_h, nat_h)
        return wcols, hrows

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

# Copyright (C) 2009-2015 Kai Willadsen <kai.willadsen@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.

"""GTK 4 and GtkSourceView 5 Compatibility Layer.

This module provides a comprehensive runtime compatibility shim for GNOME/meld to run on
GTK 4 and GtkSourceView 5. It dynamically patches and wraps deprecated or modified
PyGObject APIs and provides fallback components for widgets removed in GTK 4 (such as
GtkEventBox, GtkAlignment, GtkButtonBox, and GtkRecentChooserWidget).

Key adaptations:
1. GtkIconSize mapping and Image/IconTheme lookup patches.
2. Signal connection wrapping: maps legacy keyboard/mouse event signals to GTK 4 EventControllers.
3. Monkey-patches for widgets (Gtk.Widget, Gtk.Grid, Gtk.Notebook) to preserve layout properties.
4. GtkStyleContext state redirection to prevent native C-level segfaults.
5. Warning suppression/silencing for legacy GTK 4 deprecations.
"""

import logging
import os

import gi

# Require GTK 4, GDK 4, Graphene 1.0, and GtkSourceView 5
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Graphene", "1.0")
gi.require_version("GtkSource", "5")

from gi.repository import (  # noqa: E402
    Gdk,
    GdkPixbuf,
    GLib,
    GObject,
    Graphene,
    Gtk,
    GtkSource,
)

log = logging.getLogger(__name__)

# GtkIconSize mapping
Gtk.IconSize.SMALL_TOOLBAR = Gtk.IconSize.NORMAL
Gtk.IconSize.MENU = Gtk.IconSize.NORMAL
Gtk.IconSize.BUTTON = Gtk.IconSize.NORMAL
Gtk.IconSize.DIALOG = Gtk.IconSize.LARGE
Gtk.IconSize.DND = Gtk.IconSize.NORMAL
Gtk.IconSize.LARGE_TOOLBAR = Gtk.IconSize.LARGE

original_new_from_icon_name = Gtk.Image.new_from_icon_name
Gtk.Image.new_from_icon_name = (
    lambda icon_name, *args, **kwargs: original_new_from_icon_name(icon_name)
)

original_set_from_icon_name = Gtk.Image.set_from_icon_name
Gtk.Image.set_from_icon_name = (
    lambda self, icon_name, *args, **kwargs: original_set_from_icon_name(
        self, icon_name
    )
)


Gtk.IconTheme.get_default = lambda: Gtk.IconTheme.get_for_display(
    Gdk.Display.get_default()
)


def compat_load_icon(self, icon_name, size, flags):
    try:
        paintable = self.lookup_icon(icon_name, [], size, 1, Gtk.TextDirection.LTR, 0)
        if paintable:
            gfile = paintable.get_file()
            if gfile:
                path = gfile.get_path()
                if path:
                    return GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
    except Exception as e:
        log.warning(f"Failed to load icon '{icon_name}' from path: {e}")
    try:
        paintable = self.lookup_icon(
            "image-missing", [], size, 1, Gtk.TextDirection.LTR, 0
        )
        if paintable:
            gfile = paintable.get_file()
            if gfile:
                path = gfile.get_path()
                if path:
                    return GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
    except Exception as e:
        log.debug("Failed to load compat icon: %s", e)
    return GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, size, size)


Gtk.IconTheme.load_icon = compat_load_icon

original_get_iter_at_line = Gtk.TextBuffer.get_iter_at_line


def compat_get_iter_at_line(self, line):
    res = original_get_iter_at_line(self, line)
    return res[1] if isinstance(res, tuple) else res


Gtk.TextBuffer.get_iter_at_line = compat_get_iter_at_line

original_get_iter_at_line_offset = Gtk.TextBuffer.get_iter_at_line_offset


def compat_get_iter_at_line_offset(self, line, char_offset):
    res = original_get_iter_at_line_offset(self, line, char_offset)
    return res[1] if isinstance(res, tuple) else res


Gtk.TextBuffer.get_iter_at_line_offset = compat_get_iter_at_line_offset

original_accelerator_parse = Gtk.accelerator_parse


def compat_accelerator_parse(accelerator):
    res = original_accelerator_parse(accelerator)
    return (res[1], res[2]) if len(res) == 3 else res


Gtk.accelerator_parse = compat_accelerator_parse

Gtk.binding_set_find = lambda name: None
Gtk.binding_entry_remove = lambda binding_set, key, modifiers: None


# Mock WindowState
class MockWindowState:
    WITHDRAWN = 1 << 0
    ICONIFIED = 1 << 1
    MAXIMIZED = 1 << 2
    STICKY = 1 << 3
    FULLSCREEN = 1 << 4
    ABOVE = 1 << 5
    BELOW = 1 << 6
    FOCUSED = 1 << 7
    TILED = 1 << 8


Gdk.WindowState = MockWindowState
Gdk.ModifierType.MOD1_MASK = Gdk.ModifierType.ALT_MASK


class MockEventMask:
    POINTER_MOTION_MASK = 1 << 2
    BUTTON_PRESS_MASK = 1 << 8
    BUTTON_RELEASE_MASK = 1 << 9
    EXPOSURE_MASK = 1 << 1
    BUTTON_MOTION_MASK = 1 << 4
    ENTER_NOTIFY_MASK = 1 << 10
    LEAVE_NOTIFY_MASK = 1 << 11
    KEY_PRESS_MASK = 1 << 14
    KEY_RELEASE_MASK = 1 << 15
    SCROLL_MASK = 1 << 21
    SMOOTH_SCROLL_MASK = 1 << 22
    TOUCH_MASK = 1 << 23


Gdk.EventMask = MockEventMask


# Surface wrapper to support get_state
class SurfaceWrapper:
    def __init__(self, surface, widget):
        self.surface = surface
        self.widget = widget

    def get_state(self):
        state = 0
        if getattr(self.widget, "_is_fullscreen", False):
            state |= Gdk.WindowState.FULLSCREEN
        return state

    def __getattr__(self, name):
        return getattr(self.surface, name)


# Patch fullscreen to track state
original_fullscreen = Gtk.Window.fullscreen
original_unfullscreen = Gtk.Window.unfullscreen


def compat_fullscreen(self):
    self._is_fullscreen = True
    original_fullscreen(self)


def compat_unfullscreen(self):
    self._is_fullscreen = False
    original_unfullscreen(self)


Gtk.Window.fullscreen = compat_fullscreen
Gtk.Window.unfullscreen = compat_unfullscreen


# Widget.get_window mapping
def widget_get_window(self):
    native = self.get_native()
    surface = native.get_surface() if native else None
    if surface is None:
        return None
    return SurfaceWrapper(surface, self)


Gtk.Widget.get_window = widget_get_window


# Widget.get_children / Widget.get_child mapping
def get_widget_children(widget):
    children = []
    child = widget.get_first_child()
    while child is not None:
        children.append(child)
        child = child.get_next_sibling()
    return children


Gtk.Widget.get_children = get_widget_children
Gtk.Widget.get_child = lambda self: self.get_first_child()


# Border width emulation
def widget_set_border_width(self, width):
    self.set_margin_start(width)
    self.set_margin_end(width)
    self.set_margin_top(width)
    self.set_margin_bottom(width)


Gtk.Widget.set_border_width = widget_set_border_width
Gtk.Widget.get_border_width = lambda self: self.get_margin_start()
Gtk.Widget.get_toplevel = lambda self: self.get_root() or self.get_native()

# show_all is no-op
Gtk.Widget.show_all = lambda self: None
Gtk.Widget.show = lambda self: self.set_visible(True)
Gtk.Widget.hide = lambda self: self.set_visible(False)

Gtk.Button.set_image = lambda self, image: self.set_child(image)
Gtk.Button.get_image = lambda self: self.get_child()


# Widget foreach emulation
def widget_foreach(self, callback, *user_data):
    for child in list(self.get_children()):
        callback(child, *user_data)


Gtk.Widget.foreach = widget_foreach


# Notebook child property mapping
def notebook_child_set_property(self, child, property_name, value):
    page = self.get_page(child)
    if page:
        page.set_property(property_name, value)


def notebook_child_get_property(self, child, property_name):
    page = self.get_page(child)
    if page:
        return page.get_property(property_name)
    return None


Gtk.Notebook.child_set_property = notebook_child_set_property
Gtk.Notebook.child_get_property = notebook_child_get_property
Gtk.Notebook.get_children = lambda self: [
    self.get_nth_page(i) for i in range(self.get_n_pages())
]


# Grid child property mapping
def grid_child_get_property(self, child, property_name, value):
    layout = self.get_layout_manager()
    if layout:
        layout_child = layout.get_layout_child(child)
        if layout_child:
            prop_map = {
                "left-attach": "column",
                "top-attach": "row",
                "width": "column-span",
                "height": "row-span",
            }
            mapped_name = prop_map.get(property_name, property_name)
            val = layout_child.get_property(mapped_name)
            if hasattr(value, "set_int"):
                value.set_int(val)
            elif hasattr(value, "set_boolean"):
                value.set_boolean(val)
            else:
                value = val


def grid_child_set_property(self, child, property_name, value):
    layout = self.get_layout_manager()
    if layout:
        layout_child = layout.get_layout_child(child)
        if layout_child:
            prop_map = {
                "left-attach": "column",
                "top-attach": "row",
                "width": "column-span",
                "height": "row-span",
            }
            mapped_name = prop_map.get(property_name, property_name)
            layout_child.set_property(mapped_name, value)


Gtk.Grid.child_get_property = grid_child_get_property
Gtk.Grid.child_set_property = grid_child_set_property


# override_font emulation
def widget_override_font(self, font_desc):
    if not font_desc:
        return
    font_str = (
        font_desc.to_string() if hasattr(font_desc, "to_string") else str(font_desc)
    )
    parts = font_str.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isdigit():
        family, size = parts[0], parts[1]
        css = f"* {{ font-family: '{family}'; font-size: {size}pt; }}"
    else:
        css = f"* {{ font-family: '{font_str}'; }}"
    provider = Gtk.CssProvider()
    provider.load_from_string(css)
    self.get_style_context().add_provider(
        provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


Gtk.Widget.override_font = widget_override_font
Gtk.Widget.modify_font = widget_override_font


def widget_remove(self, child):
    if isinstance(self, Gtk.Notebook):
        page_num = self.page_num(child)
        if page_num != -1:
            self.remove_page(page_num)
    elif hasattr(self, "set_child") and self.get_child() == child:
        self.set_child(None)
    elif child.get_parent() == self:
        child.unparent()


Gtk.Widget.remove = widget_remove


# Widget.add mapping
def widget_add(self, child):
    if hasattr(self, "append") and not isinstance(self, Gtk.Grid):
        self.append(child)
    elif hasattr(self, "set_child"):
        self.set_child(child)
    elif isinstance(self, Gtk.Grid):
        row = getattr(self, "_compat_grid_row", 0)
        self.attach(child, 0, row, 1, 1)
        self._compat_grid_row = row + 1


Gtk.Widget.add = widget_add


# Box layout packing mapping
def box_pack_start(self, child, expand=True, fill=True, padding=0):
    if expand:
        if self.get_orientation() == Gtk.Orientation.HORIZONTAL:
            child.set_hexpand(True)
        else:
            child.set_vexpand(True)
    self.append(child)


def box_pack_end(self, child, expand=True, fill=True, padding=0):
    if expand:
        if self.get_orientation() == Gtk.Orientation.HORIZONTAL:
            child.set_hexpand(True)
        else:
            child.set_vexpand(True)
    if self.get_orientation() == Gtk.Orientation.HORIZONTAL:
        child.set_halign(Gtk.Align.END)
    else:
        child.set_valign(Gtk.Align.END)
    self.append(child)


Gtk.Box.pack_start = box_pack_start
Gtk.Box.pack_end = box_pack_end



# Screen/display mapping for Stylesheets
if not hasattr(Gdk, "Screen"):

    class DummyScreen:
        @classmethod
        def get_default(cls):
            return cls()

    Gdk.Screen = DummyScreen


def _add_provider_for_screen(screen, provider, priority):
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(display, provider, priority)


Gtk.StyleContext.add_provider_for_screen = _add_provider_for_screen

Gtk.cairo_should_draw_window = lambda *args: True


# Compatibility Cairo drawing functions
def compat_render_background(context, cr, x, y, width, height):
    state = context.get_state()
    if state & Gtk.StateFlags.PRELIGHT:
        cr.save()
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.15)
        cr.rectangle(x, y, width, height)
        cr.fill()
        cr.restore()


def compat_render_frame(context, cr, x, y, width, height):
    state = context.get_state()
    if state & Gtk.StateFlags.PRELIGHT:
        cr.save()
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.3)
        cr.set_line_width(1.0)
        cr.rectangle(x + 0.5, y + 0.5, width - 1, height - 1)
        cr.stroke()
        cr.restore()


def compat_render_icon(context, cr, pixbuf, x, y):
    cr.save()
    Gdk.cairo_set_source_pixbuf(cr, pixbuf, x, y)
    cr.paint()
    cr.restore()


Gtk.render_background = compat_render_background
Gtk.render_frame = compat_render_frame
Gtk.render_icon = compat_render_icon


# Mock Event structure for callbacks
class MockEvent:
    def __init__(self, **kwargs):
        self.keyval = kwargs.get("keyval", 0)
        self.state = kwargs.get("state", 0)
        self.button = kwargs.get("button", 0)
        self.x = kwargs.get("x", 0.0)
        self.y = kwargs.get("y", 0.0)
        self.type = kwargs.get("type", 0)
        self.hardware_keycode = kwargs.get("hardware_keycode", 0)
        self.direction = kwargs.get("direction", 0)
        self.delta_x = kwargs.get("delta_x", 0.0)
        self.delta_y = kwargs.get("delta_y", 0.0)
        self.window = kwargs.get("window", None)

    def triggers_context_menu(self):
        return self.button == 3


def safe_emit(widget, signal, *args):
    try:
        return widget.emit(signal, *args)
    except TypeError:
        return False


# Attach event controllers
def attach_compat_controllers(widget):
    if getattr(widget, "_compat_controllers_attached", False):
        return
    widget._compat_controllers_attached = True

    # Key events
    key_ctrl = Gtk.EventControllerKey.new()

    def on_key_pressed(ctrl, keyval, keycode, state):
        ev = MockEvent(
            keyval=keyval,
            state=state,
            hardware_keycode=keycode,
            type=Gdk.EventType.KEY_PRESS,
            window=widget.get_window(),
        )
        return bool(safe_emit(widget, "key-press-event", ev))

    def on_key_released(ctrl, keyval, keycode, state):
        ev = MockEvent(
            keyval=keyval,
            state=state,
            hardware_keycode=keycode,
            type=Gdk.EventType.KEY_RELEASE,
            window=widget.get_window(),
        )
        return bool(safe_emit(widget, "key-release-event", ev))

    key_ctrl.connect("key-pressed", on_key_pressed)
    key_ctrl.connect("key-released", on_key_released)
    widget.add_controller(key_ctrl)

    # Click gesture
    click_gesture = Gtk.GestureClick.new()

    def on_pressed(gesture, n_press, x, y):
        button = gesture.get_current_button()
        state = 0
        try:
            event = gesture.get_last_event(gesture.get_current_sequence())
            if event:
                state = event.get_modifier_state()
        except Exception as e:
            log.debug("Failed to get last modifier state on press: %s", e)
        ev = MockEvent(
            button=button,
            x=x,
            y=y,
            state=state,
            type=Gdk.EventType.BUTTON_PRESS,
            window=widget.get_window(),
        )
        res = safe_emit(widget, "button-press-event", ev)
        if res:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def on_released(gesture, n_press, x, y):
        button = gesture.get_current_button()
        state = 0
        try:
            event = gesture.get_last_event(gesture.get_current_sequence())
            if event:
                state = event.get_modifier_state()
        except Exception as e:
            log.debug("Failed to get last modifier state on release: %s", e)
        ev = MockEvent(
            button=button,
            x=x,
            y=y,
            state=state,
            type=Gdk.EventType.BUTTON_RELEASE,
            window=widget.get_window(),
        )
        res = safe_emit(widget, "button-release-event", ev)
        if res:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    click_gesture.connect("pressed", on_pressed)
    click_gesture.connect("released", on_released)
    click_gesture.set_button(0)
    widget.add_controller(click_gesture)

    # Motion
    motion_ctrl = Gtk.EventControllerMotion.new()

    def on_motion(ctrl, x, y):
        state = 0
        try:
            event = ctrl.get_last_event()
            if event:
                state = event.get_modifier_state()
        except Exception as e:
            log.debug("Failed to get last modifier state on motion: %s", e)
        ev = MockEvent(
            x=x,
            y=y,
            state=state,
            type=Gdk.EventType.MOTION_NOTIFY,
            window=widget.get_window(),
        )
        safe_emit(widget, "motion-notify-event", ev)

    motion_ctrl.connect("motion", on_motion)
    widget.add_controller(motion_ctrl)

    # Scroll
    scroll_ctrl = Gtk.EventControllerScroll.new(
        Gtk.EventControllerScrollFlags.BOTH_AXES
    )

    def on_scroll(ctrl, dx, dy):
        direction = Gdk.ScrollDirection.SMOOTH
        if dy < 0:
            direction = Gdk.ScrollDirection.UP
        elif dy > 0:
            direction = Gdk.ScrollDirection.DOWN
        elif dx < 0:
            direction = Gdk.ScrollDirection.LEFT
        elif dx > 0:
            direction = Gdk.ScrollDirection.RIGHT
        ev = MockEvent(
            direction=direction,
            delta_x=dx,
            delta_y=dy,
            type=Gdk.EventType.SCROLL,
            window=widget.get_window(),
        )
        return bool(safe_emit(widget, "scroll-event", ev))

    scroll_ctrl.connect("scroll", on_scroll)
    widget.add_controller(scroll_ctrl)

    # Focus
    focus_ctrl = Gtk.EventControllerFocus.new()

    def on_focus_enter(ctrl):
        ev = MockEvent(type=0, window=widget.get_window())
        safe_emit(widget, "focus-in-event", ev)

    def on_focus_leave(ctrl):
        ev = MockEvent(type=0, window=widget.get_window())
        safe_emit(widget, "focus-out-event", ev)

    focus_ctrl.connect("enter", on_focus_enter)
    focus_ctrl.connect("leave", on_focus_leave)
    widget.add_controller(focus_ctrl)

    # Window close request and size-allocate
    if isinstance(widget, Gtk.Window):

        def on_close_request(window):
            ev = MockEvent(type=Gdk.EventType.DELETE, window=window.get_window())
            return bool(safe_emit(window, "delete-event", ev))

        widget.connect("close-request", on_close_request)

        def on_size_notify(window, pspec):
            class MockAllocation:
                def __init__(self, w, h):
                    self.x = 0
                    self.y = 0
                    self.width = w
                    self.height = h

            alloc = MockAllocation(window.get_width(), window.get_height())
            safe_emit(window, "size-allocate", alloc)

        widget.connect("notify::default-width", on_size_notify)
        widget.connect("notify::default-height", on_size_notify)


# Gtk.DestDefaults emulation
class MockDestDefaults:
    MOTION = 1 << 0
    HIGHLIGHT = 1 << 1
    DROP = 1 << 2
    ALL = MOTION | HIGHLIGHT | DROP


Gtk.DestDefaults = MockDestDefaults


def widget_drag_dest_set(self, flags, targets, actions):
    try:
        target = Gtk.DropTarget.new(Gdk.FileList, actions)
    except Exception as e:
        log.debug("Gdk.FileList DropTarget creation failed, falling back to GObject.TYPE_STRING: %s", e)
        target = Gtk.DropTarget.new(GObject.TYPE_STRING, actions)

    def on_drop(drop_target, value, x, y):
        class MockSelectionData:
            def __init__(self, uris):
                self._uris = uris

            def get_uris(self):
                return self._uris

        uris = []
        if isinstance(value, Gdk.FileList):
            files = value.get_files()
            uris = [f.get_uri() for f in files]
        elif isinstance(value, str):
            uris = [line.strip() for line in value.split("\n") if line.strip()]
        sel_data = MockSelectionData(uris)
        self.emit("drag-data-received", None, x, y, sel_data, 0, 0)
        self.emit("drag_data_received", None, x, y, sel_data, 0, 0)
        return True

    target.connect("drop", on_drop)
    self.add_controller(target)


Gtk.Widget.drag_dest_set = widget_drag_dest_set
Gtk.Widget.drag_dest_add_uri_targets = lambda self: None
Gtk.Widget.drag_dest_add_image_targets = lambda self: None
Gtk.Widget.drag_dest_add_text_targets = lambda self: None

# Patch Gtk.Widget connect

original_widget_connect = Gtk.Widget.connect


def compat_widget_connect(self, signal, callback, *args, **kwargs):
    compat_signals = {
        "button-press-event",
        "button-release-event",
        "key-press-event",
        "key-release-event",
        "motion-notify-event",
        "scroll-event",
        "drag-data-received",
        "draw",
        "focus-in-event",
        "focus-out-event",
    }
    if signal in compat_signals:
        attach_compat_controllers(self)
    return original_widget_connect(self, signal, callback, *args, **kwargs)


Gtk.Widget.connect = compat_widget_connect


# GObjectMeta class creation interceptor
import gi.types  # noqa: E402

original_new = gi.types.GObjectMeta.__new__


def custom_new(cls, name, bases, dct):
    dct["__gsignals__"] = dct.get("__gsignals__", {})

    # Check if the class is a subclass of Gtk.Widget
    is_widget = False
    for base in bases:
        if issubclass(base, Gtk.Widget):
            is_widget = True
            break

    if is_widget:
        signals_to_register = {
            "draw": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_BOOLEAN, (object,)),
            "button-press-event": (
                GObject.SignalFlags.RUN_LAST,
                GObject.TYPE_BOOLEAN,
                (object,),
            ),
            "button-release-event": (
                GObject.SignalFlags.RUN_LAST,
                GObject.TYPE_BOOLEAN,
                (object,),
            ),
            "key-press-event": (
                GObject.SignalFlags.RUN_LAST,
                GObject.TYPE_BOOLEAN,
                (object,),
            ),
            "key-release-event": (
                GObject.SignalFlags.RUN_LAST,
                GObject.TYPE_BOOLEAN,
                (object,),
            ),
            "motion-notify-event": (
                GObject.SignalFlags.RUN_LAST,
                GObject.TYPE_BOOLEAN,
                (object,),
            ),
            "scroll-event": (
                GObject.SignalFlags.RUN_LAST,
                GObject.TYPE_BOOLEAN,
                (object,),
            ),
            "popup-menu": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_BOOLEAN, ()),
            "delete-event": (
                GObject.SignalFlags.RUN_LAST,
                GObject.TYPE_BOOLEAN,
                (object,),
            ),
            "drag-data-received": (
                GObject.SignalFlags.RUN_LAST,
                GObject.TYPE_NONE,
                (object, int, int, object, int, int),
            ),
            "size-allocate": (
                GObject.SignalFlags.RUN_LAST,
                GObject.TYPE_NONE,
                (object,),
            ),
            "focus-in-event": (
                GObject.SignalFlags.RUN_LAST,
                GObject.TYPE_BOOLEAN,
                (object,),
            ),
            "focus-out-event": (
                GObject.SignalFlags.RUN_LAST,
                GObject.TYPE_BOOLEAN,
                (object,),
            ),
            "style-updated": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
        }

        for sig_name, sig_def in signals_to_register.items():
            if sig_name not in dct["__gsignals__"]:
                # Check if signal already exists in parent ancestry
                exists = False
                for base in bases:
                    if (
                        hasattr(base, "__gtype__")
                        and GObject.signal_lookup(sig_name, base.__gtype__) != 0
                    ):
                        exists = True
                        break
                if not exists:
                    dct["__gsignals__"][sig_name] = sig_def

    if "do_draw" in dct:

        def compat_do_snapshot(self, snapshot):
            for base in bases:
                if hasattr(base, "do_snapshot"):
                    base.do_snapshot(self, snapshot)
                    break
            w = self.get_width()
            h = self.get_height()
            rect = Graphene.Rect.alloc()
            rect.init(0, 0, w, h)
            cr = snapshot.append_cairo(rect)
            self.do_draw(cr)

        dct["do_snapshot"] = compat_do_snapshot

    if "do_draw_layer" in dct:

        def compat_do_snapshot_layer(self, layer, snapshot):
            for base in bases:
                if hasattr(base, "do_snapshot_layer"):
                    base.do_snapshot_layer(self, layer, snapshot)
                    break
            w = self.get_width()
            h = self.get_height()
            rect = Graphene.Rect.alloc()
            rect.init(0, 0, w, h)
            cr = snapshot.append_cairo(rect)
            self.do_draw_layer(layer, cr)

        dct["do_snapshot_layer"] = compat_do_snapshot_layer

    return original_new(cls, name, bases, dct)


gi.types.GObjectMeta.__new__ = custom_new


# MenuItem compat class
class CompatMenuItem(Gtk.Button):
    def __init__(self, label=None):
        super().__init__()
        if label:
            self.set_label(label)

    @classmethod
    def new_with_mnemonic(cls, label):
        return cls(label=label)

    @classmethod
    def new_with_label(cls, label):
        return cls(label=label)

    def connect(self, signal, callback, *args, **kwargs):
        if signal == "activate":
            signal = "clicked"
        return super().connect(signal, callback, *args, **kwargs)


Gtk.MenuItem = CompatMenuItem


# Menu compat class
class PopoverMenuWrapper:
    def __init__(self, popover):
        self.popover = popover

    def attach_to_widget(self, widget, callback=None, *args, **kwargs):
        self.popover.set_parent(widget)

    def show_all(self):
        pass

    def popup_at_pointer(self, event):
        if event and hasattr(event, "window") and event.window:
            parent = getattr(event.window, "widget", None)
            if parent:
                self.popover.set_parent(parent)
        self.popover.popup()

    def popup_at_widget(self, widget, g1, g2, event):
        self.popover.set_parent(widget)
        self.popover.popup()

    def popup_at_rect(self, window, rect, g1, g2, event):
        parent = getattr(window, "widget", None)
        if parent:
            self.popover.set_parent(parent)
        self.popover.set_pointing_to(rect)
        self.popover.popup()


class CompatPopover(Gtk.PopoverMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def bind_model(self, model, action_namespace=None):
        self.set_menu_model(model)

    @staticmethod
    def new_from_model(relative_to, model):
        popover = Gtk.PopoverMenu.new_from_model(model)
        if relative_to:
            popover.set_parent(relative_to)
        return popover


Gtk.Popover = CompatPopover

original_menubutton_set_popover = Gtk.MenuButton.set_popover


def compat_menubutton_set_popover(self, popover):
    if popover:
        parent = popover.get_parent()
        if parent:
            popover.unparent()
    original_menubutton_set_popover(self, popover)


Gtk.MenuButton.set_popover = compat_menubutton_set_popover


class CompatMenu(Gtk.Popover):
    def __init__(self):
        super().__init__()
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.set_child(self.box)
        self.box.get_style_context().add_class("menu")

    @classmethod
    def new_from_model(cls, model):
        return PopoverMenuWrapper(Gtk.PopoverMenu.new_from_model(model))

    def append(self, child):
        child.connect("clicked", lambda *args: self.popdown())
        self.box.append(child)

    def show_all(self):
        pass

    def popup_at_pointer(self, event):
        parent = None
        if event and hasattr(event, "window") and event.window:
            parent = getattr(event.window, "widget", None)
        if not parent:
            app = Gtk.Application.get_default()
            if app:
                parent = app.get_active_window()
        if parent:
            self.set_parent(parent)
            self.popup()


Gtk.Menu = CompatMenu


# Emulate other removed containers
class CompatAlignment(Gtk.Box):
    """GTK 4 substitute for GtkAlignment.

    In GTK 4, GtkAlignment was removed in favor of widget properties like
    'halign', 'valign', 'margin', and alignment properties inside layout managers.
    We emulate GtkAlignment by subclassing Gtk.Box.
    """
    __gtype_name__ = "GtkAlignment"

    def __init__(self, xalign=0.5, yalign=0.5, xscale=1.0, yscale=1.0, *args, **kwargs):
        super().__init__(*args, **kwargs)


Gtk.Alignment = CompatAlignment


class CompatEventBox(Gtk.Box):
    """GTK 4 substitute for GtkEventBox.

    In GTK 4, all widgets can receive input events directly, eliminating the need
    for a dedicated GtkEventBox container. We subclass Gtk.Box as a direct drop-in replacement.
    """
    __gtype_name__ = "GtkEventBox"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


Gtk.EventBox = CompatEventBox


# Stylesheet path / selector query functions
def append_element(path, selector):
    pass


class MockStyleContext:
    def __init__(self):
        self._state = Gtk.StateFlags.NORMAL

    def add_class(self, class_name):
        pass

    def remove_class(self, class_name):
        pass

    def set_state(self, state):
        self._state = state

    def get_state(self):
        return self._state


def create_context_for_path(path, parent):
    return MockStyleContext()


def get_style(parent, selector):
    return MockStyleContext()


def query_size(context, width, height):
    return width, height


def draw_style_common(context, cr, x, y, width, height):
    return x, y, width, height


# Gtk.RecentFilter compatibility
class MockRecentFilterFlags:
    URI = 1 << 0
    DISPLAY_NAME = 1 << 1
    MIME_TYPE = 1 << 2
    APPLICATION = 1 << 3
    GROUP = 1 << 4
    AGE = 1 << 5


Gtk.RecentFilterFlags = MockRecentFilterFlags


class MockRecentFilterInfo:
    def __init__(self):
        self.contains = 0
        self.uri = ""
        self.display_name = ""
        self.mime_type = ""
        self.applications = []
        self.groups = []
        self.age = 0


Gtk.RecentFilterInfo = MockRecentFilterInfo


class CompatRecentFilter:
    def __init__(self):
        self.mime_types = []
        self.custom_func = None
        self.custom_user_data = ()

    def add_mime_type(self, mime):
        self.mime_types.append(mime)

    def add_custom(self, needed, func, *user_data):
        self.custom_func = func
        self.custom_user_data = user_data

    def get_needed(self):
        return Gtk.RecentFilterFlags.MIME_TYPE

    def filter(self, filter_info):
        if self.custom_func:
            return self.custom_func(filter_info, *self.custom_user_data)
        return filter_info.mime_type in self.mime_types


Gtk.RecentFilter = CompatRecentFilter


# Gtk.Clipboard compatibility
class CompatClipboard:
    def __init__(self, gdk_clipboard):
        self.gdk_clipboard = gdk_clipboard

    @classmethod
    def get_default(cls, display):
        return cls(display.get_clipboard())

    def set_text(self, text, length=-1):
        self.gdk_clipboard.set_text(text)

    def request_text(self, callback, *user_data):
        def on_read_done(obj, result):
            try:
                text = obj.read_text_finish(result)
            except Exception as e:
                log.debug("Clipboard read text finish failed: %s", e)
                text = None
            callback(self, text, *user_data)

        self.gdk_clipboard.read_text_async(None, on_read_done)

    def set_can_store(self, targets):
        pass


original_get_clipboard = Gtk.Widget.get_clipboard


def compat_get_clipboard(self, selection=None):
    gdk_clip = original_get_clipboard(self)
    return CompatClipboard(gdk_clip)


Gtk.Widget.get_clipboard = compat_get_clipboard
Gtk.Clipboard = CompatClipboard


# Gtk.RecentChooserWidget compatibility
class CompatRecentChooserWidget(Gtk.Box):
    __gtype_name__ = "GtkRecentChooserWidget"

    __gsignals__ = {
        "selection-changed": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
        "item-activated": (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
    }

    show_icons = GObject.Property(type=bool, default=True)
    show_not_found = GObject.Property(type=bool, default=True)
    show_private = GObject.Property(type=bool, default=False)
    sort_type = GObject.Property(type=str, default="mru")

    def __init__(self, *args, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, *args, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_hexpand(True)
        self.scroll.set_vexpand(True)
        self.append(self.scroll)

        self.listbox = Gtk.ListBox()
        self.scroll.set_child(self.listbox)

        self.listbox.connect("row-selected", self._on_row_selected)
        self.listbox.connect("row-activated", self._on_row_activated)

        self.filter = None
        self.items = []
        self._current_uri = None

        self._load_items()

    def set_filter(self, recent_filter):
        self.filter = recent_filter
        self._refilter()

    def get_current_uri(self):
        return self._current_uri

    def _load_items(self):
        manager = Gtk.RecentManager.get_default()
        raw_items = manager.get_items()

        # Sort helper
        def get_mod_time(x):
            try:
                mod = x.get_modified()
                if hasattr(mod, "to_unix"):
                    return mod.to_unix()
                return mod
            except Exception as e:
                log.debug("Failed to get modified time for recent item: %s", e)
                return 0

        raw_items.sort(key=get_mod_time, reverse=True)

        self.items = raw_items
        self._refilter()

    def _refilter(self):
        while True:
            child = self.listbox.get_first_child()
            if not child:
                break
            self.listbox.remove(child)

        self._current_uri = None

        for item in self.items:
            if self.filter:

                class FilterInfoMock:
                    def __init__(self, item):
                        self.mime_type = item.get_mime_type()
                        self.display_name = item.get_display_name()
                        self.uri = item.get_uri()

                info = FilterInfoMock(item)
                if hasattr(self.filter, "custom_func") and self.filter.custom_func:
                    if not self.filter.custom_func(info, *self.filter.custom_user_data):
                        continue
                elif hasattr(self.filter, "filter"):
                    if not self.filter.filter(info):
                        continue

            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=item.get_display_name() or item.get_uri())
            label.set_xalign(0.0)
            label.set_margin_start(6)
            label.set_margin_end(6)
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            row.set_child(label)
            row._uri = item.get_uri()
            self.listbox.append(row)

    def _on_row_selected(self, listbox, row):
        if row:
            self._current_uri = row._uri
        else:
            self._current_uri = None
        self.emit("selection-changed")

    def _on_row_activated(self, listbox, row):
        if row:
            self._current_uri = row._uri
        self.emit("item-activated")


Gtk.RecentChooserWidget = CompatRecentChooserWidget


# GtkButtonBox and GtkHButtonBox compatibility
class CompatButtonBox(Gtk.Box):
    __gtype_name__ = "GtkButtonBox"
    layout_style = GObject.Property(type=str, default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class CompatHButtonBox(Gtk.Box):
    __gtype_name__ = "GtkHButtonBox"
    layout_style = GObject.Property(type=str, default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


Gtk.ButtonBox = CompatButtonBox
Gtk.HButtonBox = CompatHButtonBox


def statusbar_get_message_area(self):
    if not hasattr(self, "_compat_box"):
        self._compat_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._compat_box.set_parent(self)
        lbl = Gtk.Label()
        self._compat_box.append(lbl)
    return self._compat_box


Gtk.Statusbar.get_message_area = statusbar_get_message_area
Gtk.Statusbar.pack_end = (
    lambda self, child, *args, **kwargs: self.get_message_area().pack_end(
        child, *args, **kwargs
    )
)
Gtk.Statusbar.pack_start = (
    lambda self, child, *args, **kwargs: self.get_message_area().pack_start(
        child, *args, **kwargs
    )
)

GtkSource.GutterRenderer.set_size = lambda self, size: self.set_size_request(size, -1)

import gi._gtktemplate  # noqa: E402

original_init_template = gi._gtktemplate.init_template


def compat_init_template(self, cls, base_init_template):
    self.init_template = lambda: None
    if self.__class__ is not cls:
        raise TypeError(
            "Inheritance from classes with @Gtk.Template decorators "
            "is not allowed at this time"
        )
    self.__gtktemplate_handlers__ = set()
    base_init_template(self)
    for widget_name, attr_name in self.__gtktemplate_widgets__.items():
        self.__dict__[attr_name] = self.get_template_child(cls, widget_name)
    # Just ignore missing handlers instead of raising RuntimeError
    for handler_name, attr_name in self.__gtktemplate_methods__.items():
        if handler_name not in self.__gtktemplate_handlers__:
            log.debug(f"Ignoring missing template handler {handler_name}")


gi._gtktemplate.init_template = compat_init_template

original_gesture_multipress = Gtk.GestureClick


def compat_gesture_multipress(*args, **kwargs):
    widget = kwargs.pop("widget", None)
    gesture = original_gesture_multipress.new(*args, **kwargs)
    if widget:
        widget.add_controller(gesture)
    return gesture


compat_gesture_multipress.new = original_gesture_multipress.new
Gtk.GestureMultiPress = compat_gesture_multipress

original_event_controller_motion = Gtk.EventControllerMotion


def compat_event_controller_motion(*args, **kwargs):
    widget = kwargs.pop("widget", None)
    controller = original_event_controller_motion.new(*args, **kwargs)
    if widget:
        widget.add_controller(controller)
    return controller


compat_event_controller_motion.new = original_event_controller_motion.new
Gtk.EventControllerMotion = compat_event_controller_motion


# Gdk.cairo_get_clip_rectangle emulation
class GdkRectangle:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.width = w
        self.height = h


def cairo_get_clip_rectangle(context):
    x1, y1, x2, y2 = context.clip_extents()
    return True, GdkRectangle(x1, y1, x2 - x1, y2 - y1)


Gdk.cairo_get_clip_rectangle = cairo_get_clip_rectangle

# do_draw_layer class call fallback mapping
Gtk.TextView.do_draw_layer = lambda *args: None
if hasattr(GtkSource, "View"):
    GtkSource.View.do_draw_layer = lambda *args: None
if hasattr(GtkSource, "Map"):
    GtkSource.Map.do_draw_layer = lambda *args: None

Gtk.Window.get_size = lambda self: (self.get_width(), self.get_height())


# Gtk.StyleContext overrides to prevent C-level segfaults in GTK 4.
# Querying StyleContext on unrealized or custom widgets in GTK 4 can cause
# EXC_BAD_ACCESS at gtk_css_node_get_state. We bind the widget reference to
# the style context and redirect `get_state()` queries to the widget itself.
original_get_style_context = Gtk.Widget.get_style_context


def compat_get_style_context(self):
    ctx = original_get_style_context(self)
    ctx._widget = self
    return ctx


Gtk.Widget.get_style_context = compat_get_style_context


def compat_style_context_get_state(self):
    widget = getattr(self, "_widget", None)
    if widget:
        return widget.get_state_flags()
    return Gtk.StateFlags.NORMAL


Gtk.StyleContext.get_state = compat_style_context_get_state
Gtk.StyleContext.set_state = lambda self, state: None
Gtk.StyleContext.save = lambda self: None
Gtk.StyleContext.restore = lambda self: None

# Dummy GTK 3 style event virtual methods to prevent AttributeError on superclass calls.
# In GTK 4, direct event signals/handlers were removed in favor of EventControllers.
# We inject these fallback methods to prevent crashes on legacy custom widgets that
# subclass GTK widgets and still attempt to call superclass event handlers.
Gtk.Widget.do_button_press_event = lambda self, event: False
Gtk.Widget.do_button_release_event = lambda self, event: False
Gtk.Widget.do_motion_notify_event = lambda self, event: False
Gtk.Widget.do_scroll_event = lambda self, event: False


# Decorators to silence deprecation warnings for remaining GTK 4 legacy API surfaces
import functools  # noqa: E402
import warnings  # noqa: E402


def silence_deprecations(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            warnings.filterwarnings("ignore", category=UserWarning)
            try:
                from gi.overrides import PyGIDeprecationWarning

                warnings.filterwarnings("ignore", category=PyGIDeprecationWarning)
            except ImportError:
                pass
            return func(*args, **kwargs)

    return wrapper


def silence_class_methods(klass, methods):
    for method_name in methods:
        if hasattr(klass, method_name):
            orig = getattr(klass, method_name)
            if callable(orig):
                setattr(klass, method_name, silence_deprecations(orig))


deprecations_to_silence = {
    Gtk.ComboBox: ["get_model", "set_active", "get_active_iter", "clear", "get_active"],
    Gtk.ListStore: [
        "clear",
        "insert_with_values",
        "insert",
        "set",
        "set_value",
        "append",
        "prepend",
        "set_column_types",
    ],
    Gtk.TreeStore: [
        "clear",
        "insert_with_values",
        "insert",
        "set",
        "set_value",
        "append",
        "prepend",
        "set_column_types",
    ],
    Gtk.TreeView: [
        "get_cursor",
        "set_cursor",
        "expand_to_path",
        "expand_row",
        "collapse_row",
        "set_model",
        "set_search_equal_func",
        "append_column",
        "get_selection",
        "get_column",
        "move_column_after",
        "set_headers_visible",
    ],
    Gtk.TreeModel: [
        "get_value",
        "get_column_type",
        "get_iter_first",
        "get_iter",
        "iter_children",
        "iter_next",
        "iter_parent",
        "iter_has_child",
        "get_path",
        "get_n_columns",
        "get_string_from_iter",
        "iter_n_children",
    ],
    Gtk.TreeSelection: [
        "unselect_all",
        "select_iter",
        "get_selected_rows",
        "select_path",
        "unselect_path",
        "unselect_iter",
        "get_selected",
        "set_mode",
    ],
    Gtk.TreePath: [
        "new_first",
        "get_indices",
        "compare",
        "new_from_string",
        "to_string",
        "get_depth",
        "new",
        "up",
        "down",
        "next",
        "prev",
        "is_ancestor",
        "is_descendant",
    ],
    Gtk.TreeIter: ["copy"],
    Gtk.StyleContext: [
        "add_class",
        "remove_class",
        "has_class",
        "list_classes",
        "get_state",
        "save",
        "restore",
    ],
    Gtk.TreeViewColumn: ["set_resizable", "pack_start", "set_visible"],
    Gtk.CellLayout: ["clear_attributes", "add_attribute"],
    Gtk.Widget: ["get_style_context"],
}

for klass, methods in deprecations_to_silence.items():
    silence_class_methods(klass, methods)

try:
    from gi.module import get_introspection_module

    _GIGtk = get_introspection_module("Gtk")
    _GIGtk.TreeStore.set = silence_deprecations(_GIGtk.TreeStore.set)
    _GIGtk.ListStore.set = silence_deprecations(_GIGtk.ListStore.set)
except (ImportError, AttributeError):
    pass


# Gtk.InfoBar compatibility patches for GTK 4
def infobar_get_content_area(self):
    revealer = self.get_first_child()
    if revealer:
        outer_box = revealer.get_child()
        if outer_box:
            return outer_box.get_first_child()
    return None


def infobar_get_action_area(self):
    revealer = self.get_first_child()
    if revealer:
        outer_box = revealer.get_child()
        if outer_box:
            content_area = outer_box.get_first_child()
            if content_area:
                return content_area.get_next_sibling()
    return None


Gtk.InfoBar.get_content_area = infobar_get_content_area
Gtk.InfoBar.get_action_area = infobar_get_action_area


# Gtk.Dialog.run compatibility for GTK 4
def dialog_run(self):
    loop = GLib.MainLoop()
    response_id = Gtk.ResponseType.NONE

    def on_response(dialog, response):
        nonlocal response_id
        response_id = response
        loop.quit()

    handler_id = self.connect("response", on_response)
    self.present()
    loop.run()
    self.disconnect(handler_id)
    return response_id


Gtk.Dialog.run = dialog_run


# Initialize detailed UI activity logging
if os.environ.get("MELD_UI_DEBUG") == "1":
    from meld.ui.debug import install_ui_debug_hooks  # noqa: E402
    install_ui_debug_hooks()
